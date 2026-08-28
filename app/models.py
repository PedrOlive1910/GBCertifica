import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import validates
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def gerar_uuid():
    """Retorna um UUID no formato texto, compatível com SQLite e PostgreSQL."""
    return str(uuid.uuid4())


def agora_utc():
    """Retorna a data e a hora atuais com informação de fuso horário."""
    return datetime.now(timezone.utc)


def somente_digitos(valor):
    """Remove pontos, barras, traços e outros caracteres de CPF/CNPJ."""
    return re.sub(r"\D", "", valor or "")


def cnpj_valido(valor):
    """Valida o tamanho e os dois dígitos verificadores do CNPJ."""
    cnpj = somente_digitos(valor)
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False

    def calcular_digito(base, pesos):
        soma = sum(int(numero) * peso for numero, peso in zip(base, pesos))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    primeiro = calcular_digito(cnpj[:12], (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    segundo = calcular_digito(
        cnpj[:12] + primeiro,
        (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2),
    )
    return cnpj[-2:] == primeiro + segundo


def cpf_valido(valor):
    """Valida o tamanho e os dois dígitos verificadores do CPF."""
    cpf = somente_digitos(valor)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False

    primeiro = sum(int(cpf[index]) * (10 - index) for index in range(9))
    primeiro = (primeiro * 10) % 11
    primeiro = 0 if primeiro == 10 else primeiro

    segundo = sum(int(cpf[index]) * (11 - index) for index in range(10))
    segundo = (segundo * 10) % 11
    segundo = 0 if segundo == 10 else segundo
    return cpf[-2:] == f"{primeiro}{segundo}"


def formatar_cnpj(valor):
    """Formata um CNPJ armazenado somente com números."""
    cnpj = somente_digitos(valor)
    if len(cnpj) != 14:
        return valor or ""
    return (
        f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/"
        f"{cnpj[8:12]}-{cnpj[12:]}"
    )


def formatar_cpf(valor):
    """Formata um CPF armazenado somente com números."""
    cpf = somente_digitos(valor)
    if len(cpf) != 11:
        return valor or ""
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


class TipoDocumento:
    FICHA_EPI = "FICHA_EPI"
    ORDEM_SERVICO = "ORDEM_SERVICO"
    NR_06 = "NR_06"
    NR_12 = "NR_12"
    NR_18 = "NR_18"
    NR_35 = "NR_35"

    TODOS = (
        FICHA_EPI,
        ORDEM_SERVICO,
        NR_06,
        NR_12,
        NR_18,
        NR_35,
    )

    ROTULOS = {
        FICHA_EPI: "Ficha de Controle de EPI",
        ORDEM_SERVICO: "Ordem de Serviço",
        NR_06: "Certificado NR-06",
        NR_12: "Certificado NR-12",
        NR_18: "Certificado NR-18",
        NR_35: "Certificado NR-35",
    }


class StatusEmissao:
    RASCUNHO = "RASCUNHO"
    PROCESSANDO = "PROCESSANDO"
    CONCLUIDA = "CONCLUIDA"
    ERRO = "ERRO"
    CANCELADA = "CANCELADA"

    TODOS = (RASCUNHO, PROCESSANDO, CONCLUIDA, ERRO, CANCELADA)

    ROTULOS = {
        RASCUNHO: "Rascunho",
        PROCESSANDO: "Processando",
        CONCLUIDA: "Concluída",
        ERRO: "Erro",
        CANCELADA: "Cancelada",
    }


class StatusDocumento:
    PENDENTE = "PENDENTE"
    PROCESSANDO = "PROCESSANDO"
    CONCLUIDO = "CONCLUIDO"
    ERRO = "ERRO"

    TODOS = (PENDENTE, PROCESSANDO, CONCLUIDO, ERRO)


class FormatoArquivo:
    DOCX = "DOCX"
    PDF = "PDF"
    JPEG = "JPEG"

    TODOS = (DOCX, PDF, JPEG)


class NivelAcesso:
    ADMINISTRADOR = "ADMINISTRADOR"
    OPERADOR = "OPERADOR"
    CONSULTA = "CONSULTA"

    TODOS = (ADMINISTRADOR, OPERADOR, CONSULTA)
    ROTULOS = {
        ADMINISTRADOR: "Administrador",
        OPERADOR: "Operador",
        CONSULTA: "Consulta",
    }


class Tenant(db.Model):
    """Conta cliente isolada dentro da aplicação SaaS."""

    __tablename__ = "tenants"

    id = db.Column(db.String(36), primary_key=True, default=gerar_uuid)
    nome = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(80), nullable=False, unique=True, index=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, default=agora_utc
    )
    atualizado_em = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=agora_utc,
        onupdate=agora_utc,
    )

    # Coleções potencialmente grandes são carregadas apenas quando solicitadas.
    # Evita trazer toda a conta, empresas e auditoria em cada abertura de tela.
    usuarios = db.relationship("Usuario", back_populates="tenant", lazy="select")
    empresas = db.relationship("Empresa", back_populates="tenant", lazy="select")
    logs = db.relationship("LogAuditoria", back_populates="tenant", lazy="select")

    def __repr__(self):
        return f"<Tenant {self.nome}>"


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.String(36), primary_key=True, default=gerar_uuid)
    tenant_id = db.Column(
        db.String(36),
        db.ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    nome = db.Column(db.String(150), nullable=False, index=True)
    email = db.Column(db.String(180), nullable=False, unique=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    nivel_acesso = db.Column(
        db.String(20), nullable=False, default=NivelAcesso.CONSULTA, index=True
    )
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    deve_trocar_senha = db.Column(db.Boolean, nullable=False, default=False, index=True)
    tentativas_falhas = db.Column(db.Integer, nullable=False, default=0)
    bloqueado_ate = db.Column(db.DateTime(timezone=True), nullable=True)
    ultimo_login_em = db.Column(db.DateTime(timezone=True), nullable=True)
    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, default=agora_utc
    )
    atualizado_em = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=agora_utc,
        onupdate=agora_utc,
    )

    tenant = db.relationship("Tenant", back_populates="usuarios", lazy="joined")
    logs = db.relationship(
        "LogAuditoria", back_populates="usuario", lazy="select", passive_deletes=True
    )
    tokens_redefinicao = db.relationship(
        "TokenRedefinicaoSenha",
        back_populates="usuario",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def is_active(self):
        return bool(self.ativo)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id

    @property
    def eh_administrador(self):
        return self.nivel_acesso == NivelAcesso.ADMINISTRADOR

    @property
    def pode_editar(self):
        return self.nivel_acesso in {
            NivelAcesso.ADMINISTRADOR,
            NivelAcesso.OPERADOR,
        }

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha, method="scrypt")

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    @validates("email")
    def normalizar_email(self, _, valor):
        return (valor or "").strip().lower()

    @validates("nivel_acesso")
    def validar_nivel_acesso(self, _, valor):
        if valor not in NivelAcesso.TODOS:
            raise ValueError(f"Nível de acesso inválido: {valor}")
        return valor

    def __repr__(self):
        return f"<Usuario {self.email}>"


