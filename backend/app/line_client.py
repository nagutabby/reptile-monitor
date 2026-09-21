"""LINE Messaging API (push message) の薄いクライアント。LINE Notifyは2025年3月に
全利用者向けにサービス終了しているため使用不可。"""

import httpx

from . import config

_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def push_message(text: str) -> None:
    resp = httpx.post(
        _PUSH_URL,
        headers={
            "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"to": config.LINE_TO_ID, "messages": [{"type": "text", "text": text}]},
        timeout=10.0,
    )
    resp.raise_for_status()
