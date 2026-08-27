"""Cria e atualiza a estrutura necessária para a versão 1.0.

O script preserva os cadastros existentes. Em bancos anteriores, adiciona a
chave de tenant às empresas e vincula os registros à conta principal.
"""

import os

from sqlalchemy import inspect, select, text

from app import create_app
from app.extensions import db
from app.models import NivelAcesso, Tenant, Usuario, gerar_uuid
from app.validators import senha_forte


app = create_app()


def garantir_tenant():
    slug = os.getenv("TENANT_SLUG", "conta-principal").strip().lower()
    tenant = db.session.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant:
        return tenant
    tenant = Tenant(
        id=gerar_uuid(),
        nome=os.getenv("TENANT_NAME", "Conta Principal").strip(),
        slug=slug,
    )
    db.session.add(tenant)
    db.session.commit()
    return tenant


def migrar_empresas_para_tenant(tenant):
    inspetor = inspect(db.engine)
    if "empresas" not in inspetor.get_table_names():
        return
    colunas = {item["name"] for item in inspetor.get_columns("empresas")}
    dialecto = db.engine.dialect.name

    if "tenant_id" not in colunas:
        db.session.execute(text("ALTER TABLE empresas ADD COLUMN tenant_id VARCHAR(36)"))
        db.session.commit()

    db.session.execute(
        text("UPDATE empresas SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
        {"tenant_id": tenant.id},
    )
    db.session.commit()

    if dialecto == "postgresql":
        db.session.execute(
            text("ALTER TABLE empresas ALTER COLUMN tenant_id SET NOT NULL")
        )
        db.session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_empresas_tenant_id "
                "ON empresas (tenant_id)"
            )
        )
        db.session.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_empresa_tenant_cnpj "
                "ON empresas (tenant_id, cnpj)"
            )
        )
        db.session.execute(
            text(
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
                "WHERE conname = 'fk_empresas_tenant_id') THEN "
                "ALTER TABLE empresas ADD CONSTRAINT fk_empresas_tenant_id "
                "FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT; "
                "END IF; END $$;"
            )
        )
    else:
        db.session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_empresas_tenant_id "
                "ON empresas (tenant_id)"
            )
        )
        db.session.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_empresa_tenant_cnpj "
                "ON empresas (tenant_id, cnpj)"
            )
        )
    db.session.commit()


def criar_administrador_inicial(tenant):
    existente = db.session.scalar(
        select(Usuario).where(Usuario.tenant_id == tenant.id).limit(1)
    )
    if existente:
        return False

    nome = os.getenv("ADMIN_NOME", "").strip()
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    senha = os.getenv("ADMIN_PASSWORD", "")
    if not nome or not email or not senha_forte(senha):
        print(
            "Administrador não criado. Configure ADMIN_NOME, ADMIN_EMAIL e "
            "ADMIN_PASSWORD (8+ caracteres, maiúscula, minúscula e número) "
            "no .env e execute novamente."
        )
        return False

    usuario = Usuario(
        tenant=tenant,
        nome=nome,
        email=email,
        nivel_acesso=NivelAcesso.ADMINISTRADOR,
        ativo=True,
    )
    usuario.definir_senha(senha)
    db.session.add(usuario)
    db.session.commit()
    return True


with app.app_context():
    # Cria primeiro as novas tabelas independentes. Tabelas existentes não são apagadas.
    db.create_all()
    tenant_principal = garantir_tenant()
    migrar_empresas_para_tenant(tenant_principal)
    # Uma segunda passagem garante metadados após a atualização de bancos antigos.
    db.create_all()
    admin_criado = criar_administrador_inicial(tenant_principal)

    tabelas = inspect(db.engine).get_table_names()
    print(f"Banco atualizado para o Sistema TST v{app.config['APP_VERSION']}.")
    print("Conta cliente:", tenant_principal.nome)
    print("Administrador inicial criado." if admin_criado else "Administrador já existente ou pendente de configuração.")
    print("Tabelas encontradas:", ", ".join(sorted(tabelas)))
