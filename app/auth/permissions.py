from functools import wraps

from flask import abort, current_app
from app.models import NivelAcesso
from app.security import current_user, login_required


def niveis_permitidos(*niveis):
    def decorador(funcao):
        @wraps(funcao)
        @login_required
        def protegida(*args, **kwargs):
            if current_app.config.get("LOGIN_DISABLED"):
                return funcao(*args, **kwargs)
            if current_user.nivel_acesso not in niveis:
                abort(403)
            return funcao(*args, **kwargs)

        return protegida

    return decorador


somente_admin = niveis_permitidos(NivelAcesso.ADMINISTRADOR)
permissao_edicao = niveis_permitidos(
    NivelAcesso.ADMINISTRADOR,
    NivelAcesso.OPERADOR,
)
