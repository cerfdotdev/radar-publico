# Teste de carga da API

Cenários de carga paralela com o k6 contra a stack do compose com os **dados reais** (1.504.516 vínculos: 1.092.162 ativos de 08/2026 e 412.354 aposentados de 05/2026). Os scripts ficam em [`scripts/carga/`](../scripts/carga/), e os resumos de cada execução em [`docs/carga/`](carga/). Medido em 20/10/2026. Por causa do prazo, cada execução durou cerca de 60 s, a uma concorrência só por cenário.

## Máquina e configuração

| Item | Valor |
|---|---|
| CPU | AMD Ryzen 5 5600GT, 6 núcleos e 12 threads |
| Memória | 31 GiB |
| Sistema | Ubuntu 24.04.4 LTS, Docker 29.6.2, Compose v5.3.1 |
| k6 | v2.3.0, `grafana/k6@sha256:9c2dee7f8ed74d317e4027c06a10f169b625638189de8d4555d0b3486a5aeb34`, rodando na mesma máquina com `--network host` |
| Stack | `main` em 30585e6, com os padrões: 2 workers × 4 threads, pool de 4 por worker, `statement_timeout` de 5 s, nginx com 15 s |
| Carga da máquina | Só a stack e o k6. O load average foi de 1,4 antes da primeira execução a 16,6 no pico da sobrecarga |

Como o k6 roda na mesma máquina, ele divide a CPU com o Postgres. Os números são um piso do que a stack aguenta, e não uma medida de produção.

## Como reproduzir

```bash
cd projeto
# .env com os limites do cenário (ex.: RATE_LIMIT_REQUESTS=0 e API_CACHE_TTL_S=0). Os VUs do k6
# saem todos do mesmo IP: NGINX_LIMITE_IP=0 sempre, e NGINX_LIMITE_BACKEND=0 para repetir os
# cenários 1 a 3 como foram medidos, antes do corte da borda (cenário 5).
docker compose up -d --build --wait
# ao trocar uma variável: recria o backend e o frontend (isso também esvazia o cache do nginx)
docker compose up -d --force-recreate --wait backend frontend
cd ..

scripts/carga/rodar.sh mistura mistura-cache-off VUS=50 DURACAO=60s   # cenário 1
scripts/carga/rodar.sh sobrecarga sobrecarga-300 VUS=300 DURACAO_S=60 # cenário 2
scripts/carga/rodar.sh limite-ip limite-ip                           # cenário 3
docker compose -f projeto/docker-compose.yml exec -T db-server \
  psql -U radar -d radar < scripts/carga/explain_similar.sql         # cenário 4
```

`rodar.sh` usa o k6 da imagem fixada e grava `docs/carga/<nome>.json` (resumo) e `<nome>-console.log`. Na sobrecarga, também amostra a cada segundo as conexões do `radar_api` no `pg_stat_activity` e o estado do container do backend (`<nome>-monitor.csv`), e calcula a recuperação pelas sondas. `ALVO=http://localhost:5000/api` testa direto no backend.

| Arquivo | Conteúdo |
|---|---|
| `consultas.js` | Mistura de consultas, requisição com tags por tipo e o resumo |
| `mistura.js` | Cenário 1 |
| `sobrecarga.js` | Cenário 2 |
| `limite_ip.js` | Cenário 3 |
| `explain_similar.sql` | Cenário 4 |

O k6 não faz pausa entre as requisições: cada VU é uma requisição em andamento, e o tempo limite de cada uma é de 20 s, o mesmo do site (`SEARCH_TIMEOUT_MS`).

## Cenário 1: mistura realista, com e sem cache

`RATE_LIMIT_REQUESTS=0`, 50 VUs pelo nginx (porta 8080), 10 s de subida, 60 s estáveis e 5 s de descida. A mistura cobre os exemplos do enunciado:

| Tipo | Peso | Exemplo |
|---|---|---|
| `cargo` | 20% | `cargo=professor&page=3`, entre 13 cargos e as páginas 1 a 10 |
| `uf` | 15% | `uf=RJ`, entre as 27 UFs |
| `orgao` | 15% | `orgao=INSS`, `orgao=saude` |
| `nome_cargo_uf` | 10% | `nome=JOSE CARLOS DA SILVA&cargo=agente&uf=DF` (quase sempre 404) |
| `similar` | 15% | `similar=%MARIA%SILVA%&limit=100`, inclusive `"%MARIA%DA%SILVA%"` com aspas |
| `similar_filtro` | 10% | `similar=%SOUZA%&uf=BA&limit=20` ou com `cargo` |
| `pagina_funda` | 10% | `uf=SP&page=100..500&per_page=20` |
| `detalhe` | 5% | `/servidores/<id>`, com ids tirados de respostas anteriores |

