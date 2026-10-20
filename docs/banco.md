# Banco de dados

## Modelo

```
orgao (id, nome UNIQUE, sigla)          cargo (id, nome UNIQUE)
   ▲                                       ▲
   │ orgao_id                              │ cargo_id (NULL em 65 aposentados)
   └──────────── servidor ─────────────────┘
       id, nome, situacao ('ativo' | 'aposentado'), uf (só ativos), valor,
       codigo_carreira (só ativos),
       tipo_aposentadoria, fundamento_legal, portaria,
       data_aposentadoria, forma_ingresso, data_ingresso (só aposentados),
       referencia ('2026-08' ou '2026-05')
```

Órgãos e cargos ficam em tabelas próprias porque se repetem milhares de vezes e são buscados por "contém". Ativos e aposentados ficam na mesma tabela `servidor`, porque a API busca os dois juntos; os campos que só existem em um dos conjuntos ficam `NULL` no outro.

## Inicialização

Os scripts de `projeto/db/init/` rodam na primeira vez que o container sobe com o volume vazio:

| Script | O que faz |
|---|---|
| `01-schema.sql` | Extensão `pg_trgm` e tabelas |
| `02-dados.sh` | Usa os arquivos de `projeto/db/data/` ou baixa do dados.gov.br (6 tentativas) |
| `03-carga.sql` | Importa os arquivos e trata os dados (ver abaixo) |
| `04-indices.sql` | Cria os índices e roda `VACUUM ANALYZE` |
| `05-usuario-api.sh` | Cria o usuário da API |

Para recarregar do zero: `docker compose down -v && docker compose up --build`.

**Amostra para testes rápidos.** `projeto/db/amostra/` tem 300 ativos e 150 aposentados fictícios, no mesmo formato dos arquivos reais (gerados por `scripts/gerar_amostra.py`). O smoke test do CI usa essa amostra, porque o repositorio.dados.gov.br nem sempre responde para os servidores do GitHub. Para usar localmente, com o volume vazio: `cp projeto/db/amostra/* projeto/db/data/` (apague depois para voltar aos dados reais). A carga leva cerca de 3 s.

**Tempo medido** (notebook de desenvolvimento, arquivos já baixados): 98 s do `up` até o banco ficar saudável. O healthcheck usa TCP, que o Postgres só abre ao fim dos scripts, então o backend não sobe com o banco vazio.

### Tratamento na carga

- Cada linha entra inteira numa tabela temporária e é quebrada em SQL, para que `;` e `"` dentro dos valores não quebrem a importação.
- Linhas de título, cabeçalho e totais (`TOTAL DA CARREIRA nnn:`, `TOTAL GERAL:`) são descartadas.
- A portaria das 123 linhas com `;` é remontada a partir dos campos do meio.
- Nomes, cargos e órgãos normalizados como a API compara a entrada do usuário: maiúsculas, sem acento e com espaços simples (a fonte tem exceções, como um cargo com "Ã" e 28 nomes com espaço duplo).
- Espaços de preenchimento removidos; vazios viram `NULL`; `1.234,56` vira número; `DDMMYYYY` vira data (datas impossíveis viram `NULL`).

Conferência após a carga: 1.092.162 ativos, 412.354 aposentados, 230 órgãos, 2.999 cargos, 27 UFs; nenhum ativo sem UF; 2 aposentados sem data de aposentadoria e 4.312 sem data de ingresso, como na fonte.

## Usuário da API

O backend conecta como `radar_api` (`POSTGRES_API_USER`), nunca como o dono do banco:

- só `SELECT`, e transações somente leitura por padrão;
- `statement_timeout` de 5 s para qualquer cliente que conecte com esse usuário (a API define o seu, ver `DB_STATEMENT_TIMEOUT_S` abaixo);
- no máximo 50 conexões, para uma sobrecarga não esgotar o Postgres.

Testado: `DELETE` falha com *read-only transaction* e `pg_sleep(6)` é cancelado por *statement timeout*.

## Pool de conexões do backend

Cada worker do Gunicorn tem seu próprio pool (`psycopg_pool`), aberto no primeiro uso, já dentro do worker. Configuração por variáveis de ambiente (padrões em `projeto/backend/app/config.py`):

