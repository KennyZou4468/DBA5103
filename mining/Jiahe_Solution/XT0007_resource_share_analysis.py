"""Reproduce the mining-only resource, target-day and upgrade comparisons.

Run with Python from any directory. Existing pandas/numpy/gurobipy are required.
Outputs prefixed XG0003 are written beside this script; source data is read-only.
"""

from pathlib import Path
import math
import pandas as pd

from XT0005_mining_milp_solver import load_mining_parameters
from XT0006_full_year_mining_milp import build_and_solve_full_year_mining_milp


OUTPUT_DIR = Path(__file__).resolve().parent
TARGET = 100000.0
TOLERANCE = 1e-5


def validate_schedule(cash, schedule, model, share, lockout_days=2, daily_energy_budget=None):
    """Independently recompute feasibility and cash from unrounded decisions."""
    params = load_mining_parameters()
    zones = params["zones"]
    opening = params["mine_open_day"]
    balance = params["initial_cash"] * share
    depth_one = depth_two = 0.0
    submitted = {}
    max_energy = max_time = 0.0
    daily_energy = params["daily_energy_max"] * share if daily_energy_budget is None else daily_energy_budget
    cash_path = {t: balance for t in range(1, opening)}

    def value(name):
        variable = model.getVarByName(name)
        assert variable is not None, name
        return variable.X

    for t in range(opening, int(schedule.Day.max()) + 1):
        upgrades = [k for k in params["upgrade_tiers"] if value(f"u[{k},{t}]") > 0.5]
        assert len(upgrades) <= 1
        for tier in upgrades:
            assert tier not in submitted
            index = params["upgrade_tiers"].index(tier)
            if index:
                previous = params["upgrade_tiers"][index - 1]
                assert previous in submitted and submitted[previous] + lockout_days <= t
            assert balance + TOLERANCE >= params["upgrade_cost"][tier]
            submitted[tier] = t
        locked = any(day <= t < day + lockout_days for day in submitted.values())
        owned = [k for k in params["upgrade_tiers"] if k in submitted and submitted[k] + lockout_days <= t]
        tier = owned[-1] if owned else "Basic"
        energy = time = revenue = containers = marginal_entries = 0.0
        clears = {}
        visits = {}
        for zone in zones:
            cleared = value(f"Z_clear[{zone},{t}]")
            marginal = value(f"x_marg[{zone},{t}]")
            rocks = value(f"r_marg[{zone},{t}]")
            assert abs(cleared - round(cleared)) <= TOLERANCE
            assert abs(rocks - round(rocks)) <= TOLERANCE
            assert 0 <= cleared <= 4 + TOLERANCE
            assert -TOLERANCE <= rocks <= params["max_rocks_by_zone"][zone] * marginal + TOLERANCE
            entries = cleared + marginal
            clears[zone], visits[zone] = cleared, entries
            marginal_entries += marginal
            if entries > TOLERANCE:
                assert not locked and params["zone_available"][(zone, tier)]
                total_rocks = params["req_rocks_by_zone"][zone] * cleared + rocks
                swings = total_rocks * params["rock_swings"][(zone, tier)]
                swings += entries * sum(params["gem_cap"][(zone, gem)] * params["gem_swings"][(gem, tier)] for gem in params["gems"])
                count = entries * params["cont_cap_by_zone"][zone]
                containers += count
                energy += 2 * swings
                time += 1.4 * (swings + count)
                revenue += total_rocks * params["rock_value_by_zone"][zone]
                revenue += entries * sum(params["gem_cap"][(zone, gem)] * params["gem_price"][gem] for gem in params["gems"])
                revenue += count * params["cont_val_by_zone"][zone]
        assert marginal_entries <= int(not locked) + TOLERANCE
        push = value(f"p_push_z1[{t}]")
        assert -TOLERANCE <= push <= clears[zones[0]] + TOLERANCE
        depth_one += push
        assert depth_one <= 39 + TOLERANCE
        if visits[zones[1]] > TOLERANCE:
            assert depth_one >= 39 - TOLERANCE
            assert clears[zones[0]] - push <= TOLERANCE
        depth_two += clears[zones[1]]
        if visits[zones[2]] > TOLERANCE:
            assert depth_two >= 40 - TOLERANCE
        assert energy <= daily_energy + TOLERANCE
        assert time <= params["daily_time_max"] * share + TOLERANCE
        assert abs(time - (0.7 * energy + 1.4 * containers)) <= TOLERANCE
        balance += revenue - sum(params["upgrade_cost"][k] for k in upgrades)
        cash_path[t] = balance
        assert balance >= -TOLERANCE
        row = schedule.loc[schedule.Day == t].iloc[0]
        assert abs(row.Cash_End_g - balance) <= 0.0051
        assert abs(row.Energy - energy) <= 0.0051
        assert abs(row.Time_Min - time) <= 0.0051
        max_energy, max_time = max(max_energy, energy), max(max_time, time)
    assert abs(cash - balance) <= TOLERANCE
    assert model.Status == 2 and model.MIPGap <= TOLERANCE
    schedule.attrs["unrounded_cash"] = cash_path
    return max_energy, max_time


