# Atualização para o GBcertifica 1.2.3

Esta atualização corrige desempenho e a apresentação da tela de relatórios.

## Antes de iniciar

Mantenha o arquivo `.env` local. Ele contém dados privados e não deve ser
adicionado ao GitHub.

Esta versão não altera a estrutura do banco de dados. As tabelas e os dados da
homologação podem ser preservados.

## Configuração da versão

No `.env`, ajuste somente a versão:

```env
APP_VERSION=1.2.3
```

Não copie `.env.example` sobre o seu `.env` já configurado.

## Atualização local

Com o ambiente virtual ativo:

```powershell
pip install -r requirements.txt
python run.py
```

## Registro no GitHub

Depois de conferir a aplicação:

```powershell
git status
git add .
git commit -m "release: GBcertifica v1.2.3"
git push origin main
git tag -a v1.2.3 -m "GBcertifica 1.2.3"
git push origin v1.2.3
```

O arquivo `.gitignore` deve continuar ignorando `.env`, ambientes virtuais,
arquivos gerados e dados locais.

## Publicação futura na VPS

Na VPS, mantenha `APP_CONFIG=production`, atualize `APP_VERSION=1.2.3`, instale
as dependências e reinicie o serviço Gunicorn. O HTTPS deve permanecer ativo no
Nginx e os arquivos privados não devem ser servidos diretamente pela pasta
pública.
