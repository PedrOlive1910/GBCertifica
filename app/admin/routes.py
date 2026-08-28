from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.auth.permissions import somente_admin
from app.extensions import db
from app.models import LogAuditoria, NivelAcesso, Usuario
from app.services.auditoria import alteracoes_campos, registrar_auditoria
from app.security import current_user

from . import bp
from .forms import RedefinirSenhaUsuarioForm, StatusUsuarioForm, UsuarioForm


ITENS_POR_PAGINA = 15
ACOES = (
    "ACESSOU",
    "CADASTROU",
    "EDITOU",
    "ALTEROU_STATUS",
    "GEROU",
    "CANCELOU",
    "EXCLUIU",
    "LOGIN",
    "LOGIN_FALHOU",
    "LOGOUT",
    "ERRO_GERACAO",
    "SOLICITOU_REDEFINICAO",
    "REDEFINIU_SENHA",
    "ERRO_EMAIL",
    "ADMIN_REDEFINIU_SENHA",
    "TROCOU_SENHA_TEMPORARIA",
)


def _email_em_uso(email, ignorar_id=None):
    consulta = select(Usuario.id).where(Usuario.email == email.strip().lower())
    if ignorar_id:
        consulta = consulta.where(Usuario.id != ignorar_id)
    return db.session.scalar(consulta) is not None


def _usuario_do_tenant_ou_404(usuario_id):
    return db.first_or_404(
        select(Usuario).where(
            Usuario.id == usuario_id,
            Usuario.tenant_id == current_user.tenant_id,
        )
    )


@bp.get("/usuarios")
@somente_admin
def usuarios():
    busca = request.args.get("busca", "").strip()
    nivel = request.args.get("nivel", "").strip()
    pagina = max(request.args.get("pagina", 1, type=int), 1)
    consulta = select(Usuario).where(Usuario.tenant_id == current_user.tenant_id)
    if busca:
        consulta = consulta.where(
            or_(Usuario.nome.ilike(f"%{busca}%"), Usuario.email.ilike(f"%{busca}%"))
        )
    if nivel in NivelAcesso.TODOS:
        consulta = consulta.where(Usuario.nivel_acesso == nivel)
    paginacao = db.paginate(
        consulta.order_by(Usuario.nome),
        page=pagina,
        per_page=ITENS_POR_PAGINA,
        error_out=False,
    )
    return render_template(
        "admin/usuarios.html",
        usuarios=paginacao.items,
        paginacao=paginacao,
        busca=busca,
        nivel=nivel,
        niveis=NivelAcesso.ROTULOS,
        status_form=StatusUsuarioForm(),
    )


@bp.route("/usuarios/novo", methods=["GET", "POST"])
@somente_admin
def novo_usuario():
    form = UsuarioForm()
    if form.validate_on_submit():
        if not form.senha.data:
            form.senha.errors.append("Informe uma senha inicial com pelo menos 8 caracteres.")
        elif _email_em_uso(form.email.data):
            form.email.errors.append("Este e-mail já está cadastrado.")
        else:
            usuario = Usuario(
                tenant_id=current_user.tenant_id,
                nome=form.nome.data.strip(),
                email=form.email.data,
                nivel_acesso=form.nivel_acesso.data,
                ativo=form.ativo.data,
                deve_trocar_senha=True,
            )
            usuario.definir_senha(form.senha.data)
            db.session.add(usuario)
            try:
                db.session.flush()
                registrar_auditoria(
                    "CADASTROU",
                    "Usuários",
                    f"Usuário {usuario.nome} cadastrado.",
                    entidade_tipo="Usuario",
                    entidade_id=usuario.id,
                    detalhes={"email": usuario.email, "nivel_acesso": usuario.nivel_acesso},
                )
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                form.email.errors.append("Este e-mail já está cadastrado.")
            else:
                flash("Usuário cadastrado com sucesso.", "success")
                return redirect(url_for("admin.usuarios"))
    return render_template(
        "admin/usuario_form.html",
        form=form,
        titulo="Novo usuário",
        texto_senha="Obrigatória no primeiro cadastro.",
    )


@bp.route("/usuarios/<string:usuario_id>/editar", methods=["GET", "POST"])
@somente_admin
def editar_usuario(usuario_id):
    usuario = _usuario_do_tenant_ou_404(usuario_id)
    form = UsuarioForm(obj=usuario)
    if form.validate_on_submit():
        if _email_em_uso(form.email.data, usuario.id):
            form.email.errors.append("Este e-mail já está cadastrado.")
        elif usuario.id == current_user.id and not form.ativo.data:
            form.ativo.errors.append("Você não pode desativar o próprio usuário.")
        elif usuario.id == current_user.id and form.nivel_acesso.data != NivelAcesso.ADMINISTRADOR:
            form.nivel_acesso.errors.append("Você não pode remover o próprio acesso de administrador.")
        else:
            antes = {
                "nome": usuario.nome,
                "email": usuario.email,
                "nivel_acesso": usuario.nivel_acesso,
                "ativo": usuario.ativo,
            }
            usuario.nome = form.nome.data.strip()
            usuario.email = form.email.data
            usuario.nivel_acesso = form.nivel_acesso.data
            usuario.ativo = form.ativo.data
            senha_alterada = bool(form.senha.data)
            if senha_alterada:
                usuario.definir_senha(form.senha.data)
                usuario.deve_trocar_senha = True
            depois = {
                "nome": usuario.nome,
                "email": usuario.email,
                "nivel_acesso": usuario.nivel_acesso,
                "ativo": usuario.ativo,
            }
            mudancas = alteracoes_campos(antes, depois)
            if senha_alterada:
                mudancas["senha"] = {"antes": "protegida", "depois": "redefinida"}
            registrar_auditoria(
                "EDITOU",
                "Usuários",
                f"Usuário {usuario.nome} atualizado.",
                entidade_tipo="Usuario",
                entidade_id=usuario.id,
                detalhes={"alteracoes": mudancas},
            )
            db.session.commit()
            flash("Usuário atualizado com sucesso.", "success")
            return redirect(url_for("admin.usuarios"))
    return render_template(
        "admin/usuario_form.html",
        form=form,
        titulo="Editar usuário",
        texto_senha="Deixe em branco para manter a senha atual.",
        usuario=usuario,
    )


