import os
import pandas as pd
import numpy as np

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MINING_DIR = os.path.join(BASE_DIR, "mining", "data")
SHARED_DIR = os.path.join(BASE_DIR, "shared", "data")

def load_data():
    node_df = pd.read_csv(os.path.join(MINING_DIR, "mining_node_profiles.csv"))
    cash_df = pd.read_csv(os.path.join(MINING_DIR, "mining_resource_cash_values.csv"))
    gem_df = pd.read_csv(os.path.join(MINING_DIR, "mining_gem_node_profiles.csv"))
    gem_hits_df = pd.read_csv(os.path.join(MINING_DIR, "mining_gem_hit_requirements.csv"))
    container_df = pd.read_csv(os.path.join(MINING_DIR, "mine_container_profiles.csv"))
    rock_hits_df = pd.read_csv(os.path.join(MINING_DIR, "mining_ordinary_rock_hit_requirements.csv"))
    cash_map = dict(zip(cash_df["resource_id"], cash_df["cash_value_per_unit_g"]))
    return node_df, cash_map, gem_df, gem_hits_df, container_df, rock_hits_df

def compute_level_returns():
    node_df, cash_map, gem_df, gem_hits_df, container_df, rock_hits_df = load_data()

    zones = [
        {"id": "mine_1_40", "name": "Level 1 (Floors 1-39)", "floors": 39},
        {"id": "mine_41_80", "name": "Level 2 (Floors 40-79)", "floors": 40},
        {"id": "mine_81_120", "name": "Level 3 (Floors 80-120)", "floors": 41}
    ]

    results = []

    for z in zones:
        zid = z["id"]
        zname = z["name"]
        num_floors = z["floors"]

        # 1. Ordinary rock drops
        nrow = node_df[node_df["zone_id"] == zid].iloc[0]
        req_rocks = nrow["exploration_rocks_required_per_floor_50pct_ceiling"]

        c_ore = nrow["expected_copper_ore_per_broken_rock"] * cash_map["copper_ore"]
        i_ore = nrow["expected_iron_ore_per_broken_rock"] * cash_map["iron_ore"]
        g_ore = nrow["expected_gold_ore_per_broken_rock"] * cash_map["gold_ore"]
        stone = nrow["expected_stone_per_broken_rock"] * cash_map["stone"]
        coal = nrow["expected_coal_per_broken_rock"] * cash_map["coal"]
        geode = nrow["expected_geode_per_broken_rock"] * cash_map["geode"]
        f_geode = nrow["expected_frozen_geode_per_broken_rock"] * cash_map["frozen_geode"]
        m_geode = nrow["expected_magma_geode_per_broken_rock"] * cash_map["magma_geode"]

        rock_val = c_ore + i_ore + g_ore + stone + coal + geode + f_geode + m_geode
        base_rock_cash = rock_val * req_rocks

        # 2. Gem drops
        zgems = gem_df[gem_df["zone_id"] == zid].copy()
        zgems["expected_cash"] = zgems["expected_nodes_per_ordinary_floor"] * zgems["normal_sell_price_g"]
        gem_cash = zgems["expected_cash"].sum()
        gem_nodes = zgems["expected_nodes_per_ordinary_floor"].sum()

        # 3. Containers
        crow = container_df[container_df["zone_id"] == zid].iloc[0]
        cont_count = crow["mean_generated_containers_per_ordinary_floor"]
        cont_cash = cont_count * crow["expected_direct_sale_g_before_bottom_per_container"]

        # Total per floor
        total_floor_cash = base_rock_cash + gem_cash + cont_cash
        total_level_cash = total_floor_cash * num_floors

        results.append({
            "zone_id": zid,
            "level_name": zname,
            "floor_count": num_floors,
            "req_rocks_per_floor": req_rocks,
            "rock_cash_per_rock_g": rock_val,
            "baseline_rock_cash_per_floor_g": base_rock_cash,
            "gem_nodes_per_floor": gem_nodes,
            "gem_cash_per_floor_g": gem_cash,
            "containers_per_floor": cont_count,
            "container_cash_per_floor_g": cont_cash,
            "total_expected_return_per_floor_g": total_floor_cash,
            "total_level_capacity_cash_g": total_level_cash
        })

    res_df = pd.DataFrame(results)
    print("=" * 80)
    print("EXPECTED RETURN BY LEVEL (ZONE)")
    print("=" * 80)
    print(res_df[["level_name", "floor_count", "baseline_rock_cash_per_floor_g", "gem_cash_per_floor_g", "container_cash_per_floor_g", "total_expected_return_per_floor_g", "total_level_capacity_cash_g"]].to_string(index=False))

    print("\n" + "=" * 80)
    print("DAILY RETURN BY LEVEL AND PICKAXE TIER (270 Energy, 900 Mins)")
    print("=" * 80)

    daily_scenarios = [
        {"level": "Level 1 (Floors 1-39)", "zone_id": "mine_1_40", "pickaxe": "Basic", "rock_swings": 2, "gem_swings_gen": 5, "gem_swings_dia": 10},
        {"level": "Level 1 (Floors 1-39)", "zone_id": "mine_1_40", "pickaxe": "Copper", "rock_swings": 1, "gem_swings_gen": 3, "gem_swings_dia": 5},
        {"level": "Level 2 (Floors 40-79)", "zone_id": "mine_41_80", "pickaxe": "Copper", "rock_swings": 2, "gem_swings_gen": 3, "gem_swings_dia": 5},
        {"level": "Level 2 (Floors 40-79)", "zone_id": "mine_41_80", "pickaxe": "Steel", "rock_swings": 1, "gem_swings_gen": 2, "gem_swings_dia": 4},
        {"level": "Level 3 (Floors 80-120)", "zone_id": "mine_81_120", "pickaxe": "Gold", "rock_swings": 1, "gem_swings_gen": 2, "gem_swings_dia": 3},
    ]

    daily_res = []
    for sc in daily_scenarios:
        zid = sc["zone_id"]
        rinfo = res_df[res_df["zone_id"] == zid].iloc[0]
        req_rocks = rinfo["req_rocks_per_floor"]
        rock_swings = sc["rock_swings"]

        # calculate energy and time per floor
        rock_energy = req_rocks * rock_swings * 2.0
        rock_time = req_rocks * rock_swings * 1.4

        # gem energy and time per floor
        zgems = gem_df[gem_df["zone_id"] == zid]
        gem_swings = 0
        for _, grow in zgems.iterrows():
            cnt = grow["expected_nodes_per_ordinary_floor"]
            gid = grow["gem_id"]
            s = sc["gem_swings_dia"] if gid == "diamond" else sc["gem_swings_gen"]
            gem_swings += cnt * s
        gem_energy = gem_swings * 2.0
        gem_time = gem_swings * 1.4

        # container energy and time
        cont_count = rinfo["containers_per_floor"]
        cont_energy = 0.0
        cont_time = cont_count * 1.4

        total_energy_per_floor = rock_energy + gem_energy + cont_energy
        total_time_per_floor = rock_time + gem_time + cont_time

        # Daily throughput limited by energy (270) or time (900)
        floors_energy_lim = 270.0 / total_energy_per_floor
        floors_time_lim = 900.0 / total_time_per_floor
        floors_per_day = min(floors_energy_lim, floors_time_lim)

        expected_daily_cash = floors_per_day * rinfo["total_expected_return_per_floor_g"]

        daily_res.append({
            "level": sc["level"],
            "pickaxe": sc["pickaxe"],
            "energy_per_floor": total_energy_per_floor,
            "time_per_floor_min": total_time_per_floor,
            "max_floors_per_day": floors_per_day,
            "limiting_factor": "Energy (270)" if floors_energy_lim <= floors_time_lim else "Time (900m)",
            "expected_daily_cash_g": expected_daily_cash,
            "return_per_energy_g": expected_daily_cash / (floors_per_day * total_energy_per_floor),
            "return_per_minute_g": expected_daily_cash / (floors_per_day * total_time_per_floor)
        })

    daily_df = pd.DataFrame(daily_res)
    print(daily_df[["level", "pickaxe", "energy_per_floor", "max_floors_per_day", "limiting_factor", "expected_daily_cash_g", "return_per_energy_g"]].to_string(index=False))

if __name__ == "__main__":
    compute_level_returns()
