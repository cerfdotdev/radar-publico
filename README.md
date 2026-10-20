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

O site fica em `http://localhost:8080` e a API em `http://localhost:5000/api`. A porta 5000 só aceita conexões desta máquina; de outra, use a API pelo nginx do frontend, em `http://<máquina>:8080/api`.

Senhas e limites vêm de `projeto/.env`, que não vai para o Git. Sem ele, o compose usa os valores de desenvolvimento. Para trocar algum, copie o modelo antes de subir:

```bash
cp .env.example .env
```

O app desktop (PySide6) usa a mesma API: veja [`projeto/desktop/README.md`](projeto/desktop/README.md).

## Documentação

- [`docs/arquitetura.md`](docs/arquitetura.md): contêineres, fluxo de uma busca, carga dos dados, CI e decisões
- [`docs/api.md`](docs/api.md): contrato da API
- [`docs/banco.md`](docs/banco.md): modelo, carga, índices e pool de conexões
- [`docs/dados.md`](docs/dados.md): arquivos de origem e formato
- [`docs/relatorio.md`](docs/relatorio.md): relatório final, com a divisão das tarefas, o histórico diário do GitHub e o burndown

## Limites e ajuste por máquina

O backend lê os limites de variáveis de ambiente (padrões em `projeto/backend/server_settings.py` e `projeto/backend/app/config.py`). O `docker-compose.yml` repassa ao backend as variáveis da tabela abaixo (e `API_CACHE_TTL_S` também ao frontend); para mudar uma, preencha no `projeto/.env` e suba de novo com `docker compose up -d`. Variável vazia ou ausente usa o padrão. Por exemplo:

```bash
GUNICORN_WORKERS=4
RATE_LIMIT_REQUESTS=0   # desliga o limite por IP (ex.: teste de carga)
API_CACHE_TTL_S=0       # desliga o cache da busca no backend e no nginx (ex.: teste de carga sem cache)
```

