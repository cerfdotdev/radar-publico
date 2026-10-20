# Radar Público

## Repositório e acompanhamento

Todo o trabalho da equipe está no GitHub:

| | |
|---|---|
| Aplicação online | <https://radar.dok.hatzer.cloud> |
| Repositório | <https://github.com/cerfdotdev/radar-publico> |
| Histórico de commits | <https://github.com/cerfdotdev/radar-publico/commits/main> |
| Pull requests e revisões | <https://github.com/cerfdotdev/radar-publico/pulls?q=is%3Apr> |
| Issues (tarefas) | <https://github.com/cerfdotdev/radar-publico/issues?q=is%3Aissue> |
| Quadro das sprints (Project) | <https://github.com/users/cerfdotdev/projects/12> |
| CI (GitHub Actions) | <https://github.com/cerfdotdev/radar-publico/actions> |
| Relatório final | [`docs/relatorio.md`](docs/relatorio.md) (também em PDF no .zip da entrega) |

Equipe: [@cerfdotdev](https://github.com/cerfdotdev) (Carlos Rodrigues, líder técnico), [@joaoarenda](https://github.com/joaoarenda) (João Arenda, backend) e [@Alisson-dutra](https://github.com/Alisson-dutra) (Alisson Dutra, frontend e desktop).

## Sobre

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
- [`docs/carga.md`](docs/carga.md): teste de carga com os dados reais (vazão, latência, sobrecarga e limitações)
- [`docs/deploy.md`](docs/deploy.md): deploy no Dokploy com HTTPS e o deploy contínuo pelo CI
- [`docs/relatorio.md`](docs/relatorio.md): relatório final, com a divisão das tarefas, o histórico diário do GitHub e o burndown

## Limites e ajuste por máquina

O backend lê os limites de variáveis de ambiente (padrões em `projeto/backend/server_settings.py` e `projeto/backend/app/config.py`), e o nginx do frontend lê os da borda (padrões em `projeto/frontend/limites-borda.envsh`). O `docker-compose.yml` repassa a cada container as variáveis da tabela abaixo (`API_CACHE_TTL_S` aos dois) e usa as de recursos ao criar os containers; para mudar uma, preencha no `projeto/.env` e suba de novo com `docker compose up -d`. Variável vazia ou ausente usa o padrão, e um valor inválido também, com um aviso no log. Por exemplo:

```bash
GUNICORN_WORKERS=4
RATE_LIMIT_REQUESTS=0   # desliga o limite por IP do backend (ex.: teste de carga)
NGINX_LIMITE_IP=0       # desliga os limites por IP da borda (ex.: teste de carga, com todos os clientes num IP só)
API_CACHE_TTL_S=0       # desliga o cache da busca no backend e no nginx (ex.: teste de carga sem cache)
```

| Limite | Variável | Padrão | Como ajustar |
|---|---|---|---|
| Processos do Gunicorn | `GUNICORN_WORKERS` | 2 | Um por núcleo livre é um bom começo (o Postgres roda na mesma máquina). Cada worker tem o próprio pool e os próprios contadores dos limites por IP |
| Threads por worker | `GUNICORN_THREADS` | 4 | Buscas atendidas ao mesmo tempo = workers × threads (8); as outras esperam na fila do Gunicorn, que o corte da borda deixa em uma por thread. Ao mudar workers ou threads, ajuste `NGINX_LIMITE_BACKEND_SIMULTANEAS` |
| Conexões por worker | `DB_POOL_MAX` | = threads | Workers × `DB_POOL_MAX` fica em no máximo 45; se passar, o backend reduz o pool ([detalhes](docs/banco.md#pool-de-conexões-do-backend)) |
| Espera por uma conexão | `DB_POOL_TIMEOUT_S` | 3 s | Depois disso, 503 `SERVIDOR_OCUPADO` com `Retry-After` |
| Tempo de cada consulta | `DB_STATEMENT_TIMEOUT_S` ([detalhes](docs/banco.md#pool-de-conexões-do-backend)) | 5 s | A consulta é cancelada no banco e a API responde 504 `TEMPO_ESGOTADO`. Precisa ficar abaixo dos 15 s do nginx |
| Espera do nginx pelo backend | `proxy_read_timeout` em `projeto/frontend/api-admissao.conf` | 15 s | O nginx responde 504 `TEMPO_ESGOTADO`. Fica abaixo dos 20 s do frontend (`SEARCH_TIMEOUT_MS`). O `GUNICORN_TIMEOUT` (30 s) não corta requisição lenta: só reinicia worker travado ([detalhes](docs/arquitetura.md#limites-conhecidos)) |
| Requisições por IP | `RATE_LIMIT_REQUESTS` a cada `RATE_LIMIT_WINDOW_S` | 60 a cada 60 s | Acima disso, 429 `MUITAS_REQUISICOES` com `Retry-After`. `0` desliga. `/api/health` nunca é limitado |
| Buscas `similar` por IP | `RATE_LIMIT_SIMILAR_REQUESTS` a cada `RATE_LIMIT_WINDOW_S` | 10 a cada 60 s | Limite a mais, só para a busca parecida, a mais cara; ela conta também no geral. Acima disso, o mesmo 429 com `Retry-After`. `0` desliga só este |
| Requisições por IP na borda | `NGINX_LIMITE_IP_POR_S` e `NGINX_LIMITE_IP_RAJADA` | 10 por segundo, rajada de 20 | No nginx, em `/api/` (menos `/api/health`), antes do cache e do Gunicorn. Acima disso, 429 `MUITAS_REQUISICOES` com `Retry-After: 1`. `NGINX_LIMITE_IP=0` desliga os dois limites por IP da borda ([detalhes](#limites-da-borda)) |
| Requisições simultâneas por IP | `NGINX_LIMITE_IP_SIMULTANEAS` | 8 | Requisições do mesmo IP em andamento no nginx; acima disso, o mesmo 429. Metade do corte do backend: um IP sozinho não ocupa mais da metade das vagas |
| Requisições simultâneas no Gunicorn | `NGINX_LIMITE_BACKEND_SIMULTANEAS` | 16 | 2 × workers × threads: cada thread com uma busca rodando e no máximo uma esperando. Acima disso, 503 `SERVIDOR_OCUPADO` com `Retry-After: 2` na hora, ou a resposta vencida do cache. O que o cache responde não conta. `NGINX_LIMITE_BACKEND=0` desliga |
| Proxies na frente do backend | `PROXY_HOPS` | 1 | Quantos proxies reescrevem o `X-Forwarded-For` (o nginx do frontend); `0` ignora o header |
| Cache da busca e do detalhe | `API_CACHE_TTL_S` | 60 s | Quanto tempo o navegador e o nginx reusam uma resposta 200 ou 404. `0` desliga no backend e no nginx ([detalhes](#cache)) |
| Tamanho do cache do nginx | `proxy_cache_path` em `projeto/frontend/nginx.conf` | 64 MB, ~16 mil chaves | Cheio, o nginx apaga as respostas menos usadas; as que ninguém pede em 10 min também saem. Fica no volume `nginx-cache`, esvaziado a cada subida do frontend |
| Memória de cada container | `DB_SERVER_MEM_LIMIT`, `BACKEND_MEM_LIMIT`, `FRONTEND_MEM_LIMIT` | 2 GB, 512 MB, 128 MB | Acima disso, o kernel encerra o processo (o backend e o frontend voltam sozinhos, `restart: unless-stopped`). O banco precisa de folga para os dados reais ([detalhes](#recursos-dos-containers)) |
| CPU de cada container | `DB_SERVER_CPUS`, `BACKEND_CPUS`, `FRONTEND_CPUS` | 2, 2, 1 núcleos | Teto, não reserva. A soma (5) deve caber no servidor sem tirar o que os outros serviços usam |
| Processos de cada container | `DB_SERVER_PIDS_LIMIT`, `BACKEND_PIDS_LIMIT`, `FRONTEND_PIDS_LIMIT` | 128, 64, 32 | Processos e threads. Medido: ~20 no banco e no backend, 5 no frontend |
| Logs de cada container | `LOG_MAX_SIZE`, `LOG_MAX_FILE` | 3 arquivos de 10 MB | Rotação do log do Docker: uma enxurrada de requisições não enche o disco com o log de acesso |

**Limite por IP.** A tela só busca ao enviar o formulário ou trocar de página, então uma pessoa fica bem abaixo de uma busca por segundo, e um script em laço leva 429 em segundos. A busca `similar` tem um limite próprio, menor: ela chega a 0,8 s com padrões comuns, como `%MARIA%` ([teste de carga](docs/carga.md#cenário-4-similar-com-filtros-nos-dados-reais)), contra poucos milissegundos das outras, e uma pessoa faz poucas por minuto (digita o padrão, olha a lista, ajusta). Com 2 workers, um IP faz até 20 por minuto, cerca de 16 s de thread de 480 (8 threads × 60 s); só com o limite geral, eram até 120. Os contadores ficam na memória de cada worker (não há Redis): com 2 workers, um IP consegue de 60 a 120 requisições por minuto (de 10 a 20 buscas `similar`), conforme o Gunicorn distribui as conexões. A janela é fixa, então na virada dela passam até 2× o limite em sequência. Atrás do nginx, o IP vem do `X-Forwarded-For` que ele reescreve. Quem chama a porta 5000 direto pode mandar esse header com qualquer valor e escapar do limite, por isso ela só é publicada em `127.0.0.1` (`API_BIND_ADDRESS` no `.env` muda isso).

**Requisições simultâneas.** No máximo workers × threads buscas rodam ao mesmo tempo, com uma conexão do pool cada, e cada consulta é cortada pelo `statement_timeout`. O nginx manda ao Gunicorn no máximo `NGINX_LIMITE_BACKEND_SIMULTANEAS` (16) buscas ao mesmo tempo; da 17ª em diante, responde 503 `SERVIDOR_OCUPADO` na hora, em vez de deixar a busca esperar na fila até o 504 dos 15 s. Cada worker do Gunicorn aceita só uma conexão por thread (`GUNICORN_WORKER_CONNECTIONS`, padrão = threads, lido pelo código): quem espera fica numa fila só, a do kernel, e vai para o primeiro worker com thread livre. Medido com a amostra e os padrões, antes do corte: 2.000 buscas, 100 simultâneas pelo nginx, todas 200, p99 de 0,28 s e no máximo 8 conexões no banco. Na sobrecarga de 300 clientes com o backend lento, o corte trocou os 504 de 15 s por 503 em milissegundos, quadruplicou as buscas respondidas, manteve o `/api/health` respondendo e zerou o tempo de recuperação ([teste de carga](docs/carga.md#cenário-5-sobrecarga-com-o-corte-na-borda)).

### Limites da borda

O nginx do frontend é a entrada pública ([arquitetura](docs/arquitetura.md#contêineres-e-rede)) e tem os próprios limites, antes do cache e do Gunicorn:

- **Por IP, em `/api/`.** Uma pessoa faz uma requisição por ação (buscar, trocar de página), longe de 1 por segundo. Os padrões (10 por segundo, rajada de 20, 8 simultâneas) cobrem uma sala de aula ou uma rede de celular atrás do mesmo IP e seguram um script em laço: ele recebe 429 depois das primeiras 20 requisições e passa a valer no máximo 10 por segundo, rejeitadas pelo nginx em microssegundos. O limite por minuto do backend (`RATE_LIMIT_REQUESTS`, `RATE_LIMIT_SIMILAR_REQUESTS`) continua valendo para o que passa. Ao contrário do backend, a borda conta também o que o cache responde: 30 pessoas atrás do mesmo IP pedindo ao mesmo tempo uma busca que ainda não está no cache recebem algumas 429, e a nova tentativa, 1 s depois, já vem do cache. A chave é o IP real (`real-ip.conf`): atrás do Traefik, sem `NGINX_PROXY_CONFIAVEL` certo, todos os visitantes dividiriam o mesmo limite ([deploy](docs/deploy.md#2-variáveis-de-ambiente)).
- **Corte do backend.** Conta só o que vai ao Gunicorn, numa segunda camada do nginx por onde passa só o que o cache não respondeu: uma busca em cache nunca leva 503 por falta de vaga.
- **`/api/health`.** Fora dos limites por IP (o healthcheck, o CI e monitores nunca levam 429), mas com uma fila própria de 4 no corte do backend: uma enxurrada de `/api/health` não ocupa as vagas das buscas.
- **Requisições lentas ou grandes.** 10 s para mandar o cabeçalho ou o corpo e para ler a resposta, 15 s de conexão ociosa, corpo de até 1 KB (a API só tem GET) e linha da requisição e cada cabeçalho até 3 KB, abaixo dos 4.094 bytes que o Gunicorn aceita. Os valores e o porquê de cada um estão em `projeto/frontend/nginx.conf`.
- **Erros em JSON.** Toda resposta de erro gerada pelo próprio nginx vem no formato do contrato ([`docs/api.md`](docs/api.md#erros)): 400, 413, 414 e 431 `PARAMETRO_INVALIDO`, 405 `METODO_NAO_PERMITIDO` (só GET e HEAD chegam ao backend), 429, 500, 502, 503 e 504.
- **Cabeçalhos de segurança.** Além da CSP (com Trusted Types), `X-Frame-Options`, `nosniff`, `Referrer-Policy` e `Permissions-Policy`: `Strict-Transport-Security` de 1 ano com `includeSubDomains` (vale pelo HTTPS do Traefik; por HTTP o navegador ignora), `Cross-Origin-Opener-Policy` e `Cross-Origin-Resource-Policy` `same-origin` (`projeto/frontend/security-headers.conf`).

### Recursos dos containers

O servidor de produção é dividido com outros serviços, então cada container tem teto de memória, CPU e processos, e o log do Docker roda em arquivos de tamanho fixo (variáveis na tabela acima). Medido no teste de sobrecarga com a amostra: backend até ~110 MB, frontend ~20 MB, banco ~100 MB (a amostra cabe toda na memória; com os 1,5 milhão de linhas reais, o banco usa os 128 MB do `shared_buffers`, as conexões, os workers paralelos e o cache de páginas da tabela e dos índices, por isso os 2 GB). No teto de 1 núcleo, o frontend respondeu 13 mil req/s do cache na mistura do teste de carga (22 mil sem o teto) e cortou 2.500 req/s com 503 na sobrecarga.

Além disso:

- **Sem capabilities.** O backend e o frontend rodam com `cap_drop: [ALL]`. O banco fica só com as 4 que o entrypoint do Postgres usa antes de trocar para o usuário `postgres` (`DAC_READ_SEARCH`, `FOWNER`, `SETGID`, `SETUID`; o porquê no `docker-compose.yml`).
- **Sistema de arquivos só leitura** no backend e no frontend (`read_only`), com `tmpfs` só onde eles escrevem e o cache do nginx num volume. O banco continua gravável: o download da primeira carga pode cair na camada do container.
- **Redes.** O frontend fala com o backend, e o backend com o banco, em redes separadas: o nginx não alcança o Postgres.

### Cache

Os dados só mudam quando a base é recarregada, então `GET /api/servidores` e `GET /api/servidores/<id>` são guardados em dois lugares ([contrato](docs/api.md#cache)):

- **No nginx do frontend** (`proxy_cache`), compartilhado por todos os clientes da porta 8080. Só entram respostas 200 e 404; 429, 5xx e as páginas de erro do próprio nginx nunca. Buscas iguais ao mesmo tempo viram uma só ida ao backend (`proxy_cache_lock`), e o cabeçalho `X-Cache-Status` diz se a resposta veio do cache (`HIT`) ou do backend (`MISS`).
- **No navegador**, pelo `Cache-Control: public, max-age=60` e pelo `ETag` que o backend manda.

**Tempo de vida.** `API_CACHE_TTL_S` (60 s). Vencido o prazo, o nginx pergunta ao backend com o `ETag`, e o backend responde 304 sem refazer a busca, se os dados não mudaram. O `ETag` é a versão da carga: os meses de referência, quantas linhas vieram de cada um e o identificador do cluster do Postgres, que muda a cada recarga. Um navegador pode guardar uma resposta que já estava no nginx, então, depois de uma recarga, ele mostra dados antigos por até 2 × `API_CACHE_TTL_S` no pior caso.

**Tamanho.** 64 MB de respostas e cerca de 16 mil chaves (`keys_zone` de 2 MB) em `/var/cache/nginx/api`, no volume `nginx-cache` (o resto do container é só leitura). O cache fica em disco, e não num `tmpfs`: o nginx só confere o `max_size` de tempos em tempos (até 10 s), e uma enxurrada de buscas distintas encheu um `tmpfs` com 50% de folga antes disso; sem espaço, ele fechava as conexões sem resposta. Em disco, o excesso dura até a conferência seguinte. Uma página de 100 resultados tem uns 20 KB; um 404, menos de 1 KB.

**Limite por IP.** O que o nginx responde do cache não chega ao backend e não conta no limite do backend; só `MISS`, `EXPIRED` e as revalidações contam. Os limites por IP da borda contam tudo ([limites da borda](#limites-da-borda)). Um cliente acima do limite continua recebendo do cache as buscas que outros já fizeram, e um 429 nunca é guardado, porque o limite é de quem pediu e não da URL. O 304 do backend conta como qualquer requisição.

**Depois de recarregar a base.** O procedimento padrão (`docker compose down -v && docker compose up --build`) recria todos os containers, e isso já limpa tudo. Se o banco for recarregado de outro jeito:

```bash
docker compose restart backend     # relê cargos, órgãos e a versão dos dados
docker compose restart frontend    # esvazia o cache do nginx
```

O frontend esvazia o cache a cada subida (`projeto/frontend/limpar-cache.sh`), então qualquer restart basta: o volume sobrevive aos deploys, e sem isso uma resposta guardada por uma versão antiga do backend seguiria valendo, renovada pelo 304 do `ETag`, que só muda com os dados. Sem isso, as respostas antigas saem do nginx em até `API_CACHE_TTL_S`, quando ele revalida com o backend e o `ETag` não bate mais.

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
