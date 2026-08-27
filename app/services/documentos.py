from __future__ import annotations

import glob
import hashlib
import os
import shutil
import subprocess
import tempfile
import uuid
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


def _executavel_configurado(chave: str, nomes: tuple[str, ...]) -> str | None:
    """Resolve um executável informado no .env, aceitando arquivo ou pasta."""
    valor = str(current_app.config.get(chave, "") or "").strip().strip('"').strip("'")
    if not valor:
        return None

    caminho = Path(os.path.expandvars(valor)).expanduser()
    if caminho.is_file():
        return str(caminho)
    if caminho.is_dir():
        for nome in nomes:
            candidato = caminho / nome
            if candidato.is_file():
                return str(candidato)
    return None


def _primeiro_arquivo(candidatos: list[str | Path]) -> str | None:
    for candidato in candidatos:
        caminho = Path(candidato)
        if caminho.is_file():
            return str(caminho)
    return None


def localizar_libreoffice() -> str | None:
    nomes = ("soffice.exe", "libreoffice.exe", "soffice", "libreoffice")
    configurado = _executavel_configurado("LIBREOFFICE_PATH", nomes)
    if configurado:
        return configurado

    for comando in ("soffice", "libreoffice"):
        encontrado = shutil.which(comando)
        if encontrado:
            return encontrado

    candidatos: list[str | Path] = [
        "/usr/bin/soffice",
        "/usr/bin/libreoffice",
        "/usr/local/bin/soffice",
        "/snap/bin/libreoffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "C:/Program Files/LibreOffice/program/soffice.exe",
        "C:/Program Files (x86)/LibreOffice/program/soffice.exe",
    ]
    for variavel in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        raiz = os.getenv(variavel)
        if raiz:
            candidatos.append(Path(raiz) / "LibreOffice" / "program" / "soffice.exe")
    candidatos.extend(glob.glob("/opt/libreoffice*/program/soffice"))
    return _primeiro_arquivo(candidatos)


def localizar_pdftoppm() -> str | None:
    nomes = ("pdftoppm.exe", "pdftoppm")
    configurado = _executavel_configurado("PDFTOPPM_PATH", nomes)
    if configurado:
        return configurado

    encontrado = shutil.which("pdftoppm")
    if encontrado:
        return encontrado

    candidatos: list[str | Path] = [
        "/usr/bin/pdftoppm",
        "/usr/local/bin/pdftoppm",
        "/opt/homebrew/bin/pdftoppm",
        "/usr/local/opt/poppler/bin/pdftoppm",
        "C:/Program Files/poppler/Library/bin/pdftoppm.exe",
        "C:/Program Files/poppler/bin/pdftoppm.exe",
        "C:/poppler/Library/bin/pdftoppm.exe",
        "C:/poppler/bin/pdftoppm.exe",
    ]
    candidatos.extend(glob.glob("C:/Program Files/poppler*/Library/bin/pdftoppm.exe"))
    candidatos.extend(glob.glob("C:/Program Files/poppler*/bin/pdftoppm.exe"))
    return _primeiro_arquivo(candidatos)


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
    executavel = localizar_libreoffice()
    if not executavel:
        raise ErroGeracaoDocumento(
            "LibreOffice não encontrado. No Windows, informe no arquivo .env: "
            "LIBREOFFICE_PATH=C:/Program Files/LibreOffice/program/soffice.exe"
        )

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


