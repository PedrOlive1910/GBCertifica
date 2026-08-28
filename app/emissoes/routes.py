import shutil
from datetime import date
from pathlib import Path

from flask import (
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.auth.permissions import permissao_edicao
from app.extensions import db
from app.models import (
    ArquivoDocumento,
    DocumentoEmitido,
    Emissao,
    Empresa,
    FormatoArquivo,
    Funcionario,
    StatusDocumento,
    StatusEmissao,
    TipoDocumento,
)
from app.services.datas import calcular_datas_sequenciais
from app.services.documentos import gerar_emissao
from app.services.auditoria import alteracoes_campos, registrar_auditoria
from app.services.tenant import (
    arquivo_do_tenant_ou_404,
    emissao_do_tenant_ou_404,
    empresa_do_tenant_ou_404,
    funcionario_do_tenant_ou_404,
    tenant_atual_id,
)

from . import bp
from .forms import AcaoEmissaoForm, EmissaoForm


ITENS_POR_PAGINA = 12


def empresas_ativas(incluir_id=None):
    consulta = (
        select(Empresa)
        .where(Empresa.tenant_id == tenant_atual_id())
        .order_by(Empresa.razao_social)
    )
    if incluir_id:
        consulta = consulta.where(or_(Empresa.ativo.is_(True), Empresa.id == incluir_id))
    else:
        consulta = consulta.where(Empresa.ativo.is_(True))
    return list(db.session.scalars(consulta))


def funcionarios_ativos(incluir_id=None):
    consulta = (
        select(Funcionario)
        .join(Funcionario.empresa)
        .where(Empresa.tenant_id == tenant_atual_id())
        .order_by(Funcionario.nome)
    )
    if incluir_id:
        consulta = consulta.where(or_(Funcionario.ativo.is_(True), Funcionario.id == incluir_id))
    else:
        consulta = consulta.where(Funcionario.ativo.is_(True))
    return list(db.session.scalars(consulta))


def configurar_escolhas(form, emissao=None):
    empresas = empresas_ativas(emissao.empresa_id if emissao else None)
    funcionarios = funcionarios_ativos(emissao.funcionario_id if emissao else None)
    form.empresa_id.choices = [(item.id, item.razao_social) for item in empresas]
    form.funcionario_id.choices = [(item.id, item.nome) for item in funcionarios]
    return empresas, funcionarios


def documentos_selecionados():
    selecionados = request.form.getlist("documentos")
    return [tipo for tipo in TipoDocumento.TODOS if tipo in selecionados]


def ler_epis():
    colunas = {
        "quantidade": request.form.getlist("epi_quantidade[]"),
        "descricao": request.form.getlist("epi_descricao[]"),
        "ca": request.form.getlist("epi_ca[]"),
        "data_entrega": request.form.getlist("epi_data_entrega[]"),
        "data_devolucao": request.form.getlist("epi_data_devolucao[]"),
        "assinatura": request.form.getlist("epi_assinatura[]"),
    }
    quantidade = max((len(valores) for valores in colunas.values()), default=0)
    epis = []
    for indice in range(quantidade):
        item = {
            chave: (valores[indice].strip() if indice < len(valores) else "")
            for chave, valores in colunas.items()
        }
        if any(item.values()):
            epis.append(item)
    return epis


def ler_maquinas():
    return [item.strip() for item in request.form.getlist("maquinas[]") if item.strip()]


def dados_ordem_servico(form):
    return {
        "setor": form.setor.data or "",
        "cbo": form.cbo.data or "",
        "descricao_funcao": form.descricao_funcao.data or "",
        "risco_fisico": form.risco_fisico.data or "Não identificado.",
        "risco_quimico": form.risco_quimico.data or "Não identificado.",
        "risco_biologico": form.risco_biologico.data or "Não identificado.",
        "risco_ergonomico": form.risco_ergonomico.data or "Não identificado.",
        "risco_acidentes": form.risco_acidentes.data or "Não identificado.",
        "epis_atividade": form.epis_atividade.data or "",
        "recomendacoes": form.recomendacoes.data or "",
        "procedimentos_acidente": form.procedimentos_acidente.data or "",
        "responsavel_nome": form.responsavel_nome.data or "",
        "responsavel_cargo": form.responsavel_cargo.data or "",
        "responsavel_registro": form.responsavel_registro.data or "",
    }


def validar_dados_especificos(form, tipos, epis, maquinas):
    erros = []
    if not tipos:
        erros.append("Selecione ao menos um documento.")
    if TipoDocumento.FICHA_EPI in tipos and not epis:
        erros.append("Inclua ao menos um EPI para gerar a Ficha de EPI.")
    if TipoDocumento.NR_12 in tipos and not maquinas:
        erros.append("Inclua ao menos uma máquina ou equipamento para a NR-12.")
    if TipoDocumento.ORDEM_SERVICO in tipos:
        obrigatorios = (
            (form.setor.data, "Informe o setor da Ordem de Serviço."),
            (form.descricao_funcao.data, "Informe a descrição da função da Ordem de Serviço."),
            (form.responsavel_nome.data, "Informe o responsável pela Ordem de Serviço."),
        )
        erros.extend(mensagem for valor, mensagem in obrigatorios if not valor)
    return erros


def preencher_form_edicao(form, emissao):
    dados = emissao.dados_gerais or {}
    os_dados = dados.get("ordem_servico", {})
    form.empresa_id.data = emissao.empresa_id
    form.funcionario_id.data = emissao.funcionario_id
    form.funcao.data = emissao.funcionario_snapshot.get("funcao", "")
    data_admissao = dados.get("data_admissao")
    form.data_admissao.data = date.fromisoformat(data_admissao) if data_admissao else None
    form.data_inicial.data = emissao.data_inicial
    form.observacoes.data = emissao.observacoes
    for campo in (
        "setor", "cbo", "descricao_funcao", "risco_fisico", "risco_quimico",
        "risco_biologico", "risco_ergonomico", "risco_acidentes",
        "epis_atividade", "recomendacoes", "procedimentos_acidente",
        "responsavel_nome", "responsavel_cargo", "responsavel_registro",
    ):
        getattr(form, campo).data = os_dados.get(campo, "")


def salvar_emissao(form, emissao=None):
    empresa = empresa_do_tenant_ou_404(form.empresa_id.data)
    funcionario = funcionario_do_tenant_ou_404(form.funcionario_id.data)
    if funcionario.empresa_id != empresa.id:
        raise ValueError("O funcionário selecionado não pertence à empresa informada.")

    tipos = documentos_selecionados()
    epis = ler_epis()
    maquinas = ler_maquinas()
    erros = validar_dados_especificos(form, tipos, epis, maquinas)
    if erros:
        return None, erros

    nova_emissao = emissao is None
    estado_anterior = {}
    if nova_emissao:
        emissao = Emissao(empresa=empresa, funcionario=funcionario)
        db.session.add(emissao)
    else:
        estado_anterior = {
            "empresa_id": emissao.empresa_id,
            "funcionario_id": emissao.funcionario_id,
            "data_inicial": emissao.data_inicial.isoformat() if emissao.data_inicial else None,
            "observacoes": emissao.observacoes,
            "documentos": [item.tipo_documento for item in emissao.documentos],
            "dados_gerais": emissao.dados_gerais,
        }
        emissao.empresa = empresa
        emissao.funcionario = funcionario

    emissao.data_inicial = form.data_inicial.data
    emissao.observacoes = form.observacoes.data or None
    emissao.status = StatusEmissao.RASCUNHO
    emissao.concluido_em = None
    emissao.registrar_snapshots(form.funcao.data)
    emissao.dados_gerais = {
        "data_admissao": form.data_admissao.data.isoformat(),
        "data_admissao_formatada": form.data_admissao.data.strftime("%d/%m/%Y"),
        "epis": epis,
        "maquinas": maquinas,
        "ordem_servico": dados_ordem_servico(form),
    }

    existentes = {item.tipo_documento: item for item in emissao.documentos}
    datas = calcular_datas_sequenciais(form.data_inicial.data, len(tipos))
    documentos_atualizados = []
    for sequencia, (tipo, data_documento) in enumerate(zip(tipos, datas), start=1):
        documento = existentes.pop(tipo, None) or DocumentoEmitido(
            emissao=emissao,
            tipo_documento=tipo,
        )
        documento.titulo = TipoDocumento.ROTULOS[tipo]
        documento.sequencia = sequencia
        documento.data_documento = data_documento
        documento.versao_template = current_app.config["APP_VERSION"]
        documento.status = StatusDocumento.PENDENTE
        documento.erro_processamento = None
        documento.dados_preenchimento = {
            "epis": epis if tipo == TipoDocumento.FICHA_EPI else [],
            "maquinas": maquinas if tipo == TipoDocumento.NR_12 else [],
        }
        documentos_atualizados.append(documento)
    for removido in existentes.values():
        db.session.delete(removido)
    emissao.documentos = documentos_atualizados
    db.session.flush()
    estado_novo = {
        "empresa_id": emissao.empresa_id,
        "funcionario_id": emissao.funcionario_id,
        "data_inicial": emissao.data_inicial.isoformat() if emissao.data_inicial else None,
        "observacoes": emissao.observacoes,
        "documentos": [item.tipo_documento for item in emissao.documentos],
        "dados_gerais": emissao.dados_gerais,
    }
    registrar_auditoria(
        "CADASTROU" if nova_emissao else "EDITOU",
        "Emissões",
        f"Emissão de {funcionario.nome} {'criada' if nova_emissao else 'atualizada'}.",
        entidade_tipo="Emissao",
        entidade_id=emissao.id,
        detalhes=(
            {"dados": estado_novo}
            if nova_emissao
            else {"alteracoes": alteracoes_campos(estado_anterior, estado_novo)}
        ),
    )
    db.session.commit()
    return emissao, []


@bp.get("/")
def listar():
    pagina = request.args.get("pagina", 1, type=int)
    empresa_id = request.args.get("empresa_id", "").strip()
    status = request.args.get("status", "todos").strip()
    consulta = (
        select(Emissao)
        .join(Emissao.empresa)
        .options(selectinload(Emissao.documentos))
        .where(Empresa.tenant_id == tenant_atual_id())
    )
    if empresa_id:
        consulta = consulta.where(Emissao.empresa_id == empresa_id)
    if status in StatusEmissao.TODOS:
        consulta = consulta.where(Emissao.status == status)
    consulta = consulta.order_by(Emissao.criado_em.desc())
    paginacao = db.paginate(consulta, page=max(pagina, 1), per_page=ITENS_POR_PAGINA, error_out=False)
    return render_template(
        "emissoes/listar.html",
        emissoes=paginacao.items,
        paginacao=paginacao,
        empresas=db.session.scalars(
            select(Empresa)
            .where(Empresa.tenant_id == tenant_atual_id())
            .order_by(Empresa.razao_social)
        ),
        empresa_id=empresa_id,
        status=status,
        acao_form=AcaoEmissaoForm(),
    )


@bp.route("/nova", methods=["GET", "POST"])
@permissao_edicao
def nova():
    form = EmissaoForm()
    empresas, funcionarios = configurar_escolhas(form)
    tipos = documentos_selecionados() if request.method == "POST" else []
    epis = ler_epis() if request.method == "POST" else []
    maquinas = ler_maquinas() if request.method == "POST" else []
    erros_especificos = []
    emissao = None
    if form.validate_on_submit():
        try:
            emissao, erros_especificos = salvar_emissao(form)
        except ValueError as erro:
            erros_especificos = [str(erro)]
        if emissao:
            flash("Emissão criada. Confira os dados e gere os documentos.", "success")
            return redirect(url_for("emissoes.detalhar", emissao_id=emissao.id))
    return render_template(
        "emissoes/form.html",
        form=form,
        titulo="Nova Emissão",
        texto_botao="Salvar Emissão",
        empresas=empresas,
        funcionarios=funcionarios,
        tipos_selecionados=tipos,
        epis=epis,
        maquinas=maquinas,
        erros_especificos=erros_especificos,
        emissao=None,
    )


@bp.route("/<string:emissao_id>/editar", methods=["GET", "POST"])
@permissao_edicao
def editar(emissao_id):
    emissao = emissao_do_tenant_ou_404(emissao_id)
    if emissao.status not in {StatusEmissao.RASCUNHO, StatusEmissao.ERRO}:
        flash("Somente emissões em rascunho ou com erro podem ser editadas.", "error")
        return redirect(url_for("emissoes.detalhar", emissao_id=emissao.id))
    form = EmissaoForm()
    empresas, funcionarios = configurar_escolhas(form, emissao)
    if request.method == "GET":
        preencher_form_edicao(form, emissao)
    tipos = documentos_selecionados() if request.method == "POST" else [item.tipo_documento for item in emissao.documentos]
    dados = emissao.dados_gerais or {}
    epis = ler_epis() if request.method == "POST" else dados.get("epis", [])
    maquinas = ler_maquinas() if request.method == "POST" else dados.get("maquinas", [])
    erros_especificos = []
    if form.validate_on_submit():
        try:
            salva, erros_especificos = salvar_emissao(form, emissao)
        except ValueError as erro:
            salva = None
            erros_especificos = [str(erro)]
        if salva:
            flash("Emissão atualizada com sucesso.", "success")
            return redirect(url_for("emissoes.detalhar", emissao_id=emissao.id))
    return render_template(
        "emissoes/form.html",
        form=form,
        titulo="Editar Emissão",
        texto_botao="Salvar Alterações",
        empresas=empresas,
        funcionarios=funcionarios,
        tipos_selecionados=tipos,
        epis=epis,
        maquinas=maquinas,
        erros_especificos=erros_especificos,
        emissao=emissao,
    )


@bp.get("/<string:emissao_id>")
def detalhar(emissao_id):
    emissao = emissao_do_tenant_ou_404(emissao_id)
    return render_template(
        "emissoes/detalhar.html",
        emissao=emissao,
        acao_form=AcaoEmissaoForm(),
    )


@bp.post("/<string:emissao_id>/gerar")
@permissao_edicao
def gerar(emissao_id):
    form = AcaoEmissaoForm()
    if not form.validate_on_submit():
        abort(400)
    emissao = emissao_do_tenant_ou_404(emissao_id)
    resposta_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if emissao.status == StatusEmissao.PROCESSANDO:
        mensagem = "Esta emissão já está sendo processada."
        if resposta_json:
            return jsonify(ok=False, mensagem=mensagem), 409
        flash(mensagem, "error")
        return redirect(url_for("emissoes.detalhar", emissao_id=emissao.id))
    try:
        gerar_emissao(emissao)
    except Exception as erro:
        registrar_auditoria(
            "ERRO_GERACAO",
            "Emissões",
            f"Falha ao gerar documentos da emissão: {erro}",
            entidade_tipo="Emissao",
            entidade_id=emissao.id,
            commit=True,
        )
        mensagem = f"Não foi possível gerar os documentos: {erro}"
        if resposta_json:
            return jsonify(
                ok=False,
                mensagem=mensagem,
                status_url=url_for("emissoes.status_geracao", emissao_id=emissao.id),
            ), 500
        flash(mensagem, "error")
    else:
        registrar_auditoria(
            "GEROU",
            "Emissões",
            f"Documentos de {emissao.funcionario_snapshot.get('nome')} gerados.",
            entidade_tipo="Emissao",
            entidade_id=emissao.id,
            detalhes={"documentos": [item.tipo_documento for item in emissao.documentos]},
            commit=True,
        )
        mensagem = "Documentos gerados em DOCX, PDF e JPEG."
        if resposta_json:
            return jsonify(
                ok=True,
                mensagem=mensagem,
                destino=url_for("emissoes.detalhar", emissao_id=emissao.id),
            )
        flash(mensagem, "success")
    return redirect(url_for("emissoes.detalhar", emissao_id=emissao.id))


@bp.get("/<string:emissao_id>/status-geracao")
def status_geracao(emissao_id):
    emissao = emissao_do_tenant_ou_404(emissao_id)
    total = len(emissao.documentos)
    concluidos = sum(
        1 for item in emissao.documentos if item.status == StatusDocumento.CONCLUIDO
    )
    erros = sum(1 for item in emissao.documentos if item.status == StatusDocumento.ERRO)
    processando = next(
        (item.titulo for item in emissao.documentos if item.status == StatusDocumento.PROCESSANDO),
        None,
    )
    percentual = round((concluidos / total) * 100) if total else 0
    if emissao.status == StatusEmissao.PROCESSANDO and percentual == 0:
        percentual = 8
    return jsonify(
        status=emissao.status,
        total=total,
        concluidos=concluidos,
        erros=erros,
        processando=processando,
        percentual=percentual,
        concluida=emissao.status == StatusEmissao.CONCLUIDA,
    )


@bp.post("/<string:emissao_id>/cancelar")
@permissao_edicao
def cancelar(emissao_id):
    form = AcaoEmissaoForm()
    if not form.validate_on_submit():
        abort(400)
    emissao = emissao_do_tenant_ou_404(emissao_id)
    if emissao.status == StatusEmissao.PROCESSANDO:
        flash("Não é possível cancelar durante o processamento.", "error")
    else:
        emissao.status = StatusEmissao.CANCELADA
        registrar_auditoria(
            "CANCELOU",
            "Emissões",
            "Emissão cancelada.",
            entidade_tipo="Emissao",
            entidade_id=emissao.id,
        )
        db.session.commit()
        flash("Emissão cancelada.", "success")
    return redirect(url_for("emissoes.detalhar", emissao_id=emissao.id))


@bp.post("/<string:emissao_id>/excluir")
@permissao_edicao
def excluir(emissao_id):
    form = AcaoEmissaoForm()
    if not form.validate_on_submit():
        abort(400)
    emissao = emissao_do_tenant_ou_404(emissao_id)
    if emissao.status not in {StatusEmissao.RASCUNHO, StatusEmissao.CANCELADA}:
        flash("Somente rascunhos ou emissões canceladas podem ser excluídos.", "error")
        return redirect(url_for("emissoes.detalhar", emissao_id=emissao.id))
    pastas = {
        Path(arquivo.caminho_arquivo).parent.parent
        for documento in emissao.documentos
        for arquivo in documento.arquivos
    }
    registrar_auditoria(
        "EXCLUIU",
        "Emissões",
        f"Emissão de {emissao.funcionario_snapshot.get('nome')} excluída.",
        entidade_tipo="Emissao",
        entidade_id=emissao.id,
        detalhes={"status": emissao.status},
    )
    db.session.delete(emissao)
    db.session.commit()
    for pasta in pastas:
        shutil.rmtree(pasta, ignore_errors=True)
    flash("Emissão excluída com sucesso.", "success")
    return redirect(url_for("emissoes.listar"))


@bp.get("/arquivo/<string:arquivo_id>")
def baixar_arquivo(arquivo_id):
    arquivo = arquivo_do_tenant_ou_404(arquivo_id)
    path = Path(arquivo.caminho_arquivo)
    if not path.is_file():
        abort(404)
    inline = request.args.get("preview") == "1" and arquivo.formato in {FormatoArquivo.PDF, FormatoArquivo.JPEG}
    return send_file(
        path,
        mimetype=arquivo.mime_type,
        as_attachment=not inline,
        download_name=arquivo.nome_arquivo,
    )
