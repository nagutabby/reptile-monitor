"""室内(ケージ内)環境計測値のドメイン型。

FastAPI/Pydanticに依存しない、純粋な値オブジェクト。ここでのバリデーションは
「センサーの計測値として物理的にありえるか」(BLEデータ化け・故障の検知)であり、
「ヒョウモントカゲモドキの飼育環境として適切か」(config.TEMP_MIN_C等、alerts.pyの
通知閾値)とは別の関心事なので混同しない。
"""

from dataclasses import dataclass

# SwitchBot防水温湿度計の仕様上あり得る計測範囲。これを外れる値はセンサー異常や
# BLEデータ化けとみなし、システム境界(POST /api/readings)で拒否する。
TEMP_C_MIN = -20.0
TEMP_C_MAX = 60.0
HUMIDITY_PERCENT_MIN = 0.0
HUMIDITY_PERCENT_MAX = 100.0


@dataclass(frozen=True, order=True)
class Temperature:
    celsius: float

    def __post_init__(self) -> None:
        if not (TEMP_C_MIN <= self.celsius <= TEMP_C_MAX):
            raise ValueError(f"temp_c must be between {TEMP_C_MIN} and {TEMP_C_MAX}: {self.celsius}")


@dataclass(frozen=True, order=True)
class Humidity:
    percent: float

    def __post_init__(self) -> None:
        if not (HUMIDITY_PERCENT_MIN <= self.percent <= HUMIDITY_PERCENT_MAX):
            raise ValueError(
                f"humidity must be between {HUMIDITY_PERCENT_MIN} and {HUMIDITY_PERCENT_MAX}: {self.percent}"
            )


@dataclass(frozen=True)
class Environment:
    """ケージ内の温湿度計測値(1回分)。温度・湿度はどちらも同じ室内環境を表す一組の値。"""

    temperature: Temperature
    humidity: Humidity
