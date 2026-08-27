import os
from datetime import date, datetime
from pathlib import Path

from flask import Flask, render_template

from config import configuracoes

from .extensions import csrf, db, migrate


def create_app(config_name=None):
    """Cria e configura a aplicação Flask."""
    app = Flask(__name__, instance_relative_config=True)

    ambiente = config_name or os.getenv("APP_CONFIG", "development")
    app.config.from_object(configuracoes.get(ambiente, configuracoes["development"]))

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["DOCUMENTS_ROOT"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    csrf.init_app(app)

    # Garante que todos os models sejam registrados nos metadados do SQLAlchemy.
    from . import models

    app.jinja_env.filters["cnpj"] = models.formatar_cnpj
    app.jinja_env.filters["cpf"] = models.formatar_cpf
    app.jinja_env.filters["data_br"] = formatar_data_br

    @app.context_processor
    def contexto_global():
        return {
            "rotulos_documentos": models.TipoDocumento.ROTULOS,
            "rotulos_status_emissao": models.StatusEmissao.ROTULOS,
        }

    from .empresas import bp as empresas_bp
    from .emissoes import bp as emissoes_bp
    from .funcionarios import bp as funcionarios_bp
    from .main import bp as main_bp
    from .relatorios import bp as relatorios_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(empresas_bp)
    app.register_blueprint(funcionarios_bp)
    app.register_blueprint(emissoes_bp)
    app.register_blueprint(relatorios_bp)

    registrar_erros(app)
    return app


def formatar_data_br(valor):
    if not valor:
        return "—"
    if isinstance(valor, datetime):
        valor = valor.date()
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def registrar_erros(app):
    @app.errorhandler(404)
    def pagina_nao_encontrada(_erro):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def erro_interno(_erro):
        db.session.rollback()
        return render_template("errors/500.html"), 500
