from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError

from app.extensions import db
from app.models import Empresa, cnpj_valido, somente_digitos
from app.services.tenant import tenant_atual_id


def remover_espacos(valor):
    return valor.strip() if isinstance(valor, str) else valor


class EmpresaForm(FlaskForm):
    razao_social = StringField(
        "Razão Social",
        validators=[
            DataRequired(message="Informe a razão social."),
            Length(max=150, message="Use no máximo 150 caracteres."),
        ],
        filters=[remover_espacos],
    )
    cnpj = StringField(
        "CNPJ",
        validators=[
            DataRequired(message="Informe o CNPJ."),
            Length(min=14, max=18, message="Informe um CNPJ válido."),
        ],
        filters=[remover_espacos],
    )
    cidade = StringField(
        "Cidade",
        validators=[
            DataRequired(message="Informe a cidade."),
            Length(max=100, message="Use no máximo 100 caracteres."),
        ],
        filters=[remover_espacos],
    )
    endereco_completo = StringField(
        "Endereço Completo",
        validators=[
            DataRequired(message="Informe o endereço completo."),
            Length(max=255, message="Use no máximo 255 caracteres."),
        ],
        filters=[remover_espacos],
    )
    submit = SubmitField("Salvar Empresa")

    def __init__(self, *args, empresa_original=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_original = empresa_original

    def validate_cnpj(self, campo):
        cnpj = somente_digitos(campo.data)
        if not cnpj_valido(cnpj):
            raise ValidationError("O CNPJ informado é inválido.")

        consulta = select(Empresa.id).where(
            Empresa.tenant_id == tenant_atual_id(),
            Empresa.cnpj == cnpj,
        )
        if self.empresa_original is not None:
            consulta = consulta.where(Empresa.id != self.empresa_original.id)

        if db.session.scalar(consulta) is not None:
            raise ValidationError("Já existe uma empresa cadastrada com este CNPJ.")


class StatusEmpresaForm(FlaskForm):
    submit = SubmitField("Alterar status")
