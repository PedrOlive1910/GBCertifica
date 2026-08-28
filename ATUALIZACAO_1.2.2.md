# Atualização para o GBcertifica 1.2.2

## 1. Atualize o projeto

Mantenha seu arquivo `.env` fora do Git e substitua os arquivos do sistema pela versão 1.2.2.

No `.env`, confirme:

```env
APP_VERSION=1.2.2
```

## 2. Atualize o banco

Esta versão adiciona o controle de troca obrigatória de senha. Com o ambiente virtual ativado, execute uma vez:

```powershell
python criar_banco.py
```

O comando preserva os dados existentes e adiciona somente a coluna necessária em `usuarios`.

## 3. Inicie a aplicação

```powershell
python run.py
```

## 4. Fluxo de recuperação

Em **Administração → Usuários**, clique em **Redefinir senha**, informe uma senha temporária forte e entregue-a ao usuário por um canal privado. No próximo login, o sistema exigirá uma senha pessoal.

## 5. Git

```powershell
git add .
git commit -m "release: GBcertifica v1.2.2"
git tag -a v1.2.2 -m "GBcertifica 1.2.2"
git push origin main
git push origin v1.2.2
```

Nunca inclua o `.env`, senhas ou chaves SMTP no commit.
