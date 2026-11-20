"""Embed the current mining MILP core in the shared full-version Gurobi model."""

from __future__ import annotations

import sys
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB

from module_contract import ModuleFlows


def _copy_constraint(target: gp.Model, source_row: gp.LinExpr, sense: str, rhs: float, var_map: dict[int, gp.Var], name: str) -> None:
    expr = gp.LinExpr()
    for i in range(source_row.size()):
        expr.addTerms(source_row.getCoeff(i), var_map[source_row.getVar(i).index])
    if sense == "<":
        target.addConstr(expr <= rhs, name=name)
    elif sense == ">":
        target.addConstr(expr >= rhs, name=name)
    else:
        target.addConstr(expr == rhs, name=name)


def add_mining_module(model: gp.Model, project_root: Path, days: range, prefix: str = "mine") -> ModuleFlows:
    """Copy mining-internal constraints while replacing standalone solvency by shared cash."""
    solver_dir = project_root / "mining" / "Jiahe_Solution"
    sys.path.insert(0, str(solver_dir))
    from XT0006_full_year_mining_milp import build_and_solve_full_year_mining_milp
    from ZG0001_archive.XT0005_mining_milp_solver import load_mining_parameters

    # The source model is used only as an audited constraint template.  Its own
    # cash/solvency rows are deliberately excluded below; no source objective is copied.
    _, _, source = build_and_solve_full_year_mining_milp(
        horizon_days=len(days), integer_rocks=True, resource_share=1.0, verbose=False
    )
    params = load_mining_parameters()
    var_map: dict[int, gp.Var] = {}
    by_name: dict[str, gp.Var] = {}
    for old in source.getVars():
        new = model.addVar(lb=old.LB, ub=old.UB, vtype=old.VType, name=f"{prefix}_{old.VarName}")
        var_map[old.index] = new
        by_name[old.VarName] = new
    model.update()
    for con in source.getConstrs():
        # Standalone cash expressions are not variables, so excluding these rows
        # cleanly delegates all cash feasibility to the shared B[t] constraints.
        if con.ConstrName.startswith("Solvency_"):
            continue
        _copy_constraint(model, source.getRow(con), con.Sense, con.RHS, var_map, f"{prefix}_{con.ConstrName}")

    T = list(days)
    active = list(range(params["mine_open_day"], max(T) + 1))
    zones, tiers, upgrades = params["zones"], params["tiers"], params["upgrade_tiers"]
    u = {(k, t): by_name[f"u[{k},{t}]"] for k in upgrades for t in active}
    zclear = {(z, t): by_name[f"Z_clear[{z},{t}]"] for z in zones for t in active}
    xmarg = {(z, t): by_name[f"x_marg[{z},{t}]"] for z in zones for t in active}
    rmarg = {(z, t): by_name[f"r_marg[{z},{t}]"] for z in zones for t in active}

    service: dict[int, gp.LinExpr] = {}
    pickaxe: dict[tuple[str, int], gp.LinExpr] = {}
    for t in T:
        if t < params["mine_open_day"]:
            service[t] = gp.LinExpr(0.0)
            for k in tiers:
                pickaxe[k, t] = gp.LinExpr(1.0 if k == "Basic" else 0.0)
            continue
        y_c = gp.quicksum(u["Copper", tau] for tau in active if tau <= t - 2)
        y_s = gp.quicksum(u["Steel", tau] for tau in active if tau <= t - 2)
        y_g = gp.quicksum(u["Gold", tau] for tau in active if tau <= t - 2)
        w_c = u["Copper", t] + (u["Copper", t - 1] if t > active[0] else 0.0)
        w_s = u["Steel", t] + (u["Steel", t - 1] if t > active[0] else 0.0)
        w_g = u["Gold", t] + (u["Gold", t - 1] if t > active[0] else 0.0)
        service[t] = w_c + w_s + w_g
        pickaxe["Basic", t] = 1.0 - y_c - w_c
        pickaxe["Copper", t] = y_c - y_s - w_s
        pickaxe["Steel", t] = y_s - y_g - w_g
        pickaxe["Gold", t] = y_g

    expense, income, energy_used, time_used, submissions = {}, {}, {}, {}, {}
    max_energy, max_time = 600.0, 1500.0
    for t in T:
        if t < params["mine_open_day"]:
            expense[t] = income[t] = energy_used[t] = time_used[t] = submissions[t] = gp.LinExpr(0.0)
            continue
        submissions[t] = gp.quicksum(u[k, t] for k in upgrades)
        expense[t] = gp.quicksum(params["upgrade_cost"][k] * u[k, t] for k in upgrades)
        income[t] = gp.quicksum(
            params["rock_value_by_zone"][z] * (params["req_rocks_by_zone"][z] * zclear[z, t] + rmarg[z, t])
            + sum(params["gem_cap"][(z, gem)] * params["gem_price"][gem] for gem in params["gems"]) * (zclear[z, t] + xmarg[z, t])
            + params["cont_cap_by_zone"][z] * params["cont_val_by_zone"][z] * (zclear[z, t] + xmarg[z, t])
            for z in zones
        )
        containers = gp.quicksum(params["cont_cap_by_zone"][z] * (zclear[z, t] + xmarg[z, t]) for z in zones)
        energy_by_tier = {}
        time_by_tier = {}
        for k in tiers:
            valid = [z for z in zones if params["zone_available"][(z, k)]]
            energy_by_tier[k] = gp.quicksum(
                params["rock_swings"][(z, k)] * params["energy_per_swing"] * (params["req_rocks_by_zone"][z] * zclear[z, t] + rmarg[z, t])
                + sum(params["gem_cap"][(z, gem)] * params["gem_swings"][(gem, k)] for gem in params["gems"]) * params["energy_per_swing"] * (zclear[z, t] + xmarg[z, t])
                for z in valid
            )
            time_by_tier[k] = 0.7 * energy_by_tier[k] + 1.4 * containers
        energy_used[t] = model.addVar(lb=0.0, ub=max_energy, name=f"{prefix}_energy[{t}]")
        time_used[t] = model.addVar(lb=0.0, ub=max_time, name=f"{prefix}_time[{t}]")
        active_pickaxe = gp.quicksum(pickaxe[k, t] for k in tiers)
        model.addConstr(energy_used[t] <= max_energy * active_pickaxe, name=f"{prefix}_energy_zero_when_service[{t}]")
        model.addConstr(time_used[t] <= max_time * active_pickaxe, name=f"{prefix}_time_zero_when_service[{t}]")
        for k in tiers:
            model.addConstr(energy_used[t] - energy_by_tier[k] <= max_energy * (1 - pickaxe[k, t]), name=f"{prefix}_energy_select_up[{k},{t}]")
            model.addConstr(energy_used[t] - energy_by_tier[k] >= -max_energy * (1 - pickaxe[k, t]), name=f"{prefix}_energy_select_low[{k},{t}]")
            model.addConstr(time_used[t] - time_by_tier[k] <= max_time * (1 - pickaxe[k, t]), name=f"{prefix}_time_select_up[{k},{t}]")
            model.addConstr(time_used[t] - time_by_tier[k] >= -max_time * (1 - pickaxe[k, t]), name=f"{prefix}_time_select_low[{k},{t}]")

    artifacts = {"u": u, "zclear": zclear, "xmarg": xmarg, "rmarg": rmarg, "parameters": params, "open_day": params["mine_open_day"]}
    source.dispose()
    return ModuleFlows("mining", time_used, energy_used, expense, income, submissions, service, artifacts)
