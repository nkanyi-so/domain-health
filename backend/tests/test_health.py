from fastapi.testclient import TestClient

from domain_health.app import create_app


def test_health_route_answers_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_is_not_found() -> None:
    client = TestClient(create_app())

    assert client.get("/docs").status_code == 404
