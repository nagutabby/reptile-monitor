"""APIエンドポイントの認証・呼び出しの回帰テスト(D1/LINEへは実際には接続しない)。"""

from fastapi.testclient import TestClient

from app import alerts, config
from app import d1 as d1_module
from app.main import app

client = TestClient(app)


def test_list_readings_requires_api_key_header():
    resp = client.get("/api/readings")
    assert resp.status_code == 422  # ヘッダー自体が無い


def test_list_readings_rejects_wrong_api_key():
    resp = client.get("/api/readings", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 401


def test_create_reading_inserts_and_evaluates_alert(monkeypatch):
    inserted_sql = []
    monkeypatch.setattr(d1_module, "query", lambda sql, params=None: inserted_sql.append(sql) or [])

    notified = []
    monkeypatch.setattr(alerts, "evaluate_and_notify", lambda temp_c, humidity: notified.append((temp_c, humidity)))

    resp = client.post(
        "/api/readings",
        headers={"X-API-Key": config.API_KEY},
        json={"temp_c": 27.0, "humidity": 50.0},
    )

    assert resp.status_code == 201
    assert notified == [(27.0, 50.0)]
    assert any(sql.startswith("INSERT") for sql in inserted_sql)
