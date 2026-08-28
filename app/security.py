from functools import wraps

from flask import current_app, g, session
from werkzeug.local import LocalProxy


class UsuarioAnonimo:
    is_authenticated = False
    is_anonymous = True
    is_active = False
    eh_administrador = False
    pode_editar = False
    id = None
    tenant_id = None
    nome = "Visitante"
    nivel_acesso = None


_anonimo = UsuarioAnonimo()


def _usuario_atual():
    return getattr(g, "usuario_atual", _anonimo)


current_user = LocalProxy(_usuario_atual)


class LoginManager:
    def __init__(self):
        self.login_view = None
        self.login_message = None
        self.login_message_category = "message"
        self.session_protection = "strong"
        self._carregador = None
        self._nao_autorizado = None

    def init_app(self, app):
        @app.before_request
        def carregar_sessao():
            usuario = None
            usuario_id = session.get("_user_id")
            if usuario_id and self._carregador:
                usuario = self._carregador(usuario_id)
            if usuario is None:
                session.pop("_user_id", None)
                usuario = _anonimo
            g.usuario_atual = usuario

    def user_loader(self, funcao):
        self._carregador = funcao
        return funcao

    def unauthorized_handler(self, funcao):
        self._nao_autorizado = funcao
        return funcao

    def unauthorized(self):
        if self._nao_autorizado:
            return self._nao_autorizado()
        raise PermissionError("Autenticação obrigatória.")


def login_user(usuario, remember=False):
    if not usuario or not usuario.is_active:
        return False
    session["_user_id"] = usuario.get_id()
    session["_remember"] = bool(remember)
    session["_password_fingerprint"] = usuario.senha_hash[-24:]
    session.permanent = True
    g.usuario_atual = usuario
    return True


def logout_user():
    session.pop("_user_id", None)
    session.pop("_remember", None)
    session.pop("_password_fingerprint", None)
    g.usuario_atual = _anonimo


def login_required(funcao):
    @wraps(funcao)
    def protegida(*args, **kwargs):
        if current_app.config.get("LOGIN_DISABLED") or current_user.is_authenticated:
            return funcao(*args, **kwargs)
        from app.extensions import login_manager

        return login_manager.unauthorized()

    return protegida
