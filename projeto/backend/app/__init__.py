"""Fábrica da aplicação Flask do Radar Público."""

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.config import load_config
from app.db import init_db
from app.errors import register_error_handlers


def create_app(test_config: dict | None = None) -> Flask:
    """Cria e configura a instância do Flask."""
    app = Flask(__name__, static_folder=None)
    # Mensagens com acento saem como não, e não como \u00e3o.
    app.json.ensure_ascii = False

    app.config.update(load_config())

    if test_config:
        app.config.update(test_config)

    init_db(app)

    # Rate limiting por IP
    Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://",
    )

    from app.routes.health import health_bp
    from app.routes.servidores import servidores_bp

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(servidores_bp, url_prefix="/api")
    register_error_handlers(app)

    return app
