import os
import pandas as pd
import numpy as np
import gurobipy as gp
from gurobipy import GRB

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MINING_DIR = os.path.join(BASE_DIR, "mining", "data")
SHARED_DIR = os.path.join(BASE_DIR, "shared", "data")


def load_mining_parameters():
    """Load and compute all exact deterministic parameters from baseline CSVs."""
    global_df = pd.read_csv(os.path.join(SHARED_DIR, "global_parameters.csv"))
    node_df = pd.read_csv(os.path.join(MINING_DIR, "mining_node_profiles.csv"))
    rock_hits_df = pd.read_csv(
        os.path.join(MINING_DIR, "mining_ordinary_rock_hit_requirements.csv")
    )
    gem_df = pd.read_csv(os.path.join(MINING_DIR, "mining_gem_node_profiles.csv"))
    gem_hits_df = pd.read_csv(
        os.path.join(MINING_DIR, "mining_gem_hit_requirements.csv")
    )
    cont_df = pd.read_csv(os.path.join(MINING_DIR, "mine_container_profiles.csv"))
    cash_df = pd.read_csv(os.path.join(MINING_DIR, "mining_resource_cash_values.csv"))
    pick_df = pd.read_csv(os.path.join(MINING_DIR, "mining_pickaxe_catalog.csv"))

    global_map = dict(zip(global_df["parameter_id"], global_df["value"]))
    cash_map = dict(
        zip(cash_df["resource_id"], cash_df["cash_value_per_unit_g"].astype(float))
    )

    params = {
        "initial_cash": float(global_map["initial_gold_g"]),
        "daily_time_max": float(global_map["daily_time_limit_game_minutes"]),
        "daily_energy_max": float(global_map["daily_energy_limit"]),
        "mine_open_day": int(float(global_map["mine_open_day"])),
        "energy_per_swing": 2.0,
        "minutes_per_swing": 1.4,
        "minutes_per_container": 1.4,
    }

    zones = ["mine_1_40", "mine_41_80", "mine_81_120"]
    params["zones"] = zones
    params["zone_max_floors"] = {
        "mine_1_40": 39,
        "mine_41_80": 40,
        "mine_81_120": 41,
    }
    params["max_rocks_by_zone"] = {
        "mine_1_40": 65.3,
        "mine_41_80": 56.1,
        "mine_81_120": 65.2,
    }

    req_rocks_by_zone = {}
    rock_value_by_zone = {}
    rock_drops_by_zone = {}

    for _, row in node_df.iterrows():
        zid = row["zone_id"]
        req_rocks_by_zone[zid] = int(
            row["exploration_rocks_required_per_floor_50pct_ceiling"]
        )
        val = (
            row["expected_copper_ore_per_broken_rock"] * cash_map["copper_ore"]
            + row["expected_iron_ore_per_broken_rock"] * cash_map["iron_ore"]
            + row["expected_gold_ore_per_broken_rock"] * cash_map["gold_ore"]
            + row["expected_stone_per_broken_rock"] * cash_map["stone"]
            + row["expected_coal_per_broken_rock"] * cash_map["coal"]
            + row["expected_geode_per_broken_rock"] * cash_map["geode"]
            + row["expected_frozen_geode_per_broken_rock"] * cash_map["frozen_geode"]
            + row["expected_magma_geode_per_broken_rock"] * cash_map["magma_geode"]
            + row["expected_omni_geode_per_broken_rock"] * cash_map["omni_geode"]
        )
        rock_value_by_zone[zid] = float(val)
        rock_drops_by_zone[zid] = {
            "copper_ore": float(row["expected_copper_ore_per_broken_rock"]),
            "iron_ore": float(row["expected_iron_ore_per_broken_rock"]),
            "gold_ore": float(row["expected_gold_ore_per_broken_rock"]),
            "coal": float(row["expected_coal_per_broken_rock"]),
        }

    params["req_rocks_by_zone"] = req_rocks_by_zone
    params["rock_value_by_zone"] = rock_value_by_zone
    params["rock_drops_by_zone"] = rock_drops_by_zone

    # Containers by zone
    cont_cap_by_zone = {}
    cont_val_by_zone = {}
    for _, row in cont_df.iterrows():
        zid = row["zone_id"]
        cont_cap_by_zone[zid] = float(
            row["mean_generated_containers_per_ordinary_floor"]
        )
        cont_val_by_zone[zid] = float(
            row["expected_direct_sale_g_before_bottom_per_container"]
        )
    params["cont_cap_by_zone"] = cont_cap_by_zone
    params["cont_val_by_zone"] = cont_val_by_zone

    # Gems by zone
    gems = sorted(gem_df["gem_id"].unique().tolist())
    params["gems"] = gems
    gem_cap = {}
    gem_price = {}
    for _, row in gem_df.iterrows():
        zid = row["zone_id"]
        gid = row["gem_id"]
        gem_cap[(zid, gid)] = float(row["expected_nodes_per_ordinary_floor"])
        gem_price[gid] = float(row["normal_sell_price_g"])
    params["gem_cap"] = gem_cap
    params["gem_price"] = gem_price

    # Pickaxe tiers and hit requirements
    tiers = ["Basic", "Copper", "Steel", "Gold"]
    params["tiers"] = tiers
    upgrade_tiers = ["Copper", "Steel", "Gold"]
    params["upgrade_tiers"] = upgrade_tiers

    upgrade_cost = {}
    blacksmith_fee = {}
    for _, row in pick_df.iterrows():
        t_name = row["tier"]
        if t_name in upgrade_tiers:
            upgrade_cost[t_name] = float(row["upgrade_cash_equivalent_cost_g"])
            blacksmith_fee[t_name] = float(row["blacksmith_fee_g"])
    params["upgrade_cost"] = upgrade_cost
    params["blacksmith_fee"] = blacksmith_fee

    # Rock swings by (zone_id, tier)
    rock_swings = {}
    zone_available = {}
    for _, row in rock_hits_df.iterrows():
        zid = row["zone_id"]
        t_name = row["pickaxe_tier"]
        if t_name in tiers:
            avail = str(row["available_for_zone"]).strip().lower() == "true"
            zone_available[(zid, t_name)] = avail
            if avail:
                rock_swings[(zid, t_name)] = float(row["required_swings"])
    params["rock_swings"] = rock_swings
    params["zone_available"] = zone_available

    # Gem swings by (gem_id, tier)
    gem_swings = {}
    for gid in gems:
        target = "diamond_node" if gid == "diamond" else "generic_gem_node"
        for t_name in tiers:
            sub = gem_hits_df[
                (gem_hits_df["target_id"] == target)
                & (gem_hits_df["pickaxe_tier"] == t_name)
            ]
            gem_swings[(gid, t_name)] = float(sub.iloc[0]["required_swings"])
    params["gem_swings"] = gem_swings

    return params


