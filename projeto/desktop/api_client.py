"""Atalho de importação do cliente HTTP do app desktop."""

try:
    from radar_desktop.api import (
        LIMITE_MAX,
        LIMITE_MIN,
        LIMITE_PADRAO,
        POR_PAGINA_OPCOES,
        POR_PAGINA_PADRAO,
        ApiClient,
        ApiError,
        Busca,
        RadarApi,
        RadarApiClient,
        SearchQuery,
        buscar_servidores,
        montar_parametros,
    )
except ModuleNotFoundError:  # importado como projeto.desktop.api_client
    from .radar_desktop.api import (
        LIMITE_MAX,
        LIMITE_MIN,
        LIMITE_PADRAO,
        POR_PAGINA_OPCOES,
        POR_PAGINA_PADRAO,
        ApiClient,
        ApiError,
        Busca,
        RadarApi,
        RadarApiClient,
        SearchQuery,
        buscar_servidores,
        montar_parametros,
    )

__all__ = [
    "LIMITE_MAX",
    "LIMITE_MIN",
    "LIMITE_PADRAO",
    "POR_PAGINA_OPCOES",
    "POR_PAGINA_PADRAO",
    "ApiClient",
    "ApiError",
    "Busca",
    "RadarApi",
    "RadarApiClient",
    "SearchQuery",
    "buscar_servidores",
    "montar_parametros",
]
