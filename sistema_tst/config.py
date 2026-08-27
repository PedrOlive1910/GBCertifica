import os
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


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-no-arquivo-env")
    SQLALCHEMY_DATABASE_URI = obter_url_banco()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    DOCUMENTS_ROOT = os.getenv(
        "DOCUMENTS_ROOT", str(BASE_DIR / "storage" / "documentos")
    )
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024


class DevelopmentConfig(Config):
    DEBUG = True
    APP_ENV_LABEL = "Homologação/Desenvolvimento"


class ProductionConfig(Config):
    DEBUG = False
    APP_ENV_LABEL = "Produção"


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    APP_ENV_LABEL = "Testes"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


configuracoes = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
