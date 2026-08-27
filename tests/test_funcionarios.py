from sqlalchemy import select

from app.extensions import db
from app.models import Funcionario
from tests.helpers import criar_empresa_funcionario


def test_listagem_de_funcionarios_abre(client):
    resposta = client.get("/funcionarios/")
    assert resposta.status_code == 200
    assert "Funcionários" in resposta.get_data(as_text=True)


def test_cadastra_funcionario_e_normaliza_cpf(app, client):
    with app.app_context():
        empresa, _ = criar_empresa_funcionario()
        empresa_id = empresa.id
        db.session.delete(db.session.scalar(select(Funcionario)))
        db.session.commit()

    resposta = client.post(
        "/funcionarios/novo",
        data={
            "empresa_id": empresa_id,
            "nome": "Maria de Souza",
            "cpf": "529.982.247-25",
            "funcao": "Armadora",
        },
        follow_redirects=True,
    )
    assert "Funcionário cadastrado com sucesso." in resposta.get_data(as_text=True)
    with app.app_context():
        funcionario = db.session.scalar(select(Funcionario))
        assert funcionario.cpf == "52998224725"
        assert funcionario.funcao == "Armadora"


def test_rejeita_cpf_invalido(app, client):
    with app.app_context():
        empresa, _ = criar_empresa_funcionario()
        empresa_id = empresa.id
    resposta = client.post(
        "/funcionarios/novo",
        data={"empresa_id": empresa_id, "nome": "Teste", "cpf": "111.111.111-11"},
    )
    assert "O CPF informado é inválido." in resposta.get_data(as_text=True)
