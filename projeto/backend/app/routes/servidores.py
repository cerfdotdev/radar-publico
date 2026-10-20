"""GET /api/servidores e GET /api/servidores/<id>: busca e detalhe de vínculos (docs/api.md).

Recomendações de desempenho seguidas (docs/banco.md): ids de cargo e órgão resolvidos
antes (na memória do worker, app/lookup.py), contagem limitada a 10.000 resultados e
paginação só dentro desse limite.
"""

import math
from http import HTTPStatus

from flask import Blueprint, Response, jsonify, request
from psycopg import Cursor, sql
from psycopg.rows import dict_row

from app.db import get_db_connection
from app.errors import ApiError
from app.lookup import get_lookup
from app.search_params import (
    MAX_TOTAL,
    SearchParams,
    Situacao,
    parse_search_params,
    parse_servidor_id,
)

servidores_bp = Blueprint("servidores", __name__)

# Uma linha a mais que o teto: basta para saber se o total passou de MAX_TOTAL.
COUNT_LIMIT = MAX_TOTAL + 1
# A busca por similaridade vem inteira, até 'limit' resultados, numa página só.
SINGLE_PAGE = 1

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

# Similaridade: o LIKE do padrão usa o índice trigram de servidor.nome, e os filtros de
# cargo, órgão, UF e situação entram no mesmo WHERE da busca normal.
SIMILAR_QUERY = sql.SQL(
    """
    SELECT s.id, s.nome, s.situacao, c.nome AS cargo, o.nome AS orgao,
           o.sigla AS sigla_orgao, s.uf, s.valor,
           similarity(s.nome, %s) AS similaridade
    FROM servidor s
    JOIN orgao o ON o.id = s.orgao_id
    LEFT JOIN cargo c ON c.id = s.cargo_id
    WHERE {where}
    ORDER BY similaridade DESC, s.nome, s.id
    LIMIT %s
    """
)

DETAIL_QUERY = sql.SQL(
    """
    SELECT s.id, s.nome, s.situacao, c.nome AS cargo, o.nome AS orgao,
           o.sigla AS sigla_orgao, s.uf, s.valor, s.codigo_carreira,
           s.tipo_aposentadoria, s.fundamento_legal, s.portaria, s.data_aposentadoria,
           s.forma_ingresso, s.data_ingresso, s.referencia
    FROM servidor s
    JOIN orgao o ON o.id = s.orgao_id
    LEFT JOIN cargo c ON c.id = s.cargo_id
    WHERE s.id = %s
    """
)
DATE_FIELDS = ("data_aposentadoria", "data_ingresso")


def require_ids(ids: list[int], code: str, label: str) -> list[int]:
    if not ids:
        raise ApiError(code, f"Nenhum {label} corresponde à busca.", HTTPStatus.NOT_FOUND)
    return ids


def id_filter(column: str, ids: list) -> tuple[sql.Composable, object]:
    """Um id usa '=' (o planejador estima bem); vários usam '= ANY'."""
    target = sql.Identifier("s", column)
    if len(ids) == 1:
        return sql.SQL("{} = %s").format(target), ids[0]
    return sql.SQL("{} = ANY(%s)").format(target), ids


def build_filters(params: SearchParams) -> tuple[sql.Composable, list]:
    """WHERE da busca. Chame sem conexão em mãos: a primeira vez lê cargo e órgão do banco."""
    conditions: list[sql.Composable] = []
    values: list = []

    if params.cargo is not None:
        ids = require_ids(get_lookup().cargo_ids(params.cargo), "CARGO_NAO_ENCONTRADO", "cargo")
        condition, value = id_filter("cargo_id", ids)
        conditions.append(condition)
        values.append(value)

    if params.orgao is not None:
        ids = require_ids(get_lookup().orgao_ids(params.orgao), "ORGAO_NAO_ENCONTRADO", "órgão")
        condition, value = id_filter("orgao_id", ids)
        conditions.append(condition)
        values.append(value)

    for column, value in (("nome", params.nome), ("uf", params.uf)):
        if value is not None:
            conditions.append(sql.SQL("{} = %s").format(sql.Identifier("s", column)))
            values.append(value)

    if params.similar is not None:
        # O '%' da entrada é o curinga; '_' e '\\' já foram recusados na validação.
        conditions.append(sql.SQL("s.nome LIKE %s"))
        values.append(params.similar)

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


def serialize_detail(row: dict) -> dict:
    """Linha do detalhe; datas em ISO (AAAA-MM-DD), como no contrato."""
    dates = {field: row[field] and row[field].isoformat() for field in DATE_FIELDS}
    return {**serialize(row), **dates}


@servidores_bp.get("/servidores")
def listar_servidores() -> Response:
    """Busca servidores por nome exato ou parecido, cargo, órgão, UF e situação."""
    params = parse_search_params(request.args)

    if params.uf is not None and params.situacao is Situacao.APOSENTADO:
        raise ApiError(
            "NAO_ENCONTRADO",
            "Aposentados não têm UF na fonte; o filtro de UF só encontra ativos.",
            HTTPStatus.NOT_FOUND,
        )

    # Antes de pegar a conexão da busca: nunca duas conexões do pool na mesma thread.
    where, values = build_filters(params)
    with get_db_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        if params.similar is not None:
            return buscar_similares(cur, params, where, values)

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


def buscar_similares(
    cur: Cursor, params: SearchParams, where: sql.Composable, values: list
) -> Response:
    """Os nomes mais parecidos com o padrão, até 'limit', sem paginação."""
    cur.execute(SIMILAR_QUERY.format(where=where), (params.similar, *values, params.limit))
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
                "page": SINGLE_PAGE,
                "per_page": params.limit,
                "total_pages": SINGLE_PAGE,
            },
        }
    )


@servidores_bp.get("/servidores/<raw_id>")
def detalhar_servidor(raw_id: str) -> Response:
    """Detalhe de um vínculo, com os campos de carreira, aposentadoria e ingresso."""
    # O id é conferido antes do banco: texto ou número fora do bigint dão 400, não 500.
    servidor_id = parse_servidor_id(raw_id, request.args)
    with get_db_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(DETAIL_QUERY, (servidor_id,))
        row = cur.fetchone()
    if row is None:
        raise ApiError(
            "NAO_ENCONTRADO", f"Nenhum servidor com o id {servidor_id}.", HTTPStatus.NOT_FOUND
        )
    return jsonify({"data": serialize_detail(row)})
