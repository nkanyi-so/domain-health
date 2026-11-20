from tests.app_fixtures import build


def test_health_route_answers_ok() -> None:
    response = build().client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_no_documentation_route_is_served() -> None:
    client = build().client

    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
