from pathlib import Path
from zipfile import ZipFile

from flask import abort
from sqlalchemy import event

from app.extensions import db
from app.models import LogAuditoria, NivelAcesso, Tenant, Usuario


def test_login_apresenta_identidade_gbcertifica(client):
    resposta = client.get("/login")
    html = resposta.get_data(as_text=True)

    assert resposta.status_code == 200
    assert "GBcertifica" in html
    assert "Versão 1.2.3" in html
    assert "app.css?v=1.2.3" in html
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


def test_navegacao_nao_carrega_historico_inteiro_do_usuario(app):
    with app.app_context():
        tenant = db.session.get(Tenant, app.config["TEST_TENANT_ID"])
        usuario = Usuario(
            tenant=tenant,
            nome="Usuário de desempenho",
            email="desempenho@teste.com.br",
            nivel_acesso=NivelAcesso.ADMINISTRADOR,
            ativo=True,
        )
        usuario.definir_senha("SenhaForte123")
        db.session.add(usuario)
        db.session.flush()
        db.session.add_all(
            [
                LogAuditoria(
                    tenant_id=tenant.id,
                    usuario_id=usuario.id,
                    usuario_nome=usuario.nome,
                    acao="ACESSOU",
                    modulo="Teste",
                    descricao=f"Registro {indice}",
                )
                for indice in range(100)
            ]
        )
        db.session.commit()
        usuario_id = usuario.id
        db.session.remove()
        engine = db.engine

    app.config["LOGIN_DISABLED"] = False
    consultas = []

    def contar_consulta(_conn, _cursor, statement, _parameters, _context, _many):
        consultas.append(statement)

    event.listen(engine, "before_cursor_execute", contar_consulta)
    try:
        cliente = app.test_client()
        with cliente.session_transaction() as sessao:
            sessao["_user_id"] = usuario_id
        resposta = cliente.get("/empresas/")
    finally:
        event.remove(engine, "before_cursor_execute", contar_consulta)

    assert resposta.status_code == 200
    assert len(consultas) <= 6


def test_relatorio_usa_layout_responsivo_corrigido(client):
    resposta = client.get("/relatorios/")
    html = resposta.get_data(as_text=True)

    assert resposta.status_code == 200
    assert "report-filter-actions" in html
    assert "report-results-heading" in html
    assert "report-results-panel" in html