| | Cache desligado (`API_CACHE_TTL_S=0`) | Cache ligado (60 s), começando frio |
|---|---|---|
| Requisições | 9.581 | 1.445.832 |
| Vazão | **128 req/s** | **19.278 req/s** |
| p50 / p95 / p99 | 297 / 880 / 1.110 ms | 1,6 / 4,8 / 7,9 ms |
| Máximo | 2.043 ms | 517 ms |
| Erros (fora 404 esperados) | 0 | 0 |
| `X-Cache-Status` | — | 99,3% `HIT`; 5.936 `MISS`, 4.082 `REVALIDATED`, 165 `EXPIRED`, 108 `UPDATING` |

Por tipo, sem cache (p50 / p95 / p99 em ms):

| Tipo | Requisições | p50 | p95 | p99 | Status |
|---|---|---|---|---|---|
| `cargo` | 1.916 | 267 | 783 | 981 | 200 |
| `uf` | 1.464 | 244 | 790 | 944 | 200 |
| `orgao` | 1.331 | 250 | 778 | 968 | 200 |
| `nome_cargo_uf` | 995 | 244 | 775 | 947 | 93 × 200, 902 × 404 |
| `similar` | 1.476 | 534 | 1.127 | 1.442 | 200 |
| `similar_filtro` | 942 | 313 | 825 | 1.027 | 200 |
| `pagina_funda` | 989 | 244 | 782 | 945 | 200 |
| `detalhe` | 468 | 270 | 749 | 899 | 200 |

