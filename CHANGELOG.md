# Histórico de versões

## 1.2.3 — 28/08/2026

- corrigida a sobreposição entre nome da empresa e quantidade no ranking dos relatórios;
- posição, razão social e total agora ocupam colunas independentes;
- nomes extensos são limitados com reticências sem quebrar o card;
- quantidade recebeu indicador visual próprio.

## 1.2.2 — 28/08/2026

- corrigido o estouro horizontal dos filtros na tela de relatórios;
- botões dos filtros movidos para uma linha de ações independente;
- campos de empresa, documento e datas limitados à largura disponível;
- bloqueada a rolagem horizontal indevida da aplicação;
- CSS e JavaScript agora recebem a versão na URL para evitar cache antigo após atualizações.

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
