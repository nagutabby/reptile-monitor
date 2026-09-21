"""LINE Messaging API (push message) の薄いクライアント。LINE Notifyは2025年3月に
全利用者向けにサービス終了しているため使用不可。"""

import httpx

from . import config

_PUSH_URL = "https://api.line.me/v2/bot/message/push"

# リクエストごとにTCP/TLS接続を張り直さないよう、プロセス内で使い回す。
_client = httpx.Client(
    headers={
        "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    },
    timeout=10.0,
)


def push_message(text: str) -> None:
    resp = _client.post(
        _PUSH_URL,
        json={"to": config.LINE_TO_ID, "messages": [{"type": "text", "text": text}]},
    )
    resp.raise_for_status()
