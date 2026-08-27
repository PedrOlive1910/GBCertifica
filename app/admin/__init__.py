from flask import Blueprint


bp = Blueprint("admin", __name__, url_prefix="/administracao")

from . import routes  # noqa: E402, F401
