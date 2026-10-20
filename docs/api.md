# Contrato da API

Base: `http://localhost:5000/api`. Todas as respostas são JSON em UTF-8, inclusive os erros.

Este documento é o acordo entre backend e frontend. Mudou algo aqui? Abra um PR alterando este arquivo antes de mudar o código.

## `GET /api/servidores`

Busca servidores ativos e aposentados. Os filtros se combinam com **E**.

### Parâmetros

| Parâmetro | Tipo | Regra | Exemplo |
|---|---|---|---|
| `nome` | texto | Nome **exato** (sem diferenciar maiúsculas e acentos) | `nome=Maria da Silva` |
| `similar` | texto | Nome parecido: padrão `LIKE` com `%` como curinga, do nome inteiro (sem `%`, só o nome igual). Precisa de um trecho entre os `%` com pelo menos 3 letras seguidas (regra abaixo). Resultados do mais ao menos parecido (`similaridade`), sem páginas. Combina com `cargo`, `orgao`, `uf` e `situacao` | `similar=%MARIA%SILVA%` |
| `limit` | inteiro | Só com `similar`. Máximo de resultados, de 1 a 100. Padrão 100 | `limit=50` |
| `cargo` | texto | Parte do nome do cargo (contém) | `cargo=professor` |
| `orgao` | texto | Parte do nome ou a sigla do órgão | `orgao=saude` ou `orgao=INSS` |
| `uf` | texto | Sigla de uma das 27 UFs. **Só ativos têm UF** | `uf=DF` |
| `situacao` | texto | `ativo`, `aposentado` ou `todos`. Padrão `todos` | `situacao=ativo` |
| `page` | inteiro | Página, de 1 até `total_pages` (no máximo 10.000). Padrão 1. Não vale com `similar` | `page=2` |
| `per_page` | inteiro | Itens por página, de 1 a 100. Padrão 20. Não vale com `similar` | `per_page=50` |

Regras:

- Pelo menos um filtro entre `nome`, `similar`, `cargo`, `orgao` e `uf` é obrigatório.
- `nome` e `similar` não podem ser usados juntos.
- `limit` só vale com `similar`; `page` e `per_page` não valem com `similar` (a busca parecida não tem páginas, devolve até `limit` resultados). Os dois casos respondem 400 `PARAMETRO_INVALIDO`, em vez de ignorar o parâmetro.
- **`similar` precisa de um trecho com 3 letras seguidas.** Trecho é o que fica entre os `%`, com os espaços (`JOSE SILVA` é um trecho só); o espaço, o `'`, o `.` e o `-` separam as letras, e os acentos saem antes da contagem. Valem `%JOSE%SILVA%`, `MARIA%`, `%ANA%` e `%A%B%SILVA%`; `%A%A%A%`, `%AB%CD%`, `A%B%C` e `%JO SE%` respondem 400 `PARAMETRO_INVALIDO` com a mensagem "Use pelo menos um trecho com 3 letras seguidas entre os %.". Sem esse trecho, o índice trigram do nome não tem o que filtrar, e a busca lê a tabela inteira (2,4 s em produção, contra 0,13 s de uma busca normal; ver `docs/carga.md`).
- Textos: de 2 a 100 caracteres, sem `--`. Em `nome` e `similar`: só letras, espaços, `'`, `.` e `-` (e `%` em `similar`). Em `cargo` e `orgao`: também dígitos, `/`, `(`, `)` e `,`. A entrada é convertida para maiúsculas, sem acentos e com espaços simples antes da busca, como os dados na carga.
- Aspas em volta do valor são ignoradas em `nome`, `similar`, `cargo` e `orgao`, como no exemplo do enunciado: `similar="%MARIA%SILVA%"`, `similar=”%MARIA%SILVA%”` e `similar=“%MARIA%SILVA%”` valem o mesmo que `similar=%MARIA%SILVA%`. Só um par, nas duas pontas; aspas em outro lugar são caractere não permitido.
- **`%` sem codificar.** No curl ou na barra do navegador, `?similar=%MARIA%DE%BARROS%` chega com o `%` cru. A API decodifica um `%XY` só quando ele forma um caractere que ela usa (ASCII, letra acentuada ou as aspas acima), como `%25` (`%`), `%20` (espaço) e `%C3%A9` (`é`); os outros ficam como texto. Assim `%DE%BA`, que formaria um caractere de outro alfabeto, continua `%DE%BA`. Clientes que codificam o `%` como `%25` (o frontend e o desktop) não são afetados. Bytes que não são UTF-8 respondem 400, nunca 500.
- Parâmetro desconhecido é erro, não é ignorado.
- Ordenação: por `nome` e depois `id`; com `similar`, pela semelhança (maior primeiro), depois `nome` e `id`.

### Resposta `200`

