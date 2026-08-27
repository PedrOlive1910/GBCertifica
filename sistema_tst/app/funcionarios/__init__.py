from flask import Blueprint


bp = Blueprint("funcionarios", __name__, url_prefix="/funcionarios")

from . import routes  # noqa: E402, F401
