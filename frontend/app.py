"""ヒョウモントカゲモドキ ケージの温湿度モニター (Streamlit)。

FastAPIバックエンドの GET /api/readings を叩いて可視化する(D1には直接アクセスしない)。
"""

import os
from datetime import timedelta

import altair as alt
import httpx
import pandas as pd
import streamlit as st

# レオパ配色(config.tomlの背景色 #1a130f を基準に dataviz skill の
# validate_palette.js でCVD分離度・コントラストを検証済み)。
# 温度=黄金(体色)、湿度=スレートブルー(スノー系モルフ)、危険域=赤茶(体色寄りの警告色)。
COLOR_TEMP = "#c08a20"
COLOR_HUMIDITY = "#5a8ac2"
COLOR_CRITICAL = "#aa413c"

PAGE_TITLE = "レオパ温湿度モニター"

st.set_page_config(page_title=PAGE_TITLE, layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap');

    html, body, [class^="st-"], .stApp {
        font-family: "Noto Sans JP", sans-serif;
    }
    /* Streamlitのアイコン(expanderの矢印等)はMaterial Symbolsのリガチャ文字を
       アイコンとして描画しているため、フォントを上書きすると文字("arrow_..."等)が
       そのまま表示されてしまう。アイコン要素だけは元のフォントに戻す。 */
    [data-testid="stIconMaterial"] {
        font-family: "Material Symbols Rounded" !important;
    }
    /* モバイル幅ではタイトルとサブヘッダーのサイズ差が見た目のバランスを崩すため、
       タイトルを縮小しサブヘッダーをさらに縮小して差を詰める。 */
    @media (max-width: 480px) {
        .stApp h1 {
            font-size: 1.75rem;
        }
        .stApp h2 {
            font-size: 1.625rem;
        }
        .stApp h3 {
            font-size: 1.5rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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

# M5Stack側の温湿度収集間隔(1分。温湿度計本体のデータ記録間隔に合わせている)に
# 揃えた自動更新間隔。それより速く更新しても新しいデータは来ないため、選択肢にはしない。
AUTO_REFRESH_SECONDS = 60

# グラフの描画範囲選択肢。ラベル -> 表示期間。
RANGE_OPTIONS = {
    "30分": timedelta(minutes=30),
    "6時間": timedelta(hours=6),
    "12時間": timedelta(hours=12),
    "1日": timedelta(days=1),
    "1週間": timedelta(weeks=1),
}
DEFAULT_RANGE_LABEL = "6時間"


@st.cache_data(ttl=10)
def fetch_device_state() -> dict:
    resp = httpx.get(
        f"{FASTAPI_URL}/api/device_state",
        headers={"X-API-Key": API_KEY},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=10)
def fetch_readings(minutes: int) -> pd.DataFrame:
    resp = httpx.get(
        f"{FASTAPI_URL}/api/readings",
        headers={"X-API-Key": API_KEY},
        params={"minutes": minutes},
        timeout=10.0,
    )
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    if df.empty:
        return df
    # idはフロントエンドで使わないため表示しない。
    df = df.drop(columns=["id"])
    # バックエンドはUTCで記録している(datetime.now(timezone.utc))ため、表示はJSTに変換する。
    df["recorded_at"] = pd.to_datetime(df["recorded_at"]).dt.tz_convert("Asia/Tokyo")
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
        .mark_line(strokeWidth=3, color=color)
        .encode(
            x=alt.X(
                "recorded_at:T",
                title=None,
                # tickMinStep(時間軸ではミリ秒単位)を5分に固定し、データ間隔(1分)より
                # 密な目盛りが生成されて同じ分表示が連続する事態を防ぐ。
                axis=alt.Axis(format="%H:%M", tickMinStep=5 * 60 * 1000),
            ),
            y=alt.Y(f"{value_col}:Q", title=y_title, scale=y_scale),
            tooltip=[alt.Tooltip("recorded_at:T", title="時刻"), alt.Tooltip(f"{value_col}:Q", title=y_title)],
        )
    )
    thresholds = pd.DataFrame({"y": [min_threshold, max_threshold]})
    rules = (
        alt.Chart(thresholds)
        .mark_rule(strokeWidth=0.75, color=COLOR_CRITICAL)
        .encode(y="y:Q")
    )
    labels = (
        alt.Chart(thresholds)
        .mark_text(align="left", dx=4, dy=-4, color=COLOR_CRITICAL, fontSize=11)
        .encode(y="y:Q", text=alt.Text("y:Q"), x=alt.value(0))
    )
    return (line + rules + labels).properties(height=280).interactive()


def _device_state_label(is_on: bool | None) -> str:
    if is_on is None:
        return "不明"
    return "ON" if is_on else "OFF"


st.title(PAGE_TITLE)
st.caption("1分ごとに自動更新されます。")

if "range_label" not in st.session_state:
    st.session_state.range_label = DEFAULT_RANGE_LABEL

selected_label = st.segmented_control(
    "グラフの表示範囲",
    options=list(RANGE_OPTIONS.keys()),
    default=st.session_state.range_label,
    # keyを固定しないと、defaultの値(=session_state)が変わるたびにウィジェットの
    # 自動生成キーも変わってしまい、クリックした値が次回再実行時に反映されず
    # 2回目のクリックでようやく切り替わる不具合が起きる。
    key="range_label_widget",
)
# 選択中のボタンをもう一度押すと選択解除されNoneが返るため、その場合は前回の選択を保つ。
if selected_label is not None:
    st.session_state.range_label = selected_label

selected_range = RANGE_OPTIONS[st.session_state.range_label]


@st.fragment(run_every=AUTO_REFRESH_SECONDS)
def render_dashboard() -> None:
    # 選択範囲をそのままDB側の絞り込み条件(直近何分前まで)として渡す。
    minutes = int(selected_range.total_seconds() // 60)
    df = fetch_readings(minutes)

    if df.empty:
        st.info("まだデータがありません。M5Stackからのレポート送信をお待ちください。")
        return

    latest = df.iloc[-1]
    is_temp_abnormal = latest["temp_c"] < TEMP_MIN_C or latest["temp_c"] > TEMP_MAX_C
    is_humidity_abnormal = latest["humidity"] < HUMIDITY_MIN or latest["humidity"] > HUMIDITY_MAX

    device_state = fetch_device_state()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("最新温度", f"{latest['temp_c']:.1f} ℃", delta="異常" if is_temp_abnormal else None, delta_color="inverse")
    col2.metric("最新湿度", f"{latest['humidity']:.0f} %", delta="異常" if is_humidity_abnormal else None, delta_color="inverse")
    col3.metric("ライト", _device_state_label(device_state["is_light_on"]))
    col4.metric("パネルヒーター", _device_state_label(device_state["is_heater_on"]))

    st.caption(f"最終更新: {latest['recorded_at'].strftime('%Y-%m-%d %H:%M:%S')}")

    st.subheader("温度の推移")
    st.altair_chart(
        line_chart_with_thresholds(df, "temp_c", COLOR_TEMP, TEMP_MIN_C, TEMP_MAX_C, "温度 (℃)", y_domain=(20, 35)),
        use_container_width=True,
    )

    st.subheader("湿度の推移")
    st.altair_chart(
        line_chart_with_thresholds(
            df, "humidity", COLOR_HUMIDITY, HUMIDITY_MIN, HUMIDITY_MAX, "湿度 (%)", y_domain=(20, 100)
        ),
        use_container_width=True,
    )

    with st.expander("データ表を表示"):
        st.dataframe(df.sort_values("recorded_at", ascending=False), use_container_width=True)


render_dashboard()
