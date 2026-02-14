# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BESS (Battery Energy Storage System) electricity trade optimizer. Finds optimal charge/discharge schedule to maximize profit from buying/selling electricity on the grid, given 15-minute spot price data.

## Commands

```bash
# Install dependencies (uses uv, installs Python 3.12 automatically)
uv sync

# Run optimizer
uv run etsim run 2025-01 --mode oracle
uv run etsim run 2025-01 --mode realistic --profile large_battery --output results.csv

# Run all tests
uv run pytest

# Run single test
uv run pytest tests/test_optimizer.py::test_oracle_profitable_cycle -v

# Lint
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

## Architecture

```
src/etsim/
├── cli.py          # Click CLI entry point (etsim command)
├── config.py       # TOML config loading with profile inheritance from [default]
├── db.py           # SQLite reader — loads 15-min price slots for a month
├── models.py       # Dataclasses: Slot, SlotResult, Summary, Action enum
├── pricing.py      # Buy/sell price formulas (spot + fees + VAT / spot - margin)
├── optimizer.py    # LP optimizer (scipy linprog) — core logic
└── report.py       # Rich console tables + CSV export
```

### Data Flow

`CLI → config.load_config() → db.load_prices() → optimizer.optimize_{oracle|realistic}() → report.print_results()`

### Optimizer Modes

- **Oracle**: LP over entire month with perfect foresight. Upper bound on profit.
- **Realistic**: Rolling horizon LP. Before 14:00 knows today's prices; after 14:00 knows today+tomorrow. Re-optimizes at each boundary, commits only the known portion.

### Key Formulas (in pricing.py)

- Buy: `(spot + delivery_fee) * (1 + VAT%) / 1000` → EUR/kWh
- Sell: `max(0, spot - buyer_margin) / 1000` → EUR/kWh
- Discharge to grid: `discharge * eff_discharge - home_consumption * 0.25h` (inverter limitation)

### Configuration

`config.toml` uses TOML profiles. Non-default profiles inherit missing keys from `[default]`. Selected via `--profile` CLI flag.

### Database

SQLite in `databases/`, table with columns `datetime` (text, ISO format) and `price` (real, EUR/MWh). 15-minute intervals.
