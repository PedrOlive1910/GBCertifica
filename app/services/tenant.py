from flask import abort, current_app
from sqlalchemy import select

from app.extensions import db
from app.models import ArquivoDocumento, DocumentoEmitido, Emissao, Empresa, Funcionario
from app.security import current_user


def tenant_atual_id() -> str:
    if current_app.config.get("LOGIN_DISABLED"):
        return current_app.config["TEST_TENANT_ID"]
    if not current_user.is_authenticated or not current_user.tenant_id:
        abort(403)
    return current_user.tenant_id


def empresa_do_tenant_ou_404(empresa_id: str) -> Empresa:
    return db.first_or_404(
        select(Empresa).where(
            Empresa.id == empresa_id,
            Empresa.tenant_id == tenant_atual_id(),
        )
    )


def funcionario_do_tenant_ou_404(funcionario_id: str) -> Funcionario:
    return db.first_or_404(
        select(Funcionario)
        .join(Funcionario.empresa)
        .where(
            Funcionario.id == funcionario_id,
            Empresa.tenant_id == tenant_atual_id(),
        )
    )


def emissao_do_tenant_ou_404(emissao_id: str) -> Emissao:
    return db.first_or_404(
        select(Emissao)
        .join(Emissao.empresa)
        .where(
            Emissao.id == emissao_id,
            Empresa.tenant_id == tenant_atual_id(),
        )
    )


def arquivo_do_tenant_ou_404(arquivo_id: str) -> ArquivoDocumento:
    return db.first_or_404(
        select(ArquivoDocumento)
        .join(ArquivoDocumento.documento)
        .join(DocumentoEmitido.emissao)
        .join(Emissao.empresa)
        .where(
            ArquivoDocumento.id == arquivo_id,
            Empresa.tenant_id == tenant_atual_id(),
        )
    )
