"""ヒョウモントカゲモドキ ケージの温湿度モニター (Streamlit)。

FastAPIバックエンドの GET /api/readings を叩いて可視化する(D1には直接アクセスしない)。
"""

import os

import altair as alt
import httpx
import pandas as pd
import streamlit as st

# dataviz skill の色指定(categorical slot 1=blue, slot 2=orange, status critical=red)。
# ライトモード値をそのまま使用(Streamlitのダーク/ライト自動切替への個別最適化はしていない)。
COLOR_TEMP = "#2a78d6"
COLOR_HUMIDITY = "#eb6834"
COLOR_CRITICAL = "#d03b3b"

st.set_page_config(page_title="ヒョウモントカゲモドキ温湿度モニター", page_icon="🦎", layout="wide")


def _get_setting(key: str) -> str:
    if key in st.secrets:
        return st.secrets[key]
    return os.environ[key]


FASTAPI_URL = _get_setting("FASTAPI_URL").rstrip("/")
API_KEY = _get_setting("API_KEY")

# 異常値の目安ライン(表示用)。backend/app/config.py の値と一致させること。
TEMP_MIN_C = 24.0
TEMP_MAX_C = 30.0
HUMIDITY_MIN = 40.0
HUMIDITY_MAX = 90.0


@st.cache_data(ttl=60)
def fetch_readings(limit: int = 500) -> pd.DataFrame:
    resp = httpx.get(
        f"{FASTAPI_URL}/api/readings",
        headers={"X-API-Key": API_KEY},
        params={"limit": limit},
        timeout=10.0,
    )
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    if df.empty:
        return df
    df["recorded_at"] = pd.to_datetime(df["recorded_at"])
    return df.sort_values("recorded_at")


def line_chart_with_thresholds(
    df: pd.DataFrame,
    value_col: str,
    color: str,
    min_threshold: float,
    max_threshold: float,
    y_title: str,
    y_domain: tuple[float, float] | None = None,
) -> alt.Chart:
    y_scale = alt.Scale(domain=list(y_domain)) if y_domain else alt.Undefined
    line = (
        alt.Chart(df)
        .mark_line(strokeWidth=2, color=color)
        .encode(
            x=alt.X("recorded_at:T", title=None),
            y=alt.Y(f"{value_col}:Q", title=y_title, scale=y_scale),
            tooltip=[alt.Tooltip("recorded_at:T", title="時刻"), alt.Tooltip(f"{value_col}:Q", title=y_title)],
        )
    )
    thresholds = pd.DataFrame({"y": [min_threshold, max_threshold]})
    rules = (
        alt.Chart(thresholds)
        .mark_rule(strokeWidth=1, color=COLOR_CRITICAL)
        .encode(y="y:Q")
    )
    labels = (
        alt.Chart(thresholds)
        .mark_text(align="left", dx=4, dy=-4, color=COLOR_CRITICAL, fontSize=11)
        .encode(y="y:Q", text=alt.Text("y:Q"), x=alt.value(0))
    )
    return (line + rules + labels).properties(height=280).interactive()


st.title("🦎 ヒョウモントカゲモドキ 温湿度モニター")

df = fetch_readings()

if df.empty:
    st.info("まだデータがありません。M5Stackからのレポート送信をお待ちください。")
else:
    latest = df.iloc[-1]
    is_temp_abnormal = latest["temp_c"] < TEMP_MIN_C or latest["temp_c"] > TEMP_MAX_C
    is_humidity_abnormal = latest["humidity"] < HUMIDITY_MIN or latest["humidity"] > HUMIDITY_MAX

    col1, col2 = st.columns(2)
    col1.metric("最新温度", f"{latest['temp_c']:.1f} ℃", delta="異常" if is_temp_abnormal else None, delta_color="inverse")
    col2.metric("最新湿度", f"{latest['humidity']:.0f} %", delta="異常" if is_humidity_abnormal else None, delta_color="inverse")

    st.caption(f"最終更新: {latest['recorded_at']}")

    st.subheader("温度の推移")
    st.altair_chart(
        line_chart_with_thresholds(df, "temp_c", COLOR_TEMP, TEMP_MIN_C, TEMP_MAX_C, "温度 (℃)", y_domain=(20, 35)),
        use_container_width=True,
    )

    st.subheader("湿度の推移")
    st.altair_chart(
        line_chart_with_thresholds(df, "humidity", COLOR_HUMIDITY, HUMIDITY_MIN, HUMIDITY_MAX, "湿度 (%)"),
        use_container_width=True,
    )

    with st.expander("データ表を表示"):
        st.dataframe(df.sort_values("recorded_at", ascending=False), use_container_width=True)
