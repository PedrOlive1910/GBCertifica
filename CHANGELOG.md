# Histórico de versões

## 1.2.2 — 28/08/2026

- recuperação pública por e-mail temporariamente substituída pelo atendimento do administrador;
- criada uma ação administrativa exclusiva para redefinir senhas;
- usuários recebem senha temporária e são obrigados a criar uma senha pessoal no próximo login;
- sessões anteriores são invalidadas automaticamente após a redefinição;
- redefinições e trocas de senha são registradas na auditoria sem armazenar senhas;
- botões de ação padronizados em verde com texto branco em todas as telas;
- tela de orientação para recuperação de acesso reformulada;
- autenticação, hashing, permissões, CSRF, auditoria e multi-tenant preservados.

## 1.2.1 — 28/08/2026

- carregamento automático de coleções grandes removido das requisições comuns;
- usuário autenticado deixa de carregar logs, tokens, empresas, emissões e arquivos sem necessidade;
- consultas relacionadas passam a ser carregadas de forma explícita apenas nas telas que as utilizam;
- consulta de indicadores dos relatórios consolidada e contagem duplicada removida;
- tela de relatórios corrigida para desktop, tablet e celular;
- filtros, tabela, ações e paginação do relatório reorganizados;
- autenticação, permissões, multi-tenant, CSRF e auditoria preservados.

## 1.2.0 — 27/08/2026

- identidade do produto atualizada para GBcertifica;
- tela de login reformulada e simplificada;
- cabeçalho interno e menu de perfil redesenhados;
- páginas 403, 404 e 500 modernizadas com ícones e orientações claras;
- área de assinaturas do certificado NR-06 reorganizada;
- realces de edição removidos dos modelos de documentos;
- linhas de dados dos relatórios PDF normalizadas para fundo branco;
- versão central da aplicação atualizada para 1.2.0;
- proteções de autenticação, autorização, CSRF, multi-tenant e auditoria preservadas.
