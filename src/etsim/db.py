from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from etsim.models import Slot


def load_prices(db_path: str | Path, table: str, month: str) -> list[Slot]:
    """Load price slots for a given month.

    Handles both hourly and 15-minute data. Datetime strings may include
    timezone offsets (e.g. '2025-01-01 00:00:00+02').

    Args:
        db_path: Path to SQLite database.
        table: Table name.
        month: Month in format "YYYY-MM".

    Returns:
        List of Slot objects sorted by datetime (timezone-naive, as-is from DB).
    """
    year, mon = month.split("-")
    start = f"{year}-{mon}-01"
    m = int(mon)
    if m == 12:
        end = f"{int(year) + 1}-01-01"
    else:
        end = f"{year}-{m + 1:02d}-01"

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            f'SELECT datetime, price FROM "{table}" '
            "WHERE datetime >= ? AND datetime < ? ORDER BY datetime",
            (start, end),
        ).fetchall()
    finally:
        conn.close()

    slots = []
    for dt_str, price in rows:
        dt = _parse_datetime(dt_str)
        slots.append(Slot(dt=dt, price_eur_mwh=float(price)))

    return slots


def _parse_datetime(dt_str: str) -> datetime:
    """Parse datetime string, stripping timezone offset for simplicity."""
    # fromisoformat handles '+02' offset in Python 3.11+
    dt = datetime.fromisoformat(dt_str)
    # Store as naive datetime (local time as recorded in DB)
    return dt.replace(tzinfo=None)


def detect_slot_duration_h(slots: list[Slot]) -> float:
    """Detect slot duration from the data (hours).

    Returns 0.25 for 15-min data, 1.0 for hourly, etc.
    """
    if len(slots) < 2:
        return 0.25  # default to 15 min

    # Check the most common interval in first 10 slots
    deltas: list[timedelta] = []
    for i in range(min(10, len(slots) - 1)):
        deltas.append(slots[i + 1].dt - slots[i].dt)

    # Most common delta
    median_delta = sorted(deltas)[len(deltas) // 2]
    return median_delta.total_seconds() / 3600
