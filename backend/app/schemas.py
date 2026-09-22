from pydantic import BaseModel


class ReadingIn(BaseModel):
    temp_c: float
    humidity: float
    is_light_on: bool | None = None
    is_heater_on: bool | None = None


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
