import logging
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request

from . import alerts, config, d1
from .schemas import ReadingIn, ReadingOut

app = FastAPI(title="Reptile Monitor API")
logger = logging.getLogger("reptile_monitor")


def verify_api_key(x_api_key: str = Header(...)) -> None:
    if x_api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="invalid API key")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/api/readings", status_code=201, dependencies=[Depends(verify_api_key)])
def create_reading(reading: ReadingIn) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    d1.query(
        "INSERT INTO readings (temp_c, humidity, recorded_at) VALUES (?, ?, ?)",
        [reading.temp_c, reading.humidity, now],
    )
    alerts.evaluate_and_notify(reading.temp_c, reading.humidity)
    return {"status": "ok"}


@app.get("/api/readings", response_model=list[ReadingOut], dependencies=[Depends(verify_api_key)])
def list_readings(limit: int = Query(default=500, le=2500)) -> list[dict]:
    return d1.query(
        "SELECT id, temp_c, humidity, recorded_at FROM readings ORDER BY recorded_at DESC LIMIT ?",
        [limit],
    )


# LINE_TO_ID(push先のuserId)を特定するための診断用エンドポイント。LINE Developers
# コンソールのWebhook URLにここを設定し、ボットにメッセージを送るとサーバーログに
# userIdが出力される。署名検証はしていない(ログ出力のみで副作用がなく、ID特定後は
# LINE側のWebhook設定を無効化して構わないため)。
@app.post("/api/line/webhook")
async def line_webhook(request: Request) -> dict:
    body = await request.json()
    for event in body.get("events", []):
        user_id = event.get("source", {}).get("userId")
        if user_id:
            logger.info("[LINE webhook] userId=%s", user_id)
    return {"status": "ok"}
