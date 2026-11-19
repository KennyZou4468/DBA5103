"""Independent schedule audit: no access to the optimisation constraint matrix."""
import argparse
from collections import defaultdict
import json
from pathlib import Path


def audit_schedule(p, config, daily, activities, tolerance=1e-4):
    errors=[];checks=0
    def check(condition, message):
        nonlocal checks
        checks+=1
        if not condition: errors.append(message)
    lookup={(r["level"],r["mode"],r["fishing_location_id"],r["season"],r["time_block_id"]):r for r in p["rows"]}
    days=defaultdict(list)
    for a in activities:
        check(1<=int(a["Day"])<=config.horizon,"Activity outside horizon")
        days[int(a["Day"])].append(a)
    check([int(r["Day"]) for r in daily]==list(range(1,config.horizon+1)),"Daily rows must be unique, ordered and complete")
    if errors: return dict(passed=False,checks=checks,errors=errors)
    cash=p["cash"]*config.resource_share;count=0;owned=set()
    energy=p["energy"]*config.resource_share if config.energy_budget is None else config.energy_budget
    minutes=p["minutes"]*config.resource_share
    for d in daily:
        day=int(d["Day"]); season=("spring","summer","fall","winter")[(day-1)//28]
        level=max(k for k,n in p["levels"].items() if count>=n)
        check(int(d["Level_Start"])==level,f"Day {day}: next-day level")
        check(d["Season"]==season and int(d["Season_Day"])==(day-1)%28+1,f"Day {day}: calendar")
        rod_cost=0
        for rod,col,gate in (("fiberglass_rod","Buy_Fiberglass",2),("iridium_rod","Buy_Iridium",6)):
            purchase=float(d[col]);check(purchase in (0,1),f"Day {day}: binary purchase")
            if purchase:
                check(not config.no_rods and rod not in owned and level>=gate,f"Day {day}: rod purchase gate/once")
                owned.add(rod);rod_cost+=p["rods"][rod]
        totals=dict(Casts=0,Revenue_g=0,Time_Min=0,Energy=0,BaitCost_g=0,TackleCost_g=0)
        block_time=defaultdict(float);seen=set()
        for a in days[day]:
            n=float(a["Casts"]);check(n>=1 and n.is_integer(),f"Day {day}: integer positive casts")
            check(int(a["Level_Start"])==level and a["Season"]==season,f"Day {day}: activity state")
            key=(int(a["Level_Start"]),a["Equipment_Mode"],a["Location"],season,a["Time_Block"])
            check(key not in seen,f"Day {day}: duplicate activity");seen.add(key)
            check(key in lookup,f"Day {day}: unknown activity")
            if key not in lookup:continue
            r=lookup[key];mode=a["Equipment_Mode"]
            check(config.fixed_location is None or a["Location"]==config.fixed_location,f"Day {day}: fixed location")
            check(not config.no_rods or mode=="none",f"Day {day}: no-rods mode")
            check(mode=="none" or mode=="bait" and bool(owned) or mode not in ("none","bait") and "iridium_rod" in owned,f"Day {day}: compatible rod")
            totals["Casts"]+=n
            for col,source in (("Revenue_g","v"),("Time_Min","tau"),("Energy","e"),("BaitCost_g","beta"),("TackleCost_g","tackle_cost")):
                totals[col]+=n*r[source]
            block_time[a["Time_Block"]]+=n*r["tau"]
        spending=rod_cost+totals["BaitCost_g"]+totals["TackleCost_g"]
        check(spending<=cash+tolerance,f"Day {day}: opening cash cannot use today's revenue")
        check(totals["Time_Min"]<=minutes+tolerance,f"Day {day}: total time")
        check(totals["Energy"]<=energy+tolerance,f"Day {day}: energy")
        for b,cap in p["blocks"].items(): check(block_time[b]<=cap+tolerance,f"Day {day}: shared block {b}")
        expected=dict(totals,RodCost_g=rod_cost,Cost_g=spending,Cash_Start_g=cash,
                      Cash_End_g=cash+totals["Revenue_g"]-spending,Cum_Casts_End=count+totals["Casts"],
                      Time_Slack_Min=minutes-totals["Time_Min"],Energy_Slack=energy-totals["Energy"])
        for col,value in expected.items():
            check(abs(float(d[col])-value)<=tolerance,f"Day {day}: {col} reconstruction")
        cash=expected["Cash_End_g"];count+=totals["Casts"]
        check(cash>=-tolerance,f"Day {day}: nonnegative cash")
    return dict(passed=not errors,checks=checks,errors=errors,tolerance=tolerance,
                scope="CSV-based schedule feasibility and accounting; not a proof of game fidelity or optimality")


def main():
    from fishing_milp import Config,load_parameters,read_csv
    a=argparse.ArgumentParser(description=__doc__);a.add_argument("result_dir",type=Path);args=a.parse_args()
    summary=json.loads((args.result_dir/"summary.json").read_text())
    p=load_parameters()
    if p["fingerprints"]!=summary["input_sha256"]: raise SystemExit("Input files differ from recorded SHA256")
    report=audit_schedule(p,Config(**summary["config"]),read_csv(args.result_dir/"daily_schedule.csv"),read_csv(args.result_dir/"activity_schedule.csv"))
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not report["passed"]:raise SystemExit(1)


if __name__=="__main__":main()
