from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


def limpar_texto(valor):
    return valor.strip() if isinstance(valor, str) else valor


class EmissaoForm(FlaskForm):
    empresa_id = SelectField(
        "Empresa",
        validators=[DataRequired(message="Selecione a empresa.")],
    )
    funcionario_id = SelectField(
        "Funcionário",
        validators=[DataRequired(message="Selecione o funcionário.")],
    )
    funcao = StringField(
        "Função utilizada nos documentos",
        validators=[
            DataRequired(message="Informe a função."),
            Length(max=150),
        ],
        filters=[limpar_texto],
    )
    data_admissao = DateField(
        "Data de admissão",
        validators=[DataRequired(message="Informe a data de admissão.")],
        format="%Y-%m-%d",
    )
    data_inicial = DateField(
        "Primeira data dos documentos",
        validators=[DataRequired(message="Informe a data inicial.")],
        format="%Y-%m-%d",
    )
    observacoes = TextAreaField(
        "Observações internas",
        validators=[Optional(), Length(max=2000)],
        filters=[limpar_texto],
    )

    setor = StringField("Setor", validators=[Optional(), Length(max=120)], filters=[limpar_texto])
    cbo = StringField("CBO", validators=[Optional(), Length(max=30)], filters=[limpar_texto])
    descricao_funcao = TextAreaField("Descrição da função", validators=[Optional(), Length(max=4000)], filters=[limpar_texto])
    risco_fisico = TextAreaField("Riscos físicos", validators=[Optional(), Length(max=2000)], filters=[limpar_texto])
    risco_quimico = TextAreaField("Riscos químicos", validators=[Optional(), Length(max=2000)], filters=[limpar_texto])
    risco_biologico = TextAreaField("Riscos biológicos", validators=[Optional(), Length(max=2000)], filters=[limpar_texto])
    risco_ergonomico = TextAreaField("Riscos ergonômicos", validators=[Optional(), Length(max=2000)], filters=[limpar_texto])
    risco_acidentes = TextAreaField("Riscos de acidentes", validators=[Optional(), Length(max=2000)], filters=[limpar_texto])
    epis_atividade = TextAreaField("EPIs de uso na atividade", validators=[Optional(), Length(max=4000)], filters=[limpar_texto])
    recomendacoes = TextAreaField("Recomendações", validators=[Optional(), Length(max=5000)], filters=[limpar_texto])
    procedimentos_acidente = TextAreaField("Procedimentos em caso de acidentes", validators=[Optional(), Length(max=5000)], filters=[limpar_texto])
    responsavel_nome = StringField("Nome do responsável", validators=[Optional(), Length(max=150)], filters=[limpar_texto])
    responsavel_cargo = StringField("Cargo do responsável", validators=[Optional(), Length(max=180)], filters=[limpar_texto])
    responsavel_registro = StringField("Registro profissional", validators=[Optional(), Length(max=80)], filters=[limpar_texto])
    submit = SubmitField("Salvar Emissão")


class AcaoEmissaoForm(FlaskForm):
    submit = SubmitField("Confirmar")
