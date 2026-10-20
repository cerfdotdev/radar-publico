# Contrato da API

Base: `http://localhost:5000/api`. Todas as respostas são JSON em UTF-8, inclusive os erros.

Este documento é o acordo entre backend e frontend. Mudou algo aqui? Abra um PR alterando este arquivo antes de mudar o código.

## `GET /api/servidores`

Busca servidores ativos e aposentados. Os filtros se combinam com **E**.

### Parâmetros

| Parâmetro | Tipo | Regra | Exemplo |
|---|---|---|---|
| `nome` | texto | Nome **exato** (sem diferenciar maiúsculas e acentos) | `nome=Maria da Silva` |
| `similar` | texto | Padrão com `%` como curinga, ordenado por semelhança. Precisa de pelo menos 3 letras fora dos `%`. **Ainda não implementado** (issue #13): por enquanto responde 400 `PARAMETRO_INVALIDO` | `similar=%MARIA%SILVA%` |
| `limit` | inteiro | Só com `similar`. Máximo de resultados, de 1 a 100. Padrão 100 | `limit=50` |
| `cargo` | texto | Parte do nome do cargo (contém) | `cargo=professor` |
| `orgao` | texto | Parte do nome ou a sigla do órgão | `orgao=saude` ou `orgao=INSS` |
| `uf` | texto | Sigla de uma das 27 UFs. **Só ativos têm UF** | `uf=DF` |
| `situacao` | texto | `ativo`, `aposentado` ou `todos`. Padrão `todos` | `situacao=ativo` |
| `page` | inteiro | Página, de 1 até `total_pages` (no máximo 10.000). Padrão 1 | `page=2` |
| `per_page` | inteiro | Itens por página, de 1 a 100. Padrão 20 | `per_page=50` |

Regras:

- Pelo menos um filtro entre `nome`, `similar`, `cargo`, `orgao` e `uf` é obrigatório.
- `nome` e `similar` não podem ser usados juntos.
- Textos: de 2 a 100 caracteres, sem `--`. Em `nome` e `similar`: só letras, espaços, `'`, `.` e `-` (e `%` em `similar`). Em `cargo` e `orgao`: também dígitos, `/`, `(`, `)` e `,`. A entrada é convertida para maiúsculas, sem acentos e com espaços simples antes da busca, como os dados na carga.
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
| 404 | `PAGINA_INEXISTENTE` | `page` maior que `total_pages` (inclusive além do 10.000º resultado) |
| 404 | `ROTA_INEXISTENTE` | URL que não existe |
| 405 | `METODO_NAO_PERMITIDO` | Método diferente de GET |
| 429 | `MUITAS_REQUISICOES` | Limite de requisições por IP excedido; vem com o header `Retry-After` |
| 503 | `SERVIDOR_OCUPADO` | Limite de buscas simultâneas atingido; vem com `Retry-After` |
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
```
