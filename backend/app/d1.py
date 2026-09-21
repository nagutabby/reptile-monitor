"""Cloudflare D1をWorkersバインディングなしでHTTP経由から使うための薄いラッパー。"""

import httpx

from . import config

_QUERY_URL = (
    f"https://api.cloudflare.com/client/v4/accounts/{config.CLOUDFLARE_ACCOUNT_ID}"
    f"/d1/database/{config.CLOUDFLARE_D1_DATABASE_ID}/query"
)


def query(sql: str, params: list | None = None) -> list[dict]:
    """SQLを1文実行し、結果行(SELECTなら行のリスト、INSERT/UPDATEなら空リスト)を返す。"""
    resp = httpx.post(
        _QUERY_URL,
        headers={"Authorization": f"Bearer {config.CLOUDFLARE_API_TOKEN}"},
        json={"sql": sql, "params": params or []},
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data["success"]:
        raise RuntimeError(f"D1 query failed: {data['errors']}")
    return data["result"][0]["results"]
