"""Rota de verificação de integridade da API."""

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    """Retorna status HTTP 200 indicando que o processo está saudável."""
    return jsonify({"status": "ok"})
