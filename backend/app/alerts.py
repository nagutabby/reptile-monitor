"""異常値判定とLINE通知の重複抑制。

「正常→異常」への遷移時のみ通知し、異常が続く間は ALERT_RESEND_INTERVAL_SEC ごとに
再通知する。直前の状態はD1のalert_stateテーブル(id=1固定の1行)に保存するため、
バックエンドの再起動後も状態を失わない。
"""

from datetime import datetime, timezone

from . import config, d1, line_client


def is_abnormal(temp_c: float, humidity: float) -> bool:
    return (
        temp_c < config.TEMP_MIN_C
        or temp_c > config.TEMP_MAX_C
        or humidity < config.HUMIDITY_MIN
        or humidity > config.HUMIDITY_MAX
    )


def _get_alert_state() -> tuple[bool, datetime | None]:
    rows = d1.query("SELECT is_abnormal, last_alert_at FROM alert_state WHERE id = 1")
    if not rows:
        return False, None
    row = rows[0]
    last_alert_at = datetime.fromisoformat(row["last_alert_at"]) if row["last_alert_at"] else None
    return bool(row["is_abnormal"]), last_alert_at


def _set_alert_state(is_abnormal_now: bool, last_alert_at: datetime | None) -> None:
    d1.query(
        "UPDATE alert_state SET is_abnormal = ?, last_alert_at = ? WHERE id = 1",
        [int(is_abnormal_now), last_alert_at.isoformat() if last_alert_at else None],
    )


def evaluate_and_notify(temp_c: float, humidity: float) -> None:
    abnormal_now = is_abnormal(temp_c, humidity)
    was_abnormal, last_alert_at = _get_alert_state()

    if not abnormal_now:
        if was_abnormal:
            _set_alert_state(False, last_alert_at)
        return

    now = datetime.now(timezone.utc)
    should_notify = (
        not was_abnormal
        or last_alert_at is None
        or (now - last_alert_at).total_seconds() >= config.ALERT_RESEND_INTERVAL_SEC
    )

    if should_notify:
        line_client.push_message(
            "[異常値検知] ヒョウモントカゲモドキ ケージ\n"
            f"温度: {temp_c:.1f}C / 湿度: {humidity:.0f}%\n"
            f"許容範囲: 温度{config.TEMP_MIN_C:.0f}-{config.TEMP_MAX_C:.0f}C, "
            f"湿度{config.HUMIDITY_MIN:.0f}-{config.HUMIDITY_MAX:.0f}%"
        )
        _set_alert_state(True, now)
