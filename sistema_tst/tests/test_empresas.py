from sqlalchemy import select

from app.extensions import db
from app.models import Empresa


DADOS_EMPRESA = {
    "razao_social": "Empresa de Teste Ltda.",
    "cnpj": "11.222.333/0001-81",
    "cidade": "Belo Horizonte",
    "endereco_completo": "Rua de Teste, 100, Centro",
}


def cadastrar_empresa(client, **alteracoes):
    dados = {**DADOS_EMPRESA, **alteracoes}
    return client.post("/empresas/nova", data=dados, follow_redirects=True)


def test_listagem_de_empresas_abre(client):
    resposta = client.get("/empresas/")
    assert resposta.status_code == 200
    assert "Empresas" in resposta.get_data(as_text=True)


def test_cadastra_empresa_e_normaliza_cnpj(app, client):
    resposta = cadastrar_empresa(client)
    assert resposta.status_code == 200
    assert "Empresa cadastrada com sucesso." in resposta.get_data(as_text=True)

    with app.app_context():
        empresa = db.session.scalar(select(Empresa))
        assert empresa.razao_social == DADOS_EMPRESA["razao_social"]
        assert empresa.cnpj == "11222333000181"
        assert empresa.ativo is True


def test_impede_cnpj_duplicado(client):
    cadastrar_empresa(client)
    resposta = cadastrar_empresa(client, razao_social="Outra Empresa Ltda.")

    assert resposta.status_code == 200
    assert "Já existe uma empresa cadastrada" in resposta.get_data(as_text=True)


def test_rejeita_cnpj_invalido(client):
    resposta = cadastrar_empresa(client, cnpj="11.111.111/1111-11")
    assert "O CNPJ informado é inválido." in resposta.get_data(as_text=True)


def test_edita_empresa(app, client):
    cadastrar_empresa(client)

    with app.app_context():
        empresa_id = db.session.scalar(select(Empresa.id))

    resposta = client.post(
        f"/empresas/{empresa_id}/editar",
        data={**DADOS_EMPRESA, "cidade": "Contagem"},
        follow_redirects=True,
    )
    assert "Empresa atualizada com sucesso." in resposta.get_data(as_text=True)

    with app.app_context():
        empresa = db.session.get(Empresa, empresa_id)
        assert empresa.cidade == "Contagem"


def test_desativa_e_reativa_empresa(app, client):
    cadastrar_empresa(client)

    with app.app_context():
        empresa_id = db.session.scalar(select(Empresa.id))

    resposta = client.post(
        f"/empresas/{empresa_id}/alterar-status",
        follow_redirects=True,
    )
    assert "Empresa desativada com sucesso." in resposta.get_data(as_text=True)

    resposta = client.post(
        f"/empresas/{empresa_id}/alterar-status",
        follow_redirects=True,
    )
    assert "Empresa ativada com sucesso." in resposta.get_data(as_text=True)
