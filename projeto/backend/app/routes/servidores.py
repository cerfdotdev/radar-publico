"""GET /api/servidores: busca de servidores ativos e aposentados (docs/api.md).

Recomendações de desempenho seguidas (docs/banco.md): ids de cargo e órgão resolvidos
antes, contagem limitada a 10.000 resultados e paginação só dentro desse limite.
"""

import math
from http import HTTPStatus

from flask import Blueprint, Response, jsonify, request
from psycopg import Cursor, sql
from psycopg.rows import dict_row

from app.db import get_db_connection
from app.errors import ApiError
from app.search_params import MAX_TOTAL, SearchParams, Situacao, parse_search_params

servidores_bp = Blueprint("servidores", __name__)

# Uma linha a mais que o teto: basta para saber se o total passou de MAX_TOTAL.
COUNT_LIMIT = MAX_TOTAL + 1
LIKE_ESCAPE = "\\"

CARGO_LOOKUP = sql.SQL("SELECT id FROM cargo WHERE nome LIKE %s")
ORGAO_LOOKUP = sql.SQL("SELECT id FROM orgao WHERE nome LIKE %s OR sigla = %s")
COUNT_QUERY = sql.SQL(
    "SELECT count(*) FROM (SELECT 1 FROM servidor s WHERE {where} LIMIT %s) AS limitado"
)
# Pagina primeiro só os ids (dá para usar os índices (filtro, nome, id) sem ler a
# tabela) e depois busca as colunas e junta cargo e órgão apenas das linhas da página.
PAGE_QUERY = sql.SQL(
    """
    WITH pagina AS (
        SELECT s.id FROM servidor s
        WHERE {where}
        ORDER BY s.nome, s.id
        LIMIT %s OFFSET %s
    )
    SELECT s.id, s.nome, s.situacao, c.nome AS cargo, o.nome AS orgao,
           o.sigla AS sigla_orgao, s.uf, s.valor
    FROM pagina p
    JOIN servidor s ON s.id = p.id
    JOIN orgao o ON o.id = s.orgao_id
    LEFT JOIN cargo c ON c.id = s.cargo_id
    ORDER BY s.nome, s.id
    """
)

# Busca por similaridade usando o índice trigram de servidor.nome
SIMILAR_QUERY = sql.SQL(
    """
    SELECT s.id, s.nome, s.situacao, c.nome AS cargo, o.nome AS orgao,
           o.sigla AS sigla_orgao, s.uf, s.valor,
           similarity(s.nome, %s) AS similaridade
    FROM servidor s
    JOIN orgao o ON o.id = s.orgao_id
    LEFT JOIN cargo c ON c.id = s.cargo_id
    WHERE s.nome LIKE %s
    ORDER BY similaridade DESC, s.nome, s.id
    LIMIT %s
    """
)


def like_contains(text: str) -> str:
    """Padrão LIKE de "contém", com % _ e \\ da entrada tratados como texto."""
    escaped = (
        text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )
    return f"%{escaped}%"


def resolve_ids(cur: Cursor, query: sql.Composable, args: tuple, code: str, label: str) -> list:
    cur.execute(query, args)
    ids = [row["id"] for row in cur.fetchall()]
    if not ids:
        raise ApiError(code, f"Nenhum {label} corresponde à busca.", HTTPStatus.NOT_FOUND)
    return ids


def id_filter(column: str, ids: list) -> tuple[sql.Composable, object]:
    """Um id usa '=' (o planejador estima bem); vários usam '= ANY'."""
    target = sql.Identifier("s", column)
    if len(ids) == 1:
        return sql.SQL("{} = %s").format(target), ids[0]
    return sql.SQL("{} = ANY(%s)").format(target), ids


