"""Aplica os ajustes visuais dos modelos de documentos da versão 1.2.0.

Remove realces de edição sem alterar sombreamentos estruturais de tabelas e
reorganiza as caixas de assinatura do certificado NR-06. O script é idempotente
e atualiza tanto o DrawingML moderno quanto o fallback VML usado pelo Word.
"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_ROOT = PROJECT_ROOT / "app" / "document_templates"
TEMPLATES = (
    "ficha_epi.docx",
    "ordem_servico.docx",
    "nr06.docx",
    "nr12.docx",
    "nr18.docx",
    "nr35.docx",
)

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "v": "urn:schemas-microsoft-com:vml",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
}
W = f"{{{NS['w']}}}"


def _paragrafo(texto: str, *, tamanho: int, negrito: bool = False):
    paragrafo = etree.Element(f"{W}p")
    propriedades = etree.SubElement(paragrafo, f"{W}pPr")
    alinhamento = etree.SubElement(propriedades, f"{W}jc")
    alinhamento.set(f"{W}val", "center")
    espacamento = etree.SubElement(propriedades, f"{W}spacing")
    espacamento.set(f"{W}before", "0")
    espacamento.set(f"{W}after", "0")
    espacamento.set(f"{W}line", "200")
    espacamento.set(f"{W}lineRule", "exact")

    trecho = etree.SubElement(paragrafo, f"{W}r")
    propriedades_trecho = etree.SubElement(trecho, f"{W}rPr")
    fontes = etree.SubElement(propriedades_trecho, f"{W}rFonts")
    fontes.set(f"{W}ascii", "Arial")
    fontes.set(f"{W}hAnsi", "Arial")
    if negrito:
        etree.SubElement(propriedades_trecho, f"{W}b")
    tamanho_tag = etree.SubElement(propriedades_trecho, f"{W}sz")
    tamanho_tag.set(f"{W}val", str(tamanho))
    tamanho_cs = etree.SubElement(propriedades_trecho, f"{W}szCs")
    tamanho_cs.set(f"{W}val", str(tamanho))
    texto_tag = etree.SubElement(trecho, f"{W}t")
    texto_tag.text = texto
    return paragrafo


def _substituir_conteudo(shape, linhas: tuple[tuple[str, int, bool], ...]):
    for conteudo in shape.xpath(".//w:txbxContent", namespaces=NS):
        for filho in list(conteudo):
            conteudo.remove(filho)
        for texto, tamanho, negrito in linhas:
            conteudo.append(_paragrafo(texto, tamanho=tamanho, negrito=negrito))


def _ajustar_transformacao(shape, *, x: int, y: int, largura: int, altura: int):
    transformacao = shape.find(".//a:xfrm", namespaces=NS)
    if transformacao is None:
        return
    origem = transformacao.find("a:off", namespaces=NS)
    dimensoes = transformacao.find("a:ext", namespaces=NS)
    if origem is not None:
        origem.set("x", str(x))
        origem.set("y", str(y))
    if dimensoes is not None:
        dimensoes.set("cx", str(largura))
        dimensoes.set("cy", str(altura))


def _ajustar_estilo_vml(shape, **valores: int):
    partes = [parte for parte in (shape.get("style") or "").split(";") if parte]
    atualizados: list[str] = []
    aplicados: set[str] = set()
    for parte in partes:
        chave, separador, _ = parte.partition(":")
        if separador and chave in valores:
            atualizados.append(f"{chave}:{valores[chave]}")
            aplicados.add(chave)
        else:
            atualizados.append(parte)
    for chave, valor in valores.items():
        if chave not in aplicados:
            atualizados.append(f"{chave}:{valor}")
    shape.set("style", ";".join(atualizados))


def _ajustar_caixa(
    raiz,
    nome: str,
    linhas: tuple[tuple[str, int, bool], ...],
    *,
    x: int,
    y: int,
    largura: int,
    altura: int,
):
    modernas = raiz.xpath(
        f'//wps:wsp[wps:cNvPr[@name="{nome}"]]', namespaces=NS
    )
    for shape in modernas:
        _substituir_conteudo(shape, linhas)
        _ajustar_transformacao(
            shape, x=x, y=y, largura=largura, altura=altura
        )

    legadas = raiz.xpath(f'//v:shape[@id="{nome}"]', namespaces=NS)
    for shape in legadas:
        _substituir_conteudo(shape, linhas)
        _ajustar_estilo_vml(
            shape,
            left=round(x / 100),
            top=round(y / 100),
            width=round(largura / 100),
            height=round(altura / 100),
        )


def _ajustar_assinaturas_nr06(raiz):
    _ajustar_caixa(
        raiz,
        "Textbox 10",
        (("PARTICIPANTE", 16, True), ("{{ nome_funcionario }}", 18, True)),
        x=3190875,
        y=5998000,
        largura=3142989,
        altura=470000,
    )
    _ajustar_caixa(
        raiz,
        "Textbox 11",
        (("RESPONSÁVEL DA EMPRESA", 16, True),),
        x=6486257,
        y=5998000,
        largura=2429143,
        altura=220000,
    )
    _ajustar_caixa(
        raiz,
        "Textbox 12",
        (("{{ razao_social }}", 15, True), ("CNPJ: {{ cnpj }}", 15, False)),
        x=6486257,
        y=6220000,
        largura=2429143,
        altura=500000,
    )


def ajustar_template(caminho: Path) -> int:
    temporario = caminho.with_suffix(".v120.tmp.docx")
    removidos = 0
    with ZipFile(caminho, "r") as origem, ZipFile(
        temporario, "w", compression=ZIP_DEFLATED
    ) as destino:
        for info in origem.infolist():
            dados = origem.read(info.filename)
            if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                raiz = etree.fromstring(dados)
                realces = raiz.xpath("//w:highlight", namespaces=NS)
                removidos += len(realces)
                for realce in realces:
                    realce.getparent().remove(realce)
                if caminho.name == "nr06.docx" and info.filename == "word/document.xml":
                    _ajustar_assinaturas_nr06(raiz)
                dados = etree.tostring(
                    raiz,
                    encoding="UTF-8",
                    xml_declaration=True,
                    standalone=True,
                )
            destino.writestr(info, dados)
    temporario.replace(caminho)
    return removidos


def main():
    for nome in TEMPLATES:
        caminho = TEMPLATES_ROOT / nome
        if not caminho.is_file():
            raise FileNotFoundError(f"Modelo não encontrado: {caminho}")
        removidos = ajustar_template(caminho)
        print(f"{nome}: {removidos} realce(s) removido(s).")


if __name__ == "__main__":
    main()
