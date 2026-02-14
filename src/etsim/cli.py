from __future__ import annotations

from pathlib import Path

import click

from etsim.config import DEFAULT_CONFIG_PATH, load_config
from etsim.db import detect_slot_duration_h, load_prices
from etsim.optimizer import compute_summary, optimize_oracle, optimize_realistic
from etsim.report import export_csv, print_comparison, print_results


@click.group()
def main() -> None:
    """BESS electricity trade optimizer."""


@main.command()
@click.argument("month")
@click.option("--mode", type=click.Choice(["oracle", "realistic"]), default="oracle",
              help="Optimization mode.")
@click.option("--profile", default="default", help="Config profile name.")
@click.option("--config", "config_path", type=click.Path(exists=True),
              default=str(DEFAULT_CONFIG_PATH), help="Path to config.toml.")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Export results to CSV file.")
def run(month: str, mode: str, profile: str, config_path: str, output: str | None) -> None:
    """Run optimization for a given MONTH (format: YYYY-MM).

    Example: etsim run 2025-01 --mode oracle --profile default
    """
    config = load_config(Path(config_path), profile)

    click.echo(f"Loading prices for {month} from {config.db_path}...")
    slots = load_prices(config.db_path, config.db_table, month)

    if not slots:
        click.echo(f"No price data found for {month}.", err=True)
        raise SystemExit(1)

    # Detect slot duration from data and update config
    config.slot_duration_h = detect_slot_duration_h(slots)

    dt = config.slot_duration_h
    slot_label = f"{int(dt * 60)}min" if dt < 1 else f"{dt:.0f}h"
    click.echo(f"Found {len(slots)} slots ({slot_label} intervals). Running {mode} optimization...")

    if mode == "oracle":
        results = optimize_oracle(slots, config)
    else:
        results = optimize_realistic(slots, config)

    summary = compute_summary(results)
    print_results(results, summary)

    if output:
        export_csv(results, summary, Path(output))
        click.echo(f"Results exported to {output}")


@main.command()
@click.argument("month")
@click.option("--profile", default="default", help="Config profile name.")
@click.option("--config", "config_path", type=click.Path(exists=True),
              default=str(DEFAULT_CONFIG_PATH), help="Path to config.toml.")
def compare(month: str, profile: str, config_path: str) -> None:
    """Compare oracle vs realistic for a given MONTH (format: YYYY-MM)."""
    config = load_config(Path(config_path), profile)

    click.echo(f"Loading prices for {month} from {config.db_path}...")
    slots = load_prices(config.db_path, config.db_table, month)

    if not slots:
        click.echo(f"No price data found for {month}.", err=True)
        raise SystemExit(1)

    config.slot_duration_h = detect_slot_duration_h(slots)

    dt = config.slot_duration_h
    slot_label = f"{int(dt * 60)}min" if dt < 1 else f"{dt:.0f}h"
    click.echo(f"Found {len(slots)} slots ({slot_label} intervals). Running both modes...")

    oracle_results = optimize_oracle(slots, config)
    realistic_results = optimize_realistic(slots, config)

    oracle_summary = compute_summary(oracle_results)
    realistic_summary = compute_summary(realistic_results)

    print_comparison(oracle_summary, realistic_summary)
