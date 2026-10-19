"""Healthcheck do container: consulta /api/health no Gunicorn local.

Sai com 0 se a API responder 200 e com 1 em qualquer outro caso.
"""

import sys
from http import HTTPStatus
from http.client import HTTPConnection

import server_settings as s

EXIT_OK = 0
EXIT_FAIL = 1


def check() -> int:
    """Faz um GET no endpoint de saúde e devolve o código de saída."""
    host, port, path = s.health_url()
    connection = HTTPConnection(host, port, timeout=s.HEALTHCHECK_TIMEOUT_S)
    try:
        connection.request("GET", path)
        status = connection.getresponse().status
    except OSError:
        return EXIT_FAIL
    finally:
        connection.close()
    return EXIT_OK if status == HTTPStatus.OK else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(check())
