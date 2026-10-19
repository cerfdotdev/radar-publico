"""Configuração do servidor WSGI Gunicorn para o Radar Público."""

import os

bind = os.getenv("GUNICORN_BIND", os.getenv("BIND", "0.0.0.0:5000"))
workers = int(os.getenv("GUNICORN_WORKERS", os.getenv("WORKERS", "2")))
threads = int(os.getenv("GUNICORN_THREADS", os.getenv("THREADS", "4")))
timeout = int(os.getenv("GUNICORN_TIMEOUT", os.getenv("TIMEOUT", "30")))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "2"))
accesslog = os.getenv("GUNICORN_ACCESSLOG", "-")
errorlog = os.getenv("GUNICORN_ERRORLOG", "-")
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
