from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import EqualTo, Length, Optional

from app.models import NivelAcesso
from app.validators import validar_email, validar_senha_forte


class UsuarioForm(FlaskForm):
    nome = StringField("Nome completo", validators=[Length(min=3, max=150)])
    email = StringField("E-mail", validators=[validar_email, Length(max=180)])
    nivel_acesso = SelectField(
        "Nível de acesso",
        choices=[(item, NivelAcesso.ROTULOS[item]) for item in NivelAcesso.TODOS],
    )
    ativo = BooleanField("Usuário ativo", default=True)
    senha = PasswordField(
        "Senha",
        validators=[Optional(), Length(min=8, max=128), validar_senha_forte],
    )
    confirmar_senha = PasswordField(
        "Confirmar senha",
        validators=[Optional(), EqualTo("senha", message="As senhas não conferem.")],
    )
    submit = SubmitField("Salvar usuário")


class StatusUsuarioForm(FlaskForm):
    submit = SubmitField("Alterar status")


class RedefinirSenhaUsuarioForm(FlaskForm):
    senha = PasswordField(
        "Senha temporária",
        validators=[Length(min=8, max=128), validar_senha_forte],
    )
    confirmar_senha = PasswordField(
        "Confirmar senha temporária",
        validators=[EqualTo("senha", message="As senhas não conferem.")],
    )
    submit = SubmitField("Redefinir senha")
