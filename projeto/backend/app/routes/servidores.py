"""Rota de consulta a servidores públicos ativos e aposentados."""

import math
from http import HTTPStatus

from flask import Blueprint, jsonify, request

from app.db import get_db_connection
from app.errors import error_response

servidores_bp = Blueprint("servidores", __name__)

UFS = {
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
}

MAX_TOTAL = 10000
COUNT_LIMIT = 10001


@servidores_bp.get("/servidores")
def listar_servidores():
    """Busca servidores por nome exato, cargo, órgão e UF."""
    nome = request.args.get("nome")
    cargo = request.args.get("cargo")
    orgao = request.args.get("orgao")
    uf = request.args.get("uf")
    situacao = request.args.get("situacao", "todos").strip().lower()

    # Validação de filtros obrigatórios
    if not any([nome, cargo, orgao, uf]):
        return error_response(
            "FILTRO_OBRIGATORIO",
            "Pelo menos um filtro entre 'nome', 'cargo', 'orgao' e 'uf' deve ser informado.",
            HTTPStatus.BAD_REQUEST,
        )

    # Validação de UF
    if uf is not None:
        uf = uf.strip().upper()
        if uf not in UFS:
            return error_response(
                "UF_INVALIDA",
                f"UF '{uf}' não existe. Use uma das 27 siglas.",
                HTTPStatus.BAD_REQUEST,
            )

    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        return error_response(
            "PARAMETRO_INVALIDO",
            "Os parâmetros 'page' e 'per_page' devem ser números inteiros.",
            HTTPStatus.BAD_REQUEST,
        )

    conditions: list[str] = []
    params: list[object] = []

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Resolução prévia de IDs de cargo para otimização de plano de consulta
            if cargo is not None:
                cur.execute(
                    "SELECT id FROM cargo WHERE nome ILIKE %s",
                    (f"%{cargo.strip()}%",),
                )
                cargo_ids = [row[0] for row in cur.fetchall()]
                if not cargo_ids:
                    return error_response(
                        "CARGO_NAO_ENCONTRADO",
                        f"Nenhum cargo corresponde a '{cargo}'.",
                        HTTPStatus.NOT_FOUND,
                    )
                conditions.append("s.cargo_id = ANY(%s)")
                params.append(cargo_ids)

            # Resolução prévia de IDs de órgão
            if orgao is not None:
                cur.execute(
                    "SELECT id FROM orgao WHERE nome ILIKE %s OR upper(sigla) = %s",
                    (f"%{orgao.strip()}%", orgao.strip().upper()),
                )
                orgao_ids = [row[0] for row in cur.fetchall()]
                if not orgao_ids:
                    return error_response(
                        "ORGAO_NAO_ENCONTRADO",
                        f"Nenhum órgão corresponde a '{orgao}'.",
                        HTTPStatus.NOT_FOUND,
                    )
                conditions.append("s.orgao_id = ANY(%s)")
                params.append(orgao_ids)

            if nome is not None:
                conditions.append("s.nome = %s")
                params.append(nome.strip().upper())

            if uf is not None:
                conditions.append("s.uf = %s")
                params.append(uf)

            if situacao in ("ativo", "aposentado"):
                conditions.append("s.situacao = %s")
                params.append(situacao)

            where_clause = " AND ".join(conditions)

            # Contagem com teto de 10.001 registros para alta performance
            count_sql = (
                f"SELECT count(*) FROM ("  # nosec B608
                f"SELECT 1 FROM servidor s WHERE {where_clause} LIMIT {COUNT_LIMIT}) c"
            )
            cur.execute(count_sql, tuple(params))
            total_raw = cur.fetchone()[0]

            if total_raw == 0:
                return error_response(
                    "NAO_ENCONTRADO",
                    "Nenhum servidor encontrado com os critérios informados.",
                    HTTPStatus.NOT_FOUND,
                )

            offset = (page - 1) * per_page
            select_sql = f"""
                SELECT
                    s.id,
                    s.nome,
                    s.situacao,
                    c.nome AS cargo,
                    o.nome AS orgao,
                    o.sigla AS sigla_orgao,
                    s.uf,
                    s.valor
                FROM servidor s
                JOIN orgao o ON o.id = s.orgao_id
                LEFT JOIN cargo c ON c.id = s.cargo_id
                WHERE {where_clause}
                ORDER BY s.nome, s.id
                LIMIT %s OFFSET %s
            """  # nosec B608

            query_params = tuple(params) + (per_page, offset)
            cur.execute(select_sql, query_params)
            rows = cur.fetchall()

    servidores = [
        {
            "id": row[0],
            "nome": row[1],
            "situacao": row[2],
            "cargo": row[3],
            "orgao": row[4],
            "sigla_orgao": row[5],
            "uf": row[6],
            "valor": float(row[7]) if row[7] is not None else None,
        }
        for row in rows
    ]

    total = min(total_raw, MAX_TOTAL)
    total_exato = total_raw <= MAX_TOTAL
    total_pages = math.ceil(total / per_page) if total > 0 else 1

    return (
        jsonify(
            {
                "data": servidores,
                "meta": {
                    "total": total,
                    "total_exato": total_exato,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": total_pages,
                },
            }
        ),
        HTTPStatus.OK,
    )
