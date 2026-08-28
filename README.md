# GBcertifica — versão 1.2.3

Sistema Flask para cadastrar empresas e funcionários, montar emissões e gerar
documentos de Segurança do Trabalho em DOCX, PDF e JPEG.

## Funcionalidades

- Layout profissional, responsivo e em tons de verde;
- Dashboard operacional com indicadores, pendências e atalhos;
- CRUD de empresas e CRUD de funcionários com formulários responsivos;
- Emissões com Ficha de EPI, Ordem de Serviço, NR-06, NR-12, NR-18 e NR-35;
- Datas sequenciais, ignorando domingos;
- EPIs e máquinas da NR-12 preenchidos dinamicamente;
- Preview e download em DOCX, PDF e JPEG;
- Relatórios por empresa, período e tipo de documento, com paginação e PDF;
- Barra de progresso durante a geração de relatórios e documentos;
- Conversão dos documentos em lote para reduzir inicializações do LibreOffice;
- Login, usuários e níveis de acesso;
- Log de auditoria com usuário, tela, ação, alteração, IP e horário;
- Isolamento de contas clientes para operação multi-tenant.

Os templates preparados ficam em `app/document_templates/`. Não é necessário
editar manualmente os arquivos para inserir tags.

## Segurança

### Senhas e recuperação

- As senhas são armazenadas exclusivamente como hash `scrypt` com salt;
- o sistema nunca salva ou exibe senhas em texto aberto;
- a recuperação usa token aleatório de uso único;
- apenas o hash do token é salvo no banco;
- o link expira em uma hora e depende do SMTP configurado no `.env`;
- tentativas repetidas bloqueiam temporariamente a conta e o endereço IP.

### Sessão e ataques web

- Sessão assinada, cookie `HttpOnly`, `SameSite=Lax` e `Secure` em produção;
- expiração por inatividade configurável;
- proteção CSRF em todos os formulários;
- consultas parametrizadas pelo SQLAlchemy;
- escape automático de conteúdo pelo Jinja2;
- política CSP, bloqueio de iframe, HSTS, `nosniff` e demais cabeçalhos.

### Isolamento entre clientes

Cada usuário pertence a uma conta cliente (`tenant`). Empresas, funcionários,
emissões, relatórios, auditoria e downloads são consultados com a chave da conta
autenticada. IDs trocados manualmente na URL retornam acesso negado ou registro
inexistente.

Os arquivos físicos recebem nomes UUID, ficam fora da pasta pública do Nginx e
recebem permissões restritas no Linux. UUID evita descoberta por nomes; para
criptografia integral de disco e backups, utilize também o recurso de volume ou
backup criptografado da infraestrutura.

## Níveis de acesso

| Nível | Permissões |
| --- | --- |
| Administrador | Acesso total, gerenciamento de usuários e auditoria |
| Operador | Empresas, funcionários, emissões, downloads e relatórios |
| Consulta | Visualização, relatórios e downloads, sem alterar dados |

## Requisitos

- Python 3.11 ou superior;
- PostgreSQL;
- LibreOffice;
- Poppler com `pdftoppm`.

O sistema procura LibreOffice e Poppler no `PATH` e nos locais mais comuns do
Windows e Linux. Caminhos personalizados podem ser definidos no `.env`.

## Instalação no Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure pelo menos estas variáveis no `.env`:

```env
APP_CONFIG=development
APP_VERSION=1.2.3
APP_TIMEZONE=America/Sao_Paulo
SECRET_KEY=uma-chave-secreta-longa-e-aleatoria
DATABASE_URL=postgresql+psycopg://usuario:senha@localhost:5432/gbcertifica_homolog
DOCUMENTS_ROOT=storage/documentos
TENANT_NAME=Conta Principal
TENANT_SLUG=conta-principal
ADMIN_NOME=Administrador
ADMIN_EMAIL=admin@seudominio.com.br
ADMIN_PASSWORD=uma-senha-inicial-forte
```

Quando a senha do PostgreSQL tiver `@`, use `%40` na URL.

Para recuperação de senha, configure também:

```env
APP_BASE_URL=http://127.0.0.1:5000
SMTP_HOST=smtp.seuprovedor.com.br
SMTP_PORT=587
SMTP_USER=nao-responda@seudominio.com.br
SMTP_PASSWORD=senha-do-email
SMTP_USE_TLS=true
MAIL_FROM=nao-responda@seudominio.com.br
```

Se os conversores não forem detectados automaticamente:

```env
LIBREOFFICE_PATH=C:/Program Files/LibreOffice/program/soffice.exe
PDFTOPPM_PATH=C:/poppler/Library/bin/pdftoppm.exe
```

## Atualizar o banco

Execute:

```powershell
python criar_banco.py
```

O script não apaga empresas, funcionários ou emissões. Ele cria as tabelas de
contas, usuários, auditoria e tokens, associa os cadastros anteriores à conta
principal e cria o primeiro administrador a partir do `.env`.

Depois que o administrador for criado, remova `ADMIN_PASSWORD` do `.env`.

As tabelas atuais são:

- `tenants`;
- `usuarios`;
- `logs_auditoria`;
- `tokens_redefinicao_senha`;
- `empresas`;
- `funcionarios`;
- `emissoes`;
- `documentos_emitidos`;
- `arquivos_documentos`.

## Executar

```powershell
python run.py
```

Acesse `http://127.0.0.1:5000` e faça login com o administrador configurado.

### Atualização desta interface

Esta atualização não cria novas tabelas nem altera colunas do banco. Em uma
instalação existente, substitua os arquivos do projeto, preserve seu `.env` e
execute:

```powershell
pip install -r requirements.txt
python run.py
```

A versão definida em `APP_VERSION` é exibida na tela de login, no menu, no
rodapé, no cabeçalho interno e nos relatórios PDF.

## Testes

```powershell
pip install -r requirements-dev.txt
pytest -q
```

Os 24 testes cobrem CRUDs, templates, login, hash de senha, permissões, força
bruta, recuperação de senha, auditoria, multi-tenant, proteção de downloads,
progresso de geração e exportação dos relatórios em PDF.

## Produção na Hostinger

As configurações de Gunicorn, systemd, Nginx, HTTPS/TLS e o roteiro completo
estão em [deploy/INSTALACAO_HOSTINGER.md](deploy/INSTALACAO_HOSTINGER.md).

O PostgreSQL e o Gunicorn não devem ser publicados diretamente. O acesso
externo passa pelo Nginx com certificado HTTPS.
