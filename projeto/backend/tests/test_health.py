"""Testes da rota GET /api/health."""


def test_health_check_returns_200_and_ok(client):
    """Verifica se /api/health responde 200 com {'status': 'ok'}."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.is_json
    assert response.get_json() == {"status": "ok"}
