from datetime import datetime

from etsim.config import Config
from etsim.pricing import calc_buy_price, calc_sell_price, is_night


def test_buy_price_day(default_config: Config) -> None:
    # Day: (100 + 50) * 1.21 / 1000 = 0.1815
    dt = datetime(2025, 1, 6, 12, 0)  # Monday noon
    result = calc_buy_price(100.0, default_config, dt)
    assert abs(result - 0.1815) < 1e-6


def test_buy_price_night(default_config: Config) -> None:
    # Night: (100 + 30) * 1.21 / 1000 = 0.1573
    dt = datetime(2025, 1, 6, 23, 0)  # Monday 23:00
    result = calc_buy_price(100.0, default_config, dt)
    assert abs(result - 0.1573) < 1e-6


def test_buy_price_weekend_is_night(default_config: Config) -> None:
    # Weekend noon should use night tariff: (100 + 30) * 1.21 / 1000 = 0.1573
    dt = datetime(2025, 1, 4, 12, 0)  # Saturday noon
    result = calc_buy_price(100.0, default_config, dt)
    assert abs(result - 0.1573) < 1e-6


def test_buy_price_negative_spot(default_config: Config) -> None:
    dt = datetime(2025, 1, 6, 12, 0)
    # (-50 + 50) * 1.21 / 1000 = 0.0
    result = calc_buy_price(-50.0, default_config, dt)
    assert abs(result - 0.0) < 1e-6


def test_sell_price(default_config: Config) -> None:
    # max(0, (100 - 10)) / 1000 = 0.09
    result = calc_sell_price(100.0, default_config)
    assert abs(result - 0.09) < 1e-6


def test_sell_price_low_spot(default_config: Config) -> None:
    # max(0, (5 - 10)) / 1000 = 0.0
    result = calc_sell_price(5.0, default_config)
    assert result == 0.0


def test_sell_price_negative_spot(default_config: Config) -> None:
    result = calc_sell_price(-20.0, default_config)
    assert result == 0.0


def test_is_night_weekday_night(default_config: Config) -> None:
    assert is_night(datetime(2025, 1, 6, 23, 0), default_config) is True
    assert is_night(datetime(2025, 1, 6, 3, 0), default_config) is True


def test_is_night_weekday_day(default_config: Config) -> None:
    assert is_night(datetime(2025, 1, 6, 12, 0), default_config) is False
    assert is_night(datetime(2025, 1, 6, 7, 0), default_config) is False


def test_is_night_weekend(default_config: Config) -> None:
    assert is_night(datetime(2025, 1, 4, 12, 0), default_config) is True  # Saturday
    assert is_night(datetime(2025, 1, 5, 12, 0), default_config) is True  # Sunday