def converter_lote_para_pdf(docx_paths: list[Path], output_dir: Path) -> dict[Path, Path]:
    """Converte vários DOCX em uma única inicialização do LibreOffice."""
    executavel = localizar_libreoffice()
    if not executavel:
        raise ErroGeracaoDocumento(
            "LibreOffice não encontrado. No Windows, informe no arquivo .env: "
            "LIBREOFFICE_PATH=C:/Program Files/LibreOffice/program/soffice.exe"
        )
    if not docx_paths:
        return {}

    output_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = Path(tempfile.mkdtemp(prefix="tst_lo_lote_"))
    try:
        comando = [
            executavel,
            "--headless",
            f"-env:UserInstallation={profile_dir.as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            *[str(path) for path in docx_paths],
        ]
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=max(180, len(docx_paths) * 60),
            check=False,
        )
        convertidos = {path: output_dir / f"{path.stem}.pdf" for path in docx_paths}
        ausentes = [pdf.name for pdf in convertidos.values() if not pdf.is_file()]
        if resultado.returncode != 0 or ausentes:
            detalhe = (resultado.stderr or resultado.stdout or "erro desconhecido").strip()
            if ausentes:
                detalhe = f"Arquivos não convertidos: {', '.join(ausentes)}. {detalhe}".strip()
            raise ErroGeracaoDocumento(f"Falha na conversão em lote para PDF: {detalhe}")
        for pdf_path in convertidos.values():
            remover_paginas_pdf_vazias(pdf_path)
        return convertidos
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
    executavel = localizar_pdftoppm()
    if not executavel:
        raise ErroGeracaoDocumento(
            "Poppler/pdftoppm não encontrado. Informe no arquivo .env o caminho "
            "completo, por exemplo: PDFTOPPM_PATH=C:/poppler/Library/bin/pdftoppm.exe"
        )
    prefixo = output_dir / str(uuid.uuid4())
    resultado = subprocess.run(
        [executavel, "-jpeg", "-r", "150", str(pdf_path), str(prefixo)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    paginas = sorted(output_dir.glob(f"{prefixo.name}-*.jpg"))
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
    pasta = (
        root
        / documento.emissao.empresa.tenant_id
        / documento.emissao_id
        / documento.id
    )
    pasta.mkdir(parents=True, exist_ok=True)
    base = str(uuid.uuid4())
    docx_path = pasta / f"{base}.docx"

    renderizar_docx(documento, docx_path)
    pdf_path = converter_para_pdf(docx_path, pasta)
    paginas = converter_pdf_para_jpeg(pdf_path, pasta)

    if os.name != "nt":
        pasta.chmod(0o750)
        for arquivo_gerado in (docx_path, pdf_path, *paginas):
            arquivo_gerado.chmod(0o640)

    registrar_arquivo(documento, docx_path, FormatoArquivo.DOCX)
    registrar_arquivo(documento, pdf_path, FormatoArquivo.PDF)
    for numero, pagina_path in enumerate(paginas, start=1):
        registrar_arquivo(documento, pagina_path, FormatoArquivo.JPEG, numero)

    documento.status = StatusDocumento.CONCLUIDO
    documento.erro_processamento = None
    db.session.commit()


def gerar_emissao(emissao) -> None:
    emissao.status = StatusEmissao.PROCESSANDO
    emissao.concluido_em = None
    for documento in emissao.documentos:
        documento.status = StatusDocumento.PENDENTE
        documento.erro_processamento = None
    db.session.commit()
    documento_atual = None
    try:
        with tempfile.TemporaryDirectory(prefix="tst_emissao_") as temporario:
            raiz_temporaria = Path(temporario)
            itens = []
            for documento in emissao.documentos:
                documento_atual = documento
                documento.status = StatusDocumento.PROCESSANDO
                db.session.commit()

                pasta_temporaria = raiz_temporaria / documento.id
                pasta_temporaria.mkdir(parents=True, exist_ok=True)
                base = str(uuid.uuid4())
                docx_path = pasta_temporaria / f"{base}.docx"
                renderizar_docx(documento, docx_path)
                itens.append((documento, pasta_temporaria, docx_path))

            pdfs = converter_lote_para_pdf(
                [docx_path for _, _, docx_path in itens],
                raiz_temporaria / "pdfs",
            )
            arquivos_prontos = []
            for documento, pasta_temporaria, docx_path in itens:
                documento_atual = documento
                pdf_origem = pdfs[docx_path]
                pdf_path = pasta_temporaria / pdf_origem.name
                shutil.move(str(pdf_origem), str(pdf_path))
                paginas = converter_pdf_para_jpeg(pdf_path, pasta_temporaria)
                arquivos_prontos.append(
                    (documento, pasta_temporaria, docx_path, pdf_path, paginas)
                )

            root = Path(current_app.config["DOCUMENTS_ROOT"])
            for documento, _, docx_temp, pdf_temp, paginas_temp in arquivos_prontos:
                documento_atual = documento
                remover_arquivos_anteriores(documento)
                pasta_final = (
                    root
                    / documento.emissao.empresa.tenant_id
                    / documento.emissao_id
                    / documento.id
                )
                pasta_final.mkdir(parents=True, exist_ok=True)
                arquivos_finais = []
                for origem in (docx_temp, pdf_temp, *paginas_temp):
                    destino = pasta_final / origem.name
                    shutil.move(str(origem), str(destino))
                    arquivos_finais.append(destino)

                docx_final, pdf_final, *paginas_finais = arquivos_finais
                if os.name != "nt":
                    pasta_final.chmod(0o750)
                    for arquivo_gerado in arquivos_finais:
                        arquivo_gerado.chmod(0o640)

                registrar_arquivo(documento, docx_final, FormatoArquivo.DOCX)
                registrar_arquivo(documento, pdf_final, FormatoArquivo.PDF)
                for numero, pagina_path in enumerate(paginas_finais, start=1):
                    registrar_arquivo(
                        documento, pagina_path, FormatoArquivo.JPEG, numero
                    )
                documento.status = StatusDocumento.CONCLUIDO
                documento.erro_processamento = None
                db.session.commit()
    except Exception as erro:
        db.session.rollback()
        emissao.status = StatusEmissao.ERRO
        for documento in emissao.documentos:
            if documento.status != StatusDocumento.CONCLUIDO:
                documento.status = StatusDocumento.ERRO
                documento.erro_processamento = str(erro)[:4000]
        db.session.commit()
        raise
    emissao.status = StatusEmissao.CONCLUIDA
    emissao.concluido_em = datetime.now(timezone.utc)
    db.session.commit()
