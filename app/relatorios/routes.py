from datetime import date, datetime
from io import BytesIO
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape

from flask import current_app, render_template, request, send_file, url_for
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import DocumentoEmitido, Emissao, Empresa, StatusDocumento, TipoDocumento
from app.security import current_user
from app.services.auditoria import registrar_auditoria
from app.services.tenant import tenant_atual_id

from . import bp


ITENS_POR_PAGINA = 20
VERDE_ESCURO = colors.HexColor("#0B4F38")
VERDE = colors.HexColor("#147A52")
VERDE_CLARO = colors.HexColor("#EAF6F0")
CINZA = colors.HexColor("#667085")


def _ler_filtros():
    filtros = {
        "empresa_id": request.args.get("empresa_id", "").strip(),
        "tipo": request.args.get("tipo", "").strip(),
        "data_inicio": request.args.get("data_inicio", "").strip(),
        "data_fim": request.args.get("data_fim", "").strip(),
    }
    filtros["data_inicio_obj"] = None
    filtros["data_fim_obj"] = None
    try:
        if filtros["data_inicio"]:
            filtros["data_inicio_obj"] = date.fromisoformat(filtros["data_inicio"])
        if filtros["data_fim"]:
            filtros["data_fim_obj"] = date.fromisoformat(filtros["data_fim"])
    except ValueError:
        filtros["data_inicio"] = ""
        filtros["data_fim"] = ""
        filtros["data_inicio_obj"] = None
        filtros["data_fim_obj"] = None
    if filtros["tipo"] not in TipoDocumento.TODOS:
        filtros["tipo"] = ""
    return filtros


def _condicoes(filtros):
    condicoes = [Empresa.tenant_id == tenant_atual_id()]
    if filtros["empresa_id"]:
        condicoes.append(Emissao.empresa_id == filtros["empresa_id"])
    if filtros["tipo"]:
        condicoes.append(DocumentoEmitido.tipo_documento == filtros["tipo"])
    if filtros["data_inicio_obj"]:
        condicoes.append(DocumentoEmitido.data_documento >= filtros["data_inicio_obj"])
    if filtros["data_fim_obj"]:
        condicoes.append(DocumentoEmitido.data_documento <= filtros["data_fim_obj"])
    return condicoes


def _base_documentos():
    return select(DocumentoEmitido).join(DocumentoEmitido.emissao).join(Emissao.empresa)


def _consulta_agregada(coluna, condicoes):
    return (
        select(coluna, func.count(DocumentoEmitido.id))
        .select_from(DocumentoEmitido)
        .join(DocumentoEmitido.emissao)
        .join(Emissao.empresa)
        .where(*condicoes)
        .group_by(coluna)
    )


def _parametros_filtros(filtros):
    return {
        "empresa_id": filtros["empresa_id"],
        "tipo": filtros["tipo"],
        "data_inicio": filtros["data_inicio"],
        "data_fim": filtros["data_fim"],
    }


@bp.get("/")
def index():
    filtros = _ler_filtros()
    condicoes = _condicoes(filtros)
    pagina = max(request.args.get("pagina", 1, type=int), 1)

    consulta = (
        _base_documentos()
        .options(joinedload(DocumentoEmitido.emissao))
        .where(*condicoes)
        .order_by(DocumentoEmitido.data_documento.desc(), DocumentoEmitido.criado_em.desc())
    )
    paginacao = db.paginate(consulta, page=pagina, per_page=ITENS_POR_PAGINA, error_out=False)

    total = db.session.scalar(
        select(func.count(DocumentoEmitido.id))
        .select_from(DocumentoEmitido)
        .join(DocumentoEmitido.emissao)
        .join(Emissao.empresa)
        .where(*condicoes)
    ) or 0

    por_tipo = {item: 0 for item in TipoDocumento.TODOS}
    for tipo_documento, quantidade in db.session.execute(
        _consulta_agregada(DocumentoEmitido.tipo_documento, condicoes)
    ):
        por_tipo[tipo_documento] = quantidade

    por_status = {item: 0 for item in StatusDocumento.TODOS}
    for status, quantidade in db.session.execute(
        _consulta_agregada(DocumentoEmitido.status, condicoes)
    ):
        por_status[status] = quantidade

    consulta_empresas = (
        select(Empresa.razao_social, func.count(DocumentoEmitido.id))
        .select_from(DocumentoEmitido)
        .join(DocumentoEmitido.emissao)
        .join(Emissao.empresa)
        .where(*condicoes)
        .group_by(Empresa.id, Empresa.razao_social)
        .order_by(func.count(DocumentoEmitido.id).desc(), Empresa.razao_social)
        .limit(8)
    )
    por_empresa = list(db.session.execute(consulta_empresas))
    maior_empresa = max((quantidade for _, quantidade in por_empresa), default=1)

    empresas = list(
        db.session.scalars(
            select(Empresa)
            .where(Empresa.tenant_id == tenant_atual_id())
            .order_by(Empresa.razao_social)
        )
    )
    parametros = _parametros_filtros(filtros)
    return render_template(
        "relatorios/index.html",
        documentos=paginacao.items,
        paginacao=paginacao,
        total=total,
        por_tipo=por_tipo,
        por_status=por_status,
        por_empresa=por_empresa,
        maior_empresa=maior_empresa,
        empresas=empresas,
        filtros=parametros,
        pdf_url=url_for("relatorios.exportar_pdf", **parametros),
    )


