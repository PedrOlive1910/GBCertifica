from flask import Blueprint


bp = Blueprint("emissoes", __name__, url_prefix="/emissoes")

from . import routes  # noqa: E402, F401