```json
{
  "data": [
    {
      "id": 1048213,
      "nome": "MARIA DA SILVA",
      "situacao": "ativo",
      "cargo": "ANALISTA DE FINANCAS E CONTROLE",
      "orgao": "CONTROLADORIA-GERAL DA UNIAO",
      "sigla_orgao": null,
      "uf": "DF",
      "valor": 19090.67
    },
    {
      "id": 1503377,
      "nome": "MARIA DA SILVA SANTOS",
      "situacao": "aposentado",
      "cargo": "AGENTE ADMINISTRATIVO",
      "orgao": "MINISTERIO DA AGRICULTURA E PECUARIA",
      "sigla_orgao": "MAPA",
      "uf": null,
      "valor": 7006.78
    }
  ],
  "meta": {
    "total": 2,
    "total_exato": true,
    "page": 1,
    "per_page": 20,
    "total_pages": 1
  }
}
```

- `valor`: remuneração (ativos) ou valor da aposentadoria (aposentados), em reais, como número.
- `sigla_orgao`: sigla do órgão quando a fonte a traz (só o arquivo de aposentados tem siglas, mas elas valem para todos os vínculos do órgão; alguns órgãos não têm). `uf` só existe para ativos. O campo ausente na fonte vem `null`.
- Como aposentados não têm UF, `uf` com `situacao=aposentado` responde 404 `NAO_ENCONTRADO` sem consultar o banco.
- **Total limitado a 10.000.** Contar centenas de milhares de linhas custa até 0,8 s por requisição (ver `docs/banco.md`). Se houver mais de 10.000 resultados, `total` vem `10000`, `total_exato` vem `false` e só as páginas até o 10.000º resultado existem. O frontend deve mostrar "mais de 10.000 resultados, refine a busca".
- Com `similar`, cada item também traz `"similaridade": 0.82` (de 0 a 1, a `similarity()` do `pg_trgm` entre o nome e o padrão, com 4 casas). A resposta vem inteira, sem páginas: `meta.total` é quantos itens vieram (no máximo `limit`, não quantos nomes casam com o padrão), `total_exato` é `true`, `page` e `total_pages` são 1 e `per_page` é o `limit`. Sem nenhum nome parecido, 404 `NAO_ENCONTRADO`.

Se `total` for 1, o frontend mostra o detalhe direto; se for maior, mostra a lista paginada.

## `GET /api/servidores/<id>`

Detalhe de um vínculo, pelo `id` que a busca devolve. Além dos campos da lista:

```json
{
  "data": {
    "id": 1503377,
    "nome": "MARIA DA SILVA SANTOS",
    "situacao": "aposentado",
    "cargo": "AGENTE ADMINISTRATIVO",
    "orgao": "MINISTERIO DA AGRICULTURA E PECUARIA",
    "sigla_orgao": "MAPA",
    "uf": null,
    "valor": 7006.78,
    "codigo_carreira": null,
    "tipo_aposentadoria": "VOLUNTARIA",
    "fundamento_legal": "CF 40 III C",
    "portaria": "LEI 014600/2023, AUT.EXT.: PR PUB: DO 19JUN2023",
    "data_aposentadoria": "1990-07-02",
    "forma_ingresso": "ADMISSAO SEM CONCURSO PUBLICO",
    "data_ingresso": "1959-10-01",
    "referencia": "2026-05"
  }
}
```

Para ativos, os campos de aposentadoria vêm `null` e `codigo_carreira` é preenchido. Datas no formato ISO `AAAA-MM-DD`; `referencia` é o mês do arquivo de origem (`AAAA-MM`). Campo ausente na fonte vem `null`.