def build_filters(cur: Cursor, params: SearchParams) -> tuple[sql.Composable, list]:
    conditions: list[sql.Composable] = []
    values: list = []

    if params.cargo is not None:
        ids = resolve_ids(
            cur, CARGO_LOOKUP, (like_contains(params.cargo),), "CARGO_NAO_ENCONTRADO", "cargo"
        )
        condition, value = id_filter("cargo_id", ids)
        conditions.append(condition)
        values.append(value)

    if params.orgao is not None:
        ids = resolve_ids(
            cur,
            ORGAO_LOOKUP,
            (like_contains(params.orgao), params.orgao),
            "ORGAO_NAO_ENCONTRADO",
            "órgão",
        )
        condition, value = id_filter("orgao_id", ids)
        conditions.append(condition)
        values.append(value)

    for column, value in (("nome", params.nome), ("uf", params.uf)):
        if value is not None:
            conditions.append(sql.SQL("{} = %s").format(sql.Identifier("s", column)))
            values.append(value)

    if params.situacao is not Situacao.TODOS:
        conditions.append(sql.SQL("s.situacao = %s"))
        values.append(params.situacao.value)

    return sql.SQL(" AND ").join(conditions), values


def serialize(row: dict) -> dict:
    valor = row["valor"]
    return {**row, "valor": float(valor) if valor is not None else None}


def serialize_similar(row: dict) -> dict:
    valor = row["valor"]
    similaridade = row.get("similaridade")
    result = {**row, "valor": float(valor) if valor is not None else None}
    if similaridade is not None:
        result["similaridade"] = round(float(similaridade), 4)
    return result


@servidores_bp.get("/servidores")
def listar_servidores() -> Response:
    """Busca servidores por nome exato, similar, cargo, órgão, UF e situação."""
    params = parse_search_params(request.args)

    # --- Busca por similaridade (índice trigram, sem paginação) ---
    if params.similar is not None:
        with get_db_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(SIMILAR_QUERY, (params.similar, params.similar, params.limit))
            rows = cur.fetchall()

        if not rows:
            raise ApiError(
                "NAO_ENCONTRADO",
                "Nenhum servidor encontrado com nome parecido.",
                HTTPStatus.NOT_FOUND,
            )

        return jsonify(
            {
                "data": [serialize_similar(row) for row in rows],
                "meta": {
                    "total": len(rows),
                    "total_exato": True,
                    "page": 1,
                    "per_page": params.limit,
                    "total_pages": 1,
                },
            }
        )

    # --- Busca normal com filtros (nome exato, cargo, órgão, UF) ---
    if params.uf is not None and params.situacao is Situacao.APOSENTADO:
        raise ApiError(
            "NAO_ENCONTRADO",
            "Aposentados não têm UF na fonte; o filtro de UF só encontra ativos.",
            HTTPStatus.NOT_FOUND,
        )

    with get_db_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        where, values = build_filters(cur, params)

        cur.execute(COUNT_QUERY.format(where=where), (*values, COUNT_LIMIT))
        total_raw = cur.fetchone()["count"]
        if total_raw == 0:
            raise ApiError(
                "NAO_ENCONTRADO",
                "Nenhum servidor encontrado com esses filtros.",
                HTTPStatus.NOT_FOUND,
            )

        total = min(total_raw, MAX_TOTAL)
        total_pages = math.ceil(total / params.per_page)
        if params.page > total_pages:
            raise ApiError(
                "PAGINA_INEXISTENTE",
                f"A página {params.page} não existe; esta busca tem {total_pages} página(s).",
                HTTPStatus.NOT_FOUND,
            )

        offset = (params.page - 1) * params.per_page
        # A última página nunca passa do resultado de número MAX_TOTAL.
        limit = min(params.per_page, total - offset)
        cur.execute(PAGE_QUERY.format(where=where), (*values, limit, offset))
        rows = cur.fetchall()

    return jsonify(
        {
            "data": [serialize(row) for row in rows],
            "meta": {
                "total": total,
                "total_exato": total_raw <= MAX_TOTAL,
                "page": params.page,
                "per_page": params.per_page,
                "total_pages": total_pages,
            },
        }
    )