class LogAuditoria(db.Model):
    __tablename__ = "logs_auditoria"
    __table_args__ = (
        db.Index("ix_log_auditoria_data_modulo", "criado_em", "modulo"),
        db.Index("ix_log_auditoria_usuario_data", "usuario_id", "criado_em"),
    )

    id = db.Column(db.String(36), primary_key=True, default=gerar_uuid)
    tenant_id = db.Column(
        db.String(36),
        db.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    usuario_id = db.Column(
        db.String(36),
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    usuario_nome = db.Column(db.String(180), nullable=False, default="Sistema")
    acao = db.Column(db.String(40), nullable=False, index=True)
    modulo = db.Column(db.String(60), nullable=False, index=True)
    descricao = db.Column(db.String(500), nullable=False)
    entidade_tipo = db.Column(db.String(80), nullable=True, index=True)
    entidade_id = db.Column(db.String(36), nullable=True, index=True)
    detalhes = db.Column(db.JSON, nullable=False, default=dict)
    metodo = db.Column(db.String(10), nullable=True)
    rota = db.Column(db.String(255), nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, default=agora_utc, index=True
    )

    usuario = db.relationship("Usuario", back_populates="logs", lazy="joined")
    tenant = db.relationship("Tenant", back_populates="logs", lazy="joined")

    def __repr__(self):
        return f"<LogAuditoria {self.acao} - {self.modulo}>"


class TokenRedefinicaoSenha(db.Model):
    __tablename__ = "tokens_redefinicao_senha"

    id = db.Column(db.String(36), primary_key=True, default=gerar_uuid)
    usuario_id = db.Column(
        db.String(36),
        db.ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expira_em = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    usado_em = db.Column(db.DateTime(timezone=True), nullable=True)
    solicitado_ip = db.Column(db.String(64), nullable=True)
    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, default=agora_utc
    )

    usuario = db.relationship("Usuario", back_populates="tokens_redefinicao")


class Empresa(db.Model):
    __tablename__ = "empresas"
    __table_args__ = (
        db.UniqueConstraint("tenant_id", "cnpj", name="uq_empresa_tenant_cnpj"),
    )

    id = db.Column(db.String(36), primary_key=True, default=gerar_uuid)
    tenant_id = db.Column(
        db.String(36),
        db.ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    razao_social = db.Column(db.String(150), nullable=False, index=True)
    cnpj = db.Column(db.String(14), nullable=False, index=True)
    cidade = db.Column(db.String(100), nullable=False)
    endereco_completo = db.Column(db.String(255), nullable=False)

    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, default=agora_utc
    )
    atualizado_em = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=agora_utc,
        onupdate=agora_utc,
    )

    funcionarios = db.relationship(
        "Funcionario",
        back_populates="empresa",
        lazy="select",
        passive_deletes=True,
    )
    tenant = db.relationship("Tenant", back_populates="empresas", lazy="joined")
    emissoes = db.relationship(
        "Emissao",
        back_populates="empresa",
        lazy="select",
        passive_deletes=True,
    )

    @validates("cnpj")
    def validar_cnpj(self, _, valor):
        cnpj = somente_digitos(valor)
        if not cnpj_valido(cnpj):
            raise ValueError("O CNPJ informado é inválido.")
        return cnpj

    def __repr__(self):
        return f"<Empresa {self.razao_social}>"


class Funcionario(db.Model):
    __tablename__ = "funcionarios"
    __table_args__ = (
        db.UniqueConstraint(
            "empresa_id", "cpf", name="uq_funcionario_empresa_cpf"
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=gerar_uuid)
    nome = db.Column(db.String(150), nullable=False, index=True)
    cpf = db.Column(db.String(11), nullable=False, index=True)
    funcao = db.Column(db.String(150), nullable=True)

    empresa_id = db.Column(
        db.String(36),
        db.ForeignKey("empresas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, default=agora_utc
    )
    atualizado_em = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=agora_utc,
        onupdate=agora_utc,
    )

    empresa = db.relationship(
        "Empresa", back_populates="funcionarios", lazy="joined"
    )
    emissoes = db.relationship(
        "Emissao",
        back_populates="funcionario",
        lazy="select",
        passive_deletes=True,
    )

    @validates("cpf")
    def validar_cpf(self, _, valor):
        cpf = somente_digitos(valor)
        if not cpf_valido(cpf):
            raise ValueError("O CPF informado é inválido.")
        return cpf

    def __repr__(self):
        return f"<Funcionario {self.nome}>"


class Emissao(db.Model):
    """Agrupa todos os documentos gerados em uma única operação."""

    __tablename__ = "emissoes"
    __table_args__ = (
        db.Index("ix_emissao_empresa_criado_em", "empresa_id", "criado_em"),
        db.Index(
            "ix_emissao_funcionario_criado_em", "funcionario_id", "criado_em"
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=gerar_uuid)

    empresa_id = db.Column(
        db.String(36),
        db.ForeignKey("empresas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    funcionario_id = db.Column(
        db.String(36),
        db.ForeignKey("funcionarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Primeira data selecionada para a sequência dos documentos.
    data_inicial = db.Column(db.Date, nullable=True)
    status = db.Column(
        db.String(20),
        nullable=False,
        default=StatusEmissao.RASCUNHO,
        index=True,
    )
    observacoes = db.Column(db.Text, nullable=True)

    # Preservam exatamente os dados utilizados quando a emissão foi criada.
    empresa_snapshot = db.Column(db.JSON, nullable=False, default=dict)
    funcionario_snapshot = db.Column(db.JSON, nullable=False, default=dict)

    # Dados compartilhados pelos documentos da mesma emissão.
    dados_gerais = db.Column(db.JSON, nullable=False, default=dict)

    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, default=agora_utc, index=True
    )
    atualizado_em = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=agora_utc,
        onupdate=agora_utc,
    )
    concluido_em = db.Column(db.DateTime(timezone=True), nullable=True)

    empresa = db.relationship("Empresa", back_populates="emissoes", lazy="joined")
    funcionario = db.relationship(
        "Funcionario", back_populates="emissoes", lazy="joined"
    )
    documentos = db.relationship(
        "DocumentoEmitido",
        back_populates="emissao",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="DocumentoEmitido.sequencia",
        passive_deletes=True,
    )

    def registrar_snapshots(self, funcao_utilizada=None):
        """Copia para o histórico os dados utilizados na emissão.

        ``funcao_utilizada`` permite registrar a função informada manualmente
        na tela, sem alterar o cadastro principal do funcionário.
        """
        self.empresa_snapshot = {
            "id": self.empresa.id,
            "razao_social": self.empresa.razao_social,
            "cnpj": self.empresa.cnpj,
            "cidade": self.empresa.cidade,
            "endereco_completo": self.empresa.endereco_completo,
        }
        self.funcionario_snapshot = {
            "id": self.funcionario.id,
            "nome": self.funcionario.nome,
            "cpf": self.funcionario.cpf,
            "funcao": (
                funcao_utilizada
                if funcao_utilizada is not None
                else self.funcionario.funcao
            ),
        }

    @validates("status")
    def validar_status(self, _, valor):
        if valor not in StatusEmissao.TODOS:
            raise ValueError(f"Status de emissão inválido: {valor}")
        return valor

    def __repr__(self):
        return f"<Emissao {self.id} - {self.status}>"


class DocumentoEmitido(db.Model):
    """Representa cada Ficha de EPI, OS ou certificado NR de uma emissão."""

    __tablename__ = "documentos_emitidos"
    __table_args__ = (
        db.UniqueConstraint(
            "emissao_id",
            "tipo_documento",
            name="uq_documento_emissao_tipo",
        ),
        db.Index(
            "ix_documento_tipo_data", "tipo_documento", "data_documento"
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=gerar_uuid)
    emissao_id = db.Column(
        db.String(36),
        db.ForeignKey("emissoes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tipo_documento = db.Column(db.String(30), nullable=False, index=True)
    titulo = db.Column(db.String(150), nullable=True)
    sequencia = db.Column(db.Integer, nullable=False, default=1)
    data_documento = db.Column(db.Date, nullable=True, index=True)
    versao_template = db.Column(db.String(50), nullable=True)

    status = db.Column(
        db.String(20),
        nullable=False,
        default=StatusDocumento.PENDENTE,
        index=True,
    )

    # Exemplos:
    # Ficha de EPI: {"epis": [{"descricao": "...", "ca": "..."}]}
    # NR-12: {"maquinas": ["Torno", "Furadeira"]}
    dados_preenchimento = db.Column(db.JSON, nullable=False, default=dict)
    erro_processamento = db.Column(db.Text, nullable=True)

    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, default=agora_utc
    )
    atualizado_em = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=agora_utc,
        onupdate=agora_utc,
    )

    emissao = db.relationship("Emissao", back_populates="documentos")
    arquivos = db.relationship(
        "ArquivoDocumento",
        back_populates="documento",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="ArquivoDocumento.pagina",
        passive_deletes=True,
    )

    @validates("tipo_documento")
    def validar_tipo_documento(self, _, valor):
        if valor not in TipoDocumento.TODOS:
            raise ValueError(f"Tipo de documento inválido: {valor}")
        return valor

    @validates("status")
    def validar_status(self, _, valor):
        if valor not in StatusDocumento.TODOS:
            raise ValueError(f"Status de documento inválido: {valor}")
        return valor

    def __repr__(self):
        return f"<DocumentoEmitido {self.tipo_documento}>"


class ArquivoDocumento(db.Model):
    """Registra DOCX, PDF e uma ou várias páginas JPEG de um documento."""

    __tablename__ = "arquivos_documentos"
    __table_args__ = (
        db.Index(
            "ix_arquivo_documento_formato", "documento_id", "formato"
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=gerar_uuid)
    documento_id = db.Column(
        db.String(36),
        db.ForeignKey("documentos_emitidos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    formato = db.Column(db.String(10), nullable=False)
    caminho_arquivo = db.Column(db.String(500), nullable=False)
    nome_arquivo = db.Column(db.String(255), nullable=True)

    # Para JPEG, informa a página; para DOCX e PDF, permanece nulo.
    pagina = db.Column(db.Integer, nullable=True)
    mime_type = db.Column(db.String(100), nullable=True)
    tamanho_bytes = db.Column(db.BigInteger, nullable=True)
    hash_sha256 = db.Column(db.String(64), nullable=True)

    criado_em = db.Column(
        db.DateTime(timezone=True), nullable=False, default=agora_utc
    )

    documento = db.relationship("DocumentoEmitido", back_populates="arquivos")

    @validates("formato")
    def validar_formato(self, _, valor):
        if valor not in FormatoArquivo.TODOS:
            raise ValueError(f"Formato de arquivo inválido: {valor}")
        return valor

    def __repr__(self):
        return f"<ArquivoDocumento {self.formato} - {self.caminho_arquivo}>"
