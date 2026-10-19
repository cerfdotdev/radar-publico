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

**Tempo medido** (notebook de desenvolvimento, arquivos já baixados): 98 s do `up` até o banco ficar saudável. O healthcheck usa TCP, que o Postgres só abre ao fim dos scripts, então o backend não sobe com o banco vazio.

### Tratamento na carga

- Cada linha entra inteira numa tabela temporária e é quebrada em SQL, para que `;` e `"` dentro dos valores não quebrem a importação.
- Linhas de título, cabeçalho e totais (`TOTAL DA CARREIRA nnn:`, `TOTAL GERAL:`) são descartadas.
- A portaria das 123 linhas com `;` é remontada a partir dos campos do meio.
- Espaços de preenchimento removidos; vazios viram `NULL`; `1.234,56` vira número; `DDMMYYYY` vira data (datas impossíveis viram `NULL`).

Conferência após a carga: 1.092.162 ativos, 412.354 aposentados, 230 órgãos, 2.999 cargos, 27 UFs; nenhum ativo sem UF; 2 aposentados sem data de aposentadoria e 4.312 sem data de ingresso, como na fonte.

## Usuário da API

O backend conecta como `radar_api` (`POSTGRES_API_USER`), nunca como o dono do banco:

- só `SELECT`, e transações somente leitura por padrão;
- `statement_timeout` de 5 s: a consulta é cancelada no banco e a API responde 504;
- no máximo 50 conexões, para uma sobrecarga não esgotar o Postgres.

Testado: `DELETE` falha com *read-only transaction* e `pg_sleep(6)` é cancelado por *statement timeout*.

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

1. **Resolva os ids de `cargo` e `orgao` antes** (`SELECT id FROM cargo WHERE nome LIKE ...`) e passe como `= ANY(%s)`. Com subconsulta no `IN`, o Postgres não sabe quantos ids vêm e `orgao=INSS` leva 536 ms em vez de 0,2 ms.
2. **Não conte tudo**: conte no máximo 10.001 linhas (`SELECT count(*) FROM (... LIMIT 10001)`). Contagem exata em filtros amplos custa até 0,8 s por requisição.
3. **Limite a navegação** aos primeiros 10.000 resultados, porque `OFFSET` grande lê todas as linhas anteriores.
