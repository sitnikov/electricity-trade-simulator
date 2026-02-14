from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Action(Enum):
    CHARGE = "charge"
    DISCHARGE = "discharge"
    IDLE = "idle"


@dataclass
class Slot:
    dt: datetime
    price_eur_mwh: float


@dataclass
class SlotResult:
    dt: datetime
    price_eur_mwh: float
    action: Action
    energy_kwh: float  # energy moved to/from battery
    energy_grid_kwh: float  # energy taken from / sent to grid
    buy_price_kwh: float  # EUR/kWh effective buy price
    sell_price_kwh: float  # EUR/kWh effective sell price
    cost_eur: float  # cost of buying (positive)
    revenue_eur: float  # revenue from selling (positive)
    soc_kwh: float  # SOC after this slot
    soc_pct: float  # SOC % after this slot

    @property
    def profit_eur(self) -> float:
        return self.revenue_eur - self.cost_eur


@dataclass
class Summary:
    total_profit_eur: float
    total_bought_kwh: float
    total_sold_kwh: float
    total_cost_eur: float
    total_revenue_eur: float
    charge_cycles: int
    discharge_cycles: int
    avg_buy_price_kwh: float
    avg_sell_price_kwh: float
