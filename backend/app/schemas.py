from pydantic import BaseModel


class ReadingIn(BaseModel):
    temp_c: float
    humidity: float


class ReadingOut(BaseModel):
    id: int
    temp_c: float
    humidity: float
    recorded_at: str
