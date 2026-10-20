"""Testes do arquivo de configuração do Gunicorn."""

import importlib.util
from pathlib import Path

import pytest

import server_settings as s

GUNICORN_ENV = [
    "GUNICORN_PORT",
    "GUNICORN_WORKERS",
    "GUNICORN_THREADS",
    "GUNICORN_TIMEOUT",
    "GUNICORN_GRACEFUL_TIMEOUT",
    "GUNICORN_KEEPALIVE",
    "GUNICORN_WORKER_CONNECTIONS",
    "GUNICORN_MAX_REQUESTS",
    "GUNICORN_MAX_REQUESTS_JITTER",
    "GUNICORN_ACCESSLOG",
    "GUNICORN_ERRORLOG",
    "GUNICORN_LOGLEVEL",
]


@pytest.fixture
def clean_env(monkeypatch):
    """Remove as variáveis GUNICORN_* do ambiente do teste."""
    for var in GUNICORN_ENV:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def load_gunicorn_conf():
    """Carrega dinamicamente o arquivo gunicorn.conf.py."""
    conf_path = Path(__file__).resolve().parent.parent / "gunicorn.conf.py"
    spec = importlib.util.spec_from_file_location("gunicorn_conf", conf_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_defaults(clean_env):
    conf = load_gunicorn_conf()
    assert conf.bind == f"{s.DEFAULT_HOST}:{s.DEFAULT_PORT}"
    assert conf.workers == s.DEFAULT_WORKERS
    assert conf.threads == s.DEFAULT_THREADS
    assert conf.worker_class == "gthread"
    assert conf.timeout == s.DEFAULT_TIMEOUT_S
    assert conf.graceful_timeout == s.DEFAULT_GRACEFUL_TIMEOUT_S
    assert conf.keepalive == s.DEFAULT_KEEPALIVE_S
    # Uma conexão por thread: sem fila dentro do worker.
    assert conf.worker_connections == s.DEFAULT_THREADS
    assert conf.max_requests == s.DEFAULT_MAX_REQUESTS
    assert conf.max_requests_jitter == s.DEFAULT_MAX_REQUESTS_JITTER
    assert conf.worker_tmp_dir == s.WORKER_TMP_DIR
    assert conf.control_socket_disable is True
    assert conf.accesslog == s.LOG_TO_STDOUT
    assert conf.errorlog == s.LOG_TO_STDOUT
    assert conf.loglevel == s.DEFAULT_LOGLEVEL


def test_custom_env(clean_env):
    clean_env.setenv("GUNICORN_PORT", "8000")
    clean_env.setenv("GUNICORN_WORKERS", "8")
    clean_env.setenv("GUNICORN_THREADS", "16")
    clean_env.setenv("GUNICORN_TIMEOUT", "45")
    clean_env.setenv("GUNICORN_MAX_REQUESTS", "0")
    clean_env.setenv("GUNICORN_LOGLEVEL", "warning")

    conf = load_gunicorn_conf()
    assert conf.bind == f"{s.DEFAULT_HOST}:8000"
    assert conf.workers == 8
    assert conf.threads == 16
    assert conf.timeout == 45
    assert conf.max_requests == 0
    assert conf.loglevel == "warning"
    # worker_connections acompanha as threads quando não é definido.
    assert conf.worker_connections == 16


def test_worker_connections_and_keepalive_from_env(clean_env):
    clean_env.setenv("GUNICORN_WORKER_CONNECTIONS", "32")
    clean_env.setenv("GUNICORN_KEEPALIVE", "5")
    conf = load_gunicorn_conf()
    assert conf.worker_connections == 32
    assert conf.keepalive == 5


@pytest.mark.parametrize("raw", ["abc", "0", "-1"])
def test_invalid_worker_connections_fall_back_to_threads(clean_env, raw):
    clean_env.setenv("GUNICORN_THREADS", "6")
    clean_env.setenv("GUNICORN_WORKER_CONNECTIONS", raw)
    conf = load_gunicorn_conf()
    assert conf.worker_connections == 6


def test_single_thread_uses_sync_worker(clean_env):
    clean_env.setenv("GUNICORN_THREADS", "1")
    conf = load_gunicorn_conf()
    assert conf.threads == 1
    assert conf.worker_class == "sync"


@pytest.mark.parametrize("raw", ["abc", "", "  ", "0", "-3", "2.5"])
def test_invalid_workers_fall_back_to_default(clean_env, raw):
    clean_env.setenv("GUNICORN_WORKERS", raw)
    conf = load_gunicorn_conf()
    assert conf.workers == s.DEFAULT_WORKERS


@pytest.mark.parametrize("raw", ["abc", "0"])
def test_invalid_port_falls_back_to_default(clean_env, raw):
    clean_env.setenv("GUNICORN_PORT", raw)
    conf = load_gunicorn_conf()
    assert conf.bind == f"{s.DEFAULT_HOST}:{s.DEFAULT_PORT}"


def test_invalid_value_is_logged(clean_env, caplog):
    clean_env.setenv("GUNICORN_THREADS", "muitas")
    with caplog.at_level("WARNING", logger="gunicorn.error"):
        conf = load_gunicorn_conf()
    assert conf.threads == s.DEFAULT_THREADS
    assert "GUNICORN_THREADS" in caplog.text
