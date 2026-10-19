"""Respostas de erro em JSON no formato do contrato (docs/api.md)."""

from http import HTTPStatus

from flask import Flask, Response, current_app, jsonify
from psycopg_pool import PoolTimeout, TooManyRequests
from werkzeug.exceptions import HTTPException, MethodNotAllowed

ERRO_INTERNO = "ERRO_INTERNO"
SERVIDOR_OCUPADO = "SERVIDOR_OCUPADO"
BUSY_MESSAGE = "O servidor está ocupado no momento. Tente de novo em instantes."
# Sugestão ao cliente para tentar de novo (header Retry-After), em segundos.
BUSY_RETRY_AFTER_S = 2

# Erros HTTP gerados pelo próprio Flask/Werkzeug, antes de chegar a uma rota.
HTTP_ERRORS: dict[int, tuple[str, str]] = {
    HTTPStatus.BAD_REQUEST: ("PARAMETRO_INVALIDO", "Requisição inválida."),
    HTTPStatus.NOT_FOUND: ("ROTA_INEXISTENTE", "Rota não encontrada."),
    HTTPStatus.METHOD_NOT_ALLOWED: ("METODO_NAO_PERMITIDO", "Método não permitido."),
}
INTERNAL_ERROR_MESSAGE = "Algo deu errado do nosso lado. Tente de novo em instantes."


def error_response(code: str, message: str, status: int) -> tuple[Response, int]:
    """Monta {"error": {"code", "message"}} com o status HTTP."""
    return jsonify({"error": {"code": code, "message": message}}), status


def register_error_handlers(app: Flask) -> None:
    """Faz todo erro da aplicação responder em JSON."""

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException) -> Response:
        code, message = HTTP_ERRORS.get(error.code, (ERRO_INTERNO, INTERNAL_ERROR_MESSAGE))
        response, status = error_response(code, message, error.code)
        if isinstance(error, MethodNotAllowed) and error.valid_methods:
            response.headers["Allow"] = ", ".join(error.valid_methods)
        response.status_code = status
        return response

    @app.errorhandler(PoolTimeout)
    @app.errorhandler(TooManyRequests)
    def handle_pool_exhausted(error: Exception) -> Response:
        # Pool cheio ou banco inacessível: o pool não entregou conexão dentro do timeout.
        current_app.logger.warning("Sem conexão disponível no pool: %s", error)
        response, status = error_response(
            SERVIDOR_OCUPADO, BUSY_MESSAGE, HTTPStatus.SERVICE_UNAVAILABLE
        )
        response.status_code = status
        response.headers["Retry-After"] = str(BUSY_RETRY_AFTER_S)
        return response

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception) -> tuple[Response, int]:
        current_app.logger.exception("Erro inesperado", exc_info=error)
        return error_response(
            ERRO_INTERNO, INTERNAL_ERROR_MESSAGE, HTTPStatus.INTERNAL_SERVER_ERROR
        )
