"""All-module Year 1 MILP: planting, mining, and fishing in one Gurobi model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import gurobipy as gp
from gurobipy import GRB


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from adapters.fishing_adapter import add_fishing_module
from adapters.mining_adapter import add_mining_module
from adapters.planting_adapter import add_planting_module
from module_contract import add_full_version_constraints


HORIZON = 112
INITIAL_CASH = 500.0
DAILY_TIME = 900.0
DAILY_ENERGY = 270.0


def _value(expr) -> float:
    return float(expr.X if isinstance(expr, gp.Var) else expr.getValue())


def _summary(values: list[tuple[str, float]]) -> str:
    parts = [f"{label} x {value:,.0f}" for label, value in values if value > 0.5]
    return "; ".join(parts) if parts else "-"


def build_model(project_root: Path) -> tuple[gp.Model, dict, dict[int, gp.Var]]:
    """Build the full integrated MILP and return model, module flows, shared cash."""
    model = gp.Model("stardew_full_version_all_modules")
    days = range(1, HORIZON + 1)
    flows = {
        "planting": add_planting_module(model, project_root, days),
        "mining": add_mining_module(model, project_root, days),
        "fishing": add_fishing_module(model, project_root, days),
    }
    cash = add_full_version_constraints(
        model, flows, days,
        initial_cash=INITIAL_CASH,
        daily_time=DAILY_TIME,
        daily_energy=DAILY_ENERGY,
        enforce_one_blacksmith_submission=True,
        enforce_one_blacksmith_service=True,
    )
    model.setObjective(cash[HORIZON], GRB.MAXIMIZE)
    model.update()
    return model, flows, cash


def export_solution(project_root: Path, model: gp.Model, flows: dict, cash: dict[int, gp.Var]) -> dict:
    """Write daily module decisions, detailed activities, shared cash chart, and summary."""
    out = project_root / "CombineAndCompare" / "outputs" / "full_version"
    out.mkdir(parents=True, exist_ok=True)
    plant, mine, fish = (flows[key].artifacts for key in ("planting", "mining", "fishing"))
    rows, plant_batches, fish_activities = [], [], []

    for t in range(1, HORIZON + 1):
        crop_values = [(plant["crop_name"][c], plant["x"][c, t].X) for c in plant["crop_name"]]
        harvest_values = [(plant["crop_name"][c], plant["harvest"][c, t].X) for c in plant["crop_name"]]
        for c, value in ((c, plant["x"][c, t].X) for c in plant["crop_name"]):
            if value > 0.5:
                plant_batches.append({"day": t, "crop_key": c, "crop_name": plant["crop_name"][c], "tiles": value})

        mine_upgrade = []
        mine_zones, mine_rocks = [], 0.0
        if t >= mine["open_day"]:
            mine_upgrade = [tier for tier in ("Copper", "Steel", "Gold") if mine["u"][tier, t].X > 0.5]
            for zone in mine["parameters"]["zones"]:
                levels = mine["zclear"][zone, t].X + mine["xmarg"][zone, t].X
                rocks = mine["parameters"]["req_rocks_by_zone"][zone] * mine["zclear"][zone, t].X + mine["rmarg"][zone, t].X
                mine_rocks += rocks
                if levels > 0.5:
                    mine_zones.append(f"{zone}:{levels:,.0f} level(s)")

        daily_fishing = [a for a in fish["acts"] if a["day"] == t and a["var"].X > 0.5]
        fish_casts = sum(a["var"].X for a in daily_fishing)
        fish_desc = _summary([(f"{a['fishing_location_id']} / {a['mode']}", a["var"].X) for a in daily_fishing])
        fish_rods = [rod for rod in ("fiberglass_rod", "iridium_rod") if fish["buy"][t, rod].X > 0.5]
        for a in daily_fishing:
            fish_activities.append({"day": t, "location": a["fishing_location_id"], "time_block": a["time_block_id"], "level": a["level"], "mode": a["mode"], "casts": a["var"].X})

        rows.append({
            "day": t,
            "cash_start_g": cash[t - 1].X,
            "planting_action": _summary(crop_values),
            "planting_harvest": _summary(harvest_values),
            "planting_tilled": plant["tilled"][t].X,
            "planting_watered": plant["water_need"][t].X,
            "hoe_in_service": int(plant["tool_service"]["H", t].X > 0.5),
            "watering_can_in_service": int(plant["tool_service"]["W", t].X > 0.5),
            "mining_upgrade": ", ".join(mine_upgrade) or "-",
            "mining_zones": "; ".join(mine_zones) or "-",
            "mining_rocks": mine_rocks,
            "mining_pickaxe_in_service": int(_value(flows["mining"].blacksmith_service[t]) > 0.5),
            "fishing_action": fish_desc,
            "fishing_casts": fish_casts,
            "fishing_rod_purchase": ", ".join(fish_rods) or "-",
            "planting_expense_g": _value(flows["planting"].expense[t]),
            "mining_expense_g": _value(flows["mining"].expense[t]),
            "fishing_expense_g": _value(flows["fishing"].expense[t]),
            "planting_revenue_g": _value(flows["planting"].revenue[t]),
            "mining_revenue_g": _value(flows["mining"].revenue[t]),
            "fishing_revenue_g": _value(flows["fishing"].revenue[t]),
            "planting_time": _value(flows["planting"].time_used[t]),
            "mining_time": _value(flows["mining"].time_used[t]),
            "fishing_time": _value(flows["fishing"].time_used[t]),
            "total_time": sum(_value(flows[m].time_used[t]) for m in flows),
            "planting_energy": _value(flows["planting"].energy_used[t]),
            "mining_energy": _value(flows["mining"].energy_used[t]),
            "fishing_energy": _value(flows["fishing"].energy_used[t]),
            "total_energy": sum(_value(flows[m].energy_used[t]) for m in flows),
            "cash_end_g": cash[t].X,
        })

    daily = pd.DataFrame(rows)
    daily.to_csv(out / "integrated_daily_decisions.csv", index=False, encoding="utf-8-sig")

    # Module-specific daily ledgers make the integrated solution reviewable by
    # each workstream without asking users to filter the 30-column master file.
    module_columns = {
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
    for module_id, columns in module_columns.items():
        module_daily = daily[columns].copy()
        module_daily["net_cash_flow_g"] = (
            module_daily[f"{module_id}_revenue_g"] - module_daily[f"{module_id}_expense_g"]
        )
        module_daily["cumulative_net_cash_flow_g"] = module_daily["net_cash_flow_g"].cumsum()
        module_daily.to_csv(out / f"integrated_{module_id}_daily_decisions.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame(plant_batches).to_csv(out / "integrated_planting_batches.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(fish_activities).to_csv(out / "integrated_fishing_activities.csv", index=False, encoding="utf-8-sig")

    # A compact cash-flow roll-up complements the daily ledger.  The overall
    # row reconciles exactly to the shared Day-112 cash balance.
    cash_flow_summary = pd.DataFrame([
        {
            "module": module_id,
            "total_revenue_g": sum(_value(flows[module_id].revenue[t]) for t in range(1, HORIZON + 1)),
            "total_expense_g": sum(_value(flows[module_id].expense[t]) for t in range(1, HORIZON + 1)),
        }
        for module_id in flows
    ])
    cash_flow_summary["net_cash_flow_g"] = (
        cash_flow_summary["total_revenue_g"] - cash_flow_summary["total_expense_g"]
    )
    cash_flow_summary.loc[len(cash_flow_summary)] = {
        "module": "overall",
        "total_revenue_g": cash_flow_summary["total_revenue_g"].sum(),
        "total_expense_g": cash_flow_summary["total_expense_g"].sum(),
        "net_cash_flow_g": cash_flow_summary["net_cash_flow_g"].sum(),
    }
    cash_flow_summary["initial_cash_g"] = ""
    cash_flow_summary["terminal_cash_g"] = ""
    cash_flow_summary.loc[cash_flow_summary["module"].eq("overall"), "initial_cash_g"] = INITIAL_CASH
    cash_flow_summary.loc[cash_flow_summary["module"].eq("overall"), "terminal_cash_g"] = cash[HORIZON].X
    cash_flow_summary.to_csv(out / "integrated_total_cash_flow.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(daily["day"], daily["cash_end_g"], color="#2563EB", linewidth=2, label="Shared end-of-day cash")
    ax.fill_between(daily["day"], daily["cash_end_g"], color="#93C5FD", alpha=0.35)
    ax.axhline(INITIAL_CASH, color="#64748B", linestyle="--", linewidth=1, label="Initial cash")
    ax.set(title="Full Version: Shared Daily Cash Balance", xlabel="Day", ylabel="Gold (g)")
    ax.grid(axis="y", alpha=0.25); ax.legend(); fig.tight_layout()
    fig.savefig(out / "integrated_cash_balance.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # One cash-flow chart per module: bars show daily profit/loss and the line
    # shows its cumulative contribution to the shared Day-112 cash outcome.
    module_colors = {"planting": "#16A34A", "mining": "#A16207", "fishing": "#2563EB"}
    for module_id, color in module_colors.items():
        net = daily[f"{module_id}_revenue_g"] - daily[f"{module_id}_expense_g"]
        cumulative = net.cumsum()
        fig, ax1 = plt.subplots(figsize=(12, 4.5))
        ax1.bar(daily["day"], net, color=color, alpha=0.45, width=0.85, label="Daily net cash flow")
        ax1.axhline(0, color="#64748B", linewidth=0.8)
        ax1.set(xlabel="Day", ylabel="Daily net cash flow (g)")
        ax2 = ax1.twinx()
        ax2.plot(daily["day"], cumulative, color=color, linewidth=2.2, label="Cumulative net cash flow")
        ax2.set_ylabel("Cumulative net cash flow (g)")
        ax1.set_title(f"Full Version: {module_id.title()} Profit Flow")
        ax1.grid(axis="y", alpha=0.22)
        handles1, labels1 = ax1.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(handles1 + handles2, labels1 + labels2, loc="upper left")
        fig.tight_layout()
        fig.savefig(out / f"integrated_{module_id}_profit_flow.png", dpi=160, bbox_inches="tight")
        plt.close(fig)

    summary = {
        "status": int(model.Status),
        "objective_day_112_cash_g": round(float(model.ObjVal), 2),
        "best_bound": round(float(model.ObjBound), 2),
        "mip_gap": float(model.MIPGap),
        "max_total_time": round(float(daily["total_time"].max()), 4),
        "max_total_energy": round(float(daily["total_energy"].max()), 4),
        "terminal_cash_g": round(float(cash[HORIZON].X), 2),
        "total_revenue_g": {m: round(float(sum(_value(flows[m].revenue[t]) for t in range(1, HORIZON + 1))), 2) for m in flows},
        "total_expense_g": {m: round(float(sum(_value(flows[m].expense[t]) for t in range(1, HORIZON + 1))), 2) for m in flows},
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"output_dir": out, "daily": daily, "summary": summary}


def solve_full_version(project_root: Path, time_limit: float = 300.0, mip_gap: float = 0.001) -> dict:
    """Build, solve, audit basic shared limits, and export all required reports."""
    model, flows, cash = build_model(Path(project_root))
    model.Params.TimeLimit = time_limit
    model.Params.MIPGap = mip_gap
    model.optimize()
    if model.Status not in (GRB.OPTIMAL, GRB.TIME_LIMIT) or model.SolCount == 0:
        raise RuntimeError(f"No usable integrated solution; Gurobi status {model.Status}.")
    result = export_solution(Path(project_root), model, flows, cash)
    daily = result["daily"]
    assert daily["total_time"].max() <= DAILY_TIME + 1e-6
    assert daily["total_energy"].max() <= DAILY_ENERGY + 1e-6
    assert daily["cash_end_g"].min() >= -1e-6
    result["model"] = model
    return result
