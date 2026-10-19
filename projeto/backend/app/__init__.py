"""Fábrica da aplicação Flask do Radar Público."""

from flask import Flask

from app.config import Config
from app.db import init_db


def create_app(test_config: dict | None = None) -> Flask:
    """Cria e configura a instância do Flask."""
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False

    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    init_db(app)

    from app.routes.health import health_bp

    app.register_blueprint(health_bp, url_prefix="/api")

    return app
