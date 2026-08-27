from flask_wtf import FlaskForm
from wtforms import HiddenField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length

from app.validators import validar_email, validar_senha_forte


class LoginForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), validar_email, Length(max=180)])
    senha = PasswordField("Senha", validators=[DataRequired(), Length(max=128)])
    proximo = HiddenField()
    submit = SubmitField("Entrar no sistema")


class SolicitarRedefinicaoForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), validar_email, Length(max=180)])
    submit = SubmitField("Enviar link de redefinição")


class RedefinirSenhaForm(FlaskForm):
    senha = PasswordField(
        "Nova senha",
        validators=[DataRequired(), Length(min=8, max=128), validar_senha_forte],
    )
    confirmar_senha = PasswordField(
        "Confirmar nova senha",
        validators=[
            DataRequired(),
            EqualTo("senha", message="As senhas não conferem."),
        ],
    )
    submit = SubmitField("Definir nova senha")
