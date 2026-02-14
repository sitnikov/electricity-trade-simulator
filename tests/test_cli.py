import tempfile
from pathlib import Path

from click.testing import CliRunner

from etsim.cli import main


def test_run_oracle(test_db: Path, default_config) -> None:
    config_toml = f"""\
[default]
battery_capacity_kwh = 10.0
min_soc_pct = 10
max_charge_kw = 5.0
max_discharge_kw = 5.0
charge_efficiency = 0.95
discharge_efficiency = 0.95
initial_soc_pct = 50
home_consumption_kw = 0.5
delivery_fee_day_eur_mwh = 50.0
delivery_fee_night_eur_mwh = 30.0
night_start_hour = 22
night_end_hour = 7
night_on_weekends = true
vat_pct = 21
buyer_margin_eur_mwh = 10.0
db_path = "{test_db}"
db_table = "prices"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_toml)
        config_path = f.name

    runner = CliRunner()
    result = runner.invoke(main, ["run", "2025-01", "--mode", "oracle", "--config", config_path])
    assert result.exit_code == 0, result.output
    assert "Summary" in result.output

    Path(config_path).unlink(missing_ok=True)


def test_run_no_data(test_db: Path) -> None:
    config_toml = f"""\
[default]
battery_capacity_kwh = 10.0
min_soc_pct = 10
max_charge_kw = 5.0
max_discharge_kw = 5.0
charge_efficiency = 0.95
discharge_efficiency = 0.95
initial_soc_pct = 50
home_consumption_kw = 0.5
delivery_fee_day_eur_mwh = 50.0
delivery_fee_night_eur_mwh = 30.0
night_start_hour = 22
night_end_hour = 7
night_on_weekends = true
vat_pct = 21
buyer_margin_eur_mwh = 10.0
db_path = "{test_db}"
db_table = "prices"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_toml)
        config_path = f.name

    runner = CliRunner()
    result = runner.invoke(main, ["run", "2030-06", "--config", config_path])
    assert result.exit_code == 1

    Path(config_path).unlink(missing_ok=True)
