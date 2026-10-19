"""Configuração do servidor lida do ambiente, usada pelo Gunicorn e pelo healthcheck.

Valores inválidos (não numéricos ou abaixo do mínimo) caem no padrão com um aviso no log,
para que um erro de configuração não deixe o container no ar sem atender requisições.
"""

import logging
import os

log = logging.getLogger("gunicorn.error")

# Dentro do container o Gunicorn precisa escutar em todas as interfaces.
DEFAULT_HOST = "0.0.0.0"  # nosec B104
DEFAULT_PORT = 5000  # o mesmo do Dockerfile (APP_PORT) e do docker-compose.yml
HEALTHCHECK_HOST = "127.0.0.1"
HEALTH_PATH = "/api/health"
HEALTHCHECK_TIMEOUT_S = 2

DEFAULT_WORKERS = 2
DEFAULT_THREADS = 4
DEFAULT_TIMEOUT_S = 30
DEFAULT_GRACEFUL_TIMEOUT_S = 30
DEFAULT_KEEPALIVE_S = 2
# Recicla cada worker após N requisições (com variação aleatória para não reiniciar
# todos ao mesmo tempo), limitando o efeito de vazamentos de memória sob carga.
DEFAULT_MAX_REQUESTS = 5000
DEFAULT_MAX_REQUESTS_JITTER = 500

MIN_PORT = 1
MIN_WORKERS = 1
MIN_THREADS = 1
MIN_SECONDS = 1
MIN_COUNT_OFF = 0  # 0 desliga max_requests / jitter

DEFAULT_LOGLEVEL = "info"
LOG_TO_STDOUT = "-"
# Em Docker, /tmp pode estar em disco; o heartbeat dos workers fica em memória, como a
# documentação do Gunicorn recomenda. Só guarda o arquivo de heartbeat, sem dados.
WORKER_TMP_DIR = "/dev/shm"  # nosec B108


def int_from_env(name: str, default: int, minimum: int) -> int:
    """Lê um inteiro do ambiente; vazio, inválido ou abaixo do mínimo usa o padrão."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        log.warning("%s=%r não é um número inteiro; usando %d", name, raw, default)
        return default
    if value < minimum:
        log.warning("%s=%d é menor que %d; usando %d", name, value, minimum, default)
        return default
    return value


def port_from_env() -> int:
    """Porta em que o Gunicorn escuta (GUNICORN_PORT)."""
    return int_from_env("GUNICORN_PORT", DEFAULT_PORT, MIN_PORT)


def bind_address() -> str:
    """Endereço host:porta para o Gunicorn."""
    return f"{DEFAULT_HOST}:{port_from_env()}"


def health_url() -> tuple[str, int, str]:
    """Host, porta e caminho que o healthcheck do container consulta."""
    return HEALTHCHECK_HOST, port_from_env(), HEALTH_PATH
