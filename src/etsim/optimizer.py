"""LP-based optimizer for BESS charge/discharge scheduling.

Uses scipy.optimize.linprog to solve a linear program that maximizes profit
subject to battery constraints.

Variables per slot t (N slots total):
    charge[t]    — energy taken from grid (kWh), >= 0
    discharge[t] — inverter AC output (kWh), >= 0

max_charge_kw is the grid draw rate (AC).  Battery receives charge * eff_c.
max_discharge_kw is the inverter output rate (AC).  Battery drains discharge / eff_d.

Variable vector x = [charge[0..N-1], discharge[0..N-1]]

Home consumption is modeled as an inverter limitation: during discharge,
home_consumption_kw * dt of inverter output goes to the home, reducing
grid export. This is linearized by using an effective grid ratio:
    effective_grid_ratio = 1 - home_per_slot / max_discharge_per_slot
which is exact when discharge is at max rate (the typical case).
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
from scipy.optimize import linprog

from etsim.config import Config
from etsim.models import Action, Slot, SlotResult, Summary


def _build_and_solve(
    slots: list[Slot],
    config: Config,
    initial_soc: float,
) -> list[SlotResult]:
    """Solve the LP for a sequence of slots and return SlotResults."""
    from etsim.pricing import calc_buy_price, calc_sell_price

    n = len(slots)
    if n == 0:
        return []

    dt = config.slot_duration_h
    cap = config.battery_capacity_kwh
    min_soc = config.min_soc_kwh
    eff_c = config.charge_efficiency
    eff_d = config.discharge_efficiency
    home_per_slot = config.home_consumption_kw * dt
    max_charge_per_slot = config.max_charge_kw * dt
    max_discharge_per_slot = config.max_discharge_kw * dt  # inverter AC output

    # Effective grid ratio: fraction of inverter output that goes to grid.
    # grid_export = discharge - home_per_slot
    # Linearized at max rate: effective_grid_ratio = 1 - home_per_slot / max_discharge_per_slot
    if max_discharge_per_slot > 0:
        effective_grid_ratio = max(0.0, 1.0 - home_per_slot / max_discharge_per_slot)
    else:
        effective_grid_ratio = 0.0

    buy_prices = np.array([calc_buy_price(s.price_eur_mwh, config, s.dt) for s in slots])
    sell_prices = np.array([calc_sell_price(s.price_eur_mwh, config) for s in slots])

    # ---- Objective: minimize c^T x ----
    # x = [charge[0..n-1], discharge[0..n-1]]
    # maximize: sum(sell_price[t] * discharge[t] * effective_grid_ratio - buy_price[t] * charge[t])
    c = np.zeros(2 * n)
    c[:n] = buy_prices                              # cost of charging
    c[n:] = -sell_prices * effective_grid_ratio      # revenue from selling

    # ---- Bounds ----
    bounds = [(0, max_charge_per_slot)] * n + [(0, max_discharge_per_slot)] * n

    # ---- SOC constraints ----
    # SOC[t] = initial_soc + sum(charge[0..t] * eff_c) - sum(discharge[0..t] / eff_d)
    # Battery drains at discharge / eff_d because discharge is AC output.
    inv_eff_d = 1.0 / eff_d

    a_ub_rows = []
    b_ub_rows = []

    for t in range(n):
        # SOC[t] <= cap
        row = np.zeros(2 * n)
        row[:t + 1] = eff_c
        row[n:n + t + 1] = -inv_eff_d
        a_ub_rows.append(row)
        b_ub_rows.append(cap - initial_soc)

        # SOC[t] >= min_soc
        row2 = np.zeros(2 * n)
        row2[:t + 1] = -eff_c
        row2[n:n + t + 1] = inv_eff_d
        a_ub_rows.append(row2)
        b_ub_rows.append(initial_soc - min_soc)

    a_ub = np.array(a_ub_rows)
    b_ub = np.array(b_ub_rows)

    result = linprog(c, A_ub=a_ub, b_ub=b_ub, bounds=bounds, method="highs")

    if not result.success:
        raise RuntimeError(f"Optimization failed: {result.message}")

    charge = result.x[:n]
    discharge = result.x[n:]  # inverter AC output per slot

    # ---- Build SlotResults ----
    soc = initial_soc
    slot_results = []
    threshold = 0.001  # kWh, below this we treat as idle

    for t in range(n):
        s = slots[t]
        ch = charge[t]
        dis = discharge[t]
        bp = buy_prices[t]
        sp = sell_prices[t]

        if ch > threshold and ch > dis:
            action = Action.CHARGE
            energy_battery = ch * eff_c          # energy into battery
            energy_grid = ch                      # energy from grid
            cost = ch * bp
            revenue = 0.0
            soc += energy_battery
        elif dis > threshold and dis >= ch:
            action = Action.DISCHARGE
            energy_battery = dis / eff_d          # energy from battery (DC)
            energy_to_grid = max(0.0, dis - home_per_slot)  # AC output minus home
            energy_grid = energy_to_grid
            cost = 0.0
            revenue = energy_to_grid * sp
            soc -= energy_battery
        else:
            action = Action.IDLE
            energy_battery = 0.0
            energy_grid = 0.0
            cost = 0.0
            revenue = 0.0

        soc = max(min_soc, min(soc, cap))

        slot_results.append(SlotResult(
            dt=s.dt,
            price_eur_mwh=s.price_eur_mwh,
            action=action,
            energy_kwh=energy_battery,
            energy_grid_kwh=energy_grid,
            buy_price_kwh=bp,
            sell_price_kwh=sp,
            cost_eur=cost,
            revenue_eur=revenue,
            soc_kwh=round(soc, 4),
            soc_pct=round(soc / cap * 100, 2),
        ))

    return slot_results


def optimize_oracle(slots: list[Slot], config: Config) -> list[SlotResult]:
    """Oracle mode: optimize over all slots at once (perfect foresight)."""
    return _build_and_solve(slots, config, config.initial_soc_kwh)


def optimize_realistic(slots: list[Slot], config: Config) -> list[SlotResult]:
    """Realistic mode: rolling horizon optimization with day-ahead prices.

    Rules:
    - Before 14:00: we know prices for the current day only
    - At/after 14:00: we know prices for current day + next day
    - We re-optimize at 14:00 when new prices become available
    - We also re-optimize at midnight when a new day starts

    We solve the LP on the known horizon, commit the slots until the next
    re-optimization point, then advance.
    """
    if not slots:
        return []

    all_results: list[SlotResult] = []
    soc = config.initial_soc_kwh
    committed_until = 0  # index into slots

    # Group slots by date for quick lookup
    slots_by_date: dict[str, list[int]] = {}
    for i, s in enumerate(slots):
        date_key = s.dt.strftime("%Y-%m-%d")
        slots_by_date.setdefault(date_key, []).append(i)

    while committed_until < len(slots):
        current_slot = slots[committed_until]
        current_date = current_slot.dt.strftime("%Y-%m-%d")
        current_hour = current_slot.dt.hour + current_slot.dt.minute / 60

        # Determine known horizon
        today_indices = slots_by_date.get(current_date, [])
        known_end = max(today_indices) + 1 if today_indices else committed_until + 1

        if current_hour >= 14:
            # We also know tomorrow
            next_date = (current_slot.dt.replace(hour=0, minute=0, second=0)
                         + __import__("datetime").timedelta(days=1))
            next_date_key = next_date.strftime("%Y-%m-%d")
            tomorrow_indices = slots_by_date.get(next_date_key, [])
            if tomorrow_indices:
                known_end = max(tomorrow_indices) + 1

        # Determine commit point: slots until next re-optimization
        if current_hour < 14:
            commit_end = committed_until
            for i in range(committed_until, known_end):
                slot_hour = slots[i].dt.hour + slots[i].dt.minute / 60
                if slots[i].dt.strftime("%Y-%m-%d") == current_date and slot_hour < 14:
                    commit_end = i + 1
                else:
                    break
        else:
            commit_end = committed_until
            for i in range(committed_until, known_end):
                if slots[i].dt.strftime("%Y-%m-%d") == current_date:
                    commit_end = i + 1
                else:
                    break

        commit_end = max(commit_end, committed_until + 1)

        horizon_slots = slots[committed_until:known_end]
        horizon_results = _build_and_solve(horizon_slots, config, soc)

        n_commit = commit_end - committed_until
        committed_results = horizon_results[:n_commit]
        all_results.extend(committed_results)

        if committed_results:
            soc = committed_results[-1].soc_kwh

        committed_until = commit_end

    return all_results


def compute_summary(results: list[SlotResult]) -> Summary:
    """Compute summary statistics from slot results."""
    total_cost = sum(r.cost_eur for r in results)
    total_revenue = sum(r.revenue_eur for r in results)
    total_bought = sum(r.energy_grid_kwh for r in results if r.action == Action.CHARGE)
    total_sold = sum(r.energy_grid_kwh for r in results if r.action == Action.DISCHARGE)
    charge_count = sum(1 for r in results if r.action == Action.CHARGE)
    discharge_count = sum(1 for r in results if r.action == Action.DISCHARGE)

    return Summary(
        total_profit_eur=total_revenue - total_cost,
        total_bought_kwh=total_bought,
        total_sold_kwh=total_sold,
        total_cost_eur=total_cost,
        total_revenue_eur=total_revenue,
        charge_cycles=charge_count,
        discharge_cycles=discharge_count,
        avg_buy_price_kwh=total_cost / total_bought if total_bought > 0 else 0,
        avg_sell_price_kwh=total_revenue / total_sold if total_sold > 0 else 0,
    )
