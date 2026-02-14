# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BESS (Battery Energy Storage System) electricity trade optimizer. Finds optimal charge/discharge schedule to maximize profit from buying/selling electricity on the grid, given spot price data (15-min or hourly intervals, auto-detected).

## Commands

```bash
uv sync                          # install dependencies
uv run etsim run 2026-01 --mode oracle
uv run etsim run 2026-01 --mode realistic
uv run etsim compare 2026-01     # side-by-side oracle vs realistic
uv run etsim run 2026-01 --mode oracle --profile large_battery --output results.csv

uv run pytest                    # all tests
uv run pytest tests/test_optimizer.py::test_oracle_profitable_cycle -v
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

## Architecture

```
src/etsim/
├── cli.py          # Click CLI: run, compare commands
├── config.py       # TOML config with profile inheritance from [default]
├── db.py           # SQLite reader, auto-detects slot duration (15min/1h)
├── models.py       # Dataclasses: Slot, SlotResult, Summary, Action enum
├── pricing.py      # Buy/sell price formulas, day/night delivery fee tariffs
├── optimizer.py    # LP optimizer (scipy linprog) — core logic
└── report.py       # Rich console tables, comparison table, CSV export
```

### Data Flow

`CLI → config.load_config() → db.load_prices() → optimizer.optimize_{oracle|realistic}() → report`

### Optimizer (optimizer.py)

LP variables per slot: `charge[t]` (grid draw, kWh) and `discharge[t]` (inverter AC output, kWh).

- `max_charge_kw` = grid draw rate (AC). Battery receives `charge * eff_c`.
- `max_discharge_kw` = inverter output rate (AC). Battery drains `discharge / eff_d`.
- Home consumption reduces grid export: `grid_export = discharge - home_consumption * dt`
- Linearized as `effective_grid_ratio = 1 - home_per_slot / max_discharge_per_slot`
- SOC constraint: `SOC[t] = initial + Σ(charge * eff_c) - Σ(discharge / eff_d)`

**Oracle**: LP over entire month (perfect foresight, upper bound on profit).
**Realistic**: Rolling horizon LP. Before 14:00 knows today; after 14:00 knows today+tomorrow. Re-optimizes at each boundary.

### Pricing (pricing.py)

- Buy: `(spot + delivery_fee) * (1 + VAT%) / 1000` → EUR/kWh
- Sell: `max(0, spot - buyer_margin) / 1000` → EUR/kWh
- Delivery fee: day/night tariff (weekdays 22:00-07:00 = night, weekends = night)

### Configuration

`config.toml` with TOML profiles. Non-default profiles inherit from `[default]`. Selected via `--profile` CLI flag.

### Database

SQLite in `databases/`, real schema has columns: `id, source_id, datetime (TEXT with tz offset), price (REAL EUR/MWh), created_at, updated_at, ts`. Code handles timezone offsets and strips tzinfo. Data can be hourly or 15-min (auto-detected).
