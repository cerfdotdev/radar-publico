"""Testes de configuração por ambiente e pool de conexões."""

import pytest

from app.config import Config
from app.db import close_db_pool, get_db_pool, init_db


def test_config_reads_environment(monkeypatch):
    """Testa se a classe Config lê as variáveis de ambiente."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
    monkeypatch.setenv("DB_POOL_MIN", "3")
    monkeypatch.setenv("DB_POOL_MAX", "15")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "10.5")

    class CustomConfig(Config):
        import os

        DATABASE_URL = os.getenv("DATABASE_URL")
        DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
        DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))
        DB_POOL_TIMEOUT = float(os.getenv("DB_POOL_TIMEOUT", "30.0"))

    assert CustomConfig.DATABASE_URL == "postgresql://user:pass@localhost:5432/testdb"
    assert CustomConfig.DB_POOL_MIN == 3
    assert CustomConfig.DB_POOL_MAX == 15
    assert CustomConfig.DB_POOL_TIMEOUT == 10.5


def test_pool_init_and_close(app):
    """Testa inicialização e fechamento do pool de conexões."""
    init_db(app)
    pool = get_db_pool()
    assert pool is not None
    assert pool.conninfo == app.config["DATABASE_URL"]

    close_db_pool()
    with pytest.raises(RuntimeError, match="Pool de banco de dados não inicializado"):
        get_db_pool()
