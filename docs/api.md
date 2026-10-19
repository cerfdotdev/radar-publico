# Contrato da API

Base: `http://localhost:5000/api`. Todas as respostas são JSON em UTF-8, inclusive os erros.

Este documento é o acordo entre backend e frontend. Mudou algo aqui? Abra um PR alterando este arquivo antes de mudar o código.

## `GET /api/servidores`

Busca servidores ativos e aposentados. Os filtros se combinam com **E**.

### Parâmetros

| Parâmetro | Tipo | Regra | Exemplo |
|---|---|---|---|
| `nome` | texto | Nome **exato** (sem diferenciar maiúsculas e acentos) | `nome=Maria da Silva` |
| `similar` | texto | Padrão com `%` como curinga, ordenado por semelhança. Precisa de pelo menos 3 letras fora dos `%` | `similar=%MARIA%SILVA%` |
| `limit` | inteiro | Só com `similar`. Máximo de resultados, de 1 a 100. Padrão 100 | `limit=50` |
| `cargo` | texto | Parte do nome do cargo (contém) | `cargo=professor` |
| `orgao` | texto | Parte do nome ou a sigla do órgão | `orgao=saude` ou `orgao=INSS` |
| `uf` | texto | Sigla de uma das 27 UFs. **Só ativos têm UF** | `uf=DF` |
| `situacao` | texto | `ativo`, `aposentado` ou `todos`. Padrão `todos` | `situacao=ativo` |
| `page` | inteiro | Página, a partir de 1. Padrão 1 | `page=2` |
| `per_page` | inteiro | Itens por página, de 1 a 100. Padrão 20 | `per_page=50` |

Regras:

- Pelo menos um filtro entre `nome`, `similar`, `cargo`, `orgao` e `uf` é obrigatório.
- `nome` e `similar` não podem ser usados juntos.
- Textos: de 2 a 100 caracteres, sem `--`. Em `nome` e `similar`: só letras, espaços, `'`, `.` e `-` (e `%` em `similar`). Em `cargo` e `orgao`: também dígitos, `/`, `(` e `)`. A entrada é convertida para maiúsculas e sem acentos antes da busca.
- Parâmetro desconhecido é erro, não é ignorado.
- Ordenação: por `nome` e depois `id`; com `similar`, pela semelhança (maior primeiro).

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
    "page": 1,
    "per_page": 20,
    "total_pages": 1
  }
}
```

- `valor`: remuneração (ativos) ou valor da aposentadoria (aposentados), em reais, como número.
- `sigla_orgao` só existe para aposentados; `uf` só para ativos. O campo ausente na fonte vem `null`.
- Com `similar`, cada item também traz `"similaridade": 0.82` (de 0 a 1), e `total` é no máximo `limit`.

Se `total` for 1, o frontend mostra o detalhe direto; se for maior, mostra a lista paginada.

## `GET /api/servidores/<id>`

Detalhe de um servidor. Além dos campos da lista:

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

Para ativos, os campos de aposentadoria vêm `null` e `codigo_carreira` é preenchido. Datas no formato ISO `AAAA-MM-DD`.

## Listas auxiliares

Para preencher selects e autocomplete no frontend.

| Rota | Resposta |
|---|---|
| `GET /api/ufs` | `{"data": ["AC", "AL", ...]}` |
| `GET /api/orgaos?q=<texto>` | `{"data": [{"id": 1, "nome": "...", "sigla": "MS"}]}` (até 20) |
| `GET /api/cargos?q=<texto>` | `{"data": [{"id": 1, "nome": "..."}]}` (até 20) |
| `GET /api/health` | `{"status": "ok"}`, sem tocar no banco |

## Erros

Todo erro tem o formato:

```json
{ "error": { "code": "UF_INVALIDA", "message": "UF 'XX' não existe. Use uma das 27 siglas." } }
```

| HTTP | `code` | Quando |
|---|---|---|
| 400 | `PARAMETRO_DESCONHECIDO` | Parâmetro fora da lista |
| 400 | `PARAMETRO_INVALIDO` | Texto vazio, curto, longo ou com caracteres proibidos; número fora da faixa; `nome` com `similar` |
| 400 | `FILTRO_OBRIGATORIO` | Nenhum filtro informado |
| 400 | `UF_INVALIDA` | `uf` não é uma das 27 siglas |
| 404 | `CARGO_NAO_ENCONTRADO` | Nenhum cargo corresponde a `cargo` |
| 404 | `ORGAO_NAO_ENCONTRADO` | Nenhum órgão corresponde a `orgao` |
| 404 | `NAO_ENCONTRADO` | Filtros válidos, mas nenhum servidor encontrado (ex.: nome inexistente) |
| 404 | `PAGINA_INEXISTENTE` | `page` maior que `total_pages` |
| 404 | `ROTA_INEXISTENTE` | URL que não existe |
| 405 | `METODO_NAO_PERMITIDO` | Método diferente de GET |
| 429 | `MUITAS_REQUISICOES` | Limite de requisições por IP excedido; vem com o header `Retry-After` |
| 503 | `SERVIDOR_OCUPADO` | Limite de buscas simultâneas atingido; vem com `Retry-After` |
| 504 | `TEMPO_ESGOTADO` | A busca passou do tempo limite no banco |
| 500 | `ERRO_INTERNO` | Erro inesperado (sem detalhes internos na mensagem) |

Tentativas de SQL injection não têm código próprio: os valores nunca entram no SQL (consultas parametrizadas), e entradas com `;`, `--`, `/*` ou qualquer caractere fora da lista permitida já são recusadas com `PARAMETRO_INVALIDO`.

## Exemplos do enunciado

```
GET /api/servidores?cargo=professor
GET /api/servidores?uf=RJ
GET /api/servidores?orgao=INSS
GET /api/servidores?nome=JOSE CARLOS DA SILVA&cargo=agente&uf=DF
GET /api/servidores?similar=%JOSE%SILVA%&limit=100
```