def run_analysis():
    cache = {}
    search_rows, summary_rows, schedules, upgrade_rows = [], [], [], []
    sensitivity_rows = []
    params = load_mining_parameters()
    first_zone = params["zones"][0]
    floor_energy = params["energy_per_swing"] * (
        params["req_rocks_by_zone"][first_zone] * params["rock_swings"][(first_zone, "Basic")]
        + sum(params["gem_cap"][(first_zone, gem)] * params["gem_swings"][(gem, "Basic")] for gem in params["gems"])
    )
    minimum_floor_energy = math.ceil(floor_energy)

    def solve(share, horizon, fixed=None):
        key = (share, horizon, energy_budget, tuple(sorted((fixed or {}).items())))
        if key not in cache:
            result = build_and_solve_full_year_mining_milp(
                horizon_days=horizon, resource_share=share, integer_rocks=True,
                upgrade_days=fixed, verbose=False,
                daily_energy_budget=energy_budget,
            )
            validate_schedule(*result, share, daily_energy_budget=energy_budget)
            cache[key] = result
        return cache[key]

    for label, share, energy_budget in (
        ("full", 1.0, None), ("one_third", 1 / 3, None),
        ("minimum_floor", 1 / 3, minimum_floor_energy),
    ):
        year_cash, _, _ = solve(share, 112)
        for horizon in (28, 112):
            cash, schedule, model = solve(share, horizon)
            energy, time = validate_schedule(cash, schedule, model, share, daily_energy_budget=energy_budget)
            dates = {row.Upgrade: int(row.Day) for row in schedule.itertuples() if row.Upgrade != "-"}
            for tier in ("Copper", "Steel"):
                if tier not in dates:
                    continue
                day = dates[tier]
                cost = params["upgrade_cost"][tier]
                prerequisite = "Copper" if tier == "Steel" else None
                earliest = next(
                    int(row.Day) + 1 for row in schedule.itertuples()
                    if row.Day < day and schedule.attrs["unrounded_cash"][row.Day] + TOLERANCE >= cost
                    and (prerequisite is None or row.Day + 1 >= dates[prerequisite] + 2)
                )
                # Fix this purchase one day later and reoptimize every other action.
                delayed_cash, _, _ = solve(share, horizon, {tier: day + 1})
                assert delayed_cash <= cash + TOLERANCE
                upgrade_rows.append({
                    "Scenario": label, "Horizon": horizon, "Test": f"delay_{tier}_one_day",
                    "Baseline_Day": day, "First_Affordable_On_Chosen_Path": earliest,
                    "Forced_Day": day + 1, "Baseline_Cash_g": cash,
                    "Counterfactual_Cash_g": delayed_cash, "Loss_g": cash - delayed_cash,
                })
            # A counterexample to 'buy EVERY upgrade as soon as affordable'.
            if "Steel" in dates:
                candidates = schedule.loc[
                    (schedule.Day >= dates["Steel"] + 1)
                    & (schedule.Day < horizon)
                    & (schedule.Day.map(schedule.attrs["unrounded_cash"]) >= params["upgrade_cost"]["Gold"]), "Day"
                ]
                if not candidates.empty:
                    gold_day = int(candidates.iloc[0]) + 1
                    fixed = dict(dates, Gold=gold_day)
                    forced_cash, _, _ = solve(share, horizon, fixed)
                    assert forced_cash <= cash + TOLERANCE
                    upgrade_rows.append({
                        "Scenario": label, "Horizon": horizon, "Test": "buy_Gold_when_affordable",
                        "Baseline_Day": None, "First_Affordable_On_Chosen_Path": gold_day,
                        "Forced_Day": gold_day, "Baseline_Cash_g": cash,
                        "Counterfactual_Cash_g": forced_cash, "Loss_g": cash - forced_cash,
                    })
            zone_two = schedule.loc[schedule.Zones_Visited.str.contains("Z2"), "Day"]
            summary_rows.append({
                "Scenario": label, "Horizon": horizon, "Resource_Share": share,
                "Initial_Cash_g": 500 * share,
                "Daily_Energy": 270 * share if energy_budget is None else energy_budget,
                "Daily_Time_Min": 900 * share, "Optimal_Cash_g": cash,
                "Copper_Day": dates.get("Copper"), "Steel_Day": dates.get("Steel"),
                "Gold_Day": dates.get("Gold"),
                "First_Zone2_Day": None if zone_two.empty else int(zone_two.iloc[0]),
                "Max_Depth": int(schedule.Depth.max()), "Max_Energy": energy,
                "Max_Time_Min": time, "Variables": model.NumVars, "Constraints": model.NumConstrs,
            })
            schedules.append(schedule.assign(Scenario=label, Objective="max_terminal_cash", Horizon=horizon))

        # The optimal cash envelope is monotone: an earlier solution can be
        # extended by idle days. Binary search therefore finds the earliest day.
        def envelope(day):
            cash = solve(share, day)[0]
            search_rows.append({"Scenario": label, "Day": day, "Max_Cash_g": cash, "Target_g": TARGET, "Reachable": cash >= TARGET - TOLERANCE})
            return cash

        if envelope(112) >= TARGET - TOLERANCE:
            low, high = 5, 112
            while low < high:
                mid = (low + high) // 2
                if envelope(mid) >= TARGET - TOLERANCE:
                    high = mid
                else:
                    low = mid + 1
            cash, schedule, _ = solve(share, low)
            previous_cash = envelope(low - 1) if low > 5 else 500 * share
            assert previous_cash < TARGET and cash >= TARGET - TOLERANCE
            schedules.append(schedule.assign(Scenario=label, Objective="earliest_target", Horizon=low))
            target_day = low
        else:
            target_day = None
        for row in summary_rows:
            if row["Scenario"] == label:
                row["Earliest_Target_Day_Within_Year1"] = target_day
        print(f"{label}: Year 1 cash={year_cash:,.2f}g; earliest target day={target_day}", flush=True)

        for assumption, options in (
            ("strict_clear_every_entered_floor", {"allow_partial_last_floor": False}),
            ("one_day_submission_lockout", {"lockout_days": 1}),
        ):
            cash, schedule, model = build_and_solve_full_year_mining_milp(
                resource_share=share, daily_energy_budget=energy_budget, integer_rocks=True, **options
            )
            validate_schedule(cash, schedule, model, share, options.get("lockout_days", 2), energy_budget)
            dates = {row.Upgrade: int(row.Day) for row in schedule.itertuples() if row.Upgrade != "-"}
            sensitivity_rows.append({
                "Scenario": label, "Assumption": assumption, "Horizon": 112,
                "Optimal_Cash_g": cash, "Copper_Day": dates.get("Copper"),
                "Steel_Day": dates.get("Steel"), "Gold_Day": dates.get("Gold"),
                "Max_Depth": int(schedule.Depth.max()),
            })
            schedules.append(schedule.assign(Scenario=label, Objective=assumption, Horizon=112))
            model.dispose()

    summary = pd.DataFrame(summary_rows)
    upgrades = pd.DataFrame(upgrade_rows)
    search = pd.DataFrame(search_rows).drop_duplicates(["Scenario", "Day"]).sort_values(["Scenario", "Day"])
    summary.to_csv(OUTPUT_DIR / "XG0003_resource_share_summary.csv", index=False, float_format="%.8f")
    pd.concat(schedules, ignore_index=True).to_csv(OUTPUT_DIR / "XG0003_daily_schedules.csv", index=False)
    upgrades.to_csv(OUTPUT_DIR / "XG0003_upgrade_tests.csv", index=False, float_format="%.8f")
    search.to_csv(OUTPUT_DIR / "XG0003_target_search.csv", index=False, float_format="%.8f")
    sensitivity = pd.DataFrame(sensitivity_rows)
    sensitivity.to_csv(OUTPUT_DIR / "XG0003_assumption_sensitivity.csv", index=False, float_format="%.8f")
    print(summary.to_string(index=False))
    print(upgrades.to_string(index=False))
    print(sensitivity.to_string(index=False))
    for cash, schedule, model in cache.values():
        model.dispose()


if __name__ == "__main__":
    run_analysis()
