"""Testes da configuração do banco lida do ambiente."""

import pytest

import server_settings as s
from app import config as c
from app import create_app
from app.db import DatabaseNotConfiguredError

DB_ENV = [
    "GUNICORN_WORKERS",
    "GUNICORN_THREADS",
    "DB_POOL_MIN",
    "DB_POOL_MAX",
    "DB_POOL_TIMEOUT_S",
    "DB_CONNECT_TIMEOUT_S",
]


@pytest.fixture
def env(monkeypatch):
    for var in DB_ENV:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_defaults_follow_gunicorn_threads(env):
    config = c.load_config()
    assert config["DB_POOL_MAX"] == s.DEFAULT_THREADS
    assert config["DB_POOL_MIN"] == c.DEFAULT_POOL_MIN
    assert config["DB_POOL_TIMEOUT_S"] == c.DEFAULT_POOL_TIMEOUT_S
    assert config["DB_CONNECT_TIMEOUT_S"] == c.DEFAULT_CONNECT_TIMEOUT_S


def test_pool_max_follows_threads(env):
    env.setenv("GUNICORN_THREADS", "6")
    assert c.load_config()["DB_POOL_MAX"] == 6


def test_explicit_values(env):
    env.setenv("DB_POOL_MIN", "2")
    env.setenv("DB_POOL_MAX", "5")
    env.setenv("DB_POOL_TIMEOUT_S", "7")
    env.setenv("DATABASE_URL", "postgresql://u:p@db:5432/x")
    config = c.load_config()
    assert (config["DB_POOL_MIN"], config["DB_POOL_MAX"], config["DB_POOL_TIMEOUT_S"]) == (2, 5, 7)
    assert config["DATABASE_URL"] == "postgresql://u:p@db:5432/x"


def test_total_connections_stay_within_role_budget(env):
    env.setenv("GUNICORN_WORKERS", "10")
    env.setenv("DB_POOL_MAX", "10")
    config = c.load_config()
    assert config["DB_POOL_MAX"] * 10 <= c.DB_CONNECTION_BUDGET


def test_min_never_exceeds_max(env):
    env.setenv("DB_POOL_MIN", "8")
    env.setenv("DB_POOL_MAX", "3")
    config = c.load_config()
    assert config["DB_POOL_MIN"] == 3


@pytest.mark.parametrize("raw", ["abc", "0", "-1", ""])
def test_invalid_pool_max_falls_back_to_threads(env, raw):
    env.setenv("DB_POOL_MAX", raw)
    assert c.load_config()["DB_POOL_MAX"] == s.DEFAULT_THREADS


def test_create_app_reads_environment_at_call_time(env, make_app):
    env.setenv("DB_POOL_MAX", "3")
    assert make_app().config["DB_POOL_MAX"] == 3


def test_missing_database_url_fails_clearly(env):
    env.setenv("DATABASE_URL", "")
    with pytest.raises(DatabaseNotConfiguredError, match="DATABASE_URL"):
        create_app({"TESTING": True})