| Limite | Variável | Padrão | Como ajustar |
|---|---|---|---|
| Processos do Gunicorn | `GUNICORN_WORKERS` | 2 | Um por núcleo livre é um bom começo (o Postgres roda na mesma máquina). Cada worker tem o próprio pool e o próprio contador do limite por IP |
| Threads por worker | `GUNICORN_THREADS` | 4 | Buscas atendidas ao mesmo tempo = workers × threads (8); as outras esperam na fila do Gunicorn |
| Conexões por worker | `DB_POOL_MAX` | = threads | Workers × `DB_POOL_MAX` fica em no máximo 45; se passar, o backend reduz o pool ([detalhes](docs/banco.md#pool-de-conexões-do-backend)) |
| Espera por uma conexão | `DB_POOL_TIMEOUT_S` | 3 s | Depois disso, 503 `SERVIDOR_OCUPADO` com `Retry-After` |
| Tempo de cada consulta | `DB_STATEMENT_TIMEOUT_S` ([detalhes](docs/banco.md#pool-de-conexões-do-backend)) | 5 s | A consulta é cancelada no banco e a API responde 504 `TEMPO_ESGOTADO`. Precisa ficar abaixo dos 15 s do nginx |
| Espera do nginx pelo backend | `proxy_read_timeout` em `projeto/frontend/nginx.conf` | 15 s | O nginx responde 504 `TEMPO_ESGOTADO`. Fica abaixo dos 20 s do frontend (`SEARCH_TIMEOUT_MS`). O `GUNICORN_TIMEOUT` (30 s) não corta requisição lenta: só reinicia worker travado ([detalhes](docs/arquitetura.md#limites-conhecidos)) |
| Requisições por IP | `RATE_LIMIT_REQUESTS` a cada `RATE_LIMIT_WINDOW_S` | 60 a cada 60 s | Acima disso, 429 `MUITAS_REQUISICOES` com `Retry-After`. `0` desliga. `/api/health` nunca é limitado |
| Proxies na frente do backend | `PROXY_HOPS` | 1 | Quantos proxies reescrevem o `X-Forwarded-For` (o nginx do frontend); `0` ignora o header |
| Cache da busca e do detalhe | `API_CACHE_TTL_S` | 60 s | Quanto tempo o navegador e o nginx reusam uma resposta 200 ou 404. `0` desliga no backend e no nginx ([detalhes](#cache)) |
| Tamanho do cache do nginx | `proxy_cache_path` em `projeto/frontend/nginx.conf` | 64 MB, ~16 mil chaves | Cheio, o nginx apaga as respostas menos usadas; as que ninguém pede em 10 min também saem |

**Limite por IP.** A tela só busca ao enviar o formulário ou trocar de página, então uma pessoa fica bem abaixo de uma busca por segundo, e um script em laço leva 429 em segundos. O contador fica na memória de cada worker (não há Redis): com 2 workers, um IP consegue de 60 a 120 requisições por minuto, conforme o Gunicorn distribui as conexões. A janela é fixa, então na virada dela passam até 2× o limite em sequência. Atrás do nginx, o IP vem do `X-Forwarded-For` que ele reescreve. Quem chama a porta 5000 direto pode mandar esse header com qualquer valor e escapar do limite, por isso ela só é publicada em `127.0.0.1` (`API_BIND_ADDRESS` no `.env` muda isso).

**Requisições simultâneas.** No máximo workers × threads buscas rodam ao mesmo tempo, com uma conexão do pool cada; as outras esperam na fila do Gunicorn, e cada consulta é cortada pelo `statement_timeout`. Medido com a amostra e os padrões: 2.000 buscas, 100 simultâneas pelo nginx, todas 200, p99 de 0,28 s e no máximo 8 conexões no banco. Com a tabela `servidor` travada por 12 s, 40 buscas simultâneas: 8 canceladas em 5 s, mais 8 em 10 s, e as 24 restantes respondidas assim que a trava saiu. Nesse intervalo o `/api/health` esperou 10 s na mesma fila; depois tudo voltou ao normal.

### Cache

Os dados só mudam quando a base é recarregada, então `GET /api/servidores` e `GET /api/servidores/<id>` são guardados em dois lugares ([contrato](docs/api.md#cache)):

- **No nginx do frontend** (`proxy_cache`), compartilhado por todos os clientes da porta 8080. Só entram respostas 200 e 404; 429, 5xx e as páginas de erro do próprio nginx nunca. Buscas iguais ao mesmo tempo viram uma só ida ao backend (`proxy_cache_lock`), e o cabeçalho `X-Cache-Status` diz se a resposta veio do cache (`HIT`) ou do backend (`MISS`).
- **No navegador**, pelo `Cache-Control: public, max-age=60` e pelo `ETag` que o backend manda.

**Tempo de vida.** `API_CACHE_TTL_S` (60 s). Vencido o prazo, o nginx pergunta ao backend com o `ETag`, e o backend responde 304 sem refazer a busca, se os dados não mudaram. O `ETag` é a versão da carga: os meses de referência, quantas linhas vieram de cada um e o identificador do cluster do Postgres, que muda a cada recarga. Um navegador pode guardar uma resposta que já estava no nginx, então, depois de uma recarga, ele mostra dados antigos por até 2 × `API_CACHE_TTL_S` no pior caso.

**Tamanho.** 64 MB de respostas e cerca de 16 mil chaves (`keys_zone` de 2 MB) em `/var/cache/nginx/api`, dentro do container. Uma página de 100 resultados tem uns 20 KB; um 404, menos de 1 KB.

**Limite por IP.** O que o nginx responde do cache não chega ao backend e não conta no limite; só `MISS`, `EXPIRED` e as revalidações contam. Um cliente acima do limite continua recebendo do cache as buscas que outros já fizeram, e um 429 nunca é guardado, porque o limite é de quem pediu e não da URL. O 304 do backend conta como qualquer requisição.

**Depois de recarregar a base.** O procedimento padrão (`docker compose down -v && docker compose up --build`) recria todos os containers, e isso já limpa tudo. Se o banco for recarregado de outro jeito:

```bash
docker compose restart backend                     # relê cargos, órgãos e a versão dos dados
docker compose up -d --force-recreate frontend     # esvazia o cache do nginx
```

O `restart` do frontend **não** limpa o cache: o nginx relê do disco as respostas guardadas. Sem recriar o frontend, as respostas antigas saem do nginx em até `API_CACHE_TTL_S`, quando ele revalida com o backend e o `ETag` não bate mais.

**Sem cache** (`API_CACHE_TTL_S=0`, ex.: para o teste de carga comparar): o backend responde tudo com `no-store`, sem `ETag` nem 304, e o nginx repassa tudo ao backend, sem `X-Cache-Status`. Os ids de cargo e órgão continuam na memória do worker. Medido com a amostra, 2.000 buscas em 10 URLs, 50 simultâneas pelo nginx: 3.500 req/s e 10 idas ao backend com cache; 1.250 req/s e 2.000 idas ao backend sem cache. Com cache, quem espera uma busca igual que já está no backend acorda em passos de 500 ms (fixo no nginx), por isso a primeira rajada numa URL nova leva até ~0,5 s.

## Estrutura

```
projeto/            # pasta entregue no .zip
├── backend/        # API Flask + Gunicorn (Dockerfile)
├── frontend/       # aplicação web (Dockerfile)
├── desktop/        # app PySide6 que consome a API
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

O burndown das tarefas fica em [`docs/burndown.md`](docs/burndown.md), gerado a partir das issues do Project com `python3 scripts/burndown.py`.
