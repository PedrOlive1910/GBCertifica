import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

from flask import current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, select

from app.extensions import db
from app.models import LogAuditoria, TokenRedefinicaoSenha, Usuario
from app.services.auditoria import registrar_auditoria
from app.services.email import ErroEnvioEmail, enviar_email
from app.security import current_user, login_user, logout_user

from . import bp
from .forms import LoginForm, RedefinirSenhaForm, SolicitarRedefinicaoForm


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
    form = SolicitarRedefinicaoForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        usuario = db.session.scalar(
            select(Usuario).where(Usuario.email == email, Usuario.ativo.is_(True))
        )
        if usuario:
            agora = _agora()
            for anterior in usuario.tokens_redefinicao:
                if anterior.usado_em is None:
                    anterior.usado_em = agora
            token_aberto = secrets.token_urlsafe(48)
            token = TokenRedefinicaoSenha(
                usuario=usuario,
                token_hash=hashlib.sha256(token_aberto.encode()).hexdigest(),
                expira_em=agora + timedelta(hours=1),
                solicitado_ip=_ip_atual(),
            )
            db.session.add(token)
            db.session.flush()
            caminho = url_for("auth.redefinir_senha", token=token_aberto)
            link = f"{current_app.config['APP_BASE_URL'].rstrip('/')}{caminho}"
            texto = (
                f"Olá, {usuario.nome}.\n\n"
                "Recebemos uma solicitação para redefinir sua senha do GBcertifica.\n"
                f"Use o link abaixo em até 1 hora:\n\n{link}\n\n"
                "O link é de uso único. Se você não solicitou, ignore este e-mail."
            )
            try:
                enviar_email(usuario.email, "Redefinição de senha — GBcertifica", texto)
            except ErroEnvioEmail as erro:
                db.session.delete(token)
                registrar_auditoria(
                    "ERRO_EMAIL",
                    "Autenticação",
                    "Não foi possível enviar o e-mail de redefinição.",
                    entidade_tipo="Usuario",
                    entidade_id=usuario.id,
                    detalhes={"erro": str(erro)},
                    usuario=usuario,
                )
                current_app.logger.exception("Falha no envio da recuperação de senha")
            else:
                registrar_auditoria(
                    "SOLICITOU_REDEFINICAO",
                    "Autenticação",
                    "Link de redefinição de senha solicitado.",
                    entidade_tipo="Usuario",
                    entidade_id=usuario.id,
                    usuario=usuario,
                )
            db.session.commit()
        flash(
            "Se o e-mail estiver cadastrado, enviaremos um link válido por 1 hora.",
            "success",
        )
        return redirect(url_for("auth.login"))
    return render_template("auth/solicitar_redefinicao.html", form=form)


@bp.route("/redefinir-senha/<string:token>", methods=["GET", "POST"])
def redefinir_senha(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    registro = db.session.scalar(
        select(TokenRedefinicaoSenha).where(
            TokenRedefinicaoSenha.token_hash == token_hash,
            TokenRedefinicaoSenha.usado_em.is_(None),
        )
    )
    if not registro or _como_utc(registro.expira_em) <= _agora():
        flash("Este link é inválido ou expirou. Solicite um novo.", "error")
        return redirect(url_for("auth.solicitar_redefinicao"))

    form = RedefinirSenhaForm()
    if form.validate_on_submit():
        registro.usuario.definir_senha(form.senha.data)
        registro.usuario.tentativas_falhas = 0
        registro.usuario.bloqueado_ate = None
        registro.usado_em = _agora()
        registrar_auditoria(
            "REDEFINIU_SENHA",
            "Autenticação",
            "Senha redefinida por token de uso único.",
            entidade_tipo="Usuario",
            entidade_id=registro.usuario_id,
            usuario=registro.usuario,
        )
        db.session.commit()
        flash("Senha redefinida com sucesso. Faça login com a nova senha.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/redefinir_senha.html", form=form)


@bp.post("/logout")
def logout():
    if current_user.is_authenticated:
        registrar_auditoria(
            "LOGOUT", "Autenticação", "Sessão encerrada pelo usuário.", commit=True
        )
        logout_user()
    session.clear()
    return redirect(url_for("auth.login"))
