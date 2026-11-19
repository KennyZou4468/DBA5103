import os
import pandas as pd
import numpy as np

# Load core baseline values
DAILY_ENERGY = 270.0
DAILY_MINUTES = 900.0
INITIAL_CASH = 500.0

# Level 1 (Floors 1-39)
L1_ROCKS_REQ = 33
L1_CASH_PER_FLOOR = 98.1398
L1_ENERGY_BASIC = 133.6578  # 33 * 2 * 2 + gem energy
L1_ENERGY_COPPER = 66.9947  # 33 * 1 * 2 + gem energy
L1_DAILY_CASH_BASIC = (DAILY_ENERGY / L1_ENERGY_BASIC) * L1_CASH_PER_FLOOR   # ~198.25g
L1_DAILY_CASH_COPPER = (DAILY_ENERGY / L1_ENERGY_COPPER) * L1_CASH_PER_FLOOR # ~395.52g

# Level 2 (Floors 40-79)
L2_ROCKS_REQ = 29
L2_CASH_PER_FLOOR = 420.5830
L2_ENERGY_COPPER = 117.8064 # 29 * 2 * 2 + gem energy
L2_ENERGY_STEEL = 59.2509   # 29 * 1 * 2 + gem energy
L2_DAILY_CASH_COPPER = (DAILY_ENERGY / L2_ENERGY_COPPER) * L2_CASH_PER_FLOOR # ~963.93g
L2_DAILY_CASH_STEEL = (DAILY_ENERGY / L2_ENERGY_STEEL) * L2_CASH_PER_FLOOR   # ~1916.55g

# Level 3 (Floors 80-120)
L3_CASH_PER_FLOOR = 303.1582
L3_ENERGY_GOLD = 68.1039
L3_DAILY_CASH_GOLD = (DAILY_ENERGY / L3_ENERGY_GOLD) * L3_CASH_PER_FLOOR     # ~1201.88g

# Upgrade Costs & Downtime
COPPER_COST = 2300.0
STEEL_COST = 5600.0
GOLD_COST = 11250.0
DOWNTIME_DAYS = 2 # day t and day t+1 no mining, available morning of day t+2

def simulate_steel_upgrade_timing(horizon_days=28):
    """
    Simulate: Once in Zone 2 with Copper Pickaxe and 5,600g accumulated:
    Does upgrading to Steel Pickaxe 'as soon as possible' always beat delaying or not upgrading?
    Evaluate ending cash at Day T for different upgrade days.
    """
    print("=" * 80)
    print("INVESTIGATION: DOES UPGRADING TO STEEL PICKAXE ASAP ALWAYS BEAT NOT UPGRADING?")
    print("=" * 80)

    # Payback period calculation:
    direct_cost = STEEL_COST
    opportunity_cost_2days = 2 * L2_DAILY_CASH_COPPER
    total_investment = direct_cost + opportunity_cost_2days
    daily_gain = L2_DAILY_CASH_STEEL - L2_DAILY_CASH_COPPER
    payback_days = total_investment / daily_gain

    print(f"Direct Cash Cost: {direct_cost:.2f}g")
    print(f"Lost Income during 2 Days Downtime: {opportunity_cost_2days:.2f}g")
    print(f"Total True Economic Cost: {total_investment:.2f}g")
    print(f"Daily Productivity Gain (Steel vs Copper): {daily_gain:.2f}g / day")
    print(f"Break-even (Payback) Horizon Required: {payback_days:.2f} active days after upgrade!")
    print("-" * 80)

    # Compare ending cash for different remaining days left in the season:
    print("Impact of Remaining Days Left in Horizon on Ending Cash:")
    results = []
    for remaining_days in range(2, 20):
        # Policy 1: Do NOT upgrade to Steel, just keep farming with Copper Pickaxe
        cash_no_upgrade = remaining_days * L2_DAILY_CASH_COPPER

        # Policy 2: Upgrade to Steel on Day 1 (takes 2 days downtime, remaining-2 days with Steel)
        if remaining_days >= 2:
            days_with_steel = remaining_days - 2
            cash_with_upgrade = -direct_cost + (days_with_steel * L2_DAILY_CASH_STEEL)
        else:
            cash_with_upgrade = -direct_cost

        net_diff = cash_with_upgrade - cash_no_upgrade
        results.append({
            "remaining_days": remaining_days,
            "no_upgrade_net_gain_g": cash_no_upgrade,
            "upgrade_net_gain_g": cash_with_upgrade,
            "upgrade_advantage_g": net_diff,
            "better_choice": "Upgrade to Steel" if net_diff > 0 else "DO NOT UPGRADE"
        })
    df_res = pd.DataFrame(results)
    print(df_res.to_string(index=False))

def simulate_gold_upgrade_timing():
    print("\n" + "=" * 80)
    print("INVESTIGATION: DOES UPGRADING TO GOLD PICKAXE 'ASAP' MAKE SENSE?")
    print("=" * 80)
    direct_cost = GOLD_COST
    opportunity_cost = 2 * L2_DAILY_CASH_STEEL
    total_cost = direct_cost + opportunity_cost
    daily_gain = L3_DAILY_CASH_GOLD - L2_DAILY_CASH_STEEL

    print(f"Direct Gold Upgrade Cost: {direct_cost:.2f}g")
    print(f"Opportunity Cost (2 days downtime from Zone 2): {opportunity_cost:.2f}g")
    print(f"Total Cost to Upgrade: {total_cost:.2f}g")
    print(f"Daily Cash Change (Zone 3 Gold vs Zone 2 Steel): {daily_gain:.2f}g / day")
    if daily_gain < 0:
        print("RESULT: Upgrading to Gold yields NEGATIVE daily return! Payback is IMPOSSIBLE.")
        print("Upgrading to Gold 'ASAP' always DECREASES total cash in pure standalone mining!")

if __name__ == "__main__":
    simulate_steel_upgrade_timing()
    simulate_gold_upgrade_timing()
