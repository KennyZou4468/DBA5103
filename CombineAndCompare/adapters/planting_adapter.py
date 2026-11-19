"""Planting constraints embedded in the shared full-version Gurobi model."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import gurobipy as gp
from gurobipy import GRB

from module_contract import ModuleFlows


def add_planting_module(model: gp.Model, project_root: Path, days: range, prefix: str = "plant") -> ModuleFlows:
    """Add all planting-internal constraints, excluding standalone cash/resource caps."""
    data = project_root / "planting" / "data"
    shared = project_root / "shared" / "data" / "global_parameters.csv"
    calendar = pd.read_csv(data / "crop_planting_calendar.csv")
    events = pd.read_csv(data / "crop_daily_events.csv")
    crops = pd.read_csv(data / "crops.csv")
    tools = pd.read_csv(data / "planting_tool_catalog.csv")
    parameters = pd.read_csv(shared)

    T, C, J, K, UPGRADE_K = list(days), sorted(calendar.crop_key.unique()), ["H", "W"], [0, 1, 2, 3], [1, 2, 3]
    tier_name = {0: "Basic", 1: "Copper", 2: "Steel", 3: "Gold"}
    tool_name = {"H": "Hoe", "W": "Watering Can"}

    def flag(value):
        return str(value).strip().lower() == "true"

    A = {(r.crop_key, int(r.plant_day)): int(flag(r.plant_allowed_A_ct)) for r in calendar.itertuples(index=False)}
    seed_price = crops.groupby("seed_id").seed_price_g.first().to_dict()
    seed_id = {r.crop_key: int(r.seed_id) for r in calendar.itertuples(index=False)}
    p = {c: float(seed_price[seed_id[c]]) for c in C}
    crop_name = calendar.groupby("crop_key").crop_name.first().to_dict()
    lookup = events.set_index(["crop_key", "plant_day", "calendar_day"])

    def event(c, s, t, column, cast=float):
        key = (c, s, t)
        return cast(lookup.loc[key, column]) if key in lookup.index else cast(0)

    h = {(c, s, t): event(c, s, t, "is_harvest", lambda v: int(flag(v))) for c in C for s in T for t in T if s <= t}
    f = {(c, s, t): event(c, s, t, "releases_land", lambda v: int(flag(v))) for c in C for s in T for t in T if s <= t}
    need_water = {(c, s, t): event(c, s, t, "needs_water", lambda v: int(flag(v))) for c in C for s in T for t in T if s <= t}
    revenue = {(c, s, t): event(c, s, t, "base_revenue_g_per_tile_harvest") for c in C for s in T for t in T if s <= t}
    tool_row = tools.set_index(["tool_type", "tier"])
    tau = {(j, k): float(tool_row.loc[(tool_name[j], tier_name[k]), "time_game_minutes_per_unit"]) for j in J for k in K}
    energy = {(j, k): float(tool_row.loc[(tool_name[j], tier_name[k]), "energy_per_unit"]) for j in J for k in K}
    kappa = {k: float(tool_row.loc[("Watering Can", tier_name[k]), "upgrade_cash_equivalent_cost_g"]) for k in UPGRADE_K}
    # ``global_parameters.csv`` mixes numeric values with descriptive entries
    # (for example, ``model_time_unit = game_minutes``).  Convert only the
    # two numeric parameters this adapter needs rather than coercing the
    # entire column.
    global_map = {
        parameter_id: float(
            parameters.loc[parameters["parameter_id"].eq(parameter_id), "value"].iloc[0]
        )
        for parameter_id in ("daily_time_limit_game_minutes",)
    }
    M_L = M_W = int(global_map["daily_time_limit_game_minutes"] // 1.4)
    X_UB = int(global_map["daily_time_limit_game_minutes"] // 2.8)
    delta = {t: int(t in {1, 29, 57, 85}) for t in T}
    name = lambda key: f"{prefix}_{key}"

    x = model.addVars(C, T, vtype=GRB.INTEGER, lb=0, ub=X_UB, name=name("x"))
    L = model.addVars(T, vtype=GRB.INTEGER, lb=0, name=name("tilled"))
    empty = model.addVars(T, vtype=GRB.INTEGER, lb=0, name=name("empty_land"))
    H = model.addVars(C, T, vtype=GRB.INTEGER, lb=0, name=name("harvest"))
    W = model.addVars(T, vtype=GRB.INTEGER, lb=0, name=name("water_need"))
    F = model.addVars(T, vtype=GRB.INTEGER, lb=0, name=name("land_release"))
    U = model.addVars(J, UPGRADE_K, T, vtype=GRB.BINARY, name=name("upgrade"))
    S = model.addVars(J, K, T, vtype=GRB.BINARY, name=name("tool_state"))
    D = model.addVars(J, T, vtype=GRB.BINARY, name=name("tool_service"))
    Z = model.addVars(J, K, T, vtype=GRB.BINARY, name=name("tool_available"))
    till = model.addVars(K, T, vtype=GRB.INTEGER, lb=0, name=name("till"))
    water = model.addVars(K, T, vtype=GRB.INTEGER, lb=0, name=name("water"))

    for c in C:
        for t in T:
            model.addConstr(x[c, t] <= X_UB * A[c, t], name=name(f"plant_allowed[{c},{t}]"))
    for t in T:
        for c in C:
            model.addConstr(H[c, t] == gp.quicksum(h[c, s, t] * x[c, s] for s in T if s <= t), name=name(f"harvest_event[{c},{t}]"))
        model.addConstr(F[t] == gp.quicksum(f[c, s, t] * x[c, s] for c in C for s in T if s <= t), name=name(f"land_release[{t}]"))
        model.addConstr(W[t] == gp.quicksum(need_water[c, s, t] * x[c, s] for c in C for s in T if s <= t), name=name(f"water_need[{t}]"))
        prior = 0 if t == T[0] else empty[t - 1]
        model.addConstr(empty[t] == (1 - delta[t]) * prior + L[t] + F[t] - gp.quicksum(x[c, t] for c in C), name=name(f"land_balance[{t}]"))

    for j in J:
        model.addConstr(S[j, 0, T[0]] == 1, name=name(f"initial_basic[{j}]"))
        for k in UPGRADE_K:
            model.addConstr(S[j, k, T[0]] == 0, name=name(f"initial_nonbasic[{j},{k}]"))
        for t in T:
            model.addConstr(gp.quicksum(S[j, k, t] for k in K) == 1, name=name(f"one_tier[{j},{t}]"))
            for k in UPGRADE_K:
                model.addConstr(U[j, k, t] <= S[j, k - 1, t], name=name(f"sequential_upgrade[{j},{k},{t}]"))
            today = gp.quicksum(U[j, k, t] for k in UPGRADE_K)
            yesterday = 0 if t == T[0] else gp.quicksum(U[j, k, t - 1] for k in UPGRADE_K)
            model.addConstr(D[j, t] == today + yesterday, name=name(f"service_state[{j},{t}]"))
            model.addConstr(today + yesterday <= 1, name=name(f"no_resubmit[{j},{t}]"))
            if t != T[0]:
                for k in K:
                    leave = 0 if k == 3 or t == T[1] else U[j, k + 1, t - 2]
                    enter = 0 if k == 0 or t == T[1] else U[j, k, t - 2]
                    model.addConstr(S[j, k, t] == S[j, k, t - 1] - leave + enter, name=name(f"tier_transition[{j},{k},{t}]"))
            for k in K:
                model.addConstr(Z[j, k, t] <= S[j, k, t], name=name(f"available_owned[{j},{k},{t}]"))
                model.addConstr(Z[j, k, t] <= 1 - D[j, t], name=name(f"available_service[{j},{k},{t}]"))
                model.addConstr(Z[j, k, t] >= S[j, k, t] - D[j, t], name=name(f"available_exact[{j},{k},{t}]"))

    for t in T:
        model.addConstr(gp.quicksum(till[k, t] for k in K) == L[t], name=name(f"till_all[{t}]"))
        model.addConstr(gp.quicksum(water[k, t] for k in K) == W[t], name=name(f"water_all[{t}]"))
        for k in K:
            model.addConstr(till[k, t] <= M_L * Z["H", k, t], name=name(f"till_tool[{k},{t}]"))
            model.addConstr(water[k, t] <= M_W * Z["W", k, t], name=name(f"water_tool[{k},{t}]"))

    time_used = {t: gp.quicksum(tau["H", k] * till[k, t] + tau["W", k] * water[k, t] for k in K) + 1.4 * gp.quicksum(x[c, t] + H[c, t] for c in C) for t in T}
    energy_used = {t: gp.quicksum(energy["H", k] * till[k, t] + energy["W", k] * water[k, t] for k in K) for t in T}
    expense = {t: gp.quicksum(p[c] * x[c, t] for c in C) + gp.quicksum(kappa[k] * U[j, k, t] for j in J for k in UPGRADE_K) for t in T}
    income = {t: gp.quicksum(revenue[c, s, t] * x[c, s] for c in C for s in T if s <= t) for t in T}
    submissions = {t: gp.quicksum(U[j, k, t] for j in J for k in UPGRADE_K) for t in T}
    service = {t: gp.quicksum(D[j, t] for j in J) for t in T}
    return ModuleFlows("planting", time_used, energy_used, expense, income, submissions, service,
                       {"x": x, "harvest": H, "water_need": W, "tilled": L, "tool_service": D, "crop_name": crop_name})
