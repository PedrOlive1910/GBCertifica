from pathlib import Path
from zipfile import ZipFile

from flask import abort


def test_login_apresenta_identidade_gbcertifica(client):
    resposta = client.get("/login")
    html = resposta.get_data(as_text=True)

    assert resposta.status_code == 200
    assert "GBcertifica" in html
    assert "Versão 1.2.0" in html
    assert "Acesse sua conta" in html
    assert "Sistema TST" not in html
    assert "Acesso seguro" not in html
    assert "Entrar no sistema" not in html


def test_pagina_404_tem_apresentacao_orientativa(client):
    resposta = client.get("/endereco-que-nao-existe")
    html = resposta.get_data(as_text=True)

    assert resposta.status_code == 404
    assert 'class="error-illustration"' in html
    assert "Página não encontrada" in html
    assert "Voltar à visão geral" in html


def test_paginas_403_e_500_possuem_identidade_visual(app):
    @app.get("/__teste-403")
    def teste_403():
        abort(403)

    @app.get("/__teste-500")
    def teste_500():
        raise RuntimeError("Falha controlada para testar a página 500.")

    app.config["PROPAGATE_EXCEPTIONS"] = False
    cliente = app.test_client()

    resposta_403 = cliente.get("/__teste-403")
    resposta_500 = cliente.get("/__teste-500")

    assert resposta_403.status_code == 403
    assert "error-illustration-warning" in resposta_403.get_data(as_text=True)
    assert resposta_500.status_code == 500
    assert "error-illustration-danger" in resposta_500.get_data(as_text=True)


def test_templates_nao_possuem_realces_de_edicao(app):
    raiz = Path(app.root_path) / "document_templates"
    for caminho in raiz.glob("*.docx"):
        with ZipFile(caminho) as arquivo:
            xml = b"".join(
                arquivo.read(nome)
                for nome in arquivo.namelist()
                if nome.startswith("word/") and nome.endswith(".xml")
            )
        assert b"w:highlight" not in xml, caminho.name


def test_nr06_tem_assinaturas_reorganizadas(app):
    caminho = Path(app.root_path) / "document_templates" / "nr06.docx"
    with ZipFile(caminho) as arquivo:
        xml = arquivo.read("word/document.xml").decode("utf-8")

    assert "RESPONSÁVEL DA EMPRESA" in xml
    assert "PARTICIPANTE" in xml
    assert "ASS.</w:t>" not in xml
