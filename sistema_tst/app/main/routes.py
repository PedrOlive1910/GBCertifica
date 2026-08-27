from flask import render_template
from sqlalchemy import func, select

from app.extensions import db
from app.models import DocumentoEmitido, Emissao, Empresa, Funcionario

from . import bp


def contar(model):
    return db.session.scalar(select(func.count()).select_from(model)) or 0


@bp.get("/")
def dashboard():
    indicadores = {
        "empresas": contar(Empresa),
        "funcionarios": contar(Funcionario),
        "emissoes": contar(Emissao),
        "documentos": contar(DocumentoEmitido),
    }
    ultimas_emissoes = list(
        db.session.scalars(
            select(Emissao).order_by(Emissao.criado_em.desc()).limit(5)
        )
    )
    return render_template(
        "main/dashboard.html",
        indicadores=indicadores,
        ultimas_emissoes=ultimas_emissoes,
    )


@bp.get("/health")
def health():
    return {"status": "ok", "aplicacao": "Sistema TST"}
