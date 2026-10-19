"""Testes do arquivo de configuração do Gunicorn."""

import importlib.util
from pathlib import Path


def load_gunicorn_conf():
    """Carrega dinamicamente o arquivo gunicorn.conf.py."""
    conf_path = Path(__file__).resolve().parent.parent / "gunicorn.conf.py"
    spec = importlib.util.spec_from_file_location("gunicorn_conf", conf_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gunicorn_conf_defaults(monkeypatch):
    """Testa os valores padrão de configuração do Gunicorn."""
    for var in [
        "GUNICORN_BIND",
        "BIND",
        "GUNICORN_WORKERS",
        "WORKERS",
        "GUNICORN_THREADS",
        "THREADS",
        "GUNICORN_TIMEOUT",
        "TIMEOUT",
    ]:
        monkeypatch.delenv(var, raising=False)

    conf = load_gunicorn_conf()
    assert conf.bind == "0.0.0.0:5000"
    assert conf.workers == 2
    assert conf.threads == 4
    assert conf.timeout == 30


def test_gunicorn_conf_custom_env(monkeypatch):
    """Testa se workers e threads respeitam variáveis de ambiente."""
    monkeypatch.setenv("GUNICORN_WORKERS", "8")
    monkeypatch.setenv("GUNICORN_THREADS", "16")
    monkeypatch.setenv("GUNICORN_BIND", "127.0.0.1:8000")
    monkeypatch.setenv("GUNICORN_TIMEOUT", "45")

    conf = load_gunicorn_conf()
    assert conf.workers == 8
    assert conf.threads == 16
    assert conf.bind == "127.0.0.1:8000"
    assert conf.timeout == 45
