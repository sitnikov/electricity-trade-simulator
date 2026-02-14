from __future__ import annotations

import csv
from pathlib import Path

from rich.console import Console
from rich.table import Table

from etsim.models import Action, SlotResult, Summary


def print_results(results: list[SlotResult], summary: Summary) -> None:
    """Print detailed results and summary to console using rich."""
    console = Console()

    table = Table(title="BESS Optimization Results", show_lines=False)
    table.add_column("Datetime", style="cyan", no_wrap=True)
    table.add_column("Spot EUR/MWh", justify="right")
    table.add_column("Action", justify="center")
    table.add_column("Energy kWh", justify="right")
    table.add_column("Grid kWh", justify="right")
    table.add_column("Cost EUR", justify="right")
    table.add_column("Revenue EUR", justify="right")
    table.add_column("Profit EUR", justify="right")
    table.add_column("SOC kWh", justify="right")
    table.add_column("SOC %", justify="right")

    for r in results:
        action_style = {
            Action.CHARGE: "green",
            Action.DISCHARGE: "red",
            Action.IDLE: "dim",
        }[r.action]

        profit = r.profit_eur
        profit_style = "green" if profit > 0 else ("red" if profit < 0 else "dim")

        table.add_row(
            r.dt.strftime("%Y-%m-%d %H:%M"),
            f"{r.price_eur_mwh:.2f}",
            f"[{action_style}]{r.action.value}[/]",
            f"{r.energy_kwh:.3f}" if r.action != Action.IDLE else "-",
            f"{r.energy_grid_kwh:.3f}" if r.action != Action.IDLE else "-",
            f"{r.cost_eur:.4f}" if r.cost_eur > 0 else "-",
            f"{r.revenue_eur:.4f}" if r.revenue_eur > 0 else "-",
            f"[{profit_style}]{profit:.4f}[/]" if r.action != Action.IDLE else "-",
            f"{r.soc_kwh:.2f}",
            f"{r.soc_pct:.1f}",
        )

    console.print(table)
    console.print()

    # Summary
    summary_table = Table(title="Monthly Summary", show_header=False)
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value", justify="right")

    profit_style = "green" if summary.total_profit_eur >= 0 else "red"
    summary_table.add_row("Total Profit", f"[{profit_style}]{summary.total_profit_eur:.4f} EUR[/]")
    summary_table.add_row("Total Cost", f"{summary.total_cost_eur:.4f} EUR")
    summary_table.add_row("Total Revenue", f"{summary.total_revenue_eur:.4f} EUR")
    summary_table.add_row("Total Bought", f"{summary.total_bought_kwh:.3f} kWh")
    summary_table.add_row("Total Sold", f"{summary.total_sold_kwh:.3f} kWh")
    summary_table.add_row("Charge Slots", str(summary.charge_cycles))
    summary_table.add_row("Discharge Slots", str(summary.discharge_cycles))
    summary_table.add_row("Avg Buy Price", f"{summary.avg_buy_price_kwh:.4f} EUR/kWh")
    summary_table.add_row("Avg Sell Price", f"{summary.avg_sell_price_kwh:.4f} EUR/kWh")

    console.print(summary_table)


def print_comparison(oracle: Summary, realistic: Summary) -> None:
    """Print side-by-side comparison of oracle and realistic summaries."""
    console = Console()

    table = Table(title="Oracle vs Realistic Comparison", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Oracle", justify="right")
    table.add_column("Realistic", justify="right")
    table.add_column("Diff", justify="right")

    rows = [
        ("Profit", "total_profit_eur", "EUR", True),
        ("Cost", "total_cost_eur", "EUR", False),
        ("Revenue", "total_revenue_eur", "EUR", False),
        ("Bought", "total_bought_kwh", "kWh", False),
        ("Sold", "total_sold_kwh", "kWh", False),
        ("Charge Slots", "charge_cycles", "", False),
        ("Discharge Slots", "discharge_cycles", "", False),
        ("Avg Buy Price", "avg_buy_price_kwh", "EUR/kWh", False),
        ("Avg Sell Price", "avg_sell_price_kwh", "EUR/kWh", False),
    ]

    for label, attr, unit, highlight in rows:
        o_val = getattr(oracle, attr)
        r_val = getattr(realistic, attr)
        diff = o_val - r_val

        if isinstance(o_val, int):
            o_str = f"{o_val} {unit}".strip()
            r_str = f"{r_val} {unit}".strip()
            d_str = f"{diff:+d} {unit}".strip()
        else:
            o_str = f"{o_val:.4f} {unit}".strip()
            r_str = f"{r_val:.4f} {unit}".strip()
            d_str = f"{diff:+.4f} {unit}".strip()

        if highlight:
            o_style = "green" if o_val >= 0 else "red"
            r_style = "green" if r_val >= 0 else "red"
            o_str = f"[{o_style}]{o_str}[/]"
            r_str = f"[{r_style}]{r_str}[/]"

        d_style = "green" if diff > 0 else ("red" if diff < 0 else "dim")
        d_str = f"[{d_style}]{d_str}[/]"

        table.add_row(label, o_str, r_str, d_str)

    console.print(table)


def export_csv(results: list[SlotResult], summary: Summary, path: Path) -> None:
    """Export results to CSV file."""
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "datetime", "price_eur_mwh", "action", "energy_kwh", "grid_kwh",
            "buy_price_kwh", "sell_price_kwh", "cost_eur", "revenue_eur",
            "profit_eur", "soc_kwh", "soc_pct",
        ])
        for r in results:
            writer.writerow([
                r.dt.isoformat(),
                f"{r.price_eur_mwh:.2f}",
                r.action.value,
                f"{r.energy_kwh:.4f}",
                f"{r.energy_grid_kwh:.4f}",
                f"{r.buy_price_kwh:.6f}",
                f"{r.sell_price_kwh:.6f}",
                f"{r.cost_eur:.6f}",
                f"{r.revenue_eur:.6f}",
                f"{r.profit_eur:.6f}",
                f"{r.soc_kwh:.4f}",
                f"{r.soc_pct:.2f}",
            ])

        # Empty row + summary
        writer.writerow([])
        writer.writerow(["# Summary"])
        writer.writerow(["total_profit_eur", f"{summary.total_profit_eur:.6f}"])
        writer.writerow(["total_cost_eur", f"{summary.total_cost_eur:.6f}"])
        writer.writerow(["total_revenue_eur", f"{summary.total_revenue_eur:.6f}"])
        writer.writerow(["total_bought_kwh", f"{summary.total_bought_kwh:.4f}"])
        writer.writerow(["total_sold_kwh", f"{summary.total_sold_kwh:.4f}"])
        writer.writerow(["charge_slots", summary.charge_cycles])
        writer.writerow(["discharge_slots", summary.discharge_cycles])
        writer.writerow(["avg_buy_price_kwh", f"{summary.avg_buy_price_kwh:.6f}"])
        writer.writerow(["avg_sell_price_kwh", f"{summary.avg_sell_price_kwh:.6f}"])
