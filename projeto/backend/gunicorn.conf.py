"""Configuração do servidor WSGI Gunicorn para o Radar Público.

Cada valor pode ser sobrescrito por uma variável GUNICORN_*; os padrões ficam em
server_settings.py.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server_settings as s  # noqa: E402

bind = s.bind_address()
workers = s.int_from_env("GUNICORN_WORKERS", s.DEFAULT_WORKERS, s.MIN_WORKERS)
threads = s.int_from_env("GUNICORN_THREADS", s.DEFAULT_THREADS, s.MIN_THREADS)
worker_class = "gthread" if threads > s.MIN_THREADS else "sync"
timeout = s.int_from_env("GUNICORN_TIMEOUT", s.DEFAULT_TIMEOUT_S, s.MIN_SECONDS)
graceful_timeout = s.int_from_env(
    "GUNICORN_GRACEFUL_TIMEOUT", s.DEFAULT_GRACEFUL_TIMEOUT_S, s.MIN_SECONDS
)
# Conexões que cada worker aceita: uma por thread. Sem fila dentro do worker, quem espera fica na
# fila do kernel (backlog), que é uma só para todos os workers: a próxima busca vai para o
# primeiro worker com thread livre, em vez de esperar atrás de buscas lentas no worker errado. O
# padrão do Gunicorn (1.000) deixava cada worker acumular a própria fila (docs/carga.md). O backlog
# não é um corte rápido (cheio, o kernel descarta o SYN e o cliente fica tentando); quem limita a
# fila e responde 503 na hora é a admissão do nginx (NGINX_LIMITE_BACKEND_SIMULTANEAS).
worker_connections = s.int_from_env("GUNICORN_WORKER_CONNECTIONS", threads, s.MIN_THREADS)
keepalive = s.int_from_env("GUNICORN_KEEPALIVE", s.DEFAULT_KEEPALIVE_S, s.MIN_COUNT_OFF)
max_requests = s.int_from_env("GUNICORN_MAX_REQUESTS", s.DEFAULT_MAX_REQUESTS, s.MIN_COUNT_OFF)
max_requests_jitter = s.int_from_env(
    "GUNICORN_MAX_REQUESTS_JITTER", s.DEFAULT_MAX_REQUESTS_JITTER, s.MIN_COUNT_OFF
)
worker_tmp_dir = s.WORKER_TMP_DIR
control_socket_disable = True

accesslog = os.getenv("GUNICORN_ACCESSLOG", s.LOG_TO_STDOUT)
errorlog = os.getenv("GUNICORN_ERRORLOG", s.LOG_TO_STDOUT)
loglevel = os.getenv("GUNICORN_LOGLEVEL", s.DEFAULT_LOGLEVEL)
