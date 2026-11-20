"""One-at-a-time sensitivity analysis for the integrated Year 1 MILP.

The scenarios change only decision-relevant assumptions that are not fixed by
the game data: starting cash, daily time, daily energy, and Blacksmith service
capacity.  Each run writes its usual auditable full-version output in a
scenario-specific directory, followed by a compact cross-scenario summary.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from full_version_solver import (
    DAILY_ENERGY,
    DAILY_TIME,
    INITIAL_CASH,
    solve_full_version,
)


@dataclass(frozen=True)
class SensitivityScenario:
    """One complete, independently solvable integrated-model setting."""

    name: str
    changed_input: str
    initial_cash: float = INITIAL_CASH
    daily_time: float = DAILY_TIME
    daily_energy: float = DAILY_ENERGY
    blacksmith_submission_capacity: int = 1
    blacksmith_service_capacity: int = 1


SCENARIOS = (
    SensitivityScenario("baseline", "Baseline"),
    SensitivityScenario("cash_250", "Initial cash = 250g", initial_cash=250.0),
    SensitivityScenario("cash_1000", "Initial cash = 1,000g", initial_cash=1_000.0),
    SensitivityScenario("time_720", "Daily time = 720 minutes", daily_time=720.0),
    SensitivityScenario("time_1080", "Daily time = 1,080 minutes", daily_time=1_080.0),
    SensitivityScenario("energy_216", "Daily energy = 216", daily_energy=216.0),
    SensitivityScenario("energy_324", "Daily energy = 324", daily_energy=324.0),
    SensitivityScenario(
        "blacksmith_service_2",
        "Blacksmith service capacity = 2 tools/day",
        blacksmith_service_capacity=2,
    ),
)


def _result_row(scenario: SensitivityScenario, result: dict) -> dict:
    """Flatten a solver result into one analysis-table row."""
    summary = result["summary"]
    return {
        "scenario": scenario.name,
        "changed_input": scenario.changed_input,
        "initial_cash_g": scenario.initial_cash,
        "daily_time_limit": scenario.daily_time,
        "daily_energy_limit": scenario.daily_energy,
        "blacksmith_submission_capacity": scenario.blacksmith_submission_capacity,
        "blacksmith_service_capacity": scenario.blacksmith_service_capacity,
        "status": summary["status"],
        "terminal_cash_g": summary["terminal_cash_g"],
        "best_bound_g": summary["best_bound"],
        "mip_gap": summary["mip_gap"],
        "planting_revenue_g": summary["total_revenue_g"]["planting"],
        "mining_revenue_g": summary["total_revenue_g"]["mining"],
        "fishing_revenue_g": summary["total_revenue_g"]["fishing"],
        "planting_expense_g": summary["total_expense_g"]["planting"],
        "mining_expense_g": summary["total_expense_g"]["mining"],
        "fishing_expense_g": summary["total_expense_g"]["fishing"],
        "max_time_used": summary["max_total_time"],
        "max_energy_used": summary["max_total_energy"],
        "scenario_output_directory": str(result["output_dir"]),
    }


def _save_figures(summary: pd.DataFrame, output_dir: Path) -> None:
    """Create comparable terminal-cash and revenue-composition plots."""
    colors = ["#2563EB" if scenario == "baseline" else "#7C3AED" for scenario in summary["scenario"]]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(summary["scenario"], summary["terminal_cash_g"], color=colors)
    ax.set(title="Sensitivity Analysis: Terminal Cash by Scenario", xlabel="Scenario", ylabel="Day-112 cash (g)")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "terminal_cash_by_scenario.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    revenue_columns = ["planting_revenue_g", "mining_revenue_g", "fishing_revenue_g"]
    revenue_labels = ["Planting", "Mining", "Fishing"]
    revenue_colors = ["#16A34A", "#A16207", "#2563EB"]
    fig, ax = plt.subplots(figsize=(12, 5))
    bottom = pd.Series(0.0, index=summary.index)
    for column, label, color in zip(revenue_columns, revenue_labels, revenue_colors):
        ax.bar(summary["scenario"], summary[column], bottom=bottom, label=label, color=color)
        bottom += summary[column]
    ax.set(title="Sensitivity Analysis: Module Revenue Composition", xlabel="Scenario", ylabel="Total revenue (g)")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "module_revenue_by_scenario.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def run_sensitivity_analysis(
    project_root: Path,
    time_limit: float = 180.0,
    mip_gap: float = 0.001,
    scenarios: tuple[SensitivityScenario, ...] = SCENARIOS,
) -> pd.DataFrame:
    """Solve all one-at-a-time scenarios and write summary tables and charts.

    The default 180-second cap matches the computational experiment reported
    for the full version.  Time-limited MIP results remain valid feasible
    solutions; the exported MIP gap makes their precision explicit.
    """
    project_root = Path(project_root).resolve()
    output_dir = project_root / "CombineAndCompare" / "outputs" / "sensitivity_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for scenario in scenarios:
        scenario_dir = output_dir / scenario.name
        result = solve_full_version(
            project_root,
            time_limit=time_limit,
            mip_gap=mip_gap,
            initial_cash=scenario.initial_cash,
            daily_time=scenario.daily_time,
            daily_energy=scenario.daily_energy,
            blacksmith_submission_capacity=scenario.blacksmith_submission_capacity,
            blacksmith_service_capacity=scenario.blacksmith_service_capacity,
            output_dir=scenario_dir,
        )
        rows.append(_result_row(scenario, result))

    summary = pd.DataFrame(rows)
    baseline_cash = float(summary.loc[summary["scenario"].eq("baseline"), "terminal_cash_g"].iloc[0])
    summary["cash_change_from_baseline_g"] = summary["terminal_cash_g"] - baseline_cash
    summary["cash_change_from_baseline_pct"] = 100.0 * summary["cash_change_from_baseline_g"] / baseline_cash
    summary.to_csv(output_dir / "sensitivity_summary.csv", index=False, encoding="utf-8-sig")
    payload = {
        "time_limit_seconds_per_scenario": time_limit,
        "mip_gap_target": mip_gap,
        "scenario_definitions": [asdict(scenario) for scenario in scenarios],
        "results": summary.to_dict(orient="records"),
    }
    (output_dir / "sensitivity_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _save_figures(summary, output_dir)
    return summary


if __name__ == "__main__":
    root = HERE.parent
    print(run_sensitivity_analysis(root).to_string(index=False))
