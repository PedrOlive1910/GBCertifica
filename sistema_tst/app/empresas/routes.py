from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Empresa, somente_digitos

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

    consulta = select(Empresa)

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
def nova():
    form = EmpresaForm()
    if form.validate_on_submit():
        empresa = Empresa(
            razao_social=form.razao_social.data,
            cnpj=form.cnpj.data,
            cidade=form.cidade.data,
            endereco_completo=form.endereco_completo.data,
        )
        db.session.add(empresa)

        try:
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
def editar(empresa_id):
    empresa = db.get_or_404(Empresa, empresa_id)
    form = EmpresaForm(obj=empresa, empresa_original=empresa)

    if form.validate_on_submit():
        empresa.razao_social = form.razao_social.data
        empresa.cnpj = form.cnpj.data
        empresa.cidade = form.cidade.data
        empresa.endereco_completo = form.endereco_completo.data

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
def alterar_status(empresa_id):
    form = StatusEmpresaForm()
    if not form.validate_on_submit():
        abort(400)

    empresa = db.get_or_404(Empresa, empresa_id)
    empresa.ativo = not empresa.ativo
    db.session.commit()

    acao = "ativada" if empresa.ativo else "desativada"
    flash(f"Empresa {acao} com sucesso.", "success")
    return redirect(url_for("empresas.listar", status="todos"))
