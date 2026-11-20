"""Solve and export the standardized mining one-third-resource benchmark.

Run from any directory.  The active mining solver is intentionally reused so
that this scenario does not duplicate or diverge from the module's core MILP.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt


SCENARIO_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCENARIO_DIR.parents[1]
SOLVER_DIR = PROJECT_ROOT / "mining" / "Jiahe_Solution"
RESULTS_DIR = SCENARIO_DIR / "results"
CONFIG_PATH = SCENARIO_DIR / "config.json"

# The active solver imports ZG0001_archive as a sibling package.
sys.path.insert(0, str(SOLVER_DIR))
from XT0006_full_year_mining_milp import build_and_solve_full_year_mining_milp  # noqa: E402


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    terminal_cash, schedule, model = build_and_solve_full_year_mining_milp(
        horizon_days=int(config["horizon_days"]),
        resource_share=float(config["resource_share"]),
        integer_rocks=bool(config["integer_rocks"]),
        verbose=False,
    )

    schedule_path = RESULTS_DIR / "daily_schedule.csv"
    schedule.to_csv(schedule_path, index=False, encoding="utf-8-sig")

    upgrades = {
        str(row.Upgrade): int(row.Day)
        for row in schedule.itertuples(index=False)
        if str(row.Upgrade) != "-"
    }
    zone_two_days = schedule.loc[schedule["Zones_Visited"].astype(str).str.contains("Z2"), "Day"]
    summary = {
        "scenario": config["scenario"],
        "horizon_days": int(config["horizon_days"]),
        "resource_share": float(config["resource_share"]),
        "initial_cash_g": float(config["resource_definition"]["initial_cash_g"]),
        "daily_energy_limit": float(config["resource_definition"]["daily_energy"]),
        "daily_time_limit_game_minutes": float(config["resource_definition"]["daily_time_game_minutes"]),
        "terminal_cash_g": round(float(terminal_cash), 2),
        "max_energy_used": round(float(schedule["Energy"].max()), 2),
        "max_time_used_game_minutes": round(float(schedule["Time_Min"].max()), 2),
        "max_depth": int(schedule["Depth"].max()),
        "upgrade_days": upgrades,
        "first_zone_2_day": None if zone_two_days.empty else int(zone_two_days.iloc[0]),
        "variables": int(model.NumVars),
        "constraints": int(model.NumConstrs),
    }
    (RESULTS_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(schedule["Day"], schedule["Cash_End_g"], color="#2563EB", linewidth=2)
    ax.fill_between(schedule["Day"], schedule["Cash_End_g"], color="#93C5FD", alpha=0.35)
    ax.axhline(summary["initial_cash_g"], color="#64748B", linestyle="--", linewidth=1, label="Initial cash (1/3)")
    ax.set(title="Mining Daily End-of-Day Cash: One-Third Resource Scenario", xlabel="Day", ylabel="Gold (g)")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "daily_cash_balance.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    model.dispose()
    print(f"Terminal cash: {summary['terminal_cash_g']:,.2f}g")
    print(f"Wrote: {schedule_path}")
    print(f"Wrote: {RESULTS_DIR / 'summary.json'}")
    print(f"Wrote: {RESULTS_DIR / 'daily_cash_balance.png'}")


if __name__ == "__main__":
    main()
