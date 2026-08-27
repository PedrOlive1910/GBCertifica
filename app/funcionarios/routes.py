from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.auth.permissions import permissao_edicao
from app.models import Empresa, Funcionario, somente_digitos
from app.services.auditoria import alteracoes_campos, registrar_auditoria
from app.services.tenant import (
    empresa_do_tenant_ou_404,
    funcionario_do_tenant_ou_404,
    tenant_atual_id,
)

from . import bp
from .forms import FuncionarioForm, StatusFuncionarioForm


ITENS_POR_PAGINA = 12


def escolhas_empresas(incluir_id=None):
    consulta = select(Empresa).where(Empresa.tenant_id == tenant_atual_id()).order_by(Empresa.razao_social)
    if incluir_id:
        consulta = consulta.where(
            or_(Empresa.ativo.is_(True), Empresa.id == incluir_id)
        )
    else:
        consulta = consulta.where(Empresa.ativo.is_(True))
    return [(empresa.id, empresa.razao_social) for empresa in db.session.scalars(consulta)]


@bp.get("/")
def listar():
    pagina = request.args.get("pagina", 1, type=int)
    busca = request.args.get("busca", "").strip()
    empresa_id = request.args.get("empresa_id", "").strip()
    status = request.args.get("status", "ativos")
    if status not in {"ativos", "inativos", "todos"}:
        status = "ativos"

    consulta = (
        select(Funcionario)
        .join(Funcionario.empresa)
        .where(Empresa.tenant_id == tenant_atual_id())
    )
    if busca:
        filtros = [Funcionario.nome.ilike(f"%{busca}%")]
        busca_numerica = somente_digitos(busca)
        if busca_numerica:
            filtros.append(Funcionario.cpf.ilike(f"%{busca_numerica}%"))
        consulta = consulta.where(or_(*filtros))
    if empresa_id:
        consulta = consulta.where(Funcionario.empresa_id == empresa_id)
    if status == "ativos":
        consulta = consulta.where(Funcionario.ativo.is_(True))
    elif status == "inativos":
        consulta = consulta.where(Funcionario.ativo.is_(False))

    consulta = consulta.order_by(Funcionario.nome)
    paginacao = db.paginate(
        consulta,
        page=max(pagina, 1),
        per_page=ITENS_POR_PAGINA,
        error_out=False,
    )
    return render_template(
        "funcionarios/listar.html",
        funcionarios=paginacao.items,
        paginacao=paginacao,
        busca=busca,
        empresa_id=empresa_id,
        status=status,
        empresas=db.session.scalars(
            select(Empresa)
            .where(Empresa.tenant_id == tenant_atual_id())
            .order_by(Empresa.razao_social)
        ),
        status_form=StatusFuncionarioForm(),
    )


@bp.route("/novo", methods=["GET", "POST"])
@permissao_edicao
def novo():
    form = FuncionarioForm()
    form.empresa_id.choices = escolhas_empresas()
    if form.validate_on_submit():
        empresa = empresa_do_tenant_ou_404(form.empresa_id.data)
        funcionario = Funcionario(
            empresa=empresa,
            nome=form.nome.data,
            cpf=form.cpf.data,
            funcao=form.funcao.data or None,
        )
        db.session.add(funcionario)
        try:
            db.session.flush()
            registrar_auditoria(
                "CADASTROU",
                "Funcionários",
                f"Funcionário {funcionario.nome} cadastrado.",
                entidade_tipo="Funcionario",
                entidade_id=funcionario.id,
                detalhes={
                    "empresa": empresa.razao_social,
                    "cpf": funcionario.cpf,
                    "funcao": funcionario.funcao,
                },
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.cpf.errors.append(
                "Não foi possível salvar: CPF duplicado para esta empresa."
            )
        else:
            flash("Funcionário cadastrado com sucesso.", "success")
            return redirect(url_for("funcionarios.listar"))
    return render_template(
        "funcionarios/form.html",
        form=form,
        titulo="Cadastrar Funcionário",
        texto_botao="Cadastrar Funcionário",
    )


@bp.route("/<string:funcionario_id>/editar", methods=["GET", "POST"])
@permissao_edicao
def editar(funcionario_id):
    funcionario = funcionario_do_tenant_ou_404(funcionario_id)
    form = FuncionarioForm(
        obj=funcionario,
        funcionario_original=funcionario,
    )
    form.empresa_id.choices = escolhas_empresas(funcionario.empresa_id)
    if form.validate_on_submit():
        empresa = empresa_do_tenant_ou_404(form.empresa_id.data)
        antes = {
            "empresa_id": funcionario.empresa_id,
            "nome": funcionario.nome,
            "cpf": funcionario.cpf,
            "funcao": funcionario.funcao,
        }
        funcionario.empresa = empresa
        funcionario.nome = form.nome.data
        funcionario.cpf = form.cpf.data
        funcionario.funcao = form.funcao.data or None
        depois = {
            "empresa_id": funcionario.empresa_id,
            "nome": funcionario.nome,
            "cpf": funcionario.cpf,
            "funcao": funcionario.funcao,
        }
        registrar_auditoria(
            "EDITOU",
            "Funcionários",
            f"Funcionário {funcionario.nome} atualizado.",
            entidade_tipo="Funcionario",
            entidade_id=funcionario.id,
            detalhes={"alteracoes": alteracoes_campos(antes, depois)},
        )
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.cpf.errors.append(
                "Não foi possível salvar: CPF duplicado para esta empresa."
            )
        else:
            flash("Funcionário atualizado com sucesso.", "success")
            return redirect(url_for("funcionarios.listar"))
    return render_template(
        "funcionarios/form.html",
        form=form,
        titulo="Editar Funcionário",
        texto_botao="Salvar Alterações",
        funcionario=funcionario,
    )


@bp.post("/<string:funcionario_id>/alterar-status")
@permissao_edicao
def alterar_status(funcionario_id):
    form = StatusFuncionarioForm()
    if not form.validate_on_submit():
        abort(400)
    funcionario = funcionario_do_tenant_ou_404(funcionario_id)
    funcionario.ativo = not funcionario.ativo
    registrar_auditoria(
        "ALTEROU_STATUS",
        "Funcionários",
        f"Funcionário {funcionario.nome} {'ativado' if funcionario.ativo else 'desativado'}.",
        entidade_tipo="Funcionario",
        entidade_id=funcionario.id,
        detalhes={"ativo": funcionario.ativo},
    )
    db.session.commit()
    acao = "ativado" if funcionario.ativo else "desativado"
    flash(f"Funcionário {acao} com sucesso.", "success")
    return redirect(url_for("funcionarios.listar", status="todos"))
