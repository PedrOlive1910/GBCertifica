from datetime import date
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy import select

from app.extensions import db
from app.models import Emissao, StatusEmissao
from app.services.documentos import renderizar_docx
from tests.helpers import criar_empresa_funcionario


def dados_emissao(empresa_id, funcionario_id):
    return {
        "empresa_id": empresa_id,
        "funcionario_id": funcionario_id,
        "funcao": "Carpinteiro",
        "data_admissao": "2026-08-01",
        "data_inicial": "2026-09-06",
        "documentos": ["NR_06", "NR_12"],
        "maquinas[]": ["Serra circular", "Furadeira"],
    }


def test_cria_emissao_e_ignora_domingo(app, client):
    with app.app_context():
        empresa, funcionario = criar_empresa_funcionario()
        ids = empresa.id, funcionario.id
    resposta = client.post("/emissoes/nova", data=dados_emissao(*ids), follow_redirects=True)
    assert resposta.status_code == 200
    assert "Emissão criada" in resposta.get_data(as_text=True)
    with app.app_context():
        emissao = db.session.scalar(select(Emissao))
        assert emissao.status == StatusEmissao.RASCUNHO
        assert [item.data_documento for item in emissao.documentos] == [
            date(2026, 9, 7),
            date(2026, 9, 8),
        ]
        assert emissao.dados_gerais["maquinas"] == ["Serra circular", "Furadeira"]


def test_renderiza_os_seis_templates_docx(app, client, tmp_path):
    with app.app_context():
        empresa, funcionario = criar_empresa_funcionario()
        dados = dados_emissao(empresa.id, funcionario.id)
    dados.update(
        {
            "documentos": ["FICHA_EPI", "ORDEM_SERVICO", "NR_06", "NR_12", "NR_18", "NR_35"],
            "epi_quantidade[]": ["01"],
            "epi_descricao[]": ["Capacete de segurança"],
            "epi_ca[]": ["12345"],
            "epi_data_entrega[]": ["2026-09-07"],
            "epi_data_devolucao[]": [""],
            "epi_assinatura[]": ["X"],
            "setor": "Obra",
            "cbo": "7155-05",
            "descricao_funcao": "Executar serviços de carpintaria.",
            "risco_fisico": "Ruído e calor.",
            "risco_quimico": "Poeiras minerais.",
            "risco_biologico": "Não identificado.",
            "risco_ergonomico": "Posturas incômodas.",
            "risco_acidentes": "Queda e corte.",
            "epis_atividade": "Capacete; óculos; luvas.",
            "recomendacoes": "Utilizar os EPIs durante toda a atividade.",
            "procedimentos_acidente": "Comunicar imediatamente ao responsável.",
            "responsavel_nome": "Elton Bruno A. Olegario",
            "responsavel_cargo": "Técnico de Segurança do Trabalho",
            "responsavel_registro": "0018863/PE",
        }
    )
    resposta = client.post("/emissoes/nova", data=dados, follow_redirects=True)
    assert resposta.status_code == 200
    with app.app_context():
        emissao = db.session.scalar(select(Emissao))
        for documento in emissao.documentos:
            destino = tmp_path / f"{documento.tipo_documento}.docx"
            renderizar_docx(documento, destino)
            assert destino.is_file()
            assert destino.stat().st_size > 1000
            with ZipFile(destino) as arquivo:
                xml = "".join(
                    arquivo.read(nome).decode("utf-8", errors="ignore")
                    for nome in arquivo.namelist()
                    if nome.startswith("word/") and nome.endswith(".xml")
                )
            assert "{{" not in xml
            assert "FABIO CARVALHO DA SILVA" not in xml
            assert "FRANCISCO DAS CHAGAS" not in xml
            if documento.tipo_documento == "FICHA_EPI":
                assert "07/09/2026" in xml


def test_relatorio_abre(client):
    resposta = client.get("/relatorios/")
    assert resposta.status_code == 200
    assert "Relatórios" in resposta.get_data(as_text=True)
