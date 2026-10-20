"""Cargos e órgãos na memória de cada worker, para resolver os filtros sem ir ao banco.

São tabelas pequenas (2.999 cargos e 230 órgãos na carga real, docs/banco.md) que só mudam
quando a base é recarregada. Cada worker as lê uma vez, no primeiro filtro por cargo ou
órgão, e a partir daí a busca não faz mais uma consulta por filtro. A comparação é a mesma
do SQL que a busca usava: nome LIKE '%texto%' com % _ e \\ escapados (contém, diferenciando
maiúsculas) e, no órgão, também sigla = texto. Os textos já chegam normalizados como os da
carga (app/search_params.py).

Depois de recarregar a base, reinicie o backend: o `docker compose down -v` da recarga já
recria o container (README, "Cache").
"""

from dataclasses import dataclass

from flask import Flask, current_app

from app.db import get_db_connection
from app.lazy import Lazy

EXTENSION_KEY = "lookup"
CARGOS_QUERY = "SELECT id, nome FROM cargo ORDER BY id"
ORGAOS_QUERY = "SELECT id, nome, sigla FROM orgao ORDER BY id"


@dataclass(frozen=True, slots=True)
class Cargo:
    id: int
    nome: str


@dataclass(frozen=True, slots=True)
class Orgao:
    id: int
    nome: str
    sigla: str | None


@dataclass(frozen=True, slots=True)
class Lookup:
    """As duas tabelas, só para leitura: várias threads consultam ao mesmo tempo."""

    cargos: tuple[Cargo, ...]
    orgaos: tuple[Orgao, ...]

    def cargo_ids(self, texto: str) -> list[int]:
        """Ids dos cargos cujo nome contém o texto."""
        return [cargo.id for cargo in self.cargos if texto in cargo.nome]

    def orgao_ids(self, texto: str) -> list[int]:
        """Ids dos órgãos cujo nome contém o texto ou cuja sigla é igual a ele."""
        return [orgao.id for orgao in self.orgaos if texto in orgao.nome or orgao.sigla == texto]


def load_lookup() -> Lookup:
    """Lê as duas tabelas inteiras (uma vez por worker)."""
    with get_db_connection() as conn, conn.cursor() as cur:
        cargos = tuple(Cargo(*row) for row in cur.execute(CARGOS_QUERY))
        orgaos = tuple(Orgao(*row) for row in cur.execute(ORGAOS_QUERY))
    return Lookup(cargos, orgaos)


def init_lookup(app: Flask) -> None:
    """Registra as tabelas ainda vazias; a leitura acontece no primeiro uso, já no worker."""
    app.extensions[EXTENSION_KEY] = Lazy(load_lookup)


def get_lookup() -> Lookup:
    """As tabelas do worker, lidas do banco na primeira chamada."""
    lazy: Lazy[Lookup] = current_app.extensions[EXTENSION_KEY]
    return lazy.get()
