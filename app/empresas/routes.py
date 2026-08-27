from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Empresa, somente_digitos
from app.auth.permissions import permissao_edicao
from app.services.auditoria import alteracoes_campos, registrar_auditoria
from app.services.tenant import empresa_do_tenant_ou_404, tenant_atual_id

from . import bp
from .forms import EmpresaForm, StatusEmpresaForm


ITENS_POR_PAGINA = 10


@bp.get("/")
def listar():
    pagina = request.args.get("pagina", 1, type=int)
    busca = request.args.get("busca", "").strip()
    status = request.args.get("status", "ativos")
    if status not in {"ativos", "inativos", "todos"}:
        status = "ativos"

    consulta = select(Empresa).where(Empresa.tenant_id == tenant_atual_id())

    if busca:
        filtros = [Empresa.razao_social.ilike(f"%{busca}%")]
        busca_numerica = somente_digitos(busca)
        if busca_numerica:
            filtros.append(Empresa.cnpj.ilike(f"%{busca_numerica}%"))
        consulta = consulta.where(or_(*filtros))

    if status == "ativos":
        consulta = consulta.where(Empresa.ativo.is_(True))
    elif status == "inativos":
        consulta = consulta.where(Empresa.ativo.is_(False))

    consulta = consulta.order_by(Empresa.razao_social.asc())
    paginacao = db.paginate(
        consulta,
        page=max(pagina, 1),
        per_page=ITENS_POR_PAGINA,
        error_out=False,
    )

    return render_template(
        "empresas/listar.html",
        empresas=paginacao.items,
        paginacao=paginacao,
        busca=busca,
        status=status,
        status_form=StatusEmpresaForm(),
    )


@bp.route("/nova", methods=["GET", "POST"])
@permissao_edicao
def nova():
    form = EmpresaForm()
    if form.validate_on_submit():
        empresa = Empresa(
            tenant_id=tenant_atual_id(),
            razao_social=form.razao_social.data,
            cnpj=form.cnpj.data,
            cidade=form.cidade.data,
            endereco_completo=form.endereco_completo.data,
        )
        db.session.add(empresa)

        try:
            db.session.flush()
            registrar_auditoria(
                "CADASTROU",
                "Empresas",
                f"Empresa {empresa.razao_social} cadastrada.",
                entidade_tipo="Empresa",
                entidade_id=empresa.id,
                detalhes={"cnpj": empresa.cnpj, "cidade": empresa.cidade},
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.cnpj.errors.append(
                "Não foi possível salvar: este CNPJ já está cadastrado."
            )
        else:
            flash("Empresa cadastrada com sucesso.", "success")
            return redirect(url_for("empresas.listar"))

    return render_template(
        "empresas/form.html",
        form=form,
        titulo="Cadastrar Empresa",
        texto_botao="Cadastrar Empresa",
    )


@bp.route("/<string:empresa_id>/editar", methods=["GET", "POST"])
@permissao_edicao
def editar(empresa_id):
    empresa = empresa_do_tenant_ou_404(empresa_id)
    form = EmpresaForm(obj=empresa, empresa_original=empresa)

    if form.validate_on_submit():
        antes = {
            "razao_social": empresa.razao_social,
            "cnpj": empresa.cnpj,
            "cidade": empresa.cidade,
            "endereco_completo": empresa.endereco_completo,
        }
        empresa.razao_social = form.razao_social.data
        empresa.cnpj = form.cnpj.data
        empresa.cidade = form.cidade.data
        empresa.endereco_completo = form.endereco_completo.data
        depois = {
            "razao_social": empresa.razao_social,
            "cnpj": empresa.cnpj,
            "cidade": empresa.cidade,
            "endereco_completo": empresa.endereco_completo,
        }
        registrar_auditoria(
            "EDITOU",
            "Empresas",
            f"Empresa {empresa.razao_social} atualizada.",
            entidade_tipo="Empresa",
            entidade_id=empresa.id,
            detalhes={"alteracoes": alteracoes_campos(antes, depois)},
        )

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.cnpj.errors.append(
                "Não foi possível salvar: este CNPJ já está cadastrado."
            )
        else:
            flash("Empresa atualizada com sucesso.", "success")
            return redirect(url_for("empresas.listar"))

    return render_template(
        "empresas/form.html",
        form=form,
        titulo="Editar Empresa",
        texto_botao="Salvar Alterações",
        empresa=empresa,
    )


@bp.post("/<string:empresa_id>/alterar-status")
@permissao_edicao
def alterar_status(empresa_id):
    form = StatusEmpresaForm()
    if not form.validate_on_submit():
        abort(400)

    empresa = empresa_do_tenant_ou_404(empresa_id)
    empresa.ativo = not empresa.ativo
    registrar_auditoria(
        "ALTEROU_STATUS",
        "Empresas",
        f"Empresa {empresa.razao_social} {'ativada' if empresa.ativo else 'desativada'}.",
        entidade_tipo="Empresa",
        entidade_id=empresa.id,
        detalhes={"ativo": empresa.ativo},
    )
    db.session.commit()

    acao = "ativada" if empresa.ativo else "desativada"
    flash(f"Empresa {acao} com sucesso.", "success")
    return redirect(url_for("empresas.listar", status="todos"))
