def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code in (200, 503)
    body = r.get_json()
    assert body["status"] in ("ok", "degraded")
    assert "db" in body
