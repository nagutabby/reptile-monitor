"""異常値判定とLINE通知の重複抑制ロジックの回帰テスト。

このロジックは一度、再通知抑制の仕様(異常が続いている間はALERT_RESEND_INTERVAL_SEC
ごとにしか再通知しない)を「通知が届かない不具合」と誤解しかけた経緯があるため、
状態遷移(正常→異常、異常継続、異常→正常)を明示的にテストする。
"""

from datetime import datetime, timedelta, timezone

import pytest

from app import alerts, config
from app.domain import Environment, Humidity, Temperature


def _env(temp_c: float, humidity: float) -> Environment:
    return Environment(Temperature(temp_c), Humidity(humidity))


class FakeD1:
    """alert_state テーブル1行分をメモリ上で模倣するフェイク。"""

    def __init__(self):
        self.state = {"is_abnormal": 0, "last_alert_at": None}

    def query(self, sql, params=None):
        if sql.startswith("SELECT"):
            return [dict(self.state)]
        if sql.startswith("UPDATE"):
            is_abnormal, last_alert_at = params
            self.state = {"is_abnormal": is_abnormal, "last_alert_at": last_alert_at}
            return []
        raise AssertionError(f"unexpected SQL in test: {sql}")


@pytest.fixture
def fake_d1(monkeypatch):
    fake = FakeD1()
    monkeypatch.setattr(alerts, "d1", fake)
    return fake


@pytest.fixture
def sent_messages(monkeypatch):
    sent: list[str] = []
    monkeypatch.setattr(alerts.line_client, "push_message", lambda text: sent.append(text))
    return sent


@pytest.mark.parametrize(
    ("temp_c", "humidity", "expected"),
    [
        (config.TEMP_MIN_C, config.HUMIDITY_MIN, False),  # 下限そのものは正常側
        (config.TEMP_MIN_C - 0.1, config.HUMIDITY_MIN, True),  # 温度が下限未満
        (config.TEMP_MAX_C, config.HUMIDITY_MIN, False),  # 上限そのものは正常側
        (config.TEMP_MAX_C + 0.1, config.HUMIDITY_MIN, True),  # 温度が上限超過
        (27.0, config.HUMIDITY_MIN - 0.1, True),  # 湿度が下限未満
        (27.0, config.HUMIDITY_MAX, False),  # 上限そのものは正常側
        (27.0, config.HUMIDITY_MAX + 0.1, True),  # 湿度が上限超過
        (27.0, 50.0, False),  # 両方正常範囲内
    ],
)
def test_is_abnormal_boundaries(temp_c, humidity, expected):
    assert alerts.is_abnormal(_env(temp_c, humidity)) is expected


def test_normal_to_normal_does_not_notify(fake_d1, sent_messages):
    alerts.evaluate_and_notify(_env(27.0, 50.0))

    assert sent_messages == []
    assert fake_d1.state["is_abnormal"] == 0


def test_normal_to_abnormal_notifies_once(fake_d1, sent_messages):
    alerts.evaluate_and_notify(_env(config.TEMP_MIN_C - 1, 50.0))

    assert len(sent_messages) == 1
    assert fake_d1.state["is_abnormal"] == 1


def test_repeated_abnormal_within_resend_interval_is_suppressed(fake_d1, sent_messages):
    alerts.evaluate_and_notify(_env(config.TEMP_MIN_C - 1, 50.0))
    assert len(sent_messages) == 1

    # 異常が続いたまま(別の指標=湿度)でも、再通知抑制期間中は通知しない。
    alerts.evaluate_and_notify(_env(27.0, config.HUMIDITY_MIN - 1))

    assert len(sent_messages) == 1


def test_repeated_abnormal_after_resend_interval_renotifies(fake_d1, sent_messages):
    alerts.evaluate_and_notify(_env(config.TEMP_MIN_C - 1, 50.0))
    assert len(sent_messages) == 1

    long_ago = datetime.now(timezone.utc) - timedelta(seconds=config.ALERT_RESEND_INTERVAL_SEC + 1)
    fake_d1.state["last_alert_at"] = long_ago.isoformat()

    alerts.evaluate_and_notify(_env(config.TEMP_MIN_C - 1, 50.0))

    assert len(sent_messages) == 2


def test_abnormal_to_normal_resets_state_without_notifying(fake_d1, sent_messages):
    alerts.evaluate_and_notify(_env(config.TEMP_MIN_C - 1, 50.0))
    assert fake_d1.state["is_abnormal"] == 1
    assert len(sent_messages) == 1

    alerts.evaluate_and_notify(_env(27.0, 50.0))

    assert fake_d1.state["is_abnormal"] == 0
    assert len(sent_messages) == 1  # 2回目(正常化)では通知していない
