from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from etsim.config import Config
from etsim.models import Slot


@pytest.fixture
def default_config() -> Config:
    return Config(
        battery_capacity_kwh=10.0,
        min_soc_pct=10,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        initial_soc_pct=50,
        home_consumption_kw=0.5,
        delivery_fee_day_eur_mwh=50.0,
        delivery_fee_night_eur_mwh=30.0,
        night_start_hour=22,
        night_end_hour=7,
        night_on_weekends=True,
        vat_pct=21,
        buyer_margin_eur_mwh=10.0,
        db_path="test.db",
        db_table="prices",
    )


@pytest.fixture
def sample_slots() -> list[Slot]:
    """24 hours of slots (96 x 15min) with a price pattern: low at night, high midday."""
    base = datetime(2025, 1, 1, 0, 0, 0)
    slots = []
    for i in range(96):
        dt = base + timedelta(minutes=15 * i)
        hour = dt.hour + dt.minute / 60
        # Price: 20 EUR/MWh at night, peaks at 150 EUR/MWh at noon
        if 6 <= hour <= 20:
            price = 20 + 130 * (1 - abs(hour - 13) / 7)
        else:
            price = 20.0
        slots.append(Slot(dt=dt, price_eur_mwh=round(price, 2)))
    return slots


@pytest.fixture
def test_db(sample_slots: list[Slot]) -> Path:
    """Create a temporary SQLite database with sample prices."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE prices (datetime TEXT, price REAL)")
    for s in sample_slots:
        conn.execute(
            "INSERT INTO prices VALUES (?, ?)",
            (s.dt.isoformat(), s.price_eur_mwh),
        )
    conn.commit()
    conn.close()

    yield db_path

    db_path.unlink(missing_ok=True)
