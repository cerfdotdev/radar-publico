"""Fábrica da aplicação Flask do Radar Público."""

from flask import Flask

from app.config import load_config
from app.db import init_db
from app.errors import register_error_handlers
from app.query_string import ApiRequest
from app.rate_limit import init_rate_limit


def create_app(test_config: dict | None = None) -> Flask:
    """Cria e configura a instância do Flask."""
    app = Flask(__name__, static_folder=None)
    # Aceita '%' digitado sem codificar, como em ?similar=%JOSE%DE%BARROS%.
    app.request_class = ApiRequest
    # Mensagens com acento saem como "não", e não "não".
    app.json.ensure_ascii = False

    app.config.update(load_config())

    if test_config:
        app.config.update(test_config)

    init_db(app)
    init_rate_limit(app)

    from app.routes.health import health_bp
    from app.routes.servidores import servidores_bp

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(servidores_bp, url_prefix="/api")
    register_error_handlers(app)

    return app
