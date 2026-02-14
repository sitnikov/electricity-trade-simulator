from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config.toml")


@dataclass
class Config:
    # Battery
    battery_capacity_kwh: float
    min_soc_pct: float
    max_charge_kw: float
    max_discharge_kw: float
    charge_efficiency: float
    discharge_efficiency: float
    initial_soc_pct: float

    # Home consumption
    home_consumption_kw: float

    # Buy pricing
    delivery_fee_day_eur_mwh: float
    delivery_fee_night_eur_mwh: float
    night_start_hour: int
    night_end_hour: int
    night_on_weekends: bool
    vat_pct: float

    # Sell pricing
    buyer_margin_eur_mwh: float

    # Database
    db_path: str
    db_table: str

    @property
    def min_soc_kwh(self) -> float:
        return self.battery_capacity_kwh * self.min_soc_pct / 100

    @property
    def initial_soc_kwh(self) -> float:
        return self.battery_capacity_kwh * self.initial_soc_pct / 100

    # Set at runtime based on detected data interval
    slot_duration_h: float = 0.25


def load_config(path: Path = DEFAULT_CONFIG_PATH, profile: str = "default") -> Config:
    with open(path, "rb") as f:
        data = tomllib.load(f)

    if "default" not in data:
        raise ValueError("config.toml must have a [default] section")

    params = dict(data["default"])

    if profile != "default":
        if profile not in data:
            raise ValueError(f"Profile '{profile}' not found in {path}")
        params.update(data[profile])

    return Config(**params)
