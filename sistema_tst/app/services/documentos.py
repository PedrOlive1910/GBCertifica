from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from docxtpl import DocxTemplate
from flask import current_app
from jinja2 import Environment, StrictUndefined
from pypdf import PdfReader, PdfWriter

from app.extensions import db
from app.models import (
    ArquivoDocumento,
    FormatoArquivo,
    StatusDocumento,
    StatusEmissao,
    TipoDocumento,
    formatar_cnpj,
    formatar_cpf,
)


TEMPLATE_FILES = {
    TipoDocumento.FICHA_EPI: "ficha_epi.docx",
    TipoDocumento.ORDEM_SERVICO: "ordem_servico.docx",
    TipoDocumento.NR_06: "nr06.docx",
    TipoDocumento.NR_12: "nr12.docx",
    TipoDocumento.NR_18: "nr18.docx",
    TipoDocumento.NR_35: "nr35.docx",
}

MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


class ErroGeracaoDocumento(RuntimeError):
    pass


def data_extenso(valor: date) -> str:
    return f"{valor.day} de {MESES[valor.month - 1]} de {valor.year}"


def data_br(valor: date | None) -> str:
    return valor.strftime("%d/%m/%Y") if valor else ""


def data_br_texto(valor: str | None) -> str:
    if not valor:
        return ""
    try:
        return date.fromisoformat(valor).strftime("%d/%m/%Y")
    except ValueError:
        return valor


def limpar_nome_arquivo(valor: str) -> str:
    permitidos = []
    for caractere in valor.strip():
        if caractere.isalnum() or caractere in {"-", "_"}:
            permitidos.append(caractere)
        elif caractere.isspace():
            permitidos.append("_")
    return "".join(permitidos).strip("_") or "documento"


def contexto_documento(documento) -> dict:
    emissao = documento.emissao
    empresa = emissao.empresa_snapshot
    funcionario = emissao.funcionario_snapshot
    dados = emissao.dados_gerais or {}
    os_dados = dados.get("ordem_servico", {})
    epis = []
    for original in dados.get("epis", []):
        item = dict(original)
        item["data_entrega"] = data_br_texto(item.get("data_entrega"))
        item["data_devolucao"] = data_br_texto(item.get("data_devolucao"))
        epis.append(item)
    minimo_linhas = 15
    while len(epis) < minimo_linhas:
        epis.append(
            {
                "quantidade": "",
                "descricao": "",
                "ca": "",
                "data_entrega": "",
                "data_devolucao": "",
                "assinatura": "",
            }
        )

    maquinas = [item.strip() for item in dados.get("maquinas", []) if item.strip()]
    return {
        "nome_funcionario": funcionario.get("nome", ""),
        "cpf_funcionario": formatar_cpf(funcionario.get("cpf", "")),
        "funcao": funcionario.get("funcao", ""),
        "razao_social": empresa.get("razao_social", ""),
        "cnpj": formatar_cnpj(empresa.get("cnpj", "")),
        "cidade_empresa": empresa.get("cidade", ""),
        "endereco_completo": empresa.get("endereco_completo", ""),
        "data_admissao": dados.get("data_admissao_formatada", ""),
        "data_documento": data_br(documento.data_documento),
        "data_documento_extenso": data_extenso(documento.data_documento),
        "epis": epis,
        "maquinas_texto": ", ".join(maquinas),
        "setor": os_dados.get("setor", ""),
        "cbo": os_dados.get("cbo", ""),
        "descricao_funcao": os_dados.get("descricao_funcao", ""),
        "risco_fisico": os_dados.get("risco_fisico", "Não identificado."),
        "risco_quimico": os_dados.get("risco_quimico", "Não identificado."),
        "risco_biologico": os_dados.get("risco_biologico", "Não identificado."),
        "risco_ergonomico": os_dados.get("risco_ergonomico", "Não identificado."),
        "risco_acidentes": os_dados.get("risco_acidentes", "Não identificado."),
        "epis_atividade_texto": os_dados.get("epis_atividade", ""),
        "recomendacoes": os_dados.get("recomendacoes", ""),
        "procedimentos_acidente": os_dados.get("procedimentos_acidente", ""),
        "responsavel_nome": os_dados.get("responsavel_nome", ""),
        "responsavel_cargo": os_dados.get("responsavel_cargo", ""),
        "responsavel_registro": os_dados.get("responsavel_registro", ""),
    }


def renderizar_docx(documento, destino: Path) -> None:
    template_path = Path(current_app.root_path) / "document_templates" / TEMPLATE_FILES[documento.tipo_documento]
    if not template_path.exists():
        raise ErroGeracaoDocumento(f"Template não encontrado: {template_path.name}")
    template = DocxTemplate(template_path)
    ambiente = Environment(undefined=StrictUndefined, autoescape=False)
    template.render(contexto_documento(documento), jinja_env=ambiente)
    template.save(destino)


