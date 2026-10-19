"""Rota de verificação de integridade da API."""

from flask import Blueprint, Response, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health() -> Response:
    """Retorna status HTTP 200 indicando que o processo está saudável (sem tocar no banco)."""
    return jsonify({"status": "ok"})
