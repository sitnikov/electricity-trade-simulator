import tempfile
from pathlib import Path

import pytest

from etsim.config import Config, load_config

SAMPLE_TOML = """\
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
db_path = "databases/prices.db"
db_table = "prices"

[big]
battery_capacity_kwh = 20.0
max_charge_kw = 10.0
"""


@pytest.fixture
def config_file() -> Path:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_TOML)
        p = Path(f.name)
    yield p
    p.unlink(missing_ok=True)


def test_load_default(config_file: Path) -> None:
    cfg = load_config(config_file)
    assert cfg.battery_capacity_kwh == 10.0
    assert cfg.min_soc_kwh == 1.0
    assert cfg.initial_soc_kwh == 5.0


def test_load_profile_inherits(config_file: Path) -> None:
    cfg = load_config(config_file, profile="big")
    assert cfg.battery_capacity_kwh == 20.0
    assert cfg.max_charge_kw == 10.0
    # inherited from default
    assert cfg.charge_efficiency == 0.95
    assert cfg.home_consumption_kw == 0.5


def test_unknown_profile(config_file: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        load_config(config_file, profile="nonexistent")