@bp.post("/usuarios/<string:usuario_id>/alterar-status")
@somente_admin
def alterar_status_usuario(usuario_id):
    form = StatusUsuarioForm()
    if not form.validate_on_submit():
        abort(400)
    usuario = _usuario_do_tenant_ou_404(usuario_id)
    if usuario.id == current_user.id:
        flash("Você não pode desativar o próprio usuário.", "error")
        return redirect(url_for("admin.usuarios"))
    if usuario.ativo and usuario.nivel_acesso == NivelAcesso.ADMINISTRADOR:
        ativos = db.session.scalar(
            select(func.count()).select_from(Usuario).where(
                Usuario.ativo.is_(True),
                Usuario.tenant_id == current_user.tenant_id,
                Usuario.nivel_acesso == NivelAcesso.ADMINISTRADOR,
            )
        )
        if ativos <= 1:
            flash("O sistema precisa manter ao menos um administrador ativo.", "error")
            return redirect(url_for("admin.usuarios"))
    usuario.ativo = not usuario.ativo
    registrar_auditoria(
        "ALTEROU_STATUS",
        "Usuários",
        f"Usuário {usuario.nome} {'ativado' if usuario.ativo else 'desativado'}.",
        entidade_tipo="Usuario",
        entidade_id=usuario.id,
        detalhes={"ativo": usuario.ativo},
    )
    db.session.commit()
    flash("Status do usuário atualizado.", "success")
    return redirect(url_for("admin.usuarios"))


@bp.route("/usuarios/<string:usuario_id>/redefinir-senha", methods=["GET", "POST"])
@somente_admin
def redefinir_senha_usuario(usuario_id):
    usuario = _usuario_do_tenant_ou_404(usuario_id)
    form = RedefinirSenhaUsuarioForm()
    if form.validate_on_submit():
        usuario.definir_senha(form.senha.data)
        usuario.deve_trocar_senha = True
        usuario.tentativas_falhas = 0
        usuario.bloqueado_ate = None
        for token in usuario.tokens_redefinicao:
            if token.usado_em is None:
                token.usado_em = token.expira_em
        registrar_auditoria(
            "ADMIN_REDEFINIU_SENHA",
            "Usuários",
            f"Senha temporária definida para {usuario.nome}.",
            entidade_tipo="Usuario",
            entidade_id=usuario.id,
            detalhes={"troca_obrigatoria": True},
        )
        db.session.commit()
        flash(
            "Senha temporária definida. O usuário deverá alterá-la no próximo acesso.",
            "success",
        )
        return redirect(url_for("admin.usuarios"))
    return render_template(
        "admin/redefinir_senha_usuario.html", form=form, usuario=usuario
    )


@bp.get("/auditoria")
@somente_admin
def auditoria():
    pagina = max(request.args.get("pagina", 1, type=int), 1)
    usuario_id = request.args.get("usuario_id", "").strip()
    modulo = request.args.get("modulo", "").strip()
    acao = request.args.get("acao", "").strip()
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()
    consulta = select(LogAuditoria).where(
        LogAuditoria.tenant_id == current_user.tenant_id
    )
    if usuario_id:
        consulta = consulta.where(LogAuditoria.usuario_id == usuario_id)
    if modulo:
        consulta = consulta.where(LogAuditoria.modulo == modulo)
    if acao:
        consulta = consulta.where(LogAuditoria.acao == acao)
    try:
        if data_inicio:
            consulta = consulta.where(LogAuditoria.criado_em >= date.fromisoformat(data_inicio))
        if data_fim:
            consulta = consulta.where(
                func.date(LogAuditoria.criado_em) <= date.fromisoformat(data_fim)
            )
    except ValueError:
        data_inicio = data_fim = ""
    paginacao = db.paginate(
        consulta.order_by(LogAuditoria.criado_em.desc()),
        page=pagina,
        per_page=25,
        error_out=False,
    )
    modulos = list(
        db.session.scalars(
            select(LogAuditoria.modulo)
            .where(LogAuditoria.tenant_id == current_user.tenant_id)
            .distinct()
            .order_by(LogAuditoria.modulo)
        )
    )
    return render_template(
        "admin/auditoria.html",
        logs=paginacao.items,
        paginacao=paginacao,
        usuarios=db.session.scalars(
            select(Usuario)
            .where(Usuario.tenant_id == current_user.tenant_id)
            .order_by(Usuario.nome)
        ),
        modulos=modulos,
        acoes=ACOES,
        usuario_id=usuario_id,
        modulo=modulo,
        acao=acao,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@bp.get("/auditoria/<string:log_id>")
@somente_admin
def detalhe_auditoria(log_id):
    log = db.first_or_404(
        select(LogAuditoria).where(
            LogAuditoria.id == log_id,
            LogAuditoria.tenant_id == current_user.tenant_id,
        )
    )
    return render_template("admin/auditoria_detalhe.html", log=log)
