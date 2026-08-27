import os
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, current_app, flash, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from config import configuracoes

from .extensions import csrf, db, login_manager, migrate
from .security import current_user


def create_app(config_name=None):
    """Cria e configura a aplicação Flask."""
    app = Flask(__name__, instance_relative_config=True)

    ambiente = config_name or os.getenv("APP_CONFIG", "development")
    app.config.from_object(configuracoes.get(ambiente, configuracoes["development"]))
    if ambiente == "production":
        if app.config["SECRET_KEY"] == "troque-esta-chave-no-arquivo-env":
            raise RuntimeError("Defina uma SECRET_KEY forte no .env antes de iniciar em produção.")
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["DOCUMENTS_ROOT"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para acessar o sistema."
    login_manager.login_message_category = "error"
    login_manager.session_protection = "strong"

    # Garante que todos os models sejam registrados nos metadados do SQLAlchemy.
    from . import models

    @login_manager.user_loader
    def carregar_usuario(usuario_id):
        usuario = db.session.get(models.Usuario, usuario_id)
        if not usuario or not usuario.ativo or not usuario.tenant.ativo:
            return None
        return usuario

    @login_manager.unauthorized_handler
    def acesso_nao_autorizado():
        flash("Faça login para acessar o sistema.", "error")
        return redirect(url_for("auth.login", next=request.full_path))

    app.jinja_env.filters["cnpj"] = models.formatar_cnpj
    app.jinja_env.filters["cpf"] = models.formatar_cpf
    app.jinja_env.filters["data_br"] = formatar_data_br
    app.jinja_env.filters["data_hora_br"] = formatar_data_hora_br

    @app.context_processor
    def contexto_global():
        return {
            "current_user": current_user,
            "rotulos_documentos": models.TipoDocumento.ROTULOS,
            "rotulos_status_emissao": models.StatusEmissao.ROTULOS,
            "rotulos_niveis": models.NivelAcesso.ROTULOS,
            "versao_sistema": app.config["APP_VERSION"],
        }

    from .admin import bp as admin_bp
    from .auth import bp as auth_bp
    from .empresas import bp as empresas_bp
    from .emissoes import bp as emissoes_bp
    from .funcionarios import bp as funcionarios_bp
    from .main import bp as main_bp
    from .relatorios import bp as relatorios_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(empresas_bp)
    app.register_blueprint(funcionarios_bp)
    app.register_blueprint(emissoes_bp)
    app.register_blueprint(relatorios_bp)
    app.register_blueprint(admin_bp)

    registrar_seguranca_e_auditoria(app)

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


def formatar_data_hora_br(valor):
    if not valor:
        return "—"
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=timezone.utc)
        valor = valor.astimezone(ZoneInfo(current_app.config["APP_TIMEZONE"]))
        return valor.strftime("%d/%m/%Y %H:%M:%S")
    return str(valor)


def registrar_erros(app):
    @app.errorhandler(403)
    def acesso_negado(_erro):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def pagina_nao_encontrada(_erro):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def erro_interno(_erro):
        db.session.rollback()
        return render_template("errors/500.html"), 500


def registrar_seguranca_e_auditoria(app):
    rotulos_telas = {
        "main.dashboard": ("Dashboard", "Dashboard"),
        "empresas.listar": ("Empresas", "Listagem de empresas"),
        "empresas.nova": ("Empresas", "Cadastro de empresa"),
        "empresas.editar": ("Empresas", "Edição de empresa"),
        "funcionarios.listar": ("Funcionários", "Listagem de funcionários"),
        "funcionarios.novo": ("Funcionários", "Cadastro de funcionário"),
        "funcionarios.editar": ("Funcionários", "Edição de funcionário"),
        "emissoes.listar": ("Emissões", "Listagem de emissões"),
        "emissoes.nova": ("Emissões", "Nova emissão"),
        "emissoes.editar": ("Emissões", "Edição de emissão"),
        "emissoes.detalhar": ("Emissões", "Detalhes da emissão"),
        "emissoes.baixar_arquivo": ("Arquivos", "Download ou visualização de arquivo"),
        "relatorios.index": ("Relatórios", "Relatórios"),
        "admin.usuarios": ("Usuários", "Administração de usuários"),
        "admin.novo_usuario": ("Usuários", "Cadastro de usuário"),
        "admin.editar_usuario": ("Usuários", "Edição de usuário"),
        "admin.auditoria": ("Auditoria", "Log de auditoria"),
        "admin.detalhe_auditoria": ("Auditoria", "Detalhes do log"),
    }

    @app.before_request
    def exigir_autenticacao():
        if app.config.get("LOGIN_DISABLED"):
            return None
        endpoint = request.endpoint or ""
        publico = endpoint.startswith("auth.") or endpoint == "main.health"
        if endpoint == "static" or publico or current_user.is_authenticated:
            return None
        return login_manager.unauthorized()

    @app.after_request
    def auditar_tela_aberta(resposta):
        if (
            not app.config.get("LOGIN_DISABLED")
            and current_user.is_authenticated
            and request.method == "GET"
            and resposta.status_code < 400
            and request.endpoint in rotulos_telas
        ):
            from .services.auditoria import registrar_auditoria

            modulo, tela = rotulos_telas[request.endpoint]
            try:
                registrar_auditoria(
                    "ACESSOU",
                    modulo,
                    f"Abriu a tela: {tela}.",
                    detalhes={
                        "parametros": request.args.to_dict(flat=True),
                        "rota_parametros": request.view_args or {},
                    },
                    commit=True,
                )
            except Exception:
                db.session.rollback()
        return resposta

    @app.after_request
    def aplicar_cabecalhos_seguranca(resposta):
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["X-Frame-Options"] = "DENY"
        resposta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resposta.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        resposta.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        resposta.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; font-src 'self'; object-src 'none'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if app.config.get("PREFERRED_URL_SCHEME") == "https":
            resposta.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        if request.endpoint and request.endpoint != "static":
            resposta.headers["Cache-Control"] = "no-store"
        return resposta
