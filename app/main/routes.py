from flask import current_app, render_template
from sqlalchemy import func, select

from app.extensions import db
from app.models import DocumentoEmitido, Emissao, Empresa, Funcionario
from app.services.tenant import tenant_atual_id

from . import bp


@bp.get("/")
def dashboard():
    tenant_id = tenant_atual_id()
    indicadores = {
        "empresas": db.session.scalar(select(func.count()).select_from(Empresa).where(Empresa.tenant_id == tenant_id)) or 0,
        "funcionarios": db.session.scalar(select(func.count()).select_from(Funcionario).join(Funcionario.empresa).where(Empresa.tenant_id == tenant_id)) or 0,
        "emissoes": db.session.scalar(select(func.count()).select_from(Emissao).join(Emissao.empresa).where(Empresa.tenant_id == tenant_id)) or 0,
        "documentos": db.session.scalar(select(func.count()).select_from(DocumentoEmitido).join(DocumentoEmitido.emissao).join(Emissao.empresa).where(Empresa.tenant_id == tenant_id)) or 0,
    }
    ultimas_emissoes = list(
        db.session.scalars(
            select(Emissao)
            .join(Emissao.empresa)
            .where(Empresa.tenant_id == tenant_id)
            .order_by(Emissao.criado_em.desc())
            .limit(5)
        )
    )
    return render_template(
        "main/dashboard.html",
        indicadores=indicadores,
        ultimas_emissoes=ultimas_emissoes,
    )


@bp.get("/health")
def health():
    return {
        "status": "ok",
        "aplicacao": "Sistema TST",
        "versao": current_app.config["APP_VERSION"],
    }
