from flask import current_app

from app.extensions import db
from app.models import Empresa, Funcionario


def criar_empresa_funcionario():
    empresa = Empresa(
        tenant_id=current_app.config["TEST_TENANT_ID"],
        razao_social="Construtora Verde Ltda.",
        cnpj="11222333000181",
        cidade="Belo Horizonte - MG",
        endereco_completo="Rua das Obras, 100, Centro, Belo Horizonte - MG",
    )
    funcionario = Funcionario(
        empresa=empresa,
        nome="João da Silva",
        cpf="52998224725",
        funcao="Carpinteiro",
    )
    db.session.add_all([empresa, funcionario])
    db.session.commit()
    return empresa, funcionario
