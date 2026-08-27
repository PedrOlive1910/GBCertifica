from flask import Blueprint


bp = Blueprint("empresas", __name__, url_prefix="/empresas")

from . import routes  # noqa: E402, F401
