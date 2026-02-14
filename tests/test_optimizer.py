from datetime import datetime, timedelta

from etsim.config import Config
from etsim.models import Action, Slot
from etsim.optimizer import compute_summary, optimize_oracle, optimize_realistic


def _config_with_min_soc_start(default_config: Config) -> Config:
    """Config where initial SOC = min SOC (battery nearly empty)."""
    return Config(
        **{**default_config.__dict__, "initial_soc_pct": default_config.min_soc_pct}
    )


def test_oracle_no_slots(default_config: Config) -> None:
    results = optimize_oracle([], default_config)
    assert results == []


def test_oracle_profitable_cycle(default_config: Config) -> None:
    """Low price then high price should result in charge then discharge."""
    cfg = _config_with_min_soc_start(default_config)
    slots = [
        Slot(dt=datetime(2025, 1, 1, 2, 0), price_eur_mwh=10.0),
        Slot(dt=datetime(2025, 1, 1, 2, 15), price_eur_mwh=10.0),
        Slot(dt=datetime(2025, 1, 1, 14, 0), price_eur_mwh=200.0),
        Slot(dt=datetime(2025, 1, 1, 14, 15), price_eur_mwh=200.0),
    ]
    results = optimize_oracle(slots, cfg)
    assert len(results) == 4

    actions = [r.action for r in results]
    assert Action.CHARGE in actions
    assert Action.DISCHARGE in actions

    summary = compute_summary(results)
    assert summary.total_profit_eur > 0


def test_oracle_unprofitable_no_trade(default_config: Config) -> None:
    """When spread doesn't cover losses + fees, should stay idle.

    Start at min SOC so there's no free energy to sell.
    """
    cfg = _config_with_min_soc_start(default_config)
    slots = [
        Slot(dt=datetime(2025, 1, 1, i, 0), price_eur_mwh=50.0)
        for i in range(24)
    ]
    results = optimize_oracle(slots, cfg)
    summary = compute_summary(results)
    # With flat prices, no profitable round-trip exists
    assert summary.total_profit_eur <= 0.01  # allow tiny numerical noise


def test_oracle_soc_limits(default_config: Config) -> None:
    """SOC should never go below min or above capacity."""
    base = datetime(2025, 1, 1, 0, 0)
    slots = [
        Slot(
            dt=base + timedelta(minutes=15 * i),
            price_eur_mwh=10.0 if i < 48 else 300.0,
        )
        for i in range(96)
    ]
    results = optimize_oracle(slots, default_config)
    for r in results:
        assert r.soc_kwh >= default_config.min_soc_kwh - 0.01
        assert r.soc_kwh <= default_config.battery_capacity_kwh + 0.01


def test_oracle_sells_existing_energy(default_config: Config) -> None:
    """With initial SOC > min, optimizer should sell existing energy when profitable."""
    slots = [
        Slot(dt=datetime(2025, 1, 1, 14, 0), price_eur_mwh=200.0),
        Slot(dt=datetime(2025, 1, 1, 14, 15), price_eur_mwh=200.0),
    ]
    results = optimize_oracle(slots, default_config)
    assert any(r.action == Action.DISCHARGE for r in results)
    summary = compute_summary(results)
    assert summary.total_profit_eur > 0


def test_realistic_produces_results(default_config: Config, sample_slots: list[Slot]) -> None:
    """Realistic mode should produce results for all slots."""
    results = optimize_realistic(sample_slots, default_config)
    assert len(results) == len(sample_slots)


def test_realistic_vs_oracle_profit(default_config: Config, sample_slots: list[Slot]) -> None:
    """Oracle should always be >= realistic in terms of profit."""
    oracle_results = optimize_oracle(sample_slots, default_config)
    realistic_results = optimize_realistic(sample_slots, default_config)

    oracle_summary = compute_summary(oracle_results)
    realistic_summary = compute_summary(realistic_results)

    assert oracle_summary.total_profit_eur >= realistic_summary.total_profit_eur - 0.01


def test_compute_summary(default_config: Config) -> None:
    slots = [
        Slot(dt=datetime(2025, 1, 1, 2, 0), price_eur_mwh=10.0),
        Slot(dt=datetime(2025, 1, 1, 14, 0), price_eur_mwh=200.0),
    ]
    results = optimize_oracle(slots, default_config)
    summary = compute_summary(results)

    assert summary.total_profit_eur == summary.total_revenue_eur - summary.total_cost_eur
    assert summary.charge_cycles + summary.discharge_cycles <= len(results)
