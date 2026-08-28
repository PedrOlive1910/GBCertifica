# Publicação na VPS Hostinger KVM 1

Esta configuração foi dimensionada para uma VPS KVM 1. O Gunicorn inicia com
dois processos e duas threads, enquanto as conversões de documentos continuam
sendo executadas pelo LibreOffice e pelo Poppler já instalados.

Substitua `sistema.seudominio.com.br` pelo domínio real antes de publicar.

## 1. Pacotes do servidor

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx python3-venv
which python3
which libreoffice || which soffice
which pdftoppm
```

## 2. Usuário e diretório da aplicação

```bash
sudo adduser --system --group --home /opt/sistema_tst sistema_tst
sudo mkdir -p /opt/sistema_tst
sudo chown -R sistema_tst:www-data /opt/sistema_tst
```

Envie o conteúdo do projeto para `/opt/sistema_tst` e então execute:

```bash
sudo -u sistema_tst python3 -m venv /opt/sistema_tst/.venv
sudo -u sistema_tst /opt/sistema_tst/.venv/bin/pip install --upgrade pip
sudo -u sistema_tst /opt/sistema_tst/.venv/bin/pip install -r /opt/sistema_tst/requirements.txt
sudo -u sistema_tst mkdir -p /opt/sistema_tst/storage/documentos /opt/sistema_tst/instance
```

## 3. Configuração privada

Crie `/opt/sistema_tst/.env` com permissão restrita:

```env
APP_CONFIG=production
APP_VERSION=1.2.0
APP_TIMEZONE=America/Sao_Paulo
SECRET_KEY=gere-uma-chave-longa-e-aleatoria
DATABASE_URL=postgresql+psycopg://usuario:senha-codificada@localhost:5432/gbcertifica
DOCUMENTS_ROOT=/opt/sistema_tst/storage/documentos
APP_BASE_URL=https://sistema.seudominio.com.br
TENANT_NAME=Conta Principal
TENANT_SLUG=conta-principal
ADMIN_NOME=Administrador
ADMIN_EMAIL=admin@seudominio.com.br
ADMIN_PASSWORD=defina-uma-senha-inicial-forte
SESSION_TIMEOUT_MINUTES=30
MAX_LOGIN_FAILURES=5
LOGIN_BLOCK_MINUTES=15
SMTP_HOST=smtp.seuprovedor.com.br
SMTP_PORT=587
SMTP_USER=nao-responda@seudominio.com.br
SMTP_PASSWORD=senha-do-email
SMTP_USE_TLS=true
MAIL_FROM=nao-responda@seudominio.com.br
```

Proteja o arquivo e atualize o banco sem apagar os cadastros:

```bash
sudo chown sistema_tst:www-data /opt/sistema_tst/.env
sudo chmod 640 /opt/sistema_tst/.env
sudo -u sistema_tst /opt/sistema_tst/.venv/bin/python /opt/sistema_tst/criar_banco.py
```

Após o primeiro administrador ser criado, remova `ADMIN_PASSWORD` do `.env`.

## 4. Serviço Gunicorn

```bash
sudo cp /opt/sistema_tst/deploy/sistema_tst.service.example /etc/systemd/system/sistema_tst.service
sudo systemctl daemon-reload
sudo systemctl enable --now sistema_tst
sudo systemctl status sistema_tst
```

## 5. Nginx e HTTPS

Primeiro copie o arquivo e mantenha temporariamente apenas o bloco da porta 80
até o Certbot emitir o certificado:

```bash
sudo cp /opt/sistema_tst/deploy/nginx_sistema_tst.conf.example /etc/nginx/sites-available/sistema_tst
sudo ln -s /etc/nginx/sites-available/sistema_tst /etc/nginx/sites-enabled/sistema_tst
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d sistema.seudominio.com.br
```

Confirme que o certificado foi aplicado, restaure os dois blocos do arquivo de
exemplo se necessário e execute novamente `sudo nginx -t` e o reload.

## 6. Firewall e verificação

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
curl -I https://sistema.seudominio.com.br/health
sudo journalctl -u sistema_tst -n 100 --no-pager
```

O PostgreSQL e a porta 8000 não devem ser publicados diretamente na internet.
Somente as portas 80, 443 e o acesso SSH administrativo ficam expostos.