| Variável | Padrão | Uso |
|---|---|---|
| `DATABASE_URL` | obrigatória | Conexão do usuário `radar_api` (o compose já define) |
| `DB_POOL_MAX` | = `GUNICORN_THREADS` (4) | Conexões por worker; uma por thread |
| `DB_POOL_MIN` | 1 | Conexões mantidas abertas por worker |
| `DB_POOL_TIMEOUT_S` | 3 | Espera por uma conexão livre; depois disso a API responde 503 `SERVIDOR_OCUPADO` |
| `DB_STATEMENT_TIMEOUT_S` | 5 | Tempo máximo de cada consulta (`statement_timeout` da sessão); a consulta é cancelada no banco e a API responde 504 `TEMPO_ESGOTADO` |
| `DB_CONNECT_TIMEOUT_S` | 5 | Tempo máximo para abrir uma conexão nova |

Workers × `DB_POOL_MAX` nunca passa de 45 (o limite de 50 do usuário menos uma folga): se a configuração pedir mais, o pool de cada worker é reduzido e um aviso vai para o log. Conexões quebradas (ex.: banco reiniciado) são descartadas e trocadas antes de serem entregues.

O backend define o próprio `statement_timeout` em cada conexão nova do pool, em vez de depender só do usuário do banco: o 504 funciona com qualquer usuário na `DATABASE_URL` (os testes do CI conectam como `radar`, que não tem timeout), e as `options` que vierem na URL são mantidas. O valor da sessão vale sobre o do usuário `radar_api`.

O limite é por consulta, e os tempos ficam em ordem: 5 s no banco < 15 s do nginx (`proxy_read_timeout`) < 20 s do frontend < 30 s do Gunicorn. Uma busca faz até 4 consultas (cargo, órgão, contagem e página) e pode esperar até 3 s por uma conexão; se ela somar mais de 15 s, quem responde 504 `TEMPO_ESGOTADO` é o nginx.

## Índices e desempenho

| Índice | Para |
|---|---|
| `servidor (nome, id)` | nome exato e ordenação padrão |
| GIN trigram em `servidor.nome` | `similar` com `%` |
| `servidor (cargo_id, nome, id)`, `(orgao_id, nome, id)`, `(uf, nome, id)` | filtros já na ordem da listagem |
| GIN trigram em `cargo.nome` e `orgao.nome`, `upper(orgao.sigla)` | resolver `cargo`/`orgao` por "contém" ou sigla |

`EXPLAIN ANALYZE` dos exemplos do enunciado, com cache quente:

| Consulta | Plano | Tempo |
|---|---|---|
| `uf=RJ`, página 1 | Index Only Scan em `(uf, nome, id)` | 0,2 ms |
| `orgao=INSS`, página 1 (id já resolvido) | Index Only Scan em `(orgao_id, nome, id)` | 0,2 ms |
| `cargo=professor` (42 cargos), página 1 | Index Scan em `(nome, id)` | 0,6 ms |
| `nome` exato + `cargo` + `uf=DF` | Index Scan em `(uf, nome, id)` | 0,7 ms |
| `similar=MARIA%SOUZA` | Bitmap Index Scan no trigram | 66 ms |
| `similar=%JOSE%SILVA%` (11.774 candidatos) | Bitmap Index Scan no trigram | 144 ms |
| total exato de `cargo=professor` (266 mil linhas) | Index Only Scan | 778 ms |
| total limitado a 10.001 linhas | Index Only Scan | 57 ms |
| `uf=DF`, página 5.000 (`OFFSET 99980`) | Index Only Scan | 289 ms |

Conclusões para o backend:

1. **Resolva os ids de `cargo` e `orgao` antes** (`SELECT id FROM cargo WHERE nome LIKE ...`) e passe como `= ANY(%s)` (ou `= %s` quando for um id só). Com subconsulta no `IN`, o Postgres não sabe quantos ids vêm e `orgao=INSS` leva 536 ms em vez de 0,2 ms.
   Para órgãos e cargos raros (1 a 20 vínculos), as estatísticas padrão estimavam ~1.000 linhas e o planejador percorria o índice de nome inteiro: 1,5 a 2 s por consulta. O `04-indices.sql` aumenta as estatísticas de `orgao_id` e `cargo_id` (`SET STATISTICS 1000/3000`) e essas buscas caem para 4 a 20 ms.
2. **Não conte tudo**: conte no máximo 10.001 linhas (`SELECT count(*) FROM (... LIMIT 10001)`). Contagem exata em filtros amplos custa até 0,8 s por requisição.
3. **Limite a navegação** aos primeiros 10.000 resultados, porque `OFFSET` grande lê todas as linhas anteriores.
