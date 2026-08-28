from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

from flask import current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, select

from app.extensions import db
from app.models import LogAuditoria, Usuario
from app.services.auditoria import registrar_auditoria
from app.security import current_user, login_required, login_user, logout_user

from . import bp
from .forms import LoginForm, RedefinirSenhaForm


def _agora():
    return datetime.now(timezone.utc)


def _como_utc(valor):
    if valor and valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor


def _ip_atual():
    encaminhado = request.headers.get("X-Forwarded-For", "")
    return encaminhado.split(",")[0].strip() if encaminhado else request.remote_addr


def _destino_seguro(destino: str | None) -> bool:
    if not destino:
        return False
    base = urlparse(request.host_url)
    alvo = urlparse(urljoin(request.host_url, destino))
    return alvo.scheme in {"http", "https"} and base.netloc == alvo.netloc


def _ip_temporariamente_bloqueado() -> bool:
    desde = _agora() - timedelta(minutes=current_app.config["LOGIN_BLOCK_MINUTES"])
    quantidade = db.session.scalar(
        select(func.count()).select_from(LogAuditoria).where(
            LogAuditoria.ip == _ip_atual(),
            LogAuditoria.acao == "LOGIN_FALHOU",
            LogAuditoria.criado_em >= desde,
        )
    )
    return (quantidade or 0) >= current_app.config["MAX_LOGIN_FAILURES"]


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if request.method == "GET":
        form.proximo.data = request.args.get("next", "")

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        usuario = db.session.scalar(select(Usuario).where(Usuario.email == email))
        agora = _agora()
        conta_bloqueada = bool(
            usuario
            and usuario.bloqueado_ate
            and _como_utc(usuario.bloqueado_ate) > agora
        )
        ip_bloqueado = _ip_temporariamente_bloqueado()

        credenciais_validas = bool(
            not conta_bloqueada
            and not ip_bloqueado
            and usuario
            and usuario.ativo
            and usuario.tenant.ativo
            and usuario.verificar_senha(form.senha.data)
        )
        if credenciais_validas:
            usuario.ultimo_login_em = agora
            usuario.tentativas_falhas = 0
            usuario.bloqueado_ate = None
            registrar_auditoria(
                "LOGIN",
                "Autenticação",
                "Login realizado com sucesso.",
                entidade_tipo="Usuario",
                entidade_id=usuario.id,
                usuario=usuario,
            )
            db.session.commit()
            session.clear()
            session.permanent = True
            login_user(usuario)
            session["_password_fingerprint"] = usuario.senha_hash[-24:]
            if usuario.deve_trocar_senha:
                return redirect(url_for("auth.trocar_senha_temporaria"))
            destino = form.proximo.data
            return redirect(destino if _destino_seguro(destino) else url_for("main.dashboard"))

        if usuario and not conta_bloqueada:
            usuario.tentativas_falhas += 1
            if usuario.tentativas_falhas >= current_app.config["MAX_LOGIN_FAILURES"]:
                usuario.bloqueado_ate = agora + timedelta(
                    minutes=current_app.config["LOGIN_BLOCK_MINUTES"]
                )
        registrar_auditoria(
            "LOGIN_FALHOU",
            "Autenticação",
            "Tentativa de login recusada.",
            detalhes={
                "email_informado": email,
                "bloqueio_temporario": bool(conta_bloqueada or ip_bloqueado),
            },
            usuario=usuario,
            usuario_nome=email,
        )
        db.session.commit()
        flash(
            "Acesso recusado. Confira os dados ou aguarde alguns minutos antes de tentar novamente.",
            "error",
        )

    return render_template("auth/login.html", form=form)


@bp.route("/esqueci-a-senha", methods=["GET", "POST"])
def solicitar_redefinicao():
    if request.method == "POST":
        flash("Solicite a redefinição de senha ao administrador do sistema.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/solicitar_redefinicao.html")


@bp.route("/redefinir-senha/<string:token>", methods=["GET", "POST"])
def redefinir_senha(token):
    flash("Este recurso está temporariamente sob controle do administrador.", "error")
    return redirect(url_for("auth.solicitar_redefinicao"))


@bp.route("/trocar-senha-temporaria", methods=["GET", "POST"])
@login_required
def trocar_senha_temporaria():
    if not current_user.deve_trocar_senha:
        return redirect(url_for("main.dashboard"))
    form = RedefinirSenhaForm()
    if form.validate_on_submit():
        current_user.definir_senha(form.senha.data)
        current_user.deve_trocar_senha = False
        current_user.tentativas_falhas = 0
        current_user.bloqueado_ate = None
        registrar_auditoria(
            "TROCOU_SENHA_TEMPORARIA",
            "Autenticação",
            "Usuário substituiu a senha temporária.",
            entidade_tipo="Usuario",
            entidade_id=current_user.id,
        )
        db.session.commit()
        session["_password_fingerprint"] = current_user.senha_hash[-24:]
        flash("Senha pessoal criada com sucesso.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("auth/redefinir_senha.html", form=form, troca_obrigatoria=True)


@bp.post("/logout")
def logout():
    if current_user.is_authenticated:
        registrar_auditoria(
            "LOGOUT", "Autenticação", "Sessão encerrada pelo usuário.", commit=True
        )
        logout_user()
    session.clear()
    return redirect(url_for("auth.login"))
