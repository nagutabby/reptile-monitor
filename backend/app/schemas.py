from pydantic import BaseModel, field_validator

from .domain import Environment, Humidity, Temperature


class ReadingIn(BaseModel):
    temp_c: float
    humidity: float
    is_light_on: bool | None = None
    is_heater_on: bool | None = None

    @field_validator("temp_c")
    @classmethod
    def _validate_temp_c(cls, v: float) -> float:
        Temperature(v)  # 範囲外ならValueError -> FastAPIが422にする
        return v

    @field_validator("humidity")
    @classmethod
    def _validate_humidity(cls, v: float) -> float:
        Humidity(v)
        return v

    def to_environment(self) -> Environment:
        return Environment(Temperature(self.temp_c), Humidity(self.humidity))


class ReadingOut(BaseModel):
    id: int
    temp_c: float
    humidity: float
    recorded_at: str


class DeviceStateOut(BaseModel):
    is_light_on: bool | None
    is_light_on_changed_at: str | None
    is_heater_on: bool | None
    is_heater_on_changed_at: str | None
