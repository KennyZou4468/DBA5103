import os
import pandas as pd
import numpy as np

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MINING_DIR = os.path.join(BASE_DIR, "mining", "data")
SHARED_DIR = os.path.join(BASE_DIR, "shared", "data")

def load_tables():
    tables = {}
    tables["global_parameters"] = pd.read_csv(os.path.join(SHARED_DIR, "global_parameters.csv"))
    tables["mining_node_profiles"] = pd.read_csv(os.path.join(MINING_DIR, "mining_node_profiles.csv"))
    tables["mining_ordinary_rock_hit_requirements"] = pd.read_csv(os.path.join(MINING_DIR, "mining_ordinary_rock_hit_requirements.csv"))
    tables["mining_gem_node_profiles"] = pd.read_csv(os.path.join(MINING_DIR, "mining_gem_node_profiles.csv"))
    tables["mining_gem_hit_requirements"] = pd.read_csv(os.path.join(MINING_DIR, "mining_gem_hit_requirements.csv"))
    tables["mine_container_profiles"] = pd.read_csv(os.path.join(MINING_DIR, "mine_container_profiles.csv"))
    tables["mining_resource_cash_values"] = pd.read_csv(os.path.join(MINING_DIR, "mining_resource_cash_values.csv"))
    tables["mining_pickaxe_catalog"] = pd.read_csv(os.path.join(MINING_DIR, "mining_pickaxe_catalog.csv"))
    return tables

