from datetime import datetime, timezone

from flask import current_app, render_template
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import (
    DocumentoEmitido,
    Emissao,
    Empresa,
    Funcionario,
    StatusDocumento,
    StatusEmissao,
    TipoDocumento,
)
from app.services.tenant import tenant_atual_id

from . import bp


@bp.get("/")
def dashboard():
    tenant_id = tenant_atual_id()
    agora = datetime.now(timezone.utc)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    empresas_ativas = db.session.scalar(
        select(func.count(Empresa.id)).where(
            Empresa.tenant_id == tenant_id,
            Empresa.ativo.is_(True),
        )
    ) or 0
    funcionarios_ativos = db.session.scalar(
        select(func.count(Funcionario.id))
        .join(Funcionario.empresa)
        .where(Empresa.tenant_id == tenant_id, Funcionario.ativo.is_(True))
    ) or 0
    emissoes_mes = db.session.scalar(
        select(func.count(Emissao.id))
        .join(Emissao.empresa)
        .where(Empresa.tenant_id == tenant_id, Emissao.criado_em >= inicio_mes)
    ) or 0
    documentos_concluidos = db.session.scalar(
        select(func.count(DocumentoEmitido.id))
        .join(DocumentoEmitido.emissao)
        .join(Emissao.empresa)
        .where(
            Empresa.tenant_id == tenant_id,
            DocumentoEmitido.status == StatusDocumento.CONCLUIDO,
        )
    ) or 0

    por_status = {item: 0 for item in StatusEmissao.TODOS}
    for status, quantidade in db.session.execute(
        select(Emissao.status, func.count(Emissao.id))
        .join(Emissao.empresa)
        .where(Empresa.tenant_id == tenant_id)
        .group_by(Emissao.status)
    ):
        por_status[status] = quantidade
    total_emissoes = sum(por_status.values())
    taxa_conclusao = round(
        (por_status[StatusEmissao.CONCLUIDA] / total_emissoes) * 100
    ) if total_emissoes else 0

    por_tipo = {item: 0 for item in TipoDocumento.TODOS}
    for tipo, quantidade in db.session.execute(
        select(DocumentoEmitido.tipo_documento, func.count(DocumentoEmitido.id))
        .join(DocumentoEmitido.emissao)
        .join(Emissao.empresa)
        .where(Empresa.tenant_id == tenant_id)
        .group_by(DocumentoEmitido.tipo_documento)
    ):
        por_tipo[tipo] = quantidade
    maior_tipo = max(por_tipo.values(), default=1) or 1

    ultimas_emissoes = list(
        db.session.scalars(
            select(Emissao)
            .join(Emissao.empresa)
            .options(selectinload(Emissao.documentos))
            .where(Empresa.tenant_id == tenant_id)
            .order_by(Emissao.criado_em.desc())
            .limit(7)
        )
    )
    indicadores = {
        "empresas_ativas": empresas_ativas,
        "funcionarios_ativos": funcionarios_ativos,
        "emissoes_mes": emissoes_mes,
        "documentos_concluidos": documentos_concluidos,
        "total_emissoes": total_emissoes,
        "taxa_conclusao": taxa_conclusao,
        "atencao": por_status[StatusEmissao.ERRO] + por_status[StatusEmissao.PROCESSANDO],
    }
    return render_template(
        "main/dashboard.html",
        indicadores=indicadores,
        por_status=por_status,
        por_tipo=por_tipo,
        maior_tipo=maior_tipo,
        ultimas_emissoes=ultimas_emissoes,
    )


@bp.get("/health")
def health():
    return {
        "status": "ok",
        "aplicacao": "Sistema TST",
        "versao": current_app.config["APP_VERSION"],
    }
