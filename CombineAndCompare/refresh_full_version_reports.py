"""Regenerate module-level views from an existing FullVersion daily ledger.

This utility is intentionally independent of Gurobi.  Use it after changing
only output formatting, so a costly full MILP solve does not need to be rerun.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


MODULE_COLUMNS = {
    "planting": [
        "day", "planting_action", "planting_harvest", "planting_tilled", "planting_watered",
        "hoe_in_service", "watering_can_in_service", "planting_expense_g", "planting_revenue_g",
        "planting_time", "planting_energy",
    ],
    "mining": [
        "day", "mining_upgrade", "mining_zones", "mining_rocks", "mining_pickaxe_in_service",
        "mining_expense_g", "mining_revenue_g", "mining_time", "mining_energy",
    ],
    "fishing": [
        "day", "fishing_action", "fishing_casts", "fishing_rod_purchase", "fishing_expense_g",
        "fishing_revenue_g", "fishing_time", "fishing_energy",
    ],
}
MODULE_COLORS = {"planting": "#16A34A", "mining": "#A16207", "fishing": "#2563EB"}


def refresh(output_dir: Path) -> None:
    """Write individual module daily-ledgers and profit-flow figures."""
    output_dir = Path(output_dir)
    daily = pd.read_csv(output_dir / "integrated_daily_decisions.csv")

    for module_id, columns in MODULE_COLUMNS.items():
        module_daily = daily[columns].copy()
        net = module_daily[f"{module_id}_revenue_g"] - module_daily[f"{module_id}_expense_g"]
        module_daily["net_cash_flow_g"] = net
        module_daily["cumulative_net_cash_flow_g"] = net.cumsum()
        module_daily.to_csv(
            output_dir / f"integrated_{module_id}_daily_decisions.csv",
            index=False,
            encoding="utf-8-sig",
        )

        fig, ax1 = plt.subplots(figsize=(12, 4.5))
        color = MODULE_COLORS[module_id]
        ax1.bar(daily["day"], net, color=color, alpha=0.45, width=0.85, label="Daily net cash flow")
        ax1.axhline(0, color="#64748B", linewidth=0.8)
        ax1.set(xlabel="Day", ylabel="Daily net cash flow (g)")
        ax2 = ax1.twinx()
        ax2.plot(daily["day"], net.cumsum(), color=color, linewidth=2.2, label="Cumulative net cash flow")
        ax2.set_ylabel("Cumulative net cash flow (g)")
        ax1.set_title(f"Full Version: {module_id.title()} Profit Flow")
        ax1.grid(axis="y", alpha=0.22)
        handles1, labels1 = ax1.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(handles1 + handles2, labels1 + labels2, loc="upper left")
        fig.tight_layout()
        fig.savefig(output_dir / f"integrated_{module_id}_profit_flow.png", dpi=160, bbox_inches="tight")
        plt.close(fig)


if __name__ == "__main__":
    refresh(Path(__file__).resolve().parent / "outputs" / "full_version")
    print("Module-level FullVersion reports refreshed.")
