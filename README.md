# Radar Público

Aplicação full stack para consulta de servidores ativos e aposentados do Poder Executivo Federal, usando os dados abertos do [dados.gov.br](https://dados.gov.br):

- [Gestão de Pessoas do Executivo Federal — Aposentados](https://dados.gov.br/dados/conjuntos-dados/gestao-de-pessoas-executivo-federal--aposentados)
- [Gestão de Pessoas do Executivo Federal — Carreiras/Cargos](https://dados.gov.br/dados/conjuntos-dados/gestao-de-pessoas-executivo-federal---carreiras--cargos)

## Stack

| Camada | Tecnologia |
|---|---|
| Banco (`db-server`) | PostgreSQL + `pg_trgm` (busca por similaridade) |
| Backend | Python + Flask + Gunicorn |
| Frontend | Aplicação web em container próprio |
| Desktop (extra) | Python + PySide6, compilado com PyInstaller |
| Orquestração | Docker Compose |

## Como executar

```bash
cd projeto
docker compose up --build
```

## Limites e ajuste por máquina

O backend lê os limites de variáveis de ambiente (padrões em `projeto/backend/server_settings.py` e `projeto/backend/app/config.py`). O `docker-compose.yml` só passa a `DATABASE_URL`; para mudar outro valor, crie `projeto/docker-compose.override.yml`, que o Compose lê sozinho:

```yaml
services:
  backend:
    environment:
      GUNICORN_WORKERS: "4"
      RATE_LIMIT_REQUESTS: "0" # desliga o limite por IP (ex.: teste de carga)
```

| Limite | Variável | Padrão | Como ajustar |
|---|---|---|---|
| Processos do Gunicorn | `GUNICORN_WORKERS` | 2 | Um por núcleo livre é um bom começo (o Postgres roda na mesma máquina). Cada worker tem o próprio pool e o próprio contador do limite por IP |
| Threads por worker | `GUNICORN_THREADS` | 4 | Buscas atendidas ao mesmo tempo = workers × threads (8); as outras esperam na fila do Gunicorn |
| Conexões por worker | `DB_POOL_MAX` | = threads | Workers × `DB_POOL_MAX` fica em no máximo 45; se passar, o backend reduz o pool ([detalhes](docs/banco.md#pool-de-conexões-do-backend)) |
| Espera por uma conexão | `DB_POOL_TIMEOUT_S` | 3 s | Depois disso, 503 `SERVIDOR_OCUPADO` com `Retry-After` |
| Tempo de cada consulta | `statement_timeout` ([detalhes](docs/banco.md#usuário-da-api)) | 5 s | A consulta é cancelada no banco e a API responde 504 `TEMPO_ESGOTADO`. Precisa ficar abaixo dos 15 s do nginx |
| Espera do nginx pelo backend | `proxy_read_timeout` em `projeto/frontend/nginx.conf` | 15 s | O nginx responde 504 `TEMPO_ESGOTADO`. Fica abaixo dos 20 s do frontend (`SEARCH_TIMEOUT_MS`) e dos 30 s do Gunicorn (`GUNICORN_TIMEOUT`) |
| Requisições por IP | `RATE_LIMIT_REQUESTS` a cada `RATE_LIMIT_WINDOW_S` | 60 a cada 60 s | Acima disso, 429 `MUITAS_REQUISICOES` com `Retry-After`. `0` desliga. `/api/health` nunca é limitado |
| Proxies na frente do backend | `TRUSTED_PROXY_HOPS` | 1 | Quantos proxies reescrevem o `X-Forwarded-For` (o nginx do frontend); `0` ignora o header |

**Limite por IP.** A tela só busca ao enviar o formulário ou trocar de página, então uma pessoa fica bem abaixo de uma busca por segundo, e um script em laço leva 429 em segundos. O contador fica na memória de cada worker (não há Redis): com 2 workers, um IP consegue de 60 a 120 requisições por minuto, conforme o Gunicorn distribui as conexões. A janela é fixa, então na virada dela passam até 2× o limite em sequência. Atrás do nginx, o IP vem do `X-Forwarded-For` que ele reescreve; quem chama a porta 5000 direto pode mandar esse header com qualquer valor e escapar do limite.

**Requisições simultâneas.** No máximo workers × threads buscas rodam ao mesmo tempo, com uma conexão do pool cada; as outras esperam na fila do Gunicorn, e cada consulta é cortada pelo `statement_timeout`. Medido com a amostra e os padrões: 2.000 buscas, 100 simultâneas pelo nginx, todas 200, p99 de 0,28 s e no máximo 8 conexões no banco. Com a tabela `servidor` travada por 12 s, 40 buscas simultâneas: 8 canceladas em 5 s, mais 8 em 10 s, e as 24 restantes respondidas assim que a trava saiu. Nesse intervalo o `/api/health` esperou 10 s na mesma fila; depois tudo voltou ao normal.

## Estrutura

```
projeto/            # pasta entregue no .zip
├── backend/        # API Flask + Gunicorn (Dockerfile)
├── frontend/       # aplicação web (Dockerfile)
├── db/             # scripts de schema, índices e carga dos dados
│   ├── init/       # executados pelo Postgres na primeira inicialização
│   └── data/       # CSVs baixados (não versionados)
└── docker-compose.yml
docs/               # relatório, sprints, dailies, burndown
scripts/            # utilitários da equipe (ex.: gerar burndown)
```

## Equipe

| Papel | GitHub | Responsabilidade principal |
|---|---|---|
| Líder técnico | [@cerfdotdev](https://github.com/cerfdotdev) | Banco de dados, Docker, relatório e burndown, revisão de PRs |
| Dev | [@joaoarenda](https://github.com/joaoarenda) | Backend / API |
| Dev | [@Alisson-dutra](https://github.com/Alisson-dutra) | Frontend web e app desktop |

## Metodologia

Scrum com 2 sprints de 1 dia (18/10/2026 e 19/10/2026), gerenciadas no GitHub Project **Radar Público**. Detalhes em [`CONTRIBUTING.md`](CONTRIBUTING.md) e [`docs/`](docs/).
