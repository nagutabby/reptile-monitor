"""ドメイン値オブジェクト(Temperature/Humidity/Environment)の単体テスト。

FastAPI/D1を一切使わない、純粋なバリデーションロジックだけの回帰テスト。
"""

import pytest

from app.domain import Environment, Humidity, Temperature


def test_temperature_accepts_lower_bound():
    assert Temperature(-20.0).celsius == -20.0


def test_temperature_accepts_upper_bound():
    assert Temperature(60.0).celsius == 60.0


def test_temperature_rejects_below_lower_bound():
    with pytest.raises(ValueError):
        Temperature(-20.1)


def test_temperature_rejects_above_upper_bound():
    with pytest.raises(ValueError):
        Temperature(60.1)


def test_humidity_accepts_lower_bound():
    assert Humidity(0.0).percent == 0.0


def test_humidity_accepts_upper_bound():
    assert Humidity(100.0).percent == 100.0


def test_humidity_rejects_negative():
    with pytest.raises(ValueError):
        Humidity(-0.1)


def test_humidity_rejects_above_100():
    with pytest.raises(ValueError):
        Humidity(100.1)


def test_temperature_is_orderable():
    assert Temperature(20.0) < Temperature(25.0)
    assert Temperature(25.0) > Temperature(20.0)
    assert not (Temperature(25.0) < Temperature(25.0))


def test_humidity_is_orderable():
    assert Humidity(40.0) < Humidity(50.0)
    assert Humidity(50.0) > Humidity(40.0)
    assert not (Humidity(50.0) < Humidity(50.0))


def test_environment_pairs_temperature_and_humidity():
    env = Environment(Temperature(25.0), Humidity(50.0))

    assert env.temperature.celsius == 25.0
    assert env.humidity.percent == 50.0