def build_and_solve_mining_milp(
    horizon_days=28,
    min_one_rock_per_entered_level=False,
    integer_rocks=False,
    allow_partial_last_floor=True,
    lockout_days=2,
    maximize_depth=False,
    verbose=True,
):
    """
    Build and solve the Level-Indexed Standalone Mining MILP in Gurobi.

    Key Modeling Assumptions (aligned with XG0002_constraint_improvement.md):
    1. Single daily mine entry & sequential descent: The player enters the mine at most
       once per day and descends sequentially through slots l in {1..5}. Only the final
       level visited on day t may be left uncleared (z_{l,m,t} = 0), preventing
       unrealistic repeated re-entry of uncleared Zone 2 floors for free containers.
    2. Exact daily time constraint: Every pickaxe swing across all zones and tiers costs
       2.0 energy and 1.4 game minutes (0.7 min/energy), plus 1.4 min per container:
       0.7 * E_t + 1.4 * c_t <= 900 * (1 - w_t).
    3. Daily cash non-negativity: Cash_t >= 0 is enforced on every day t.
    4. Optional integer rocks (integer_rocks=True): r_{l,m,t} in Z_{>=0}.
    """
    params = load_mining_parameters()
    T = horizon_days
    open_day = params["mine_open_day"]
    active_days = list(range(open_day, T + 1))
    all_days = list(range(1, T + 1))
    slots = [1, 2, 3, 4, 5]
    zones = params["zones"]
    tiers = params["tiers"]
    upgrade_tiers = params["upgrade_tiers"]
    gems = params["gems"]

    model = gp.Model(f"Standalone_Mining_MILP_T{T}")
    if not verbose:
        model.Params.OutputFlag = 0
    model.Params.MIPGap = 0.0

    # =========================================================================
    # 1. DECISION VARIABLES
    # =========================================================================
    x = model.addVars(slots, zones, active_days, vtype=GRB.BINARY, name="x")
    z = model.addVars(slots, zones, active_days, vtype=GRB.BINARY, name="z")
    r_vtype = GRB.INTEGER if integer_rocks else GRB.CONTINUOUS
    r = model.addVars(slots, zones, active_days, lb=0.0, vtype=r_vtype, name="r")

    p_push = model.addVars(
        zones, active_days, lb=0.0, vtype=GRB.INTEGER, name="p_push"
    )
    g = model.addVars(gems, active_days, lb=0.0, vtype=GRB.CONTINUOUS, name="g")
    c = model.addVars(active_days, lb=0.0, vtype=GRB.CONTINUOUS, name="c")

    # Daily mining energy E[t] (explicit variable for exact time constraint & global merge)
    E_day = model.addVars(
        active_days,
        lb=0.0,
        ub=params["daily_energy_max"],
        vtype=GRB.CONTINUOUS,
        name="E_day",
    )

    u = model.addVars(upgrade_tiers, active_days, vtype=GRB.BINARY, name="u")
    w = model.addVars(active_days, vtype=GRB.BINARY, name="w")
    p = model.addVars(tiers, active_days, vtype=GRB.BINARY, name="p")
    v_z2 = model.addVars(active_days, vtype=GRB.BINARY, name="v_z2")
    v_z3 = model.addVars(active_days, vtype=GRB.BINARY, name="v_z3")

    # Cash balance at end of day t (lb=0.0 enforces Cash_t >= 0 on every day)
    cash = model.addVars(
        range(open_day - 1, T + 1), lb=0.0, vtype=GRB.CONTINUOUS, name="Cash"
    )

    # =========================================================================
    # 2. OBJECTIVE FUNCTION
    # =========================================================================
    if maximize_depth:
        total_depth_expr = gp.quicksum(
            p_push[m, t] for m in zones for t in active_days
        )
        model.setObjective(total_depth_expr * 1e5 + cash[T], GRB.MAXIMIZE)
    else:
        model.setObjective(cash[T], GRB.MAXIMIZE)

    # =========================================================================
    # 3. CONSTRAINTS
    # =========================================================================
    model.addConstr(cash[open_day - 1] == params["initial_cash"], name="InitCash")

    for k in upgrade_tiers:
        model.addConstr(
            gp.quicksum(u[k, t] for t in active_days) <= 1, name=f"OneUpgrade_{k}"
        )

    for t in active_days:
        model.addConstr(
            u["Steel", t]
            <= gp.quicksum(u["Copper", tau] for tau in active_days if tau <= t - 2),
            name=f"Prereq_Steel_{t}",
        )
        model.addConstr(
            u["Gold", t]
            <= gp.quicksum(u["Steel", tau] for tau in active_days if tau <= t - 2),
            name=f"Prereq_Gold_{t}",
        )
        # Blacksmith lockout: 2 days (day t and t+1) by default, or 1 intervening day (t+1 only)
        if lockout_days == 2:
            model.addConstr(
                w[t]
                == gp.quicksum(u[k, t] for k in upgrade_tiers)
                + (
                    gp.quicksum(u[k, t - 1] for k in upgrade_tiers)
                    if t > open_day
                    else 0.0
                ),
                name=f"Lockout_{t}",
            )
        else:
            model.addConstr(
                w[t]
                == (
                    gp.quicksum(u[k, t - 1] for k in upgrade_tiers)
                    if t > open_day
                    else 0.0
                ),
                name=f"Lockout_{t}",
            )

    for m in zones:
        model.addConstr(
            gp.quicksum(p_push[m, t] for t in active_days)
            <= params["zone_max_floors"][m],
            name=f"MaxDepth_{m}",
        )

    M_energy = 600.0
    for t in active_days:
        model.addConstr(
            gp.quicksum(p[k, t] for k in tiers) == 1 - w[t], name=f"ActivePick_{t}"
        )
        for k in upgrade_tiers:
            model.addConstr(
                p[k, t]
                <= gp.quicksum(u[k, tau] for tau in active_days if tau <= t - 2),
                name=f"UnlockedPick_{k}_{t}",
            )

        # Single daily mine entry at Slot 1 (subsequent slots require clearing previous ladder)
        model.addConstr(
            gp.quicksum(x[1, m, t] for m in zones) <= 1 - w[t],
            name=f"OneZoneSlot1_{t}",
        )
        model.addConstr(
            gp.quicksum(x[l, "mine_41_80", t] for l in slots) <= len(slots) * v_z2[t],
            name=f"VisitZ2_Link_{t}",
        )
        model.addConstr(
            gp.quicksum(x[l, "mine_81_120", t] for l in slots) <= len(slots) * v_z3[t],
            name=f"VisitZ3_Link_{t}",
        )
        model.addConstr(
            v_z2[t] <= p["Copper", t] + p["Steel", t] + p["Gold", t],
            name=f"UnlockZ2_Tool_{t}",
        )
        model.addConstr(
            v_z3[t] <= p["Gold", t],
            name=f"UnlockZ3_Tool_{t}",
        )

        cum_d1_prev = gp.quicksum(
            p_push["mine_1_40", tau] for tau in active_days if tau < t
        )
        cum_d2_prev = gp.quicksum(
            p_push["mine_41_80", tau] for tau in active_days if tau < t
        )
        cum_d1_curr = cum_d1_prev + p_push["mine_1_40", t]
        cum_d2_curr = cum_d2_prev + p_push["mine_41_80", t]

        model.addConstr(
            39.0 * x[1, "mine_41_80", t] <= cum_d1_prev, name=f"StartZ2_Depth_{t}"
        )
        model.addConstr(
            40.0 * x[1, "mine_81_120", t] <= cum_d2_prev, name=f"StartZ3_Depth_{t}"
        )
        model.addConstr(
            39.0 * v_z2[t] <= cum_d1_curr, name=f"UnlockZ2_Depth_{t}"
        )
        model.addConstr(
            40.0 * v_z3[t] <= cum_d2_curr, name=f"UnlockZ3_Depth_{t}"
        )
        model.addConstr(
            gp.quicksum(z[l, "mine_1_40", t] for l in slots) - p_push["mine_1_40", t]
            <= len(slots) * (1 - v_z2[t]),
            name=f"StrictPushTransitionZ1_{t}",
        )
        model.addConstr(
            gp.quicksum(z[l, "mine_41_80", t] for l in slots) - p_push["mine_41_80", t]
            <= len(slots) * (1 - v_z3[t]),
            name=f"StrictPushTransitionZ2_{t}",
        )

        for l in slots:
            if l < max(slots):
                model.addConstr(
                    gp.quicksum(x[l + 1, m, t] for m in zones)
                    <= gp.quicksum(z[l, m, t] for m in zones),
                    name=f"SeqClearance_{l}_{t}",
                )
                model.addConstr(
                    x[l + 1, "mine_1_40", t] <= z[l, "mine_1_40", t],
                    name=f"NoRegressZ1_{l}_{t}",
                )

            for m in zones:
                max_r = (
                    int(np.floor(params["max_rocks_by_zone"][m]))
                    if integer_rocks
                    else params["max_rocks_by_zone"][m]
                )
                req_r = params["req_rocks_by_zone"][m]

                if not allow_partial_last_floor:
                    # Strict V1 Section 4.1 rule: every entered level must clear >= req_r rocks
                    model.addConstr(z[l, m, t] == x[l, m, t], name=f"StrictClear_{l}_{m}_{t}")
                    model.addConstr(
                        r[l, m, t] <= max_r * x[l, m, t], name=f"MaxRocks_{l}_{m}_{t}"
                    )
                    model.addConstr(
                        r[l, m, t] >= req_r * z[l, m, t], name=f"LadderReq_{l}_{m}_{t}"
                    )
                else:
                    model.addConstr(
                        r[l, m, t]
                        <= req_r * z[l, m, t] + max_r * (x[l, m, t] - z[l, m, t]),
                        name=f"MaxRocks_{l}_{m}_{t}",
                    )
                    if min_one_rock_per_entered_level:
                        model.addConstr(
                            r[l, m, t] >= 1.0 * x[l, m, t] + (req_r - 1.0) * z[l, m, t],
                            name=f"LadderReq_{l}_{m}_{t}",
                        )
                    else:
                        model.addConstr(
                            r[l, m, t] >= req_r * z[l, m, t],
                            name=f"LadderReq_{l}_{m}_{t}",
                        )

        for m in zones:
            model.addConstr(
                p_push[m, t] <= gp.quicksum(z[l, m, t] for l in slots),
                name=f"PushBound_{m}_{t}",
            )

        for j in gems:
            model.addConstr(
                g[j, t]
                <= gp.quicksum(
                    params["gem_cap"][(m, j)] * gp.quicksum(x[l, m, t] for l in slots)
                    for m in zones
                ),
                name=f"GemCap_{j}_{t}",
            )
        model.addConstr(
            c[t]
            <= params["cont_cap_by_zone"]["mine_41_80"]
            * gp.quicksum(x[l, "mine_41_80", t] for l in slots),
            name=f"ContCap_{t}",
        )

        # Daily Energy (270) and Exact Time (900m) Budgets across all zones and tiers
        for k in tiers:
            valid_zones = [
                m for m in zones if params["zone_available"][(m, k)]
            ]
            e_rocks = gp.quicksum(
                (params["rock_swings"][(m, k)] * params["energy_per_swing"])
                * gp.quicksum(r[l, m, t] for l in slots)
                for m in valid_zones
            )
            e_gems = gp.quicksum(
                (params["gem_swings"][(j, k)] * params["energy_per_swing"]) * g[j, t]
                for j in gems
            )
            model.addConstr(
                e_rocks + e_gems
                <= E_day[t] + M_energy * (1 - p[k, t] - w[t]),
                name=f"EnergyTier_{k}_{t}",
            )

        # Exact daily energy and time bounds (1 swing = 2.0 E = 1.4 min -> 0.7 min/E)
        model.addConstr(
            E_day[t] <= params["daily_energy_max"] * (1 - w[t]),
            name=f"EnergyMax_{t}",
        )
        model.addConstr(
            0.7 * E_day[t] + params["minutes_per_container"] * c[t]
            <= params["daily_time_max"] * (1 - w[t]),
            name=f"TimeMax_{t}",
        )

        # Daily Revenue and Cash Balance (with start-of-day upgrade solvency if lockout_days == 1)
        rev_t = (
            gp.quicksum(
                params["rock_value_by_zone"][m]
                * gp.quicksum(r[l, m, t] for l in slots)
                for m in zones
            )
            + params["cont_val_by_zone"]["mine_41_80"] * c[t]
            + gp.quicksum(params["gem_price"][j] * g[j, t] for j in gems)
        )
        upg_t = gp.quicksum(
            params["upgrade_cost"][k] * u[k, t] for k in upgrade_tiers
        )
        if lockout_days == 1:
            model.addConstr(cash[t - 1] >= upg_t, name=f"Solvency_{t}")
        model.addConstr(
            cash[t] == cash[t - 1] + rev_t - upg_t, name=f"CashBal_{t}"
        )

    model.update()
    model.optimize()
    if model.Status != GRB.OPTIMAL:
        raise RuntimeError(f"Model did not solve to optimality. Status: {model.Status}")

    rows = []
    cum_ores = {"copper_ore": 0.0, "iron_ore": 0.0, "gold_ore": 0.0, "coal": 0.0}
    for t in all_days:
        if t < open_day:
            rows.append(
                {
                    "Day": t,
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
                }
            )
            continue

        upg_list = [k for k in upgrade_tiers if u[k, t].X > 0.5]
        upg_str = upg_list[0] if upg_list else "-"
        upg_val = sum(params["upgrade_cost"][k] * u[k, t].X for k in upgrade_tiers)

        active_k = "Lockout" if w[t].X > 0.5 else "None"
        for k in tiers:
            if p[k, t].X > 0.5:
                active_k = k

        entered_slots = []
        cleared_slots = []
        req_cleared_rocks = 0
        total_rocks = 0.0
        zones_visited = []
        for l in slots:
            for m in zones:
                if x[l, m, t].X > 0.5:
                    entered_slots.append((l, m))
                    zshort = (
                        m.replace("mine_", "Z")
                        .replace("1_40", "1")
                        .replace("41_80", "2")
                        .replace("81_120", "3")
                    )
                    if zshort not in zones_visited:
                        zones_visited.append(zshort)
                    total_rocks += r[l, m, t].X
                    for ore_k in cum_ores:
                        cum_ores[ore_k] += (
                            r[l, m, t].X * params["rock_drops_by_zone"][m][ore_k]
                        )
                    if z[l, m, t].X > 0.5:
                        cleared_slots.append((l, m))
                        req_cleared_rocks += params["req_rocks_by_zone"][m]

        marginal_rocks = max(0.0, total_rocks - req_cleared_rocks)
        tot_gems = sum(g[j, t].X for j in gems)
        tot_cont = c[t].X
        tot_depth = int(
            round(
                sum(
                    p_push[m, tau].X
                    for m in zones
                    for tau in active_days
                    if tau <= t
                )
            )
        )

        energy_used = 0.0
        time_used = 0.0
        if active_k in tiers:
            for l, m in entered_slots:
                r_sw = params["rock_swings"][(m, active_k)]
                energy_used += r[l, m, t].X * r_sw * 2.0
                time_used += r[l, m, t].X * r_sw * 1.4
            for j in gems:
                g_sw = params["gem_swings"][(j, active_k)]
                energy_used += g[j, t].X * g_sw * 2.0
                time_used += g[j, t].X * g_sw * 1.4
            time_used += tot_cont * 1.4

        rev_val = (
            sum(
                params["rock_value_by_zone"][m]
                * sum(r[l, m, t].X for l in slots)
                for m in zones
            )
            + params["cont_val_by_zone"]["mine_41_80"] * tot_cont
            + sum(params["gem_price"][j] * g[j, t].X for j in gems)
        )

        rows.append(
            {
                "Day": t,
                "Pickaxe": active_k,
                "Upgrade": upg_str,
                "Zones_Visited": "+".join(zones_visited) if zones_visited else "-",
                "Lvls_Entered": len(entered_slots),
                "Lvls_Cleared": len(cleared_slots),
                "Cleared_Rocks": req_cleared_rocks,
                "Marginal_Rocks": round(marginal_rocks, 2),
                "Total_Rocks": round(total_rocks, 2),
                "Gems": round(tot_gems, 2),
                "Containers": round(tot_cont, 2),
                "Energy": round(energy_used, 2),
                "Time_Min": round(time_used, 2),
                "Depth": tot_depth,
                "Revenue_g": round(rev_val, 2),
                "UpgCost_g": round(upg_val, 2),
                "Cash_End_g": round(cash[t].X, 2),
            }
        )

    df_res = pd.DataFrame(rows)
    return cash[T].X, df_res, model


if __name__ == "__main__":
    print("=" * 115)
    print("SCENARIO 1A: SPRING (T = 28), CONTINUOUS MARGINAL ROCKS (Baseline)")
    print("=" * 115)
    c1a, df1a, m1a = build_and_solve_mining_milp(
        horizon_days=28, integer_rocks=False, verbose=False
    )
    print(f"Model Size: {m1a.NumVars} vars, {m1a.NumConstrs} constrs | Optimal Cash: {c1a:,.2f} g\n")
    print(df1a.to_string(index=False))

    print("\n" + "=" * 115)
    print("SCENARIO 1B: SPRING (T = 28), INTEGER MARGINAL ROCKS (r_{l,m,t} in Z_{>=0}, XG0002 Item 5)")
    print("=" * 115)
    c1b, df1b, m1b = build_and_solve_mining_milp(
        horizon_days=28, integer_rocks=True, verbose=False
    )
    print(f"Model Size: {m1b.NumVars} vars, {m1b.NumConstrs} constrs | Optimal Cash (Integer Rocks): {c1b:,.2f} g\n")
    print(df1b.to_string(index=False))
