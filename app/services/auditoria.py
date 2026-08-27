from __future__ import annotations

from flask import has_request_context, request
from app.extensions import db
from app.models import LogAuditoria
from app.security import current_user


def _ip_requisicao() -> str | None:
    if not has_request_context():
        return None
    encaminhado = request.headers.get("X-Forwarded-For", "")
    return (encaminhado.split(",")[0].strip() if encaminhado else request.remote_addr)


def registrar_auditoria(
    acao: str,
    modulo: str,
    descricao: str,
    *,
    entidade_tipo: str | None = None,
    entidade_id: str | None = None,
    detalhes: dict | None = None,
    usuario=None,
    usuario_nome: str | None = None,
    commit: bool = False,
) -> LogAuditoria:
    usuario_atual = usuario
    if usuario_atual is None and has_request_context() and current_user.is_authenticated:
        usuario_atual = current_user

    log = LogAuditoria(
        tenant_id=getattr(usuario_atual, "tenant_id", None),
        usuario_id=getattr(usuario_atual, "id", None),
        usuario_nome=(
            usuario_nome
            or getattr(usuario_atual, "nome", None)
            or getattr(usuario_atual, "email", None)
            or "Sistema"
        ),
        acao=acao,
        modulo=modulo,
        descricao=descricao[:500],
        entidade_tipo=entidade_tipo,
        entidade_id=entidade_id,
        detalhes=detalhes or {},
        metodo=request.method if has_request_context() else None,
        rota=request.path[:255] if has_request_context() else None,
        ip=_ip_requisicao(),
        user_agent=(request.user_agent.string[:255] if has_request_context() else None),
    )
    db.session.add(log)
    if commit:
        db.session.commit()
    return log


def alteracoes_campos(antes: dict, depois: dict) -> dict:
    return {
        campo: {"antes": antes.get(campo), "depois": valor}
        for campo, valor in depois.items()
        if antes.get(campo) != valor
    }
