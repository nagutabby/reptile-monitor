"""APIエンドポイントの認証・呼び出しの回帰テスト(D1/LINEへは実際には接続しない)。"""

from fastapi.testclient import TestClient

from app import alerts, config
from app import d1 as d1_module
from app.main import MAX_LOOKBACK_MINUTES, app

client = TestClient(app)


def test_list_readings_requires_api_key_header():
    resp = client.get("/api/readings")
    assert resp.status_code == 422  # ヘッダー自体が無い


def test_list_readings_rejects_wrong_api_key():
    resp = client.get("/api/readings", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 401


def test_list_readings_filters_by_minutes(monkeypatch):
    queries = []
    fake_rows = [{"id": 1, "temp_c": 27.0, "humidity": 50.0, "recorded_at": "2026-09-21T00:00:00+00:00"}]
    monkeypatch.setattr(d1_module, "query", lambda sql, params=None: queries.append((sql, params)) or fake_rows)

    resp = client.get("/api/readings", headers={"X-API-Key": config.API_KEY}, params={"minutes": 30})

    assert resp.status_code == 200
    assert resp.json() == fake_rows
    assert len(queries) == 1
    sql, params = queries[0]
    assert "WHERE recorded_at >= ?" in sql
    assert "ORDER BY recorded_at ASC" in sql
    assert len(params) == 1  # cutoff(直近30分前の時刻)のみ


def test_list_readings_default_minutes_is_used_when_omitted(monkeypatch):
    queries = []
    monkeypatch.setattr(d1_module, "query", lambda sql, params=None: queries.append((sql, params)) or [])

    resp = client.get("/api/readings", headers={"X-API-Key": config.API_KEY})

    assert resp.status_code == 200
    assert len(queries) == 1


def test_list_readings_rejects_minutes_below_one():
    resp = client.get("/api/readings", headers={"X-API-Key": config.API_KEY}, params={"minutes": 0})
    assert resp.status_code == 422


def test_list_readings_rejects_minutes_beyond_one_week():
    resp = client.get(
        "/api/readings", headers={"X-API-Key": config.API_KEY}, params={"minutes": MAX_LOOKBACK_MINUTES + 1}
    )
    assert resp.status_code == 422


def test_list_readings_accepts_minutes_at_one_week_boundary(monkeypatch):
    monkeypatch.setattr(d1_module, "query", lambda sql, params=None: [])

    resp = client.get(
        "/api/readings", headers={"X-API-Key": config.API_KEY}, params={"minutes": MAX_LOOKBACK_MINUTES}
    )

    assert resp.status_code == 200


def test_device_state_requires_api_key_header():
    resp = client.get("/api/device_state")
    assert resp.status_code == 422  # ヘッダー自体が無い


def test_device_state_returns_latest_non_null_values(monkeypatch):
    queries = []

    def fake_query(sql, params=None):
        queries.append(sql)
        if "is_light_on" in sql:
            return [{"is_light_on": 1, "recorded_at": "2026-09-22T10:00:00+00:00"}]
        return [{"is_heater_on": 0, "recorded_at": "2026-09-22T09:00:00+00:00"}]

    monkeypatch.setattr(d1_module, "query", fake_query)

    resp = client.get("/api/device_state", headers={"X-API-Key": config.API_KEY})

    assert resp.status_code == 200
    assert resp.json() == {
        "is_light_on": True,
        "is_light_on_changed_at": "2026-09-22T10:00:00+00:00",
        "is_heater_on": False,
        "is_heater_on_changed_at": "2026-09-22T09:00:00+00:00",
    }
    assert len(queries) == 2


def test_device_state_is_null_when_never_reported(monkeypatch):
    monkeypatch.setattr(d1_module, "query", lambda sql, params=None: [])

    resp = client.get("/api/device_state", headers={"X-API-Key": config.API_KEY})

    assert resp.status_code == 200
    assert resp.json() == {
        "is_light_on": None,
        "is_light_on_changed_at": None,
        "is_heater_on": None,
        "is_heater_on_changed_at": None,
    }


def test_create_reading_inserts_and_evaluates_alert(monkeypatch):
    inserted_sql = []
    monkeypatch.setattr(d1_module, "query", lambda sql, params=None: inserted_sql.append(sql) or [])

    notified = []
    monkeypatch.setattr(alerts, "evaluate_and_notify", lambda environment: notified.append(environment))

    resp = client.post(
        "/api/readings",
        headers={"X-API-Key": config.API_KEY},
        json={"temp_c": 27.0, "humidity": 50.0},
    )

    assert resp.status_code == 201
    assert len(notified) == 1
    assert notified[0].temperature.celsius == 27.0
    assert notified[0].humidity.percent == 50.0
    assert any(sql.startswith("INSERT") for sql in inserted_sql)


def test_create_reading_accepts_optional_device_state(monkeypatch):
    inserted_params = []
    monkeypatch.setattr(
        d1_module, "query", lambda sql, params=None: inserted_params.append(params) or []
    )
    monkeypatch.setattr(alerts, "evaluate_and_notify", lambda environment: None)

    resp = client.post(
        "/api/readings",
        headers={"X-API-Key": config.API_KEY},
        json={"temp_c": 27.0, "humidity": 50.0, "is_light_on": True, "is_heater_on": False},
    )

    assert resp.status_code == 201
    assert inserted_params == [[27.0, 50.0, True, False, inserted_params[0][4]]]


def test_create_reading_rejects_out_of_range_temp_c():
    resp = client.post(
        "/api/readings",
        headers={"X-API-Key": config.API_KEY},
        json={"temp_c": 60.1, "humidity": 50.0},
    )
    assert resp.status_code == 422


def test_create_reading_rejects_out_of_range_humidity():
    resp = client.post(
        "/api/readings",
        headers={"X-API-Key": config.API_KEY},
        json={"temp_c": 27.0, "humidity": 100.1},
    )
    assert resp.status_code == 422


def test_create_reading_stores_null_when_device_state_omitted(monkeypatch):
    inserted_params = []
    monkeypatch.setattr(
        d1_module, "query", lambda sql, params=None: inserted_params.append(params) or []
    )
    monkeypatch.setattr(alerts, "evaluate_and_notify", lambda environment: None)

    resp = client.post(
        "/api/readings",
        headers={"X-API-Key": config.API_KEY},
        json={"temp_c": 27.0, "humidity": 50.0},
    )

    assert resp.status_code == 201
    assert inserted_params == [[27.0, 50.0, None, None, inserted_params[0][4]]]
