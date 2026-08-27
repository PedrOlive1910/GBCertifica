from datetime import date

from flask import render_template, request
from sqlalchemy import func, select

from app.extensions import db
from app.models import DocumentoEmitido, Emissao, Empresa, TipoDocumento
from app.services.tenant import tenant_atual_id

from . import bp


@bp.get("/")
def index():
    empresa_id = request.args.get("empresa_id", "").strip()
    tipo = request.args.get("tipo", "").strip()
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()

    consulta = (
        select(DocumentoEmitido)
        .join(DocumentoEmitido.emissao)
        .join(Emissao.empresa)
    )
    filtros = [Empresa.tenant_id == tenant_atual_id()]
    if empresa_id:
        filtros.append(Emissao.empresa_id == empresa_id)
    if tipo in TipoDocumento.TODOS:
        filtros.append(DocumentoEmitido.tipo_documento == tipo)
    try:
        if data_inicio:
            filtros.append(DocumentoEmitido.data_documento >= date.fromisoformat(data_inicio))
        if data_fim:
            filtros.append(DocumentoEmitido.data_documento <= date.fromisoformat(data_fim))
    except ValueError:
        data_inicio = data_fim = ""
    if filtros:
        consulta = consulta.where(*filtros)
    consulta = consulta.order_by(DocumentoEmitido.data_documento.desc())
    documentos = list(db.session.scalars(consulta))

    por_tipo = {item: 0 for item in TipoDocumento.TODOS}
    por_empresa = {}
    for documento in documentos:
        por_tipo[documento.tipo_documento] += 1
        nome = documento.emissao.empresa_snapshot.get(
            "razao_social", documento.emissao.empresa.razao_social
        )
        por_empresa[nome] = por_empresa.get(nome, 0) + 1
    return render_template(
        "relatorios/index.html",
        documentos=documentos,
        total=len(documentos),
        por_tipo=por_tipo,
        por_empresa=sorted(por_empresa.items(), key=lambda item: (-item[1], item[0]))[:8],
        empresas=db.session.scalars(
            select(Empresa)
            .where(Empresa.tenant_id == tenant_atual_id())
            .order_by(Empresa.razao_social)
        ),
        empresa_id=empresa_id,
        tipo=tipo,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
