from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from app.extensions import db
from app.models import Funcionario, cpf_valido, somente_digitos


def limpar_texto(valor):
    return valor.strip() if isinstance(valor, str) else valor


class FuncionarioForm(FlaskForm):
    empresa_id = SelectField(
        "Empresa",
        validators=[DataRequired(message="Selecione a empresa.")],
    )
    nome = StringField(
        "Nome Completo",
        validators=[
            DataRequired(message="Informe o nome do funcionário."),
            Length(max=150, message="Use no máximo 150 caracteres."),
        ],
        filters=[limpar_texto],
    )
    cpf = StringField(
        "CPF",
        validators=[
            DataRequired(message="Informe o CPF."),
            Length(min=11, max=14, message="Informe um CPF válido."),
        ],
        filters=[limpar_texto],
    )
    funcao = StringField(
        "Função Padrão",
        validators=[
            Optional(),
            Length(max=150, message="Use no máximo 150 caracteres."),
        ],
        filters=[limpar_texto],
    )
    submit = SubmitField("Salvar Funcionário")

    def __init__(self, *args, funcionario_original=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.funcionario_original = funcionario_original

    def validate_cpf(self, campo):
        cpf = somente_digitos(campo.data)
        if not cpf_valido(cpf):
            raise ValidationError("O CPF informado é inválido.")

        consulta = select(Funcionario.id).where(
            Funcionario.empresa_id == self.empresa_id.data,
            Funcionario.cpf == cpf,
        )
        if self.funcionario_original is not None:
            consulta = consulta.where(
                Funcionario.id != self.funcionario_original.id
            )
        if db.session.scalar(consulta) is not None:
            raise ValidationError(
                "Este CPF já está cadastrado para a empresa selecionada."
            )


class StatusFuncionarioForm(FlaskForm):
    submit = SubmitField("Alterar status")
