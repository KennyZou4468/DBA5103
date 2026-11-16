import os
import pandas as pd
import numpy as np
import gurobipy as gp
from gurobipy import GRB

from XT0005_mining_milp_solver import load_mining_parameters, build_and_solve_mining_milp


def build_and_solve_full_year_mining_milp(
    horizon_days=112,
    require_depth_120=False,
    min_one_rock_per_entered_level=False,
    integer_rocks=False,
    lockout_days=2,
    allow_partial_last_floor=True,
    verbose=False,
    resource_share=1.0,
    upgrade_days=None,
    daily_energy_budget=None,
):
    """
    Build and solve the Full-Year (T = 112 days) Standalone Mining MILP in Gurobi.

    Uses:
    1. The exact order-preserving chain bijection of the Professor's level-variable
       formulation:
         - Z_clear[m, t] = sum_{l=1}^4 z_{l,m,t} in {0..4} (cleared levels on day t)
         - x_marg[m, t] in {0, 1} (entry into the final marginal level l* = Z_clear + 1)
         - r_marg[m, t] >= 0 (marginal rocks dug on the final level l*)
       which uniquely reconstructs (x_{l,m,t}, z_{l,m,t}, r_{l,m,t}) for all l in {1..5}.
    2. The exact telescoping linear identity for active pickaxe tiers p_{k,t} in terms
       of upgrade decisions u_{k,t}, keeping the 112-day Year 1 MILP at ~1,620 variables
       and ~1,850 constraints (well within the 2,000 Gurobi restricted license limit).

    resource_share scales daily energy, daily time, and starting cash together.
    upgrade_days optionally fixes a tier to a date (or prohibits it with None).
    daily_energy_budget overrides energy alone, leaving scaled time/cash intact.
    The supported horizon is Day 5 through Day 112; gems and containers use the
    original all-generated-nodes-collected simplification of this compact model.
    """
    # A share reserves this fraction of energy, time AND initial cash for mining.
    # Other activities contribute no income to this standalone experiment.
    if not 0.0 < resource_share <= 1.0:
        raise ValueError("resource_share must be in (0, 1]")
    if not isinstance(horizon_days, int) or not 5 <= horizon_days <= 112:
        raise ValueError("horizon_days must be an integer from 5 through 112 (Year 1)")
    params = load_mining_parameters()
    if daily_energy_budget is not None and not 0 < daily_energy_budget <= params["daily_energy_max"]:
        raise ValueError("daily_energy_budget must be positive and at most the full daily energy")
    for key in ("daily_energy_max", "daily_time_max", "initial_cash"):
        params[key] *= resource_share
    if daily_energy_budget is not None:
        params["daily_energy_max"] = daily_energy_budget
    T = horizon_days
    open_day = params["mine_open_day"]
    active_days = list(range(open_day, T + 1))
    all_days = list(range(1, T + 1))
    zones = params["zones"]
    tiers = params["tiers"]
    upgrade_tiers = params["upgrade_tiers"]
    gems = params["gems"]

    # Precompute expected gem cash and gem swings per entered level in zone m for tier k
    gem_cash_per_level = {}
    gem_energy_per_level = {}
    gem_time_per_level = {}
    gem_count_per_level = {}
    for m in zones:
        gem_cash_per_level[m] = sum(
            params["gem_cap"][(m, j)] * params["gem_price"][j] for j in gems
        )
        gem_count_per_level[m] = sum(params["gem_cap"][(m, j)] for j in gems)
        for k in tiers:
            swings = sum(
                params["gem_cap"][(m, j)] * params["gem_swings"][(j, k)]
                for j in gems
            )
            gem_energy_per_level[(m, k)] = swings * params["energy_per_swing"]
            gem_time_per_level[(m, k)] = swings * params["minutes_per_swing"]

    model = gp.Model(f"FullYear_Mining_MILP_T{T}")
    if not verbose:
        model.Params.OutputFlag = 0
    model.Params.MIPGap = 0.0

    # =========================================================================
    # 1. DECISION VARIABLES
    # =========================================================================
    # Z_clear[m, t] = sum_{l=1}^4 z_{l,m,t} in {0..4}: number of levels cleared in zone m on day t
    Z_clear = model.addVars(
        zones, active_days, lb=0.0, ub=4.0, vtype=GRB.INTEGER, name="Z_clear"
    )
    # x_marg[m, t] in {0, 1}: binary decision to enter the final marginal level l* = Z_clear + 1 in zone m
    x_marg = model.addVars(
        zones,
        active_days,
        ub=1.0 if allow_partial_last_floor else 0.0,
        vtype=GRB.BINARY,
        name="x_marg",
    )
    # r_marg[m, t] >= 0: marginal ordinary rocks dug on the final uncleared level in zone m on day t
    r_vtype = GRB.INTEGER if integer_rocks else GRB.CONTINUOUS
    r_marg = model.addVars(
        zones,
        active_days,
        lb=0.0,
        ub=GRB.INFINITY if allow_partial_last_floor else 0.0,
        vtype=r_vtype,
        name="r_marg",
    )
    # p_push_z1[t] in {0..4}: new floors pushed in Zone 1 on day t
    p_push_z1 = model.addVars(
        active_days, lb=0.0, ub=4.0, vtype=GRB.INTEGER, name="p_push_z1"
    )
    # v_z2[t], v_z3[t] in {0, 1}: binary indicators that Zone 2 / Zone 3 are visited on day t
    v_z2 = model.addVars(active_days, vtype=GRB.BINARY, name="v_z2")
    v_z3 = model.addVars(active_days, vtype=GRB.BINARY, name="v_z3")

    # Tool upgrade binary variables u[k, t]
    u = model.addVars(upgrade_tiers, active_days, vtype=GRB.BINARY, name="u")
    # Fix dates for counterfactual comparisons; None prohibits that upgrade.
    # Bounds add no rows, preserving the restricted-license constraint budget.
    for tier, day in (upgrade_days or {}).items():
        if tier not in upgrade_tiers:
            raise ValueError(f"Unknown upgrade tier: {tier}")
        if day is not None and (not isinstance(day, int) or day not in active_days):
            raise ValueError(f"Upgrade day must be within {open_day}..{T}, or None")
        for t in active_days:
            u[tier, t].UB = float(t == day)
            u[tier, t].LB = float(t == day)

    # =========================================================================
    # 2. EXACT TELESCOPING PICKAXE TIER & CASH EXPRESSIONS
    # =========================================================================
    p_expr = {}
    w_expr = {}
    rev_expr = {}
    upg_expr = {}

    for t in active_days:
        if lockout_days == 2:
            Y_cop = gp.quicksum(u["Copper", tau] for tau in active_days if tau <= t - 2)
            Y_stl = gp.quicksum(u["Steel", tau] for tau in active_days if tau <= t - 2)
            Y_gld = gp.quicksum(u["Gold", tau] for tau in active_days if tau <= t - 2)
            W_cop = u["Copper", t] + (u["Copper", t - 1] if t > open_day else 0.0)
            W_stl = u["Steel", t] + (u["Steel", t - 1] if t > open_day else 0.0)
            W_gld = u["Gold", t] + (u["Gold", t - 1] if t > open_day else 0.0)
        elif lockout_days == 1:
            # 1-day lockout (V1 §6.2): Day t is locked out, upgraded pickaxe active on Day t+1
            Y_cop = gp.quicksum(u["Copper", tau] for tau in active_days if tau <= t - 1)
            Y_stl = gp.quicksum(u["Steel", tau] for tau in active_days if tau <= t - 1)
            Y_gld = gp.quicksum(u["Gold", tau] for tau in active_days if tau <= t - 1)
            W_cop = u["Copper", t]
            W_stl = u["Steel", t]
            W_gld = u["Gold", t]
        else:
            raise ValueError("lockout_days must be 1 or 2")

        w_expr[t] = W_cop + W_stl + W_gld
        p_expr[("Basic", t)] = 1.0 - Y_cop - W_cop
        p_expr[("Copper", t)] = Y_cop - Y_stl - W_stl
        p_expr[("Steel", t)] = Y_stl - Y_gld - W_gld
        p_expr[("Gold", t)] = Y_gld

        upg_expr[t] = gp.quicksum(
            params["upgrade_cost"][k] * u[k, t] for k in upgrade_tiers
        )
        rev_expr[t] = gp.quicksum(
            params["rock_value_by_zone"][m]
            * (params["req_rocks_by_zone"][m] * Z_clear[m, t] + r_marg[m, t])
            + gem_cash_per_level[m] * (Z_clear[m, t] + x_marg[m, t])
            + (
                params["cont_cap_by_zone"][m]
                * params["cont_val_by_zone"][m]
                * (Z_clear[m, t] + x_marg[m, t])
            )
            for m in zones
        )

    cash_expr = {}
    cash_expr[open_day - 1] = params["initial_cash"]
    for t in active_days:
        cash_expr[t] = cash_expr[t - 1] + rev_expr[t] - upg_expr[t]

    # =========================================================================
    # 3. OBJECTIVE FUNCTION: Maximize Terminal Cash at Day T
    # =========================================================================
    model.setObjective(cash_expr[T], GRB.MAXIMIZE)

    # =========================================================================
    # 4. CONSTRAINTS
    # =========================================================================
    # Upgrade uniqueness and sequential ordering across the horizon
    sum_u_cop = gp.quicksum(u["Copper", t] for t in active_days)
    sum_u_stl = gp.quicksum(u["Steel", t] for t in active_days)
    sum_u_gld = gp.quicksum(u["Gold", t] for t in active_days)
    day_u_cop = gp.quicksum(t * u["Copper", t] for t in active_days)
    day_u_stl = gp.quicksum(t * u["Steel", t] for t in active_days)
    day_u_gld = gp.quicksum(t * u["Gold", t] for t in active_days)

    model.addConstr(sum_u_cop <= 1, name="OneUpg_Copper")
    model.addConstr(sum_u_stl <= sum_u_cop, name="OrderUpg_Steel")
    model.addConstr(sum_u_gld <= sum_u_stl, name="OrderUpg_Gold")
    model.addConstr(
        day_u_cop + float(lockout_days) * sum_u_stl <= day_u_stl + T * (1.0 - sum_u_stl),
        name="Timing_Copper_Steel",
    )
    model.addConstr(
        day_u_stl + float(lockout_days) * sum_u_gld <= day_u_gld + T * (1.0 - sum_u_gld),
        name="Timing_Steel_Gold",
    )

    # Zone 1 exploration limit (39 floors) and optional Depth 120 quest completion
    model.addConstr(
        gp.quicksum(p_push_z1[t] for t in active_days) <= 39.0,
        name="MaxDepth_Z1",
    )
    if require_depth_120:
        model.addConstr(
            gp.quicksum(p_push_z1[t] for t in active_days) == 39.0,
            name="QuestDepth_Z1",
        )
        model.addConstr(
            gp.quicksum(Z_clear["mine_41_80", t] for t in active_days) >= 40.0,
            name="QuestDepth_Z2",
        )
        # Per XG0002 Item 4: 40 clears in Zone 3 advances from Floor 80 to Floor 120
        model.addConstr(
            gp.quicksum(Z_clear["mine_81_120", t] for t in active_days) >= 40.0,
            name="QuestDepth_Z3",
        )

    # Exact time = 0.7 * energy + 1.4 * containers. Each zone permits four
    # cleared levels, with at most one additional marginal level across zones.
    # Omit time rows only when this bound proves them redundant.
    max_containers = (
        4 * sum(params["cont_cap_by_zone"].values())
        + int(allow_partial_last_floor) * max(params["cont_cap_by_zone"].values())
    )
    time_is_redundant = (
        0.7 * params["daily_energy_max"] + 1.4 * max_containers
        <= params["daily_time_max"]
    )

    M_energy = 600.0
    for t in active_days:
        # At most one marginal (uncleared) final level entered per day (XG0002 Item 2)
        model.addConstr(
            gp.quicksum(x_marg[m, t] for m in zones) <= 1.0 - w_expr[t],
            name=f"OneMarg_{t}",
        )
        # Zone 1 push bound and no fake refarming on transition day
        model.addConstr(
            p_push_z1[t] <= Z_clear["mine_1_40", t], name=f"PushZ1_{t}"
        )
        model.addConstr(
            Z_clear["mine_1_40", t] - p_push_z1[t] <= 4.0 * (1.0 - v_z2[t]),
            name=f"StrictTransZ1_{t}",
        )

        # Zone 2 & Zone 3 visit indicators, tool gates, and depth gates
        model.addConstr(
            Z_clear["mine_41_80", t] + x_marg["mine_41_80", t] <= 5.0 * v_z2[t],
            name=f"VisitZ2_{t}",
        )
        model.addConstr(
            Z_clear["mine_81_120", t] + x_marg["mine_81_120", t] <= 5.0 * v_z3[t],
            name=f"VisitZ3_{t}",
        )
        model.addConstr(
            v_z2[t]
            <= p_expr[("Copper", t)] + p_expr[("Steel", t)] + p_expr[("Gold", t)],
            name=f"ToolZ2_{t}",
        )
        model.addConstr(
            v_z3[t] <= p_expr[("Gold", t)],
            name=f"ToolZ3_{t}",
        )

        cum_d1_curr = gp.quicksum(
            p_push_z1[tau] for tau in active_days if tau <= t
        )
        cum_d2_prev = gp.quicksum(
            Z_clear["mine_41_80", tau] for tau in active_days if tau < t
        )
        cum_d2_curr = cum_d2_prev + Z_clear["mine_41_80", t]
        model.addConstr(
            39.0 * v_z2[t] <= cum_d1_curr, name=f"DepthZ2_{t}"
        )
        model.addConstr(
            40.0 * v_z3[t] <= cum_d2_curr, name=f"DepthZ3_{t}"
        )
        # Prevent mixing Z2 and Z3 on the same day after all 40 floors of Z2 are already cleared
        if require_depth_120:
            model.addConstr(
                Z_clear["mine_41_80", t] + 40.0 * x_marg["mine_41_80", t]
                <= (40.0 - cum_d2_prev) + 500.0 * (1.0 - v_z3[t]),
                name=f"StrictTransZ2_{t}",
            )

        # Marginal rock bounds per zone
        for m in zones:
            max_r = params["max_rocks_by_zone"][m]
            model.addConstr(
                r_marg[m, t] <= max_r * x_marg[m, t], name=f"MaxMarg_{m}_{t}"
            )
            if min_one_rock_per_entered_level and allow_partial_last_floor:
                model.addConstr(
                    r_marg[m, t] >= 1.0 * x_marg[m, t], name=f"MinMarg_{m}_{t}"
                )

        for k in tiers:
            valid_zones = [
                m for m in zones if params["zone_available"][(m, k)]
            ]
            e_day = gp.quicksum(
                (params["rock_swings"][(m, k)] * params["energy_per_swing"])
                * (params["req_rocks_by_zone"][m] * Z_clear[m, t] + r_marg[m, t])
                + gem_energy_per_level[(m, k)] * (Z_clear[m, t] + x_marg[m, t])
                for m in valid_zones
            )
            model.addConstr(
                e_day
                <= params["daily_energy_max"] * p_expr[(k, t)]
                + M_energy * (1.0 - p_expr[(k, t)] - w_expr[t]),
                name=f"Energy_{k}_{t}",
            )
            if not time_is_redundant:
                containers = gp.quicksum(
                    params["cont_cap_by_zone"][m] * (Z_clear[m, t] + x_marg[m, t])
                    for m in zones
                )
                # Upper bound across all zone variables for an inactive tier.
                max_tier_energy = sum(
                    params["rock_swings"][(m, k)] * 2.0
                    * (4 * params["req_rocks_by_zone"][m] + params["max_rocks_by_zone"][m])
                    + 5 * gem_energy_per_level[(m, k)]
                    for m in valid_zones
                )
                time_big_m = 0.7 * max_tier_energy + 1.4 * max_containers
                model.addConstr(
                    0.7 * e_day + 1.4 * containers
                    <= params["daily_time_max"] * (1.0 - w_expr[t])
                    + time_big_m * (1.0 - p_expr[(k, t)] - w_expr[t]),
                    name=f"Time_{k}_{t}",
                )

        # Solvency constraint on EVERY active day t (XG0002 Item 3)
        model.addConstr(cash_expr[t] >= 0.0, name=f"Solvency_{t}")

    model.update()
    model.optimize()
    if model.Status != GRB.OPTIMAL:
        raise RuntimeError(f"Model did not solve to optimality. Status: {model.Status}")

    # Extract daily schedule, reconstruct explicit slot variables, and track ores/coal (XG0002 Item 8)
    rows = []
    cum_z1 = 0
    cum_z2 = 0
    cum_z3 = 0
    cum_ores = {"copper_ore": 0.0, "iron_ore": 0.0, "gold_ore": 0.0, "coal": 0.0}
    for t in all_days:
        season = ["Spring", "Summer", "Fall", "Winter"][(t - 1) // 28]
        day_of_season = ((t - 1) % 28) + 1
        if t < open_day:
            rows.append(
                {
                    "Day": t,
                    "Season_Day": f"{season} {day_of_season}",
                    "Pickaxe": "Basic (Closed)",
                    "Upgrade": "-",
                    "Zones_Visited": "-",
                    "Lvls_Entered": 0,
                    "Lvls_Cleared": 0,
                    "Cleared_Rocks": 0,
                    "Marginal_Rocks": 0.0,
                    "Total_Rocks": 0.0,
                    "Gems": 0.0,
                    "Containers": 0.0,
                    "Energy": 0.0,
                    "Time_Min": 0.0,
                    "Depth": 0,
                    "Revenue_g": 0.0,
                    "UpgCost_g": 0.0,
                    "Cash_End_g": round(params["initial_cash"], 2),
                    "Cum_Copper_Ore": 0.0,
                    "Cum_Iron_Ore": 0.0,
                    "Cum_Gold_Ore": 0.0,
                    "Cum_Coal": 0.0,
                }
            )
            continue

        upg_list = [k for k in upgrade_tiers if u[k, t].X > 0.5]
        upg_str = upg_list[0] if upg_list else "-"
        upg_val = upg_expr[t].getValue()
        w_val = w_expr[t].getValue()

        active_k = "Lockout" if w_val > 0.5 else "None"
        for k in tiers:
            if p_expr[(k, t)].getValue() > 0.5:
                active_k = k

        zones_visited = []
        lvls_entered = 0
        lvls_cleared = 0
        cleared_rocks = 0
        marginal_rocks = 0.0
        tot_gems = 0.0
        tot_cont = 0.0
        energy_used = 0.0
        time_used = 0.0

        for m in zones:
            zc = int(round(Z_clear[m, t].X))
            xm = int(round(x_marg[m, t].X))
            rm = r_marg[m, t].X
            if zc + xm > 0:
                zshort = (
                    m.replace("mine_", "Z")
                    .replace("1_40", "1")
                    .replace("41_80", "2")
                    .replace("81_120", "3")
                )
                zones_visited.append(zshort)
                lvls_entered += zc + xm
                lvls_cleared += zc
                cleared_rocks += zc * params["req_rocks_by_zone"][m]
                marginal_rocks += rm
                tot_gems += (zc + xm) * gem_count_per_level[m]
                tot_cont += (zc + xm) * params["cont_cap_by_zone"][m]
                r_tot_m = zc * params["req_rocks_by_zone"][m] + rm
                for ore_k in cum_ores:
                    cum_ores[ore_k] += (
                        r_tot_m * params["rock_drops_by_zone"][m][ore_k]
                    )
                if active_k in tiers:
                    r_sw = params["rock_swings"][(m, active_k)]
                    energy_used += (
                        r_tot_m * r_sw * 2.0
                        + (zc + xm) * gem_energy_per_level[(m, active_k)]
                    )
                    time_used += (
                        r_tot_m * r_sw * 1.4
                        + (zc + xm) * gem_time_per_level[(m, active_k)]
                        + (zc + xm) * params["cont_cap_by_zone"][m] * 1.4
                    )

        cum_z1 = min(39, cum_z1 + int(round(p_push_z1[t].X)))
        cum_z2 = min(40, cum_z2 + int(round(Z_clear["mine_41_80", t].X)))
        cum_z3 = min(41, cum_z3 + int(round(Z_clear["mine_81_120", t].X)))
        tot_depth = cum_z1 + cum_z2 + cum_z3

        rows.append(
            {
                "Day": t,
                "Season_Day": f"{season} {day_of_season}",
                "Pickaxe": active_k,
                "Upgrade": upg_str,
                "Zones_Visited": "+".join(zones_visited) if zones_visited else "-",
                "Lvls_Entered": lvls_entered,
                "Lvls_Cleared": lvls_cleared,
                "Cleared_Rocks": cleared_rocks,
                "Marginal_Rocks": round(marginal_rocks, 2),
                "Total_Rocks": round(cleared_rocks + marginal_rocks, 2),
                "Gems": round(tot_gems, 2),
                "Containers": round(tot_cont, 2),
                "Energy": round(energy_used, 2),
                "Time_Min": round(time_used, 2),
                "Depth": tot_depth,
                "Revenue_g": round(rev_expr[t].getValue(), 2),
                "UpgCost_g": round(upg_val, 2),
                "Cash_End_g": round(cash_expr[t].getValue(), 2),
                "Cum_Copper_Ore": round(cum_ores["copper_ore"], 1),
                "Cum_Iron_Ore": round(cum_ores["iron_ore"], 1),
                "Cum_Gold_Ore": round(cum_ores["gold_ore"], 1),
                "Cum_Coal": round(cum_ores["coal"], 1),
            }
        )

    df_res = pd.DataFrame(rows)
    return cash_expr[T].getValue(), df_res, model


if __name__ == "__main__":
    print("=" * 120)
    print("1. EQUIVALENCE VERIFICATION AT T = 28 DAYS (Explicit 5-Slot vs Chain-Bijection)")
    print("=" * 120)
    c28_exp, _, _ = build_and_solve_mining_milp(horizon_days=28, integer_rocks=False, verbose=False)
    c28_bij, _, m28_bij = build_and_solve_full_year_mining_milp(horizon_days=28, integer_rocks=False, verbose=False)
    c28_exp_int, _, _ = build_and_solve_mining_milp(horizon_days=28, integer_rocks=True, verbose=False)
    c28_bij_int, _, _ = build_and_solve_full_year_mining_milp(horizon_days=28, integer_rocks=True, verbose=False)
    print(f"T=28 Continuous : Explicit 5-Slot = {c28_exp:,.4f} g | Chain-Bijection = {c28_bij:,.4f} g (Diff = {abs(c28_exp - c28_bij):.6f} g)")
    print(f"T=28 Integer    : Explicit 5-Slot = {c28_exp_int:,.4f} g | Chain-Bijection = {c28_bij_int:,.4f} g (Diff = {abs(c28_exp_int - c28_bij_int):.6f} g)")

    print("\n" + "=" * 120)
    print("2. FULL YEAR 1 (T = 112 DAYS) SCENARIO A: PURE CASH MAXIMIZATION (Continuous vs Integer Rocks)")
    print("=" * 120)
    c112_a_cont, df112_a_cont, m112_a_cont = build_and_solve_full_year_mining_milp(
        horizon_days=112, require_depth_120=False, integer_rocks=False, verbose=False
    )
    c112_a_int, df112_a_int, m112_a_int = build_and_solve_full_year_mining_milp(
        horizon_days=112, require_depth_120=False, integer_rocks=True, verbose=False
    )
    print(f"Model Size (T=112): {m112_a_int.NumVars} variables ({m112_a_int.NumIntVars} int/bin), {m112_a_int.NumConstrs} constraints")
    print(f"Optimal Year 1 Terminal Cash (Continuous Rocks) : {c112_a_cont:,.2f} g")
    print(f"Optimal Year 1 Terminal Cash (Integer Rocks)    : {c112_a_int:,.2f} g (Diff = {c112_a_cont - c112_a_int:,.2f} g)")
    day_100k_a = df112_a_int[df112_a_int["Cash_End_g"] >= 100000.0]["Day"].min()
    print(f"First Day Reaching 100,000g Target (Integer)    : Day {day_100k_a} ({df112_a_int.loc[df112_a_int['Day']==day_100k_a, 'Season_Day'].values[0]})")
    print(f"Max Daily Time Used Across All 112 Days         : {df112_a_int['Time_Min'].max():.2f} min <= 900.0 min\n")

    cols_display = [
        "Day", "Season_Day", "Pickaxe", "Upgrade", "Zones_Visited",
        "Lvls_Entered", "Lvls_Cleared", "Cleared_Rocks", "Marginal_Rocks",
        "Total_Rocks", "Gems", "Containers", "Energy", "Time_Min",
        "Depth", "Revenue_g", "UpgCost_g", "Cash_End_g",
        "Cum_Copper_Ore", "Cum_Iron_Ore", "Cum_Gold_Ore", "Cum_Coal",
    ]
    print("--- Days 1..30 (Integer Rocks: Spring Exploration, Copper & Steel Upgrades, Zone 2 Entry) ---")
    print(df112_a_int[cols_display].iloc[0:30].to_string(index=False))

    print("\n--- Season-End Milestones (Days 28, 56, 84, 112) & 100k Target Day ---")
    milestone_days = sorted(list({13, 14, 20, 21, 22, 25, 26, 27, 28, int(day_100k_a), 56, 84, 112}))
    print(df112_a_int[df112_a_int["Day"].isin(milestone_days)][cols_display].to_string(index=False))

    print("\n" + "=" * 120)
    print("3. FULL YEAR 1 (T = 112 DAYS) SCENARIO B: MANDATORY DEPTH 120 COMPLETION (Continuous vs Integer Rocks)")
    print("=" * 120)
    c112_b_cont, df112_b_cont, m112_b_cont = build_and_solve_full_year_mining_milp(
        horizon_days=112, require_depth_120=True, integer_rocks=False, verbose=False
    )
    c112_b_int, df112_b_int, m112_b_int = build_and_solve_full_year_mining_milp(
        horizon_days=112, require_depth_120=True, integer_rocks=True, verbose=False
    )
    print(f"Model Size (T=112, Depth 120): {m112_b_int.NumVars} variables ({m112_b_int.NumIntVars} int/bin), {m112_b_int.NumConstrs} constraints")
    print(f"Optimal Year 1 Terminal Cash (Continuous Rocks) : {c112_b_cont:,.2f} g")
    print(f"Optimal Year 1 Terminal Cash (Integer Rocks)    : {c112_b_int:,.2f} g (Diff = {c112_b_cont - c112_b_int:,.2f} g)")
    day_100k_b = df112_b_int[df112_b_int["Cash_End_g"] >= 100000.0]["Day"].min()
    print(f"First Day Reaching 100,000g Target (Integer)    : Day {day_100k_b} ({df112_b_int.loc[df112_b_int['Day']==day_100k_b, 'Season_Day'].values[0]})\n")

    interesting_b = df112_b_int[
        (df112_b_int["Upgrade"] != "-")
        | (df112_b_int["Pickaxe"] == "Lockout")
        | (df112_b_int["Zones_Visited"].str.contains("Z3"))
        | (df112_b_int["Day"].isin([5, 13, 21, 25, 28, 56, int(day_100k_b), 84, 112]))
    ]
    print(interesting_b[cols_display].to_string(index=False))

    print("\n" + "=" * 120)
    print("4. SENSITIVITY ANALYSIS (XG0002 Items 5, 6, 7: Integer Rocks, Lockout Days, Partial Last Floor)")
    print("=" * 120)
    sens_configs = [
        ("A1: Pure Cash, Cont Rocks, 2-Day Lockout, Partial Last Floor", False, False, 2, True),
        ("A2: Pure Cash, Int Rocks,  2-Day Lockout, Partial Last Floor", False, True,  2, True),
        ("A3: Pure Cash, Int Rocks,  1-Day Lockout (V1 §6.2), Partial",  False, True,  1, True),
        ("A4: Pure Cash, Int Rocks,  2-Day Lockout, Strict V1 §4.1",     False, True,  2, False),
        ("B1: Depth 120, Cont Rocks, 2-Day Lockout, Partial Last Floor", True,  False, 2, True),
        ("B2: Depth 120, Int Rocks,  2-Day Lockout, Partial Last Floor", True,  True,  2, True),
        ("B3: Depth 120, Int Rocks,  1-Day Lockout (V1 §6.2), Partial",  True,  True,  1, True),
        ("B4: Depth 120, Int Rocks,  2-Day Lockout, Strict V1 §4.1",     True,  True,  2, False),
    ]
    for label, req120, int_r, lock_d, allow_part in sens_configs:
        c_val, df_s, m_s = build_and_solve_full_year_mining_milp(
            horizon_days=112,
            require_depth_120=req120,
            integer_rocks=int_r,
            lockout_days=lock_d,
            allow_partial_last_floor=allow_part,
            verbose=False,
        )
        d100 = df_s[df_s["Cash_End_g"] >= 100000.0]["Day"].min()
        c28 = df_s.loc[df_s["Day"] == 28, "Cash_End_g"].values[0]
        print(
            f"{label:<62} | Day 28: {c28:>9,.2f} g | Day 112: {c_val:>10,.2f} g | 100k Day: {int(d100):>3d}"
        )