Sozinhas, essas buscas levam de 2 a 50 ms (`similar` amplo, de 100 a 250 ms). Com 50 em andamento e só 8 threads, a maior parte do tempo é fila no Gunicorn, igual para todos os tipos, e o `similar` soma o próprio custo. Com cache, o nginx responde quase tudo sem ir ao backend. Os máximos perto de 500 ms são o passo fixo do `proxy_cache_lock`, já descrito em [arquitetura](arquitetura.md#limites-conhecidos).

## Cenário 2: sobrecarga

Cache desligado e `RATE_LIMIT_REQUESTS=0` (o pior caso), pelo nginx. São 15 s só com sondas, depois 300 VUs (37 vezes as 8 threads) em 5 s, mantidos por 60 s e cortados de uma vez, e 45 s de observação. A carga é metade `similar` caro (`%A%A%A%`, `%A%E%I%`, `%MAR%`, `%ANA%`, `%MARIA%`...) e metade página funda de cargo amplo (`cargo=de`, `cargo=professor`, páginas 50 a 100 com `per_page=100`). As sondas fazem `GET /api/health` e uma busca simples por UF, 2 vezes por segundo.

| Tipo | Requisições | 200 | 504 | p50 |
|---|---|---|---|---|
| `pesada_similar` | 636 | 61 | 575 | 15.001 ms |
| `pesada_pagina` | 601 | 74 | 527 | 15.001 ms |
| `sonda_health` | 134 | 61 | 73 | 15.001 ms |
| `sonda_busca` | 134 | 64 | 70 | 15.000 ms |

| Sonda | Antes (p50 / máx) | Durante (p50 / máx) | Depois (p50 / máx) |
|---|---|---|---|
| `/api/health` | 1 / 2 ms | 15.002 / 15.014 ms | 15.001 / 15.011 ms |
| `uf=...` | 4 / 6 ms | 15.002 / 15.017 ms | 6 / 15.014 ms |

- **Nada caiu.** Os três containers terminaram `running`, com 0 reinícios e sem OOM. Nenhum 500, 502 ou 503, e nenhum tempo esgotado no k6: todo cliente recebeu resposta em até 15 s.
- **Os 504 vieram do nginx**, aos 15 s (`proxy_read_timeout`). O p50 de 15.001 ms mostra que quase todas as requisições esperaram na fila do Gunicorn até o nginx desistir, e não que o banco cancelou a consulta aos 5 s.
- **Banco dentro do orçamento.** No máximo 8 conexões do `radar_api`, as 8 ativas, de 45 possíveis, mais até 7 workers paralelos do Postgres.
- **Health.** O `/api/health` esperou na mesma fila e levou 504 em 73 de 134 sondas. O healthcheck do container desiste em 3 s, então o backend ficou `unhealthy` em 48 das 131 amostras, mas continuou rodando: o Docker não reinicia container `unhealthy`.
- **Recuperação: mais de 45 s.** No fim da janela de 45 s, as sondas que caíam num dos workers ainda levavam 504 de 15 s, e as que caíam no outro já respondiam em 5 ms. Quando o k6 abandona as requisições, o nginx fecha a conexão com o backend, mas o Gunicorn já tinha aceitado e enfileirado essas conexões e continua executando as buscas abandonadas, uma a uma. A janela não foi longa o bastante para medir quando esse worker esvaziou a fila.

## Cenário 3: limite por IP

Limite padrão (60 a cada 60 s por worker) e cache ligado, com um cliente só pela porta 8080 ([`limite-ip-console.log`](carga/limite-ip-console.log)):

| Fase | Resultado |
|---|---|
| Mesma URL 150 vezes | 1 `MISS` e 149 `HIT`, todas 200, nenhum 429: o que vem do cache não conta |
| 250 URLs distintas (`uf=SP&page=N`) | 119 × 200 e 131 × 429. **O primeiro 429 veio na 71ª**, com `Retry-After: 57` e o código `MUITAS_REQUISICOES` |
| `/api/health` entre cada uma | 250 × 200 |
| Já limitado | A URL em cache e a página 1, já pedida, vieram do cache (200 `HIT`); uma URL nova levou 429 |

A 71ª, e não a 61ª, porque o contador é por worker: as requisições se dividem entre os 2 workers, e o 429 aparece quando um deles passa de 60. O teto é de 120 por janela, como diz o README.

## Cenário 4: `similar` com filtros nos dados reais

`EXPLAIN (ANALYZE, BUFFERS)` do SQL de `SIMILAR_QUERY`, como `radar` e sem timeout, com a máquina ainda carregada logo depois do cenário 1. A saída completa está em [`explain-similar.txt`](carga/explain-similar.txt).

| Padrão | Filtro | Candidatos do índice trigram | Plano | Tempo |
|---|---|---|---|---|
| `%JOSE%SILVA%` | — | 11.796 | Bitmap Index Scan no trigram | 199 ms |
| `%JOSE%SILVA%` | `uf=RJ` | 11.796 ∩ 144.561 | BitmapAnd do trigram com `(uf, nome, id)` | 46 ms |
| `%MARIA%` | — | 187.107 | Bitmap Index Scan no trigram | 777 ms |
| `%MARIA%` | cargo contém `PROFESSOR` | 187.107 ∩ 266.082 | BitmapAnd do trigram com `(cargo_id, nome, id)` | 498 ms |
| `%ANA%` (3 letras) | — | 88.263 | Bitmap Index Scan no trigram | 387 ms |
| `%ANA%` | `uf=SP` | 88.263 ∩ 49.624 | BitmapAnd | 71 ms |
| `%A%A%A%` | — | nenhum trigrama | **Parallel Seq Scan** em `servidor` (1,08 milhão de linhas casam) | **4.100 ms** |

Os filtros entram no plano: o Postgres combina o índice trigram com os índices de UF ou cargo, e a busca fica mais rápida, não mais lenta. Isso responde à pendência do PR #58. Todos os padrões com pedaços de 3 letras ou mais ficam bem abaixo dos 5 s do `DB_STATEMENT_TIMEOUT_S`. A exceção eram os padrões cujos pedaços têm 1 ou 2 letras: eles não geram trigramas, e a busca lê a tabela inteira e calcula a `similarity()` de mais de 1 milhão de nomes. Pela API, sozinho e com a máquina parada, `%A%A%A%` levou 0,94 s (2,4 s em produção, contra 0,13 s de uma busca normal). Sob `EXPLAIN ANALYZE` e com a máquina carregada, 4,1 s: perto do corte de 5 s. Hoje a API recusa esses padrões com 400 (ver [Limitações encontradas](#limitações-encontradas)).

## Cenário 5: sobrecarga com o corte na borda

Depois deste teste, o nginx do frontend ganhou limites por IP e um corte de requisições simultâneas ao Gunicorn (`NGINX_LIMITE_BACKEND_SIMULTANEAS`, 16 = 2 × workers × threads; [README](../README.md#limites-da-borda)), e cada worker do Gunicorn passou a aceitar uma conexão por thread. O cenário 2 foi repetido antes e depois dessa mudança, na mesma máquina, em 20/10/2026:

- **Dados e lentidão.** Só a amostra sintética (`projeto/db/amostra`, 450 vínculos), em que toda busca leva milissegundos. Para ter um backend lento como o dos dados reais, um atraso de 250 ms na rede do container do banco (`tc netem`, abaixo) faz cada busca levar de 1,0 a 1,25 s, como as pesadas do cenário 2. O mesmo atraso nas duas execuções.
- **Configuração.** Cache e limites do backend desligados (`API_CACHE_TTL_S=0`, `RATE_LIMIT_REQUESTS=0`, `RATE_LIMIT_SIMILAR_REQUESTS=0`) e, depois da mudança, `NGINX_LIMITE_IP=0`, porque os 300 VUs saem do mesmo IP. O corte do backend ligado, no padrão.
- **Consultas.** As de `sobrecarga.js`, com os padrões pesados trocados por padrões que a API aceita (`%MARIA%`, `%SILVA%`, `%SANTOS%`...): desde o #68, `%A%A%A%` e afins são 400 antes do banco.
- **Antes:** a `main` em 83b7629 (com o #68). **Depois:** esta mudança. Resumos em [`sobrecarga-borda-antes.json`](carga/sobrecarga-borda-antes.json) e [`sobrecarga-borda-depois.json`](carga/sobrecarga-borda-depois.json), com os logs das sondas e o monitor do banco ao lado.

```bash
# atraso de 250 ms em tudo que o banco manda pela rede (o healthcheck dele usa o loopback)
docker run --rm --network container:<projeto>-db-server-1 --cap-add NET_ADMIN \
  --entrypoint sh postgres:16-alpine -c 'apk add -q iproute2-tc && tc qdisc add dev eth0 root netem delay 250ms'
PROJETO_COMPOSE=<projeto> scripts/carga/rodar.sh sobrecarga sobrecarga-borda-depois VUS=300 DURACAO_S=60
```

| | Antes | Depois |
|---|---|---|
| Buscas pesadas respondidas (200 ou 404) | 142 | **573** (4 vezes mais) |
| 504 do nginx aos 15 s | 1.087 das 1.229 pesadas | **0** |
| 503 `SERVIDOR_OCUPADO` | 0 | 318.238, p50 de 76 ms |
| `/api/health` durante a carga | 504 aos 15 s em 76 de 111 sondas | **200 em todas** (251), p50 de 1,0 s e máximo de 1,8 s |
| Busca simples (sonda) durante a carga | p50 de 15 s (504) | p50 de 75 ms (503, ou 200/404 em até 1,6 s) |
| Backend `unhealthy` | sim | não |
| Recuperação depois do fim da carga | ~120 s até o `/api/health` responder em milissegundos | **imediata**: a primeira sonda depois do fim já respondeu como antes da carga |
| Memória máxima (backend, frontend, banco) | 107, 21 e 96 MB | 98, 18 e 98 MB |

- **O corte devolve trabalho útil.** Antes, o Gunicorn tinha centenas de buscas na fila e executava as que o nginx já tinha abandonado aos 15 s. Depois, ele só recebe 16 por vez, todas com alguém esperando: a mesma capacidade (8 threads de ~1 s) respondeu 4 vezes mais buscas.
- **O excesso recebe resposta na hora.** Os 300 VUs do k6 não esperam entre uma requisição e outra, então cada 503 rápido virou outra requisição: daí os 319 mil pedidos. O site espera o `Retry-After` (2 s) antes de tentar de novo.
- **Health e recuperação.** O health tem uma fila própria no corte e espera, no Gunicorn, no máximo as buscas de uma rodada (~1 s aqui). Sem fila acumulada, nada sobra para drenar no fim da carga. A recuperação do `rodar.sh` (sondas abaixo de 500 ms) não serve com o atraso, em que uma busca normal leva 1 s: ela foi calculada comparando as sondas de depois com as de antes da carga.
- **CPU da borda.** No corte, o frontend chegou ao teto de 1 núcleo (`FRONTEND_CPUS`) respondendo 2.500 req/s. Na mistura do cenário 1 com cache e a amostra, 50 VUs por 30 s, ele respondeu 13 mil req/s com 1 núcleo e 22 mil sem o teto ([`mistura-cpu-1.json`](carga/mistura-cpu-1.json), [`mistura-cpu-4.json`](carga/mistura-cpu-4.json)).

## Mecanismos de segurança observados

| Mecanismo | O que se viu |
|---|---|
| Fila do Gunicorn (2 × 4 threads) | Segura a concorrência no banco: 50 ou 300 clientes viram no máximo 8 consultas ao mesmo tempo. O resto espera, sem erro |
| Orçamento do pool (45) | Nunca passou de 8 conexões do `radar_api`; o banco não ficou sem conexões |
| `proxy_read_timeout` do nginx (15 s) | Foi o que garantiu uma resposta a todos na sobrecarga: 504 `TEMPO_ESGOTADO` em vez de espera sem fim |
| `statement_timeout` (5 s) | Nenhuma consulta isolada chegou perto, a não ser `%A%A%A%` sob carga. Na sobrecarga, o limite que agiu foi o do nginx |
| Limite por IP | 429 a partir da 71ª requisição de um mesmo IP, com `Retry-After`. O health nunca é limitado, e o cache continua respondendo. Depois desta medição, a busca `similar` ganhou um limite próprio, menor (`RATE_LIMIT_SIMILAR_REQUESTS`) |
| Cache e `proxy_cache_lock` | 150 vezes mais vazão na mistura (19.278 contra 128 req/s), com 99,3% de `HIT` e p99 de 8 ms |
| Corte da borda (cenário 5) | 503 em milissegundos em vez de 504 aos 15 s, 4 vezes mais buscas respondidas, health respondendo e recuperação imediata |

## Limitações encontradas

- **Vazão sem cache.** 128 req/s com 50 clientes simultâneos e p95 de 0,9 s. Quase todo o tempo é fila: com 2 × 4 threads, só 8 buscas rodam ao mesmo tempo.
- **Colapso de vazão na sobrecarga (mitigado).** Com 300 clientes em buscas caras e sem cache, só 11% das buscas pesadas (135 de 1.237) foram respondidas com 200. O resto levou 504 do nginx aos 15 s. A API não travou nem caiu, mas fica inútil enquanto durar a carga. Com o corte da borda, o excesso leva 503 na hora, e o backend responde 4 vezes mais buscas ([cenário 5](#cenário-5-sobrecarga-com-o-corte-na-borda)).
- **Trabalho desperdiçado e recuperação lenta (mitigado).** O Gunicorn executa as buscas que o nginx ou o cliente já abandonaram. Depois do fim da carga, um dos workers ainda dava 504 ao `/api/health` e às buscas 45 s depois. A fila não tinha limite de tamanho nem descarte por tempo de espera. Com o corte da borda, ela tem no máximo uma busca por thread, e a recuperação foi imediata ([cenário 5](#cenário-5-sobrecarga-com-o-corte-na-borda)). Uma busca abandonada pelo navegador ainda roda até o fim no Gunicorn.
- **`/api/health` na mesma fila (mitigado).** Durante a sobrecarga, o health esperou 15 s, e o container ficou `unhealthy` em 48 de 131 s, sem reiniciar. Com o corte, ele espera no máximo uma rodada de buscas: 1,8 s no pior caso do cenário 5, sem `unhealthy`.
- **Fila por worker (mitigado).** Cada worker tinha a própria fila. Depois da carga, as requisições que caíam no worker livre respondiam em 5 ms, e as do outro esperavam 15 s. Agora cada worker aceita uma conexão por thread (`GUNICORN_WORKER_CONNECTIONS`), e quem espera fica na fila do kernel, comum aos dois.
- **`similar` sem trigramas (mitigado).** Padrões só com pedaços de 1 ou 2 letras (`%A%A%A%`) liam a tabela inteira: 0,9 s sozinho, 2,4 s em produção e 4,1 s sob carga, contra os 5 s do `statement_timeout`. Com 8 deles ao mesmo tempo, a fila enchia em segundos, e um IP só, dentro do limite geral (60 por minuto em cada um dos 2 workers), ocupava a maior parte das 8 threads. Agora a validação exige um trecho entre os `%` com 3 letras seguidas (`MIN_TRIGRAM_LETTERS`) e responde 400 `PARAMETRO_INVALIDO` antes do banco para `%A%A%A%`, `%AB%CD%` e `A%B%C`. E a busca `similar` ganhou um limite próprio por IP, além do geral: `RATE_LIMIT_SIMILAR_REQUESTS`, 10 a cada 60 s por worker. Continua cara uma busca válida com um trigrama muito comum (`%MARIA%`, 0,8 s): é ela que o limite próprio segura.
- **Cache só ajuda URLs repetidas.** Os 19 mil req/s dependem de 99% de `HIT`. Uma carga de URLs sempre novas tem o desempenho da coluna sem cache.
- **Medição curta.** Execuções de 60 s, a uma concorrência só, com o k6 na mesma máquina da stack. Não foram medidas a porta 5000 direta, 100 VUs nem a sobrecarga com cache ligado.