def converter_para_pdf(docx_path: Path, output_dir: Path) -> Path:
    executavel = shutil.which("soffice") or shutil.which("libreoffice")
    if not executavel:
        raise ErroGeracaoDocumento("LibreOffice não encontrado no PATH do servidor.")

    profile_dir = Path(tempfile.mkdtemp(prefix="tst_lo_"))
    try:
        comando = [
            executavel,
            "--headless",
            f"-env:UserInstallation={profile_dir.as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(docx_path),
        ]
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        pdf_path = output_dir / f"{docx_path.stem}.pdf"
        if resultado.returncode != 0 or not pdf_path.exists():
            detalhe = (resultado.stderr or resultado.stdout or "erro desconhecido").strip()
            raise ErroGeracaoDocumento(f"Falha na conversão para PDF: {detalhe}")
        remover_paginas_pdf_vazias(pdf_path)
        return pdf_path
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)


def remover_paginas_pdf_vazias(pdf_path: Path) -> None:
    """Remove páginas totalmente vazias criadas pelo LibreOffice em modelos antigos."""
    leitor = PdfReader(str(pdf_path))
    paginas_validas = []
    for pagina in leitor.pages:
        texto = (pagina.extract_text() or "").strip()
        if texto:
            paginas_validas.append(pagina)
    if not paginas_validas or len(paginas_validas) == len(leitor.pages):
        return
    escritor = PdfWriter()
    for pagina in paginas_validas:
        escritor.add_page(pagina)
    temporario = pdf_path.with_suffix(".limpo.pdf")
    with temporario.open("wb") as arquivo:
        escritor.write(arquivo)
    temporario.replace(pdf_path)


def converter_pdf_para_jpeg(pdf_path: Path, output_dir: Path) -> list[Path]:
    executavel = shutil.which("pdftoppm")
    if not executavel:
        raise ErroGeracaoDocumento("Poppler/pdftoppm não encontrado no PATH do servidor.")
    prefixo = output_dir / "pagina"
    resultado = subprocess.run(
        [executavel, "-jpeg", "-r", "150", str(pdf_path), str(prefixo)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    paginas = sorted(output_dir.glob("pagina-*.jpg"))
    if resultado.returncode != 0 or not paginas:
        detalhe = (resultado.stderr or resultado.stdout or "erro desconhecido").strip()
        raise ErroGeracaoDocumento(f"Falha na conversão para JPEG: {detalhe}")
    return paginas


def hash_arquivo(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def registrar_arquivo(documento, path: Path, formato: str, pagina: int | None = None) -> None:
    mime_types = {
        FormatoArquivo.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        FormatoArquivo.PDF: "application/pdf",
        FormatoArquivo.JPEG: "image/jpeg",
    }
    db.session.add(
        ArquivoDocumento(
            documento=documento,
            formato=formato,
            caminho_arquivo=str(path.resolve()),
            nome_arquivo=path.name,
            pagina=pagina,
            mime_type=mime_types[formato],
            tamanho_bytes=path.stat().st_size,
            hash_sha256=hash_arquivo(path),
        )
    )


def remover_arquivos_anteriores(documento) -> None:
    diretorios: set[Path] = set()
    for arquivo in list(documento.arquivos):
        path = Path(arquivo.caminho_arquivo)
        diretorios.add(path.parent)
        db.session.delete(arquivo)
    db.session.flush()
    for diretorio in diretorios:
        if diretorio.exists():
            shutil.rmtree(diretorio, ignore_errors=True)


def gerar_documento(documento) -> None:
    documento.status = StatusDocumento.PROCESSANDO
    documento.erro_processamento = None
    db.session.commit()

    remover_arquivos_anteriores(documento)
    root = Path(current_app.config["DOCUMENTS_ROOT"])
    pasta = root / documento.emissao_id / documento.tipo_documento.lower()
    pasta.mkdir(parents=True, exist_ok=True)
    base = limpar_nome_arquivo(
        f"{documento.tipo_documento}_{documento.emissao.funcionario_snapshot.get('nome', '')}"
    )
    docx_path = pasta / f"{base}.docx"

    renderizar_docx(documento, docx_path)
    pdf_path = converter_para_pdf(docx_path, pasta)
    paginas = converter_pdf_para_jpeg(pdf_path, pasta)

    registrar_arquivo(documento, docx_path, FormatoArquivo.DOCX)
    registrar_arquivo(documento, pdf_path, FormatoArquivo.PDF)
    for numero, pagina_path in enumerate(paginas, start=1):
        registrar_arquivo(documento, pagina_path, FormatoArquivo.JPEG, numero)

    documento.status = StatusDocumento.CONCLUIDO
    documento.erro_processamento = None
    db.session.commit()


def gerar_emissao(emissao) -> None:
    emissao.status = StatusEmissao.PROCESSANDO
    db.session.commit()
    documento_atual = None
    try:
        for documento in emissao.documentos:
            documento_atual = documento
            gerar_documento(documento)
    except Exception as erro:
        db.session.rollback()
        emissao.status = StatusEmissao.ERRO
        if documento_atual is not None:
            documento_atual.status = StatusDocumento.ERRO
            documento_atual.erro_processamento = str(erro)[:4000]
        db.session.commit()
        raise
    emissao.status = StatusEmissao.CONCLUIDA
    emissao.concluido_em = datetime.now(timezone.utc)
    db.session.commit()
