from sqlalchemy import select

from app.extensions import db
from app.models import (
    ArquivoDocumento,
    DocumentoEmitido,
    Emissao,
    Empresa,
    FormatoArquivo,
    Funcionario,
    LogAuditoria,
    NivelAcesso,
    Tenant,
    TipoDocumento,
    Usuario,
)


def criar_usuario(app, *, nivel=NivelAcesso.ADMINISTRADOR, email="admin@teste.local"):
    with app.app_context():
        usuario = Usuario(
            tenant_id=app.config["TEST_TENANT_ID"],
            nome="Usuário de Teste",
            email=email,
            nivel_acesso=nivel,
            ativo=True,
        )
        usuario.definir_senha("SenhaForte123")
        db.session.add(usuario)
        db.session.commit()
        return usuario.id


def ativar_login(app):
    app.config["LOGIN_DISABLED"] = False


def entrar(client, email="admin@teste.local", senha="SenhaForte123", **opcoes):
    return client.post(
        "/login",
        data={"email": email, "senha": senha, **opcoes},
        follow_redirects=True,
    )


def test_telas_internas_exigem_login(app, client):
    ativar_login(app)
    resposta = client.get("/")
    assert resposta.status_code == 302
    assert "/login" in resposta.location


def test_senha_e_irreversivel_e_login_e_auditado(app, client):
    criar_usuario(app)
    ativar_login(app)
    with app.app_context():
        usuario = db.session.scalar(select(Usuario))
        assert usuario.senha_hash != "SenhaForte123"
        assert usuario.senha_hash.startswith("scrypt:")

    resposta = entrar(client)
    assert resposta.status_code == 200
    assert "Dashboard" in resposta.get_data(as_text=True)
    assert client.get("/administracao/usuarios").status_code == 200
    assert client.get("/administracao/auditoria").status_code == 200
    with app.app_context():
        acoes = list(db.session.scalars(select(LogAuditoria.acao)))
        assert "LOGIN" in acoes
        assert "ACESSOU" in acoes


def test_perfil_consulta_nao_pode_alterar_dados(app, client):
    criar_usuario(app, nivel=NivelAcesso.CONSULTA, email="consulta@teste.local")
    ativar_login(app)
    entrar(client, email="consulta@teste.local")
    assert client.get("/empresas/").status_code == 200
    assert client.post("/empresas/nova", data={}).status_code == 403
    assert client.get("/administracao/usuarios").status_code == 403


def test_tenant_nao_acessa_empresa_de_outra_conta(app, client):
    criar_usuario(app)
    with app.app_context():
        outro = Tenant(nome="Outra Conta", slug="outra-conta")
        empresa = Empresa(
            tenant=outro,
            razao_social="Empresa de Outra Conta",
            cnpj="11444777000161",
            cidade="São Paulo",
            endereco_completo="Rua Externa, 10",
        )
        db.session.add_all([outro, empresa])
        db.session.commit()
        empresa_id = empresa.id
    ativar_login(app)
    entrar(client)
    assert client.get(f"/empresas/{empresa_id}/editar").status_code == 404


def test_download_tambem_respeita_o_tenant(app, client, tmp_path):
    criar_usuario(app)
    arquivo_fisico = tmp_path / "arquivo-seguro.pdf"
    arquivo_fisico.write_bytes(b"PDF de teste")
    with app.app_context():
        outro = Tenant(nome="Conta Isolada", slug="conta-isolada")
        empresa = Empresa(
            tenant=outro,
            razao_social="Empresa Isolada",
            cnpj="11444777000161",
            cidade="São Paulo",
            endereco_completo="Rua Isolada, 20",
        )
        funcionario = Funcionario(
            empresa=empresa,
            nome="Funcionário Isolado",
            cpf="52998224725",
        )
        emissao = Emissao(empresa=empresa, funcionario=funcionario)
        emissao.registrar_snapshots()
        documento = DocumentoEmitido(
            emissao=emissao,
            tipo_documento=TipoDocumento.NR_06,
            sequencia=1,
        )
        arquivo = ArquivoDocumento(
            documento=documento,
            formato=FormatoArquivo.PDF,
            caminho_arquivo=str(arquivo_fisico),
            nome_arquivo="arquivo.pdf",
        )
        db.session.add_all([outro, empresa, funcionario, emissao, documento, arquivo])
        db.session.commit()
        arquivo_id = arquivo.id
    ativar_login(app)
    entrar(client)
    assert client.get(f"/emissoes/arquivo/{arquivo_id}").status_code == 404


def test_bloqueia_conta_apos_tentativas_repetidas(app, client):
    criar_usuario(app)
    ativar_login(app)
    for _ in range(app.config["MAX_LOGIN_FAILURES"]):
        entrar(client, senha="senha-incorreta")
    resposta = entrar(client)
    assert "Acesso recusado" in resposta.get_data(as_text=True)
    with app.app_context():
        usuario = db.session.scalar(select(Usuario))
        assert usuario.bloqueado_ate is not None


def test_recuperacao_publica_orienta_procurar_administrador(app, client):
    criar_usuario(app)
    ativar_login(app)
    resposta = client.get("/esqueci-a-senha")
    html = resposta.get_data(as_text=True)
    assert resposta.status_code == 200
    assert "administrador do sistema" in html


def test_admin_redefine_e_usuario_e_obrigado_a_trocar_senha(app, client):
    criar_usuario(app)
    ativar_login(app)
    entrar(client)
    with app.app_context():
        usuario = db.session.scalar(select(Usuario))
        usuario_id = usuario.id
    resposta = client.post(
        f"/administracao/usuarios/{usuario_id}/redefinir-senha",
        data={
            "senha": "Temporaria456",
            "confirmar_senha": "Temporaria456",
        },
        follow_redirects=True,
    )
    assert "Senha temporária definida" in resposta.get_data(as_text=True)
    resposta = entrar(client, senha="Temporaria456")
    assert "Crie sua senha pessoal" in resposta.get_data(as_text=True)
    resposta = client.post(
        "/trocar-senha-temporaria",
        data={"senha": "PessoalNova789", "confirmar_senha": "PessoalNova789"},
        follow_redirects=True,
    )
    assert "Dashboard" in resposta.get_data(as_text=True)
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        assert usuario.deve_trocar_senha is False
        assert usuario.verificar_senha("PessoalNova789")
