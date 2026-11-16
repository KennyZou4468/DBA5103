import os
import pandas as pd
import numpy as np

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MINING_DIR = os.path.join(BASE_DIR, "mining", "data")

def analyze_gem_nodes():
    gem_profiles = pd.read_csv(os.path.join(MINING_DIR, "mining_gem_node_profiles.csv"))
    gem_hits = pd.read_csv(os.path.join(MINING_DIR, "mining_gem_hit_requirements.csv"))
    rock_hits = pd.read_csv(os.path.join(MINING_DIR, "mining_ordinary_rock_hit_requirements.csv"))
    node_profiles = pd.read_csv(os.path.join(MINING_DIR, "mining_node_profiles.csv"))
    cash_values = pd.read_csv(os.path.join(MINING_DIR, "mining_resource_cash_values.csv"))
    cash_map = dict(zip(cash_values["resource_id"], cash_values["cash_value_per_unit_g"]))

    print("=" * 80)
    print("GEM NODES DETAILED EDA")
    print("=" * 80)

    # 1. Gem profiles across zones
    print("\n1. Gem Node Frequency & Unit Sell Prices by Zone:")
    pivot_freq = gem_profiles.pivot(index="gem_name", columns="zone_id", values="expected_nodes_per_ordinary_floor")
    price_map = gem_profiles.groupby("gem_name")["normal_sell_price_g"].first()
    pivot_freq["sell_price_g"] = price_map
    print(pivot_freq.to_string())

    # 2. Gem hit requirements by tier
    print("\n2. Gem Hit Requirements by Pickaxe Tier:")
    pivot_hits = gem_hits.pivot(index="pickaxe_tier", columns="target_id", values="required_swings")
    tier_order = ["Basic", "Copper", "Steel", "Gold", "Iridium"]
    pivot_hits = pivot_hits.reindex(tier_order)
    print(pivot_hits.to_string())

    # 3. Efficiency Metrics: Return per Energy and Return per Minute
    print("\n3. Economic Efficiency of Harvesting Gem Nodes:")
    efficiency_records = []
    gems = [
        ("Amethyst", 100, "generic_gem_node"),
        ("Topaz", 80, "generic_gem_node"),
        ("Aquamarine", 180, "generic_gem_node"),
        ("Jade", 200, "generic_gem_node"),
        ("Emerald", 250, "generic_gem_node"),
        ("Ruby", 250, "generic_gem_node"),
        ("Diamond", 750, "diamond_node")
    ]

    for gem_name, price, target_type in gems:
        for tier in tier_order:
            swings_row = gem_hits[(gem_hits["target_id"] == target_type) & (gem_hits["pickaxe_tier"] == tier)]
            if swings_row.empty:
                continue
            swings = swings_row.iloc[0]["required_swings"]
            energy = swings * 2.0
            time_min = swings * 1.4
            g_per_energy = price / energy
            g_per_min = price / time_min
            efficiency_records.append({
                "Gem": gem_name,
                "Price (g)": price,
                "Pickaxe": tier,
                "Target Type": target_type,
                "Swings": swings,
                "Energy": energy,
                "Time (min)": time_min,
                "g / Energy": round(g_per_energy, 2),
                "g / Minute": round(g_per_min, 2)
            })

    eff_df = pd.DataFrame(efficiency_records)
    print(eff_df.to_string(index=False))

    # 4. Compare with Ordinary Rocks in Each Zone
    print("\n4. Comparison: Gem Node vs Ordinary Rock Efficiency:")
    rock_eff = []
    zones = [
        ("mine_1_40", "Zone 1 (1-39)", ["Basic", "Copper"]),
        ("mine_41_80", "Zone 2 (40-79)", ["Copper", "Steel"]),
        ("mine_81_120", "Zone 3 (80-120)", ["Gold", "Iridium"])
    ]

    for zid, zname, valid_tiers in zones:
        np_row = node_profiles[node_profiles["zone_id"] == zid].iloc[0]
        # value per broken rock
        r_val = (
            np_row["expected_copper_ore_per_broken_rock"] * cash_map["copper_ore"] +
            np_row["expected_iron_ore_per_broken_rock"] * cash_map["iron_ore"] +
            np_row["expected_gold_ore_per_broken_rock"] * cash_map["gold_ore"] +
            np_row["expected_stone_per_broken_rock"] * cash_map["stone"] +
            np_row["expected_coal_per_broken_rock"] * cash_map["coal"] +
            np_row["expected_geode_per_broken_rock"] * cash_map["geode"] +
            np_row["expected_frozen_geode_per_broken_rock"] * cash_map["frozen_geode"] +
            np_row["expected_magma_geode_per_broken_rock"] * cash_map["magma_geode"]
        )
        for tier in valid_tiers:
            rh_row = rock_hits[(rock_hits["zone_id"] == zid) & (rock_hits["pickaxe_tier"] == tier)]
            if rh_row.empty:
                continue
            swings = rh_row.iloc[0]["required_swings"]
            energy = swings * 2.0
            time_min = swings * 1.4
            rock_eff.append({
                "Zone": zname,
                "Pickaxe": tier,
                "Rock Value (g)": round(r_val, 2),
                "Swings": swings,
                "Energy": energy,
                "Time (min)": time_min,
                "g / Energy": round(r_val / energy, 2),
                "g / Minute": round(r_val / time_min, 2)
            })
    print(pd.DataFrame(rock_eff).to_string(index=False))

    # 5. Zone expected gem values and swing totals per floor
    print("\n5. Expected Gem Yield and Cost per Ordinary Floor:")
    zone_summary = []
    for zid, zname, valid_tiers in zones:
        z_gems = gem_profiles[gem_profiles["zone_id"] == zid]
        total_gem_cash = (z_gems["expected_nodes_per_ordinary_floor"] * z_gems["normal_sell_price_g"]).sum()
        total_gen_nodes = z_gems[z_gems["gem_id"] != "diamond"]["expected_nodes_per_ordinary_floor"].sum()
        diamond_nodes = z_gems[z_gems["gem_id"] == "diamond"]["expected_nodes_per_ordinary_floor"].sum()

        for tier in valid_tiers:
            gen_swings = gem_hits[(gem_hits["target_id"] == "generic_gem_node") & (gem_hits["pickaxe_tier"] == tier)].iloc[0]["required_swings"]
            dia_swings = gem_hits[(gem_hits["target_id"] == "diamond_node") & (gem_hits["pickaxe_tier"] == tier)].iloc[0]["required_swings"]
            tot_swings = total_gen_nodes * gen_swings + diamond_nodes * dia_swings
            tot_energy = tot_swings * 2.0
            tot_time = tot_swings * 1.4
            zone_summary.append({
                "Zone": zname,
                "Pickaxe": tier,
                "Gen Gem Nodes/Flr": round(total_gen_nodes, 4),
                "Diamond Nodes/Flr": round(diamond_nodes, 4),
                "Expected Gem Cash (g)": round(total_gem_cash, 2),
                "Gem Swings/Flr": round(tot_swings, 2),
                "Gem Energy/Flr": round(tot_energy, 2),
                "Gem Time/Flr (min)": round(tot_time, 2),
                "Avg g / Energy": round(total_gem_cash / tot_energy, 2) if tot_energy > 0 else 0
            })
    print(pd.DataFrame(zone_summary).to_string(index=False))

if __name__ == "__main__":
    analyze_gem_nodes()
