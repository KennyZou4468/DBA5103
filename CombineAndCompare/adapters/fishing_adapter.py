"""Translate fishing's backend-neutral internal constraints into the shared Gurobi model."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB

from module_contract import ModuleFlows


def add_fishing_module(model: gp.Model, project_root: Path, days: range, prefix: str = "fish") -> ModuleFlows:
    """Add fishing C1--C31 while omitting standalone G1--G5 cash/resource rows."""
    source_dir = project_root / "fishing" / "src"
    sys.path.insert(0, str(source_dir))
    from fishing_milp import Config, build_model, load_parameters

    T = list(days)
    params = load_parameters(project_root)
    source, ctx = build_model(params, Config(horizon=len(T), resource_share=1.0, prune=True))
    ignored_indices = set(ctx["B"].values())
    index_map: dict[int, gp.Var] = {}
    for old_index, old_name in enumerate(source.names):
        if old_index in ignored_indices:
            continue
        vtype = GRB.INTEGER if source.integer[old_index] else GRB.CONTINUOUS
        index_map[old_index] = model.addVar(lb=source.lb[old_index], ub=source.ub[old_index], vtype=vtype, name=f"{prefix}_{old_name}")
    model.update()
    skip_prefixes = ("G1_time[", "G2_energy[", "G4_cash_balance[", "G5_opening_cash[")
    for terms, lb, ub, row_name in zip(source.rows, source.row_lb, source.row_ub, source.row_names):
        if row_name.startswith(skip_prefixes):
            continue
        expr = gp.quicksum(coef * index_map[i] for i, coef in terms.items())
        if not math.isinf(lb):
            model.addConstr(expr >= lb, name=f"{prefix}_{row_name}_lb")
        if not math.isinf(ub):
            model.addConstr(expr <= ub, name=f"{prefix}_{row_name}_ub")

    acts = [{**a, "var": index_map[a["index"]]} for a in ctx["acts"]]
    buy = {(t, rod): index_map[index] for (t, rod), index in ctx["buy"].items()}
    own = {(t, rod): index_map[index] for (t, rod), index in ctx["own"].items()}
    time_used, energy_used, expense, income = {}, {}, {}, {}
    for t in T:
        daily = [a for a in acts if a["day"] == t]
        time_used[t] = gp.quicksum(a["tau"] * a["var"] for a in daily)
        energy_used[t] = gp.quicksum(a["e"] * a["var"] for a in daily)
        income[t] = gp.quicksum(a["v"] * a["var"] for a in daily)
        expense[t] = gp.quicksum(a["cost"] * a["var"] for a in daily) + gp.quicksum(params["rods"][rod] * buy[t, rod] for rod in ("fiberglass_rod", "iridium_rod"))
    artifacts = {"acts": acts, "buy": buy, "own": own, "levels": ctx["z"], "U": ctx["U"]}
    return ModuleFlows("fishing", time_used, energy_used, expense, income, artifacts=artifacts)