def _texto_filtros(filtros, empresas):
    partes = []
    empresa = next((item for item in empresas if item.id == filtros["empresa_id"]), None)
    if empresa:
        partes.append(f"Empresa: {empresa.razao_social}")
    if filtros["tipo"]:
        partes.append(f"Documento: {TipoDocumento.ROTULOS[filtros['tipo']]}")
    if filtros["data_inicio"]:
        partes.append(f"De: {filtros['data_inicio_obj'].strftime('%d/%m/%Y')}")
    if filtros["data_fim"]:
        partes.append(f"Até: {filtros['data_fim_obj'].strftime('%d/%m/%Y')}")
    return "  •  ".join(partes) if partes else "Todos os documentos e períodos"


def _rodape_pdf(canvas, documento):
    canvas.saveState()
    largura, _ = landscape(A4)
    canvas.setStrokeColor(colors.HexColor("#D8E7DF"))
    canvas.line(14 * mm, 10 * mm, largura - 14 * mm, 10 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(CINZA)
    canvas.drawString(14 * mm, 6 * mm, f"Sistema TST • Versão {current_app.config['APP_VERSION']}")
    canvas.drawRightString(largura - 14 * mm, 6 * mm, f"Página {documento.page}")
    canvas.restoreState()


@bp.get("/pdf")
def exportar_pdf():
    filtros = _ler_filtros()
    condicoes = _condicoes(filtros)
    empresas = list(
        db.session.scalars(
            select(Empresa)
            .where(Empresa.tenant_id == tenant_atual_id())
            .order_by(Empresa.razao_social)
        )
    )
    documentos = list(
        db.session.scalars(
            _base_documentos()
            .options(joinedload(DocumentoEmitido.emissao))
            .where(*condicoes)
            .order_by(DocumentoEmitido.data_documento.desc(), DocumentoEmitido.criado_em.desc())
        )
    )

    agora = datetime.now(ZoneInfo(current_app.config["APP_TIMEZONE"]))
    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=15 * mm,
        bottomMargin=16 * mm,
        title="Relatório de documentos TST",
        author="Sistema TST",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloTST", parent=estilos["Title"], fontName="Helvetica-Bold",
        fontSize=19, leading=23, textColor=VERDE_ESCURO, alignment=TA_LEFT, spaceAfter=4,
    )
    apoio = ParagraphStyle(
        "ApoioTST", parent=estilos["Normal"], fontName="Helvetica",
        fontSize=8.5, leading=11, textColor=CINZA,
    )
    celula = ParagraphStyle(
        "CelulaTST", parent=estilos["Normal"], fontName="Helvetica",
        fontSize=7.5, leading=9.5, textColor=colors.HexColor("#24342D"),
    )
    numero = ParagraphStyle(
        "NumeroTST", parent=apoio, fontName="Helvetica-Bold",
        fontSize=17, textColor=VERDE, alignment=TA_RIGHT,
    )

    usuario_nome = current_user.nome if current_user.is_authenticated else "Sistema"
    historia = [
        Table([[
            Paragraph("Relatório de documentos emitidos", titulo),
            Paragraph(f"<b>{len(documentos)}</b><br/>documento(s)", numero),
        ]], colWidths=[230 * mm, 35 * mm]),
        Paragraph(escape(_texto_filtros(filtros, empresas)), apoio),
        Paragraph(escape(f"Gerado em {agora.strftime('%d/%m/%Y às %H:%M')} por {usuario_nome}."), apoio),
        Spacer(1, 7 * mm),
    ]

    linhas = [["Data", "Documento", "Empresa", "Funcionário", "Status"]]
    for item in documentos:
        linhas.append([
            item.data_documento.strftime("%d/%m/%Y") if item.data_documento else "—",
            Paragraph(escape(item.titulo or TipoDocumento.ROTULOS.get(item.tipo_documento, item.tipo_documento)), celula),
            Paragraph(escape(item.emissao.empresa_snapshot.get("razao_social", "—")), celula),
            Paragraph(escape(item.emissao.funcionario_snapshot.get("nome", "—")), celula),
            item.status.replace("_", " ").title(),
        ])
    if len(linhas) == 1:
        linhas.append(["—", "Nenhum documento encontrado", "—", "—", "—"])

    tabela = LongTable(
        linhas, repeatRows=1,
        colWidths=[23 * mm, 54 * mm, 76 * mm, 76 * mm, 30 * mm],
    )
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VERDE_ESCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#24342D")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, VERDE_CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8E7DF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    historia.append(tabela)
    pdf.build(historia, onFirstPage=_rodape_pdf, onLaterPages=_rodape_pdf)
    buffer.seek(0)

    registrar_auditoria(
        "EXPORTOU_PDF", "Relatórios",
        f"Exportou relatório em PDF com {len(documentos)} documento(s).",
        detalhes={"filtros": _parametros_filtros(filtros), "total": len(documentos)},
        commit=True,
    )
    return send_file(
        buffer, mimetype="application/pdf", as_attachment=True,
        download_name=f"relatorio_tst_{agora.strftime('%Y%m%d_%H%M')}.pdf",
        max_age=0,
    )
