# Relatório final: Radar Público

As tabelas entre os marcadores `<!-- historico:... -->` são geradas por `scripts/historico_github.py` a partir do GitHub e do `git log`; o resto do texto é escrito à mão. Todos os horários estão no horário de Brasília.

<!-- historico:gerado -->

Gerado em 20/10/2026 12:20 (horário de Brasília) a partir do `git log` de `origin/main` (commit [`30585e6`](https://github.com/cerfdotdev/radar-publico/commit/30585e63bbd142bd5e2654e30ccf7931aeec38a8)), das issues e PRs de [cerfdotdev/radar-publico](https://github.com/cerfdotdev/radar-publico) e do [Project](https://github.com/users/cerfdotdev/projects/12). Para atualizar, rode `git fetch origin`, `python3 scripts/burndown.py` e `python3 scripts/historico_github.py` na raiz do repositório.

<!-- /historico:gerado -->

## 1. Identificação

| | |
|---|---|
| Projeto | Radar Público: consulta de servidores ativos e aposentados do Poder Executivo Federal com os dados abertos do [dados.gov.br](https://dados.gov.br) |
| Repositório | [github.com/cerfdotdev/radar-publico](https://github.com/cerfdotdev/radar-publico) |
| Quadro das sprints | GitHub Project [Radar Público](https://github.com/users/cerfdotdev/projects/12) |

| Integrante | GitHub | Papel | Responsabilidade principal |
|---|---|---|---|
| Carlos Rodrigues | [@cerfdotdev](https://github.com/cerfdotdev) | Líder técnico | Banco de dados, Docker, CI, relatório e burndown, revisão e merge dos PRs |
| João Arenda | [@joaoarenda](https://github.com/joaoarenda) | Desenvolvedor | Backend (API) |
| Alisson Dutra | [@Alisson-dutra](https://github.com/Alisson-dutra) | Desenvolvedor | Frontend web e app desktop |

### Como a equipe trabalhou

O fluxo está em [`CONTRIBUTING.md`](../CONTRIBUTING.md) e as regras do repositório em [`SECURITY.md`](../SECURITY.md):

1. Cada tarefa é uma issue no Project, com os campos Pontos (Fibonacci: 1, 2, 3, 5 e 8), Sprint e Status.
2. O integrante cria uma branch a partir da `main` com o número da issue, por exemplo `feat/9-servidores-filtros-basicos`.
3. O trabalho volta por pull request com `Closes #<issue>`, e o workflow de CI roda em todo PR.
4. Outro integrante revisa. O merge só é liberado com o check `ci-ok` verde e as conversas resolvidas. Até 20/10/2026 também era preciso a aprovação de um code owner (`.github/CODEOWNERS`).
5. A `main` só recebe mudanças por PR, pelo ruleset "Proteção da main" (criado em 18/10/2026 às 22:43): sem push direto, sem force push e sem apagar a branch. Os três primeiros commits (18/10, 22:28 a 22:34) foram feitos antes dele, direto na `main`.

O ruleset só aceita merge com commit de merge (sem squash nem rebase), então cada PR deixa um commit "Merge pull request #N" na `main`, e descarta a aprovação de um PR quando chega um commit novo (as revisões `DISMISSED` das tabelas).

## 2. Ferramentas utilizadas

| Ferramenta | Para quê |
|---|---|
| GitHub (repositório) | Código, histórico de commits e pull requests com revisão |
| GitHub Issues | Uma issue por tarefa, com responsável, e as issues de daily |
| GitHub Projects ([quadro #12](https://github.com/users/cerfdotdev/projects/12)) | Backlog e sprints, com os campos Pontos, Sprint e Status; fonte do burndown |
| GitHub Actions | CI em todo PR e push na `main` (`.github/workflows/ci.yml`), build do executável do desktop (`desktop-build.yml`) e OpenSSF Scorecard (`scorecard.yml`) |
| Dependabot | PRs semanais de atualização de actions, pip, npm, Dockerfiles e compose (`.github/dependabot.yml`) e alertas de segurança |
| Ruleset do GitHub | Proteção da `main`: só por PR, com o check `ci-ok` obrigatório |
| Secret scanning com push protection | Bloqueia push com credencial |
| Docker e Docker Compose | Os três serviços (`db-server`, `backend`, `frontend`) em `projeto/docker-compose.yml`, com um Dockerfile por serviço |
| PostgreSQL 16 com `pg_trgm` | Banco dos servidores; a extensão `pg_trgm` faz a busca por nome parecido (`projeto/db/init`) |
| Python 3.13 | Backend, app desktop e scripts da equipe |
| Flask | API HTTP do backend |
| Gunicorn | Servidor WSGI do backend, com vários workers e threads |
| psycopg e psycopg_pool | Acesso ao PostgreSQL e pool de conexões por worker |
| React, Vite e TypeScript | Frontend web: interface, build e tipagem |
| nginx | Serve o build do frontend e faz o proxy de `/api/` para o backend |
| PySide6 | Interface do app desktop |
| PyInstaller | Executável do app desktop para Linux e Windows, em modo onedir (`projeto/desktop/build.py` e o workflow `desktop-build.yml`) |
| ruff | Lint e formatação do código Python |
| bandit | Análise de segurança do código Python |
| pip-audit | Vulnerabilidades conhecidas nas dependências Python |
| pytest | Testes do backend (com PostgreSQL real e cobertura mínima de 70%), do desktop e dos scripts |
| vitest | Testes do frontend |
| oxlint | Lint do frontend |
| hadolint | Lint dos Dockerfiles |
| Grype (`anchore/scan-action`) | Vulnerabilidades nas imagens Docker |
| CodeQL | Análise estática de workflows, Python e TypeScript |
| zizmor | Auditoria de segurança dos workflows do GitHub Actions |
| OpenSSF Scorecard | Avaliação das práticas de segurança do repositório |

<!-- ferramenta do teste de carga: entra com a issue #19 -->

## 3. Sprints

| Sprint | Data | Meta |
|---|---|---|
| Sprint 1 | 18/10/2026 | Containers subindo, banco carregado e indexado, API com filtros básicos, frontend fazendo a primeira busca |
| Sprint 2 | 19/10/2026 | Similaridade, busca combinada, paginação, tratamento de erros, proteção contra sobrecarga, teste de carga, frontend completo, app desktop, relatório |

Cada sprint durou um dia. O prazo do trabalho no enunciado era 13/10/2026. O trabalho começou depois desse prazo, em 18/10/2026, e continuou em 20/10/2026, depois do fim da Sprint 2.

O backlog foi cadastrado no Project em 18/10, entre 22:30 e 22:33, a uma hora e meia do fim da Sprint 1. Por isso quase todo o trabalho planejado para a Sprint 1 foi feito na madrugada de 19/10, já na data da Sprint 2. As sessões de trabalho atravessaram a meia-noite (de 18 para 19/10 e de 19 para 20/10), e nas tabelas por dia cada uma dessas sessões aparece dividida entre dois dias.

## 4. Divisão das tarefas

O responsável planejado de cada issue está em [`scripts/responsaveis.json`](../scripts/responsaveis.json), que o `scripts/atribuir_responsaveis.sh` usou para atribuir as issues no GitHub. Pontos e sprint são os campos do Project.

### Pontos por integrante

<!-- historico:pontos -->

| Integrante | Issues pelo plano | Pontos pelo plano | Pontos atribuídos | Pontos concluídos | Concluídos dentro da sprint |
|---|--:|--:|--:|--:|--:|
| @cerfdotdev | 15 | 53 | 55 | 40 | 19 |
| @joaoarenda | 9 | 32 | 32 | 32 | 0 |
| @Alisson-dutra | 6 | 25 | 23 | 23 | 0 |

Pelo plano: responsável de cada issue em `scripts/responsaveis.json`; as issues fora do arquivo (#52, #53 e #54) contam para quem está atribuído. Atribuídos, concluídos e dentro da sprint seguem a atribuição atual no Project e são os mesmos números de [`burndown.md`](burndown.md) quando os dois são gerados juntos.

- [#23](https://github.com/cerfdotdev/radar-publico/issues/23) (Desktop: compilar com PyInstaller, 2 pts): planejada para @Alisson-dutra, atribuída a @cerfdotdev no Project.

<!-- /historico:pontos -->

### Issues de cada integrante

As issues aparecem com quem as planejou; quando a atribuição atual no Project é outra, a coluna Situação mostra a quem ela está atribuída.

<!-- historico:tarefas -->

#### @cerfdotdev: Carlos Rodrigues (Líder técnico)

| Issue | Título | Pontos | Sprint | Fechada | Como fechou | PRs | Situação |
|---|---|---|---|---|---|---|---|
| [#1](https://github.com/cerfdotdev/radar-publico/issues/1) | Daily — Sprint 1 | 1 | Sprint 1 | 20/10 12:19 | manual por @cerfdotdev | — | fechada sem conclusão (NOT_PLANNED) |
| [#2](https://github.com/cerfdotdev/radar-publico/issues/2) | Analisar dicionário de dados (Aposentados e Carreiras/Cargos) | 3 | Sprint 1 | 18/10 23:05 | pelo commit [`336684a`](https://github.com/cerfdotdev/radar-publico/commit/336684a1f1122f9f9c0db89a22a0ea7f74e209e4) | [#30](https://github.com/cerfdotdev/radar-publico/pull/30) | no prazo |
| [#3](https://github.com/cerfdotdev/radar-publico/issues/3) | Modelagem do schema PostgreSQL | 5 | Sprint 1 | 18/10 23:10 | pelo PR [#31](https://github.com/cerfdotdev/radar-publico/pull/31) | [#31](https://github.com/cerfdotdev/radar-publico/pull/31) | no prazo |
| [#4](https://github.com/cerfdotdev/radar-publico/issues/4) | Carga e tratamento dos dados (ETL) | 8 | Sprint 1 | 18/10 23:10 | pelo PR [#31](https://github.com/cerfdotdev/radar-publico/pull/31) | [#31](https://github.com/cerfdotdev/radar-publico/pull/31) | no prazo |
| [#5](https://github.com/cerfdotdev/radar-publico/issues/5) | Índices B-tree e pg_trgm para buscas | 3 | Sprint 1 | 18/10 23:10 | pelo commit [`b0c524e`](https://github.com/cerfdotdev/radar-publico/commit/b0c524eb2f5b0be3c71991345208904ac0e02398) | [#31](https://github.com/cerfdotdev/radar-publico/pull/31) | no prazo |
| [#6](https://github.com/cerfdotdev/radar-publico/issues/6) | docker-compose com db-server, backend e frontend | 3 | Sprint 1 | 20/10 10:22 | pelo PR [#51](https://github.com/cerfdotdev/radar-publico/pull/51) | [#51](https://github.com/cerfdotdev/radar-publico/pull/51) | 1 d 10 h após o fim da sprint |
| [#12](https://github.com/cerfdotdev/radar-publico/issues/12) | Daily — Sprint 2 | 1 | Sprint 2 | 20/10 12:19 | manual por @cerfdotdev | — | fechada sem conclusão (NOT_PLANNED) |
| [#19](https://github.com/cerfdotdev/radar-publico/issues/19) | Teste de carga paralela da API | 5 | Sprint 2 | em aberto | — | — | em aberto |
| [#24](https://github.com/cerfdotdev/radar-publico/issues/24) | Script de burndown a partir das issues | 3 | Sprint 2 | 20/10 11:21 | pelo PR [#57](https://github.com/cerfdotdev/radar-publico/pull/57) | [#57](https://github.com/cerfdotdev/radar-publico/pull/57) | 11 h 21 min após o fim da sprint |
| [#25](https://github.com/cerfdotdev/radar-publico/issues/25) | Relatório final | 5 | Sprint 2 | em aberto | — | — | em aberto |
| [#26](https://github.com/cerfdotdev/radar-publico/issues/26) | Sprint review e retrospectiva | 1 | Sprint 2 | em aberto | — | — | em aberto |
| [#27](https://github.com/cerfdotdev/radar-publico/issues/27) | Entrega: teste limpo e .zip da pasta projeto | 2 | Sprint 2 | em aberto | — | — | em aberto |
| [#52](https://github.com/cerfdotdev/radar-publico/issues/52) | Backend: completar o contrato da API (detalhe, similar com filtros) | 5 | Sprint 2 | 20/10 11:14 | pelo PR [#58](https://github.com/cerfdotdev/radar-publico/pull/58) | [#58](https://github.com/cerfdotdev/radar-publico/pull/58) | 11 h 14 min após o fim da sprint; adicionada após o planejamento |
| [#53](https://github.com/cerfdotdev/radar-publico/issues/53) | Docs: arquitetura do sistema (system design) | 3 | Sprint 2 | 20/10 11:18 | pelo PR [#56](https://github.com/cerfdotdev/radar-publico/pull/56) | [#56](https://github.com/cerfdotdev/radar-publico/pull/56) | 11 h 18 min após o fim da sprint; adicionada após o planejamento |
| [#54](https://github.com/cerfdotdev/radar-publico/issues/54) | Backend: cache das buscas | 5 | Sprint 2 | 20/10 12:15 | pelo PR [#59](https://github.com/cerfdotdev/radar-publico/pull/59) | [#59](https://github.com/cerfdotdev/radar-publico/pull/59) | 12 h 15 min após o fim da sprint; adicionada após o planejamento |

#### @joaoarenda: João Arenda (Backend)

| Issue | Título | Pontos | Sprint | Fechada | Como fechou | PRs | Situação |
|---|---|---|---|---|---|---|---|
| [#7](https://github.com/cerfdotdev/radar-publico/issues/7) | Backend: Dockerfile, app Flask e Gunicorn | 3 | Sprint 1 | 19/10 00:47 | pelo PR [#34](https://github.com/cerfdotdev/radar-publico/pull/34) | [#34](https://github.com/cerfdotdev/radar-publico/pull/34) | 47 min após o fim da sprint |
| [#8](https://github.com/cerfdotdev/radar-publico/issues/8) | Backend: pool de conexões e configuração por ambiente | 2 | Sprint 1 | 19/10 00:55 | pelo PR [#36](https://github.com/cerfdotdev/radar-publico/pull/36) | [#36](https://github.com/cerfdotdev/radar-publico/pull/36) | 55 min após o fim da sprint |
| [#9](https://github.com/cerfdotdev/radar-publico/issues/9) | Backend: GET /api/servidores com filtros nome, cargo, uf e orgao | 5 | Sprint 1 | 19/10 18:23 | pelo PR [#38](https://github.com/cerfdotdev/radar-publico/pull/38) | [#38](https://github.com/cerfdotdev/radar-publico/pull/38) | 18 h 23 min após o fim da sprint |
| [#13](https://github.com/cerfdotdev/radar-publico/issues/13) | Backend: busca por similaridade (?similar= e limit até 100) | 5 | Sprint 2 | 20/10 09:53 | manual por @cerfdotdev | [#44](https://github.com/cerfdotdev/radar-publico/pull/44) | 9 h 53 min após o fim da sprint; PR #44 mergeado em 19/10 22:11 |
| [#14](https://github.com/cerfdotdev/radar-publico/issues/14) | Backend: paginação e metadados | 3 | Sprint 2 | 20/10 09:53 | manual por @cerfdotdev | [#38](https://github.com/cerfdotdev/radar-publico/pull/38) | 9 h 53 min após o fim da sprint; PR #38 mergeado em 19/10 18:23 |
| [#15](https://github.com/cerfdotdev/radar-publico/issues/15) | Backend: validação de parâmetros e erros padronizados | 5 | Sprint 2 | 20/10 09:53 | manual por @cerfdotdev | [#38](https://github.com/cerfdotdev/radar-publico/pull/38) | 9 h 53 min após o fim da sprint; PR #38 mergeado em 19/10 18:23 |
| [#16](https://github.com/cerfdotdev/radar-publico/issues/16) | Backend: proteção contra SQL injection | 2 | Sprint 2 | 20/10 09:53 | manual por @cerfdotdev | [#38](https://github.com/cerfdotdev/radar-publico/pull/38) | 9 h 53 min após o fim da sprint; PR #38 mergeado em 19/10 18:23 |
| [#17](https://github.com/cerfdotdev/radar-publico/issues/17) | Backend: timeout de busca | 2 | Sprint 2 | 20/10 09:53 | manual por @cerfdotdev | [#47](https://github.com/cerfdotdev/radar-publico/pull/47) | 9 h 53 min após o fim da sprint |
| [#18](https://github.com/cerfdotdev/radar-publico/issues/18) | Backend: rate limiting e limite de concorrência | 5 | Sprint 2 | 20/10 09:53 | manual por @cerfdotdev | [#49](https://github.com/cerfdotdev/radar-publico/pull/49) | 9 h 53 min após o fim da sprint |

#### @Alisson-dutra: Alisson Dutra (Frontend e desktop)

| Issue | Título | Pontos | Sprint | Fechada | Como fechou | PRs | Situação |
|---|---|---|---|---|---|---|---|
| [#10](https://github.com/cerfdotdev/radar-publico/issues/10) | Frontend: stack, Dockerfile e proxy para a API | 3 | Sprint 1 | 19/10 01:14 | pelo PR [#37](https://github.com/cerfdotdev/radar-publico/pull/37) | [#37](https://github.com/cerfdotdev/radar-publico/pull/37) | 1 h 14 min após o fim da sprint |
| [#11](https://github.com/cerfdotdev/radar-publico/issues/11) | Frontend: identidade visual e tela de busca simples | 5 | Sprint 1 | 19/10 17:48 | pelo PR [#40](https://github.com/cerfdotdev/radar-publico/pull/40) | [#40](https://github.com/cerfdotdev/radar-publico/pull/40) | 17 h 48 min após o fim da sprint |
| [#20](https://github.com/cerfdotdev/radar-publico/issues/20) | Frontend: busca por similaridade e busca combinada | 5 | Sprint 2 | 20/10 09:53 | manual por @cerfdotdev | [#46](https://github.com/cerfdotdev/radar-publico/pull/46) | 9 h 53 min após o fim da sprint |
| [#21](https://github.com/cerfdotdev/radar-publico/issues/21) | Frontend: paginação, detalhe e estados de erro | 5 | Sprint 2 | 20/10 09:54 | pelo PR [#48](https://github.com/cerfdotdev/radar-publico/pull/48) | [#48](https://github.com/cerfdotdev/radar-publico/pull/48) | 9 h 54 min após o fim da sprint |
| [#22](https://github.com/cerfdotdev/radar-publico/issues/22) | Desktop: app PySide6 consumindo a API | 5 | Sprint 2 | 20/10 10:03 | pelo PR [#50](https://github.com/cerfdotdev/radar-publico/pull/50) | [#50](https://github.com/cerfdotdev/radar-publico/pull/50) | 10 h 03 min após o fim da sprint |
| [#23](https://github.com/cerfdotdev/radar-publico/issues/23) | Desktop: compilar com PyInstaller | 2 | Sprint 2 | 20/10 11:58 | pelo PR [#55](https://github.com/cerfdotdev/radar-publico/pull/55) | [#55](https://github.com/cerfdotdev/radar-publico/pull/55) | 11 h 58 min após o fim da sprint; atribuída a @cerfdotdev |

<!-- /historico:tarefas -->

## 5. Histórico diário do GitHub

Contagens por integrante e por dia, a partir do `git log` da `main` e da API do GitHub. A lista de cada commit, PR e revisão está em [`relatorio/historico.md`](relatorio/historico.md), com as regras de contagem.

### Resumo por integrante

<!-- historico:resumo -->

| Integrante | Papel | Commits | Merges | PRs abertos | PRs mergeados | PRs que mergeou | Revisões | Issues fechadas | Pontos concluídos |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| @cerfdotdev | Líder técnico | 58 | 46 | 14 | 12 | 25 | 14 | 12 | 40 |
| @joaoarenda | Backend | 9 | 0 | 7 | 7 | 0 | 11 | 9 | 32 |
| @Alisson-dutra | Frontend e desktop | 5 | 1 | 5 | 5 | 0 | 9 | 5 | 23 |
| automação | — | 1 | 0 | 4 | 1 | 0 | 3 | 0 | 0 |
| **Total** |  | **73** | **47** | **30** | **25** | **25** | **37** | **26** | **95** |

Commits: na main, sem os merges, que ficam na coluna Merges. PRs mergeados: os do integrante; PRs que mergeou: quem apertou o merge. Revisões: enviadas em PRs de outra pessoa, em qualquer estado. Issues fechadas: atribuídas ao integrante, com os pontos do Project.

<!-- /historico:resumo -->

### Commits por dia

<!-- historico:commits-por-dia -->

| Integrante | 18/10 (Sprint 1) | 19/10 (Sprint 2) | 20/10 (após as sprints) | Total |
|---|--:|--:|--:|--:|
| @cerfdotdev | 13 | 10 | 35 | 58 |
| @joaoarenda | 0 | 7 | 2 | 9 |
| @Alisson-dutra | 0 | 3 | 2 | 5 |
| automação | 0 | 1 | 0 | 1 |

<!-- /historico:commits-por-dia -->

### Atividade de cada integrante por dia

Horário: da primeira à última atividade do integrante no dia (commit, PR, revisão ou issue fechada).

<!-- historico:diario -->

#### @cerfdotdev: Carlos Rodrigues (Líder técnico)

| Dia | Sprint | Horário | Commits | Merges | PRs abertos | PRs mergeados | PRs que mergeou | Revisões | Issues fechadas |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|
| 18/10 | Sprint 1 | 22:28–23:10 | 13 | 4 | 4 | 4 | 4 | 0 | 4 (19 pts) |
| 19/10 | Sprint 2 | 00:01–22:11 | 10 | 15 | 3 | 2 | 9 | 8 | 0 |
| 20/10 | após as sprints | 09:20–12:19 | 35 | 27 | 7 | 6 | 12 | 6 | 8 (21 pts) |
| **Total** |  |  | **58** | **46** | **14** | **12** | **25** | **14** | **12 (40 pts)** |

#### @joaoarenda: João Arenda (Backend)

| Dia | Sprint | Horário | Commits | Merges | PRs abertos | PRs mergeados | PRs que mergeou | Revisões | Issues fechadas |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|
| 18/10 | Sprint 1 | 22:44–23:09 | 0 | 0 | 0 | 0 | 0 | 5 | 0 |
| 19/10 | Sprint 2 | 00:10–23:53 | 7 | 0 | 6 | 5 | 0 | 6 | 3 (10 pts) |
| 20/10 | após as sprints | 00:09–09:53 | 2 | 0 | 1 | 2 | 0 | 0 | 6 (22 pts) |
| **Total** |  |  | **9** | **0** | **7** | **7** | **0** | **11** | **9 (32 pts)** |

#### @Alisson-dutra: Alisson Dutra (Frontend e desktop)

| Dia | Sprint | Horário | Commits | Merges | PRs abertos | PRs mergeados | PRs que mergeou | Revisões | Issues fechadas |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|
| 18/10 | Sprint 1 | 23:10 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| 19/10 | Sprint 2 | 00:25–23:34 | 3 | 1 | 3 | 2 | 0 | 7 | 2 (8 pts) |
| 20/10 | após as sprints | 00:04–10:19 | 2 | 0 | 2 | 3 | 0 | 1 | 3 (15 pts) |
| **Total** |  |  | **5** | **1** | **5** | **5** | **0** | **9** | **5 (23 pts)** |

<!-- /historico:diario -->

### O que foi feito em cada dia

Resumo tirado dos assuntos dos commits e dos títulos dos PRs.

- **18/10 (Sprint 1), 22:28 a 23:10.** O líder criou o repositório, o pipeline de CI e segurança (PR #28), o dicionário dos dados e o contrato da API (#30), o schema, a carga e os índices do banco (#31) e um ajuste no contrato (#32). O João e o Alisson aprovaram esses PRs. As issues #2 a #5 fecharam nessa noite.
- **19/10 (Sprint 2), 00:01 a 02:21.** Continuação da noite anterior. O líder publicou o sistema visual do frontend (#33 e #35). O João abriu a base Flask com Gunicorn e Dockerfile (#34), o pool de conexões (#36) e o `GET /api/servidores` com filtros (#38). O Alisson abriu a stack do frontend (#37) e a identidade visual com a busca simples (#40). O líder revisou e fez correções nas branches desses PRs, e mergeou #34, #36 e #37. O PR #39 (smoke test com amostra) foi fechado sem merge e os commits dele entraram pelo #38.
- **19/10 (Sprint 2), 11:11.** O Dependabot abriu os PRs #41, #42 e #43.
- **19/10 (Sprint 2), 17:46 a 23:53.** Merge de #40 e #38. O João e o Alisson revisaram os PRs do Dependabot. O João fez a busca por similaridade (#44, com a correção de teste do #45, que foi mergeado na branch do #44) e começou o timeout de busca (#47). O Alisson fez a busca por similaridade no frontend (#46).
- **20/10 (após as sprints), 00:04 a 00:54.** O Alisson abriu a paginação e o detalhe (#48) e o app desktop (#50). O João abriu o rate limiting (#49).
- **20/10 (após as sprints), 09:20 a 11:58.** O líder revisou, corrigiu e mergeou #46 a #50, fechou à mão as issues #13 a #18 e #20 (09:53), cujos PRs já estavam mergeados, mergeou o compose com os limites pelo `.env` (#51, aprovado pelo Alisson) e o PR #42 do Dependabot, e fechou o #29 sem merge. Criou as issues #52, #53 e #54 (escopo adicionado) e abriu e mergeou o contrato completo da API (#58), a arquitetura (#56), o script de burndown (#57) e o executável do desktop com PyInstaller (#55, que fechou a issue #23, planejada para o Alisson).

<!-- a preencher pelo líder: o resto de 20/10 e os dias seguintes, até a entrega. -->


### Commits do líder em PRs de colegas

Na revisão, o líder fez correções direto nas branches dos PRs do João e do Alisson, além de atualizar essas branches com a `main`. Esses commits são do líder e contam para ele em todas as tabelas acima.

<!-- historico:lider -->

| PR | Autor do PR | Commits do autor | Merges do autor | Commits do líder | Merges do líder | De outros |
|---|---|--:|--:|--:|--:|--:|
| [#34](https://github.com/cerfdotdev/radar-publico/pull/34) | @joaoarenda | 1 | 0 | 1 | 1 | 0 |
| [#36](https://github.com/cerfdotdev/radar-publico/pull/36) | @joaoarenda | 1 | 0 | 1 | 1 | 0 |
| [#37](https://github.com/cerfdotdev/radar-publico/pull/37) | @Alisson-dutra | 1 | 0 | 1 | 2 | 0 |
| [#38](https://github.com/cerfdotdev/radar-publico/pull/38) | @joaoarenda | 1 | 0 | 3 | 2 | 0 |
| [#40](https://github.com/cerfdotdev/radar-publico/pull/40) | @Alisson-dutra | 1 | 0 | 2 | 0 | 0 |
| [#44](https://github.com/cerfdotdev/radar-publico/pull/44) | @joaoarenda | 1 | 0 | 0 | 0 | 0 |
| [#45](https://github.com/cerfdotdev/radar-publico/pull/45) | @joaoarenda | 2 | 0 | 0 | 0 | 0 |
| [#46](https://github.com/cerfdotdev/radar-publico/pull/46) | @Alisson-dutra | 1 | 0 | 1 | 3 | 0 |
| [#47](https://github.com/cerfdotdev/radar-publico/pull/47) | @joaoarenda | 1 | 0 | 1 | 0 | 0 |
| [#48](https://github.com/cerfdotdev/radar-publico/pull/48) | @Alisson-dutra | 1 | 1 | 1 | 2 | 0 |
| [#49](https://github.com/cerfdotdev/radar-publico/pull/49) | @joaoarenda | 2 | 0 | 2 | 1 | 0 |
| [#50](https://github.com/cerfdotdev/radar-publico/pull/50) | @Alisson-dutra | 1 | 0 | 3 | 2 | 0 |
| **Total** |  | **14** | **1** | **16** | **14** | **0** |

Commits do líder (@cerfdotdev) que entraram na main por PRs abertos por colegas: correções feitas na revisão, na própria branch do PR. Merges: atualizações da branch com a main ou com outra branch; o merge do próprio PR não entra.

A lista de cada um desses commits está em [`relatorio/historico.md`](relatorio/historico.md#commits-do-líder-em-prs-de-colegas).

<!-- /historico:lider -->

## 6. Dailies

O `CONTRIBUTING.md` previa que cada integrante comentasse na issue de daily da sprint o que fez, o que vai fazer e os impedimentos. Nenhum registro de daily foi feito; o único comentário em cada issue é a nota de fechamento de 20/10:

<!-- historico:dailies -->

- [#1](https://github.com/cerfdotdev/radar-publico/issues/1) Daily — Sprint 1: 1 comentário (fechada em 20/10 12:19).
- [#12](https://github.com/cerfdotdev/radar-publico/issues/12) Daily — Sprint 2: 1 comentário (fechada em 20/10 12:19).
- Nas 30 issues do repositório há 2 comentários no total.

<!-- /historico:dailies -->

As dailies não aconteceram: a equipe não fez as reuniões diárias, nem registradas aqui nem fora do GitHub. Em 20/10/2026 as issues #1 e #12 foram fechadas como não planejadas, sem contar como concluídas no burndown, e a falta das dailies entra nos pontos fracos e na retrospectiva (#26). O que cada integrante fez em cada dia está nos commits, PRs e revisões da seção 5.

## 7. Burndown

![Burndown das sprints](burndown.svg)

<!-- historico:burndown -->

| Sprint | Período | Planejado | Adicionado depois | Concluído na sprint | Concluído após o fim | Em aberto |
|---|---|--:|--:|--:|--:|--:|
| Sprint 1 | 18/10 | 41 | 0 | 19 | 21 | 0 |
| Sprint 2 | 19/10 | 56 | 13 | 0 | 55 | 13 |
| **Total** |  | **97** | **13** | **19** | **76** | **13** |

Escopo atual: 108 pts. Concluídos: 95. Restantes: 13. Em pontos (campo Pontos do Project).

- Concluído = issue fechada (closedAt), não o merge do PR. Sprints: Sprint 1 em 18/10 e Sprint 2 em 19/10; fim planejado em 20/10 00:00.
- Planejado: 97 pts em 27 issues criadas até o fim da Sprint 1 (cadastradas no Project em 18/10 22:30–22:33); a linha real começa nesse cadastro.
- Escopo adicionado depois: +13 pts (#52, #53 e #54, criadas em 20/10).
- PR mergeado dentro da sprint, issue fechada só depois do fim (15 pts): #13 (PR #44 em 19/10 22:11); #14, #15 e #16 (PR #38 em 19/10 18:23). Fechadas em 20/10; o gráfico usa o fechamento.

<!-- /historico:burndown -->

O gráfico, as tabelas por responsável e a lista das issues estão em [`burndown.md`](burndown.md), gerados por `python3 scripts/burndown.py`. O gráfico e este relatório serão gerados de novo antes da entrega.

## 8. Pontos fortes

<!-- a preencher pelo líder -->

Sugestões (fatos verificáveis no repositório):

- Todo o código entrou por pull request desde o ruleset de 18/10 22:43, com o CI (`ci-ok`) obrigatório. Só os três commits iniciais foram direto na `main`.
- O CI cobre lint, testes, auditoria de dependências, scan das imagens, CodeQL e auditoria dos workflows; actions fixadas por SHA, imagens por digest e ferramentas de CI com hash.
- Até 19/10 todo PR mergeado na `main` teve aprovação de outro integrante: o João aprovou os do líder e os do Alisson, e o Alisson e o líder aprovaram os do João. A partir de 20/10 os PRs dos colegas foram aprovados só pelo líder, e os PRs #56, #57 e #58 do líder entraram sem revisão.
- Cada tarefa tem issue, pontos, sprint e PR ligado, o que permite gerar o burndown e este histórico a partir dos dados.
- Documentação da API, do banco, dos dados e da arquitetura em `docs/`.

## 9. Pontos fracos

<!-- a preencher pelo líder -->

Sugestões (fatos verificáveis no repositório):

- Nenhuma issue tem comentário: as dailies não foram registradas no GitHub.
- A Sprint 1 terminou com 19 dos 41 pontos planejados fechados dentro dela, e nenhuma issue da Sprint 2 fechou dentro da Sprint 2 (tabela do burndown).
- Parte dos commits e PRs não segue o padrão de mensagens do `CONTRIBUTING.md` (ex.: commits "resolve o issue 20" e PR "Fix/issue 22").
- As issues #13 a #18 e #20 não fecharam no merge dos PRs ligados a elas; o líder as fechou à mão em 20/10 às 09:53.
- 10 dos 12 PRs mergeados dos colegas receberam commits de correção do líder antes do merge (seção 5).
- Os campos Status de #24, #52 e #53 não acompanharam o fechamento das issues (avisos em `relatorio/historico.md`).

## 10. Dificuldades

<!-- a preencher pelo líder -->

Sugestões (fatos verificáveis no repositório):

- O backlog foi cadastrado a uma hora e meia do fim da Sprint 1, e as sprints de um dia ficaram menores que o trabalho planejado.
- O trabalho passou do fim da Sprint 2 e do prazo do enunciado; o escopo cresceu em 20/10 (#52, #53 e #54).
- O PR #44 recebeu pedido de mudanças e precisou de um PR de correção de teste (#45).
- O repositorio.dados.gov.br nem sempre responde para os runners do GitHub; o CI passou a usar uma amostra sintética (`scripts/gerar_amostra.py`).

## 11. Impedimentos

<!-- a preencher pelo líder -->

Sugestões (fatos verificáveis no repositório):

- A atribuição das issues dependia de os colegas aceitarem o convite do repositório (`scripts/atribuir_responsaveis.sh`).
- Os PRs do líder precisavam da aprovação de um code owner; o João virou co-dono no `CODEOWNERS` em 18/10 para isso. Em 20/10 a aprovação obrigatória saiu, porque só o líder tinha tarefas abertas (`CONTRIBUTING.md`).

## 12. Limitações

<!-- a preencher pelo líder -->

Sugestões (fatos verificáveis no repositório):

- Os limites técnicos da aplicação estão em [`arquitetura.md`](arquitetura.md#limites-conhecidos).
- Issues em aberto na geração deste relatório:

<!-- historico:abertas -->

- [#19](https://github.com/cerfdotdev/radar-publico/issues/19) Teste de carga paralela da API: 5 pts, @cerfdotdev.
- [#25](https://github.com/cerfdotdev/radar-publico/issues/25) Relatório final: 5 pts, @cerfdotdev.
- [#26](https://github.com/cerfdotdev/radar-publico/issues/26) Sprint review e retrospectiva: 1 pt, @cerfdotdev.
- [#27](https://github.com/cerfdotdev/radar-publico/issues/27) Entrega: teste limpo e .zip da pasta projeto: 2 pts, @cerfdotdev.

<!-- /historico:abertas -->

- Limites deste histórico: os commits contam pela data de autoria e só os que estão na `main`; o GitHub não registra quem fez cada push; conversas fora do GitHub não aparecem.

## 13. Documentação

- [README](../README.md): como executar, limites e ajuste por máquina
- [`api.md`](api.md): contrato da API
- [`arquitetura.md`](arquitetura.md): contêineres, fluxo de uma busca, carga dos dados, CI e decisões
- [`banco.md`](banco.md): modelo, carga, índices e pool de conexões
- [`dados.md`](dados.md): arquivos de origem e formato
- [`burndown.md`](burndown.md): burndown das sprints
- [`relatorio/historico.md`](relatorio/historico.md): histórico completo de commits, PRs e revisões
