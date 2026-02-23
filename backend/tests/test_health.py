from app.api.v1.endpoints.health import healthcheck


def test_health_payload() -> None:
    payload = healthcheck()
    assert payload.status == "ok"
    assert payload.service == "enesa-automation-hub-api"

