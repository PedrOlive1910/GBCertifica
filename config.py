import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def obter_url_banco():
    url = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'sistema_tst.db'}",
    )

    # Compatibilidade com provedores que ainda retornam postgres://.
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def env_bool(nome, padrao=False):
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


class Config:
    APP_VERSION = os.getenv("APP_VERSION", "1.2.3")
    APP_TIMEZONE = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")
    SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-no-arquivo-env")
    SQLALCHEMY_DATABASE_URI = obter_url_banco()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    DOCUMENTS_ROOT = os.getenv(
        "DOCUMENTS_ROOT", str(BASE_DIR / "storage" / "documentos")
    )
    # Caminhos opcionais. Quando vazios, o sistema procura no PATH e nos
    # diretórios de instalação mais comuns do Windows, Linux e macOS.
    LIBREOFFICE_PATH = os.getenv("LIBREOFFICE_PATH", "")
    PDFTOPPM_PATH = os.getenv("PDFTOPPM_PATH", "")
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
    )
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    SESSION_REFRESH_EACH_REQUEST = True
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = env_bool("SMTP_USE_TLS", True)
    MAIL_FROM = os.getenv("MAIL_FROM", os.getenv("SMTP_USER", ""))
    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000")
    MAX_LOGIN_FAILURES = int(os.getenv("MAX_LOGIN_FAILURES", "5"))
    LOGIN_BLOCK_MINUTES = int(os.getenv("LOGIN_BLOCK_MINUTES", "15"))


class DevelopmentConfig(Config):
    DEBUG = True
    APP_ENV_LABEL = "Homologação/Desenvolvimento"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    APP_ENV_LABEL = "Produção"
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    APP_ENV_LABEL = "Testes"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LOGIN_DISABLED = True
    TEST_TENANT_ID = "00000000-0000-0000-0000-000000000001"


configuracoes = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