def analyze():
    tables = load_tables()
    print("=" * 60)
    print("TABLE INVENTORY AND INTEGRITY CHECK")
    print("=" * 60)
    for name, df in tables.items():
        print(f"\n--- {name} ---")
        print(f"Shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        null_counts = df.isnull().sum()
        null_cols = null_counts[null_counts > 0]
        if not null_cols.empty:
            print(f"Nulls found: {dict(null_cols)}")
        else:
            print("Nulls: None")

    cash_map = dict(zip(tables["mining_resource_cash_values"]["resource_id"], tables["mining_resource_cash_values"]["cash_value_per_unit_g"]))
    print("\n" + "=" * 60)
    print("1. RESOURCE CASH VALUES MAP")
    print("=" * 60)
    for k, v in cash_map.items():
        print(f"  {k:20s}: {v:6.1f} g")

    print("\n" + "=" * 60)
    print("2. ORDINARY ROCK EXPECTED VALUE PER BROKEN ROCK BY ZONE")
    print("=" * 60)
    node_df = tables["mining_node_profiles"].copy()

    # Calculate expected value per rock
    # Columns in node_df:
    # expected_copper_ore_per_broken_rock -> copper_ore
    # expected_iron_ore_per_broken_rock -> iron_ore
    # expected_gold_ore_per_broken_rock -> gold_ore
    # expected_stone_per_broken_rock -> stone
    # expected_coal_per_broken_rock -> coal
    # expected_geode_per_broken_rock -> geode
    # expected_frozen_geode_per_broken_rock -> frozen_geode
    # expected_magma_geode_per_broken_rock -> magma_geode
    # expected_omni_geode_per_broken_rock -> omni_geode

    rock_yields = []
    for idx, row in node_df.iterrows():
        zone = row["zone_id"]
        copper_val = row["expected_copper_ore_per_broken_rock"] * cash_map["copper_ore"]
        iron_val = row["expected_iron_ore_per_broken_rock"] * cash_map["iron_ore"]
        gold_val = row["expected_gold_ore_per_broken_rock"] * cash_map["gold_ore"]
        stone_val = row["expected_stone_per_broken_rock"] * cash_map["stone"]
        coal_val = row["expected_coal_per_broken_rock"] * cash_map["coal"]
        geode_val = row["expected_geode_per_broken_rock"] * cash_map["geode"]
        frozen_val = row["expected_frozen_geode_per_broken_rock"] * cash_map["frozen_geode"]
        magma_val = row["expected_magma_geode_per_broken_rock"] * cash_map["magma_geode"]
        omni_val = row["expected_omni_geode_per_broken_rock"] * cash_map["omni_geode"]

        total_val = copper_val + iron_val + gold_val + stone_val + coal_val + geode_val + frozen_val + magma_val + omni_val
        req_rocks = row["exploration_rocks_required_per_floor_50pct_ceiling"]
        base_floor_val = total_val * req_rocks

        rock_yields.append({
            "zone_id": zone,
            "level_range": row["level_range"],
            "copper_g": copper_val,
            "iron_g": iron_val,
            "gold_g": gold_val,
            "stone_g": stone_val,
            "coal_g": coal_val,
            "geodes_g": geode_val + frozen_val + magma_val + omni_val,
            "expected_cash_per_rock_g": total_val,
            "required_rocks_per_floor": req_rocks,
            "expected_baseline_rock_cash_per_floor_g": base_floor_val
        })
    rock_yield_df = pd.DataFrame(rock_yields)
    print(rock_yield_df.to_string(index=False))

    print("\n" + "=" * 60)
    print("3. HIT REQUIREMENTS & TIME/ENERGY COST PER ROCK")
    print("=" * 60)
    rock_hits = tables["mining_ordinary_rock_hit_requirements"]
    print(rock_hits.to_string(index=False))

    print("\n" + "=" * 60)
    print("4. GEM NODES PROFILE & EXPECTED CASH PER FLOOR")
    print("=" * 60)
    gem_df = tables["mining_gem_node_profiles"].copy()
    gem_df["expected_cash_per_floor_g"] = gem_df["expected_nodes_per_ordinary_floor"] * gem_df["normal_sell_price_g"]
    print(gem_df.to_string(index=False))

    gem_summary = gem_df.groupby("zone_id")[["expected_nodes_per_ordinary_floor", "expected_cash_per_floor_g"]].sum().reset_index()
    print("\nTotal Gem Expectation Per Floor By Zone:")
    print(gem_summary.to_string(index=False))

    print("\n" + "=" * 60)
    print("5. WOODEN CONTAINERS (BARRELS) PER FLOOR")
    print("=" * 60)
    container_df = tables["mine_container_profiles"].copy()
    container_df["expected_container_cash_per_floor_g"] = container_df["mean_generated_containers_per_ordinary_floor"] * container_df["expected_direct_sale_g_before_bottom_per_container"]
    container_df["total_container_time_per_floor_min"] = container_df["mean_generated_containers_per_ordinary_floor"] * container_df["collection_time_game_minutes_per_container"]
    print(container_df.to_string(index=False))

    print("\n" + "=" * 60)
    print("6. PICKAXE CATALOG & UPGRADES")
    print("=" * 60)
    pick_df = tables["mining_pickaxe_catalog"][["pickaxe_id", "tier", "time_game_minutes_per_swing", "energy_per_swing", "upgrade_cash_equivalent_cost_g", "blacksmith_fee_g", "bars_cash_equivalent_g", "service_duration_days", "tool_unavailable_intervening_days"]]
    print(pick_df.to_string(index=False))

    print("\n" + "=" * 60)
    print("7. FLOOR CLEARING COMBINED REVENUE & COST ANALYSIS")
    print("=" * 60)
    # Combine rock baseline cash + gem expected cash + container cash
    merged_summary = []
    for zone in ["mine_1_40", "mine_41_80", "mine_81_120"]:
        r_row = rock_yield_df[rock_yield_df["zone_id"] == zone].iloc[0]
        g_row = gem_summary[gem_summary["zone_id"] == zone].iloc[0]
        c_row = container_df[container_df["zone_id"] == zone].iloc[0]

        base_rock_cash = r_row["expected_baseline_rock_cash_per_floor_g"]
        gem_cash = g_row["expected_cash_per_floor_g"]
        container_cash = c_row["expected_container_cash_per_floor_g"]
        total_potential_floor_cash = base_rock_cash + gem_cash + container_cash

        merged_summary.append({
            "zone_id": zone,
            "level_range": r_row["level_range"],
            "base_rocks": r_row["required_rocks_per_floor"],
            "base_rock_cash_g": base_rock_cash,
            "gem_cash_g": gem_cash,
            "container_cash_g": container_cash,
            "total_floor_potential_g": total_potential_floor_cash
        })
    print(pd.DataFrame(merged_summary).to_string(index=False))

if __name__ == "__main__":
    analyze()
