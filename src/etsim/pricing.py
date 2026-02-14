from __future__ import annotations

from datetime import datetime

from etsim.config import Config


def is_night(dt: datetime, config: Config) -> bool:
    """Check if a given datetime falls into the night tariff period."""
    # Weekends are night tariff if configured
    if config.night_on_weekends and dt.weekday() >= 5:
        return True
    hour = dt.hour
    if config.night_start_hour > config.night_end_hour:
        # e.g. 22:00 - 07:00
        return hour >= config.night_start_hour or hour < config.night_end_hour
    else:
        return config.night_start_hour <= hour < config.night_end_hour


def delivery_fee(dt: datetime, config: Config) -> float:
    """Return delivery fee in EUR/MWh for the given datetime."""
    if is_night(dt, config):
        return config.delivery_fee_night_eur_mwh
    return config.delivery_fee_day_eur_mwh


def calc_buy_price(spot_price_eur_mwh: float, config: Config, dt: datetime | None = None) -> float:
    """Calculate effective buy price in EUR/kWh.

    buy_price = (spot + delivery_fee) * (1 + VAT%) / 1000
    """
    fee = delivery_fee(dt, config) if dt is not None else config.delivery_fee_day_eur_mwh
    return (spot_price_eur_mwh + fee) * (1 + config.vat_pct / 100) / 1000


def calc_sell_price(spot_price_eur_mwh: float, config: Config) -> float:
    """Calculate effective sell price in EUR/kWh.

    sell_price = max(0, (spot - buyer_margin)) / 1000
    """
    return max(0.0, (spot_price_eur_mwh - config.buyer_margin_eur_mwh)) / 1000
