# Electricity Trade Simulator

LP-based optimizer for battery energy storage system (BESS) charge/discharge scheduling. Finds optimal times to buy and sell electricity on the Nord Pool spot market to maximize profit.

## How it works

The optimizer uses linear programming (scipy linprog / HiGHS) to decide when to charge the battery from the grid (buy cheap) and when to discharge to the grid (sell expensive), respecting battery constraints: capacity, minimum SOC, charge/discharge power limits, and round-trip efficiency losses.

Two optimization modes:

- **Oracle** — knows all prices for the entire month upfront (perfect foresight). Upper bound on achievable profit.
- **Realistic** — simulates day-ahead market conditions. Before 14:00, only today's prices are known; after 14:00, tomorrow's prices become available. Re-optimizes at each boundary using a rolling horizon.

## Price data

Included SQLite database (`databases/prices.db`) contains Nord Pool Estonia spot prices from 2015-01-01 to 2026-02-15. Hourly intervals before October 2025, 15-minute intervals after. Slot duration is auto-detected.

## Configuration

All parameters are in `config.toml` with TOML profile support:

```toml
[default]
battery_capacity_kwh = 45.0        # total capacity (kWh)
min_soc_pct = 20                   # minimum state of charge (%)
max_charge_kw = 5.5                # max charge power — grid draw rate (kW AC)
max_discharge_kw = 6.5             # max discharge power — inverter output (kW AC)
charge_efficiency = 0.80           # charging efficiency (0-1)
discharge_efficiency = 0.90        # discharging efficiency (0-1)
initial_soc_pct = 100              # initial SOC (%)
home_consumption_kw = 1.54         # home consumption (kW), reduces grid export during discharge

# Delivery fees (day/night tariff)
delivery_fee_day_eur_mwh = 36.9
delivery_fee_night_eur_mwh = 21.0
night_start_hour = 22
night_end_hour = 7
night_on_weekends = true
vat_pct = 24

# Sell pricing
buyer_margin_eur_mwh = 15.0        # buyer margin deducted from spot price

[large_battery]
battery_capacity_kwh = 90.0        # override specific params, rest inherited from [default]
```

## Usage

```bash
# Install (requires uv)
uv sync

# Run single mode
etsim run 2026-01 --mode oracle
etsim run 2026-01 --mode realistic

# Compare both modes side by side
etsim compare 2026-01

# Use a different config profile
etsim run 2026-01 --mode oracle --profile large_battery

# Export to CSV
etsim run 2026-01 --mode oracle --output results.csv
```

## Example output

```
$ etsim compare 2026-01

                    Oracle vs Realistic Comparison
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Metric          ┃         Oracle ┃      Realistic ┃            Diff ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ Profit          │    26.1679 EUR │    18.3011 EUR │     +7.8668 EUR │
│ Revenue         │    70.7505 EUR │    64.9449 EUR │     +5.8056 EUR │
│ Avg Buy Price   │ 0.1185 EUR/kWh │ 0.1265 EUR/kWh │ -0.0080 EUR/kWh │
│ Avg Sell Price  │ 0.3071 EUR/kWh │ 0.2876 EUR/kWh │ +0.0194 EUR/kWh │
└─────────────────┴────────────────┴────────────────┴─────────────────┘
```

## Tests

```bash
uv run pytest
```

## Key pricing formulas

- **Buy price**: `(spot + delivery_fee) * (1 + VAT%) / 1000` EUR/kWh — delivery fee varies by day/night tariff
- **Sell price**: `max(0, (spot - buyer_margin)) / 1000` EUR/kWh
- **Grid export during discharge**: `inverter_output - home_consumption` (home draws from inverter first)
