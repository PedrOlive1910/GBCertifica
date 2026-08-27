# Sistema Web de Automação TST

Sistema Flask para cadastrar empresas e funcionários, montar emissões e gerar
automaticamente documentos de Segurança do Trabalho em DOCX, PDF e JPEG.

## Funcionalidades entregues

- Interface responsiva em tons de verde;
- Dashboard com indicadores e últimas emissões;
- CRUD de Empresas, com validação de CNPJ, busca, filtros e ativação/desativação;
- CRUD de Funcionários, com validação de CPF, empresa, função e status;
- CRUD de Emissões, com criação, edição de rascunhos, leitura, cancelamento e exclusão controlada;
- Datas sequenciais com avanço automático quando a data cair em domingo;
- Tabela dinâmica para EPIs;
- Lista dinâmica de máquinas e equipamentos da NR-12;
- Campos completos da Ordem de Serviço;
- Histórico e arquivos vinculados a cada emissão;
- Conversão DOCX para PDF com LibreOffice;
- Conversão PDF para JPEG com Poppler;
- Relatórios por empresa, período e tipo de documento;
- Proteção CSRF e validações de formulário;
- Testes automatizados.

## Modelos automáticos incluídos

Os modelos enviados pelo cliente já foram preparados com tags. Não é
necessário editar manualmente os documentos para inserir `{{ nome }}`.

- Ficha de Controle de EPI;
- Ordem de Serviço;
- Certificado NR-06;
- Certificado NR-12;
- Certificado NR-18;
- Certificado NR-35.

Eles ficam em `app/document_templates/`. O script
`scripts/preparar_templates.py` documenta como os originais foram
transformados em templates, mas não precisa ser executado para usar o sistema.

## Requisitos

- Python 3.11 ou superior;
- PostgreSQL;
- LibreOffice disponível no `PATH` como `soffice` ou `libreoffice`;
- Poppler disponível no `PATH`, incluindo `pdftoppm`.

## Instalação no Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure o `.env`:

```env
APP_CONFIG=development
SECRET_KEY=uma-chave-secreta-grande
DATABASE_URL=postgresql+psycopg://usuario:senha@localhost:5432/gbcertifica_homolog
DOCUMENTS_ROOT=storage/documentos
```

Quando a senha tiver `@`, use `%40` na URL. O `.env` não deve ser enviado
para repositórios.

## Banco de dados

Para o banco vazio já criado:

```powershell
python criar_banco.py
```

O sistema utiliza as tabelas:

- `empresas`;
- `funcionarios`;
- `emissoes`;
- `documentos_emitidos`;
- `arquivos_documentos`.

Esta versão não adicionou novas colunas ao modelo que já estava criado, por
isso não é necessário apagar as tabelas existentes.

## Executar

```powershell
python run.py
```

Acesse `http://127.0.0.1:5000`.

Fluxo recomendado:

1. Cadastre a empresa;
2. cadastre o funcionário;
3. abra **Emissões > Nova Emissão**;
4. selecione os documentos;
5. preencha EPIs, máquinas ou Ordem de Serviço quando necessário;
6. salve e confira a emissão;
7. clique em **Gerar documentos**;
8. baixe DOCX, PDF ou JPEG.

## Testes

```powershell
pip install -r requirements-dev.txt
pytest -q
```

## Migrações futuras

Se o Flask-Migrate ainda não foi inicializado, crie a linha de base uma única
vez e confira a migração antes do `stamp`:

```powershell
flask --app run.py db init
flask --app run.py db migrate -m "Estrutura inicial do Sistema TST"
flask --app run.py db stamp head
```

Nas próximas alterações de banco:

```powershell
flask --app run.py db migrate -m "Descrição da alteração"
flask --app run.py db upgrade
```

## Produção

Na VPS, configure `APP_CONFIG=production`, uma chave secreta forte e o
PostgreSQL. Exemplo de inicialização:

```bash
gunicorn --bind 127.0.0.1:8000 wsgi:app
```