- `id` só com dígitos, de 1 a 9223372036854775807 (o `bigint` do banco). Texto, sinal, ponto ou número fora dessa faixa respondem 400 `PARAMETRO_INVALIDO` sem consultar o banco.
- `id` válido sem vínculo: 404 `NAO_ENCONTRADO`.
- A rota não tem parâmetros: qualquer um na query string responde 400 `PARAMETRO_DESCONHECIDO`.
- Conta no limite de requisições por IP, como a busca (o que o nginx responde do cache não chega ao backend e não conta; ver [Cache](#cache)).

## `GET /api/health`

`{"status": "ok"}`, sem tocar no banco. É o healthcheck do container, nunca recebe 429 e nunca vem de cache (`Cache-Control: no-store`).

## Cache

Os dados só mudam quando a base é recarregada. As respostas **200 e 404** de `GET /api/servidores` e `GET /api/servidores/<id>` podem ser reusadas pelo navegador e pelo nginx do frontend:

```
Cache-Control: public, max-age=60
ETag: "2026-05:412354+2026-08:1092162@7698757299317346338"
```

- `max-age` é `API_CACHE_TTL_S` (padrão 60 s, README).
- O `ETag` é a versão dos dados, igual em todas as respostas da mesma carga: os meses de referência, quantas linhas vieram de cada um e o identificador do cluster do Postgres (muda a cada recarga). O backend lê a versão uma vez por worker, na primeira busca ou detalhe válido.
- Com `If-None-Match` igual ao `ETag` atual (também `W/"..."`, que é como o gzip do nginx entrega, ou `*`), a resposta é **304** sem corpo, com os mesmos `Cache-Control` e `ETag`, e a busca não roda. A validação vem antes: parâmetro inválido continua 400.
- Todo o resto sai com `Cache-Control: no-store`: 400, 405, 429, 5xx, rotas inexistentes e `/api/health`.
- Com `API_CACHE_TTL_S=0`, tudo sai com `no-store`, sem `ETag` e sem 304.

Pelo nginx (porta 8080), as respostas dessas duas rotas trazem `X-Cache-Status`:

| Valor | Quer dizer |
|---|---|
| `MISS` | Não estava no cache; veio do backend (e é guardada se for 200 ou 404) |
| `HIT` | Veio do cache, sem ir ao backend |
| `EXPIRED` | Estava vencida e veio do backend |
| `REVALIDATED` | Estava vencida, o backend respondeu 304 e ela voltou a valer |
| `UPDATING` | Estava vencida e outra requisição já a está atualizando: veio a guardada |
| `STALE` | O backend falhou (fora do ar, 5xx ou tempo esgotado): veio a guardada, da mesma carga |

O que vem do cache (`HIT`, `UPDATING`, `STALE`) não chega ao backend e não conta no limite por IP. 429, 5xx e os 502/504 gerados pelo nginx nunca são guardados. Sem cache no nginx (`API_CACHE_TTL_S=0`, ou `/api/health`), o cabeçalho não aparece.

## Erros

Todo erro tem o formato:

```json
{ "error": { "code": "UF_INVALIDA", "message": "UF 'XX' não existe. Use uma das 27 siglas." } }
```

| HTTP | `code` | Quando |
|---|---|---|
| 400 | `PARAMETRO_DESCONHECIDO` | Parâmetro fora da lista |
| 400 | `PARAMETRO_INVALIDO` | Texto vazio, curto, longo ou com caracteres proibidos; `similar` sem um trecho com 3 letras seguidas; número fora da faixa; `nome` com `similar`; `limit` sem `similar`; `page` ou `per_page` com `similar`; `id` do detalhe que não é um inteiro de 1 a 9223372036854775807 |
| 400 | `FILTRO_OBRIGATORIO` | Nenhum filtro informado |
| 400 | `UF_INVALIDA` | `uf` não é uma das 27 siglas |
| 404 | `CARGO_NAO_ENCONTRADO` | Nenhum cargo corresponde a `cargo` |
| 404 | `ORGAO_NAO_ENCONTRADO` | Nenhum órgão corresponde a `orgao` |
| 404 | `NAO_ENCONTRADO` | Filtros válidos, mas nenhum servidor encontrado (ex.: nome inexistente, `uf` com `situacao=aposentado`); ou `id` do detalhe sem vínculo |
| 404 | `PAGINA_INEXISTENTE` | `page` maior que `total_pages` (inclusive além do 10.000º resultado) |
| 404 | `ROTA_INEXISTENTE` | URL que não existe |
| 405 | `METODO_NAO_PERMITIDO` | Método diferente de GET |
| 429 | `MUITAS_REQUISICOES` | Limite de requisições por IP excedido: o geral (`RATE_LIMIT_REQUESTS`, padrão 60 a cada 60 s) ou o das buscas com `similar` (`RATE_LIMIT_SIMILAR_REQUESTS`, padrão 10 a cada 60 s), que contam nos dois. Os limites são por worker do Gunicorn (README, "Limites e ajuste por máquina"). Vem com o header `Retry-After`. Nunca vem do cache |
| 503 | `SERVIDOR_OCUPADO` | O backend não conseguiu uma conexão com o banco em `DB_POOL_TIMEOUT_S` (padrão 3 s): banco fora do ar ou lento para aceitar conexões. Vem com `Retry-After`. Não é limite de buscas simultâneas: na configuração padrão o pool tem uma conexão por thread, e as buscas além das threads esperam na fila do Gunicorn (ver `docs/banco.md`) |
| 504 | `TEMPO_ESGOTADO` | A busca passou do tempo limite no banco, ou o backend não respondeu ao nginx em 15 s |
| 500 | `ERRO_INTERNO` | Erro inesperado (sem detalhes internos na mensagem) |
| 502 | `SERVIDOR_INDISPONIVEL` | Gerado pelo nginx do frontend quando o backend está fora do ar |

Tentativas de SQL injection não têm código próprio: os valores nunca entram no SQL (consultas parametrizadas), e entradas com `;`, `--`, `/*` ou qualquer caractere fora da lista permitida já são recusadas com `PARAMETRO_INVALIDO`.

## Exemplos do enunciado

```
GET /api/servidores?cargo=professor
GET /api/servidores?uf=RJ
GET /api/servidores?orgao=INSS
GET /api/servidores?nome=JOSE CARLOS DA SILVA&cargo=agente&uf=DF
GET /api/servidores?similar=%JOSE%SILVA%&limit=100
GET /api/servidores?similar="%MARIA%DA%SILVA%"&limit=100
```

Outros:

```
GET /api/servidores?similar=%MARIA%SILVA%&uf=RJ&situacao=ativo
GET /api/servidores?similar=%JOSE%SILVA%&cargo=professor&orgao=UFRJ&limit=20
GET /api/servidores/1048213
```
