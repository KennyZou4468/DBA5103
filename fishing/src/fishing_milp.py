"""Standalone fishing MILP. CSV coefficients are the authoritative inputs.

Run from the repository root: python fishing/src/fishing_milp.py --help
Both backends solve the same sparse linear model; HiGHS needs no licence.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, asdict
import hashlib
import json
import math
from pathlib import Path
import platform
import time

import numpy as np
from scipy.sparse import coo_matrix

MODULE = Path(__file__).resolve().parents[1]
ROOT = MODULE.parent
SEASONS = ("spring", "summer", "fall", "winter")
KEY = ("fishing_level", "equipment_mode_id", "fishing_location_id", "season", "weather", "time_block_id")
TOL = 1e-6


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@dataclass(frozen=True)
class Config:
    horizon: int = 112
    resource_share: float = 1.0
    energy_budget: float | None = None
    # Preserve the four full clock windows; share scales TOTAL time, not each bin.
    fixed_location: str | None = None
    no_rods: bool = False
    prune: bool = True


def load_parameters(root=ROOT):
    root = Path(root)
    data = root / "fishing" / "data"
    files = sorted(data.glob("*.csv")) + [root / "shared/data/global_parameters.csv"]
    fingerprints = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    global_map = {r["parameter_id"]: r["value"] for r in read_csv(files[-1])}
    blocks = {r["time_block_id"]: float(r["duration_game_minutes"]) for r in read_csv(data / "fishing_time_blocks.csv")}
    levels = {int(r["fishing_level"]): int(r["cumulative_resolved_casts_required"]) for r in read_csv(data / "fishing_experience_levels.csv")}
    modes = {r["equipment_mode_id"]: r for r in read_csv(data / "fishing_equipment_modes.csv")}
    rods = {r["rod_id"]: float(r["gold_cost_g"]) for r in read_csv(data / "fishing_rod_catalog.csv")}
    equipment = {r["equipment_id"]: r for r in read_csv(data / "fishing_equipment_catalog.csv")}
    locations = {r["fishing_location_id"] for r in read_csv(data / "fishing_locations.csv")}
    rows, seen = [], set()
    for source in read_csv(data / "fishing_solver_parameters.csv"):
        key = tuple(source[k] for k in KEY)
        if key in seen:
            raise ValueError(f"Duplicate activity key: {key}")
        seen.add(key)
        k, mode = int(source["fishing_level"]), source["equipment_mode_id"]
        m = modes[mode]
        v = float(source["expected_g_per_cast"])
        e = float(source["expected_energy_per_cast"])
        tau = float(source["expected_waiting_time_game_minutes_per_cast"])
        beta = float(source["bait_gold_cost_per_cast"])
        delta = float(source["expected_tackle_items_consumed_per_cast"])
        fish = float(source["expected_fish_nibbles_per_cast"])
        tackle = m["tackle_id"]
        if source["ready_for_solver"] != "yes" or source["weather"] != "sunny":
            raise ValueError(f"Unsupported/not-ready input: {key}")
        if (k not in levels or source["season"] not in SEASONS or source["time_block_id"] not in blocks
                or source["fishing_location_id"] not in locations or k < int(m["minimum_fishing_level"])):
            raise ValueError(f"Invalid domain/gate: {key}")
        if not all(math.isfinite(x) for x in (v, e, tau, beta, delta, fish)):
            raise ValueError(f"Nonfinite coefficient: {key}")
        if (min(v, beta, delta) < 0 or e <= 0 or tau <= 0 or not 0 <= fish <= 1
                or abs(e - (8 - .1*k)) > TOL or beta != float(m["bait_gold_cost_per_cast"])
                or abs(float(source["hook_success_rate"]) - 1) > TOL):
            raise ValueError(f"Coefficient consistency: {key}")
        expected_delta = fish / 20 if tackle != "none" else 0
        if abs(delta - expected_delta) > TOL:
            raise ValueError(f"Tackle wear: {key}")
        tackle_cost = 0 if tackle == "none" else delta * float(equipment[tackle]["shop_purchase_price_g"])
        rows.append(dict(source, level=k, mode=mode, v=v, e=e, tau=tau,
                         beta=beta, delta=delta, tackle_cost=tackle_cost, cost=beta+tackle_cost))
    expected = {(str(k), m, loc, s, "sunny", b) for k in levels for m in modes
                if k >= int(modes[m]["minimum_fishing_level"])
                for loc in locations for s in SEASONS for b in blocks}
    if seen != expected or len(rows) != 2880 or abs(sum(blocks.values()) - 900) > TOL:
        raise ValueError("Baseline activity coverage / block capacities changed; review model assumptions")
    return dict(rows=rows, blocks=blocks, levels=levels, rods=rods, locations=locations,
                cash=float(global_map["initial_gold_g"]), energy=float(global_map["daily_energy_limit"]),
                minutes=float(global_map["daily_time_limit_game_minutes"]), fingerprints=fingerprints)


def level_at(count, levels):
    return max(k for k, threshold in levels.items() if count >= threshold)


def capability(mode):
    # Sets of ownership states under which a mode is available (F=1, I=2).
    return {0, 1, 2, 3} if mode == "none" else ({1, 2, 3} if mode == "bait" else {2, 3})


def undominated(rows):
    """Exact replacement within one season/block/level; preserves cast count.

    A replacement must improve BOTH gross revenue and opening-cash cost, with
    no greater resources and no additional rod requirement. Net profit alone
    is insufficient because G5 limits spending before today's revenue.
    """
    groups = {}
    for r in rows:
        groups.setdefault((r["season"], r["time_block_id"], r["level"]), []).append(r)
    keep = []
    for group in groups.values():
        for j, r in enumerate(group):
            dominated = False
            for q, a in enumerate(group):
                if q == j or not capability(r["mode"]) <= capability(a["mode"]):
                    continue
                if a["v"] >= r["v"] and a["cost"] <= r["cost"] and a["tau"] <= r["tau"] and a["e"] <= r["e"]:
                    strict = (a["v"] > r["v"] or a["cost"] < r["cost"] or a["tau"] < r["tau"] or a["e"] < r["e"])
                    if strict or q < j:
                        dominated = True
                        break
            if not dominated:
                keep.append(r)
    return keep


class LinearModel:
    """Backend-neutral sparse coefficient store; all rows retain audit names."""
    def __init__(self):
        self.names, self.lb, self.ub, self.integer, self.obj = [], [], [], [], []
        self.rows, self.row_lb, self.row_ub, self.row_names = [], [], [], []

    def var(self, name, lb=0, ub=math.inf, integer=False, obj=0):
        i = len(self.names)
        self.names.append(name); self.lb.append(lb); self.ub.append(ub)
        self.integer.append(integer); self.obj.append(obj)
        return i

    def row(self, name, terms, lb=-math.inf, ub=math.inf):
        self.row_names.append(name); self.rows.append({i: v for i, v in terms.items() if v})
        self.row_lb.append(lb); self.row_ub.append(ub)

    def matrix(self):
        rr, cc, vv = [], [], []
        for j, row in enumerate(self.rows):
            for i, v in row.items():
                rr.append(j); cc.append(i); vv.append(v)
        return coo_matrix((vv, (rr, cc)), shape=(len(self.rows), len(self.names))).tocsc()


def add_terms(*parts):
    result = {}
    for part in parts:
        for i, v in part.items():
            result[i] = result.get(i, 0) + v
    return result


def build_model(p, config=Config()):
    c = config
    if type(c.horizon) is not int or not 1 <= c.horizon <= 112:
        raise ValueError("horizon must be an integer in 1..112")
    if not math.isfinite(c.resource_share) or not 0 < c.resource_share <= 1:
        raise ValueError("resource_share must be in (0,1]")
    energy = p["energy"] * c.resource_share if c.energy_budget is None else c.energy_budget
    if not math.isfinite(energy) or not 0 < energy <= p["energy"]:
        raise ValueError("energy_budget must be in (0,270]")
    if c.fixed_location is not None and c.fixed_location not in p["locations"]:
        raise ValueError("Unknown fixed location")
    budget = dict(energy=energy, minutes=p["minutes"]*c.resource_share, cash=p["cash"]*c.resource_share)
    U = math.floor(energy/min(r["e"] for r in p["rows"]))
    nmax = c.horizon * U
    rows = [r for r in p["rows"] if (c.fixed_location is None or r["fishing_location_id"] == c.fixed_location)
            and (not c.no_rods or r["mode"] == "none")]
    if c.prune:
        rows = undominated(rows)
    m = LinearModel()
    N = {t: m.var(f"fish_N[{t}]", ub=t*U, integer=True) for t in range(c.horizon+1)}
    B = {t: m.var(f"fish_B[{t}]", lb=budget["cash"] if t == 0 else 0,
                  ub=budget["cash"] if t == 0 else math.inf, obj=1 if t == c.horizon else 0)
         for t in range(c.horizon+1)}
    z, buy, own, acts, by_day = {}, {}, {}, [], {}
    for t in range(1, c.horizon+1):
        for k in p["levels"]:
            z[t,k] = m.var(f"fish_z[{t},{k}]", ub=int(p["levels"][k] <= (t-1)*U), integer=True)
        for rod, gate in (("fiberglass_rod", 2), ("iridium_rod", 6)):
            buy[t,rod] = m.var(f"fish_buy[{t},{rod}]", ub=0 if c.no_rods else 1, integer=True)
            own[t,rod] = m.var(f"fish_own[{t},{rod}]", ub=0 if c.no_rods else 1, integer=True)
            m.row(f"C15_16_rod_gate[{t},{rod}]", add_terms({buy[t,rod]:1}, {z[t,k]:-1 for k in p["levels"] if k>=gate}), ub=0)
            prev = {} if t == 1 else {own[t-1,rod]:-1}
            m.row(f"C18_rod_balance[{t},{rod}]", add_terms({own[t,rod]:1, buy[t,rod]:-1}, prev), lb=0, ub=0)
        m.row(f"C7_one_level[{t}]", {z[t,k]:1 for k in p["levels"]}, lb=1, ub=1)
        # Exact projection of C8-C12: z=k iff a[k] <= N[t-1] <= a[k+1]-1.
        m.row(f"C8_12_level_lb[{t}]", add_terms({N[t-1]:1}, {z[t,k]:-p["levels"][k] for k in p["levels"]}), lb=0)
        m.row(f"C8_12_level_ub[{t}]", add_terms({N[t-1]:1}, {z[t,k]:-(min(nmax,p["levels"].get(k+1,nmax+1)-1)) for k in p["levels"]}), ub=0)
        daily = []
        for r in rows:
            if r["season"] != SEASONS[(t-1)//28] or p["levels"][r["level"]] > (t-1)*U:
                continue
            ub = min(U, math.floor(p["blocks"][r["time_block_id"]]/r["tau"]))
            i = m.var(f"fish_x[{t},{r['level']},{r['mode']},{r['fishing_location_id']},{r['time_block_id']}]", ub=ub, integer=True)
            a = dict(r, day=t, index=i)
            acts.append(a); daily.append(a)
        by_day[t] = daily
        m.row(f"C6_cast_balance[{t}]", add_terms({N[t]:1,N[t-1]:-1}, {a["index"]:-1 for a in daily}), lb=0,ub=0)
        for k in p["levels"]:
            # Strengthened disaggregated upper bound; total follows C13 too.
            m.row(f"C13_level_use[{t},{k}]", add_terms({a["index"]:1 for a in daily if a["level"]==k}, {z[t,k]:-U}), ub=0)
        for block, cap in p["blocks"].items():
            m.row(f"C3_block_time[{t},{block}]", {a["index"]:a["tau"] for a in daily if a["time_block_id"]==block}, ub=cap)
        m.row(f"G1_time[{t}]", {a["index"]:a["tau"] for a in daily}, ub=budget["minutes"])
        m.row(f"G2_energy[{t}]", {a["index"]:a["e"] for a in daily}, ub=energy)
        m.row(f"C20_bait_rod[{t}]", add_terms({a["index"]:1 for a in daily if a["mode"]=="bait"}, {own[t,"fiberglass_rod"]:-U,own[t,"iridium_rod"]:-U}),ub=0)
        m.row(f"C21_tackle_rod[{t}]", add_terms({a["index"]:1 for a in daily if a["mode"] not in ("none","bait")}, {own[t,"iridium_rod"]:-U}),ub=0)
        costs = add_terms({a["index"]:a["cost"] for a in daily}, {buy[t,r]:p["rods"][r] for r in ("fiberglass_rod","iridium_rod")})
        m.row(f"G5_opening_cash[{t}]", add_terms(costs,{B[t-1]:-1}),ub=0)
        m.row(f"G4_cash_balance[{t}]", add_terms({B[t]:1,B[t-1]:-1}, costs, {a["index"]:-a["v"] for a in daily}),lb=0,ub=0)
    for r in ("fiberglass_rod","iridium_rod"):
        m.row(f"C19_once[{r}]", {buy[t,r]:1 for t in range(1,c.horizon+1)},ub=1)
    return m, dict(config=c, budget=budget, U=U, N=N, B=B, z=z, buy=buy, own=own, acts=acts, by_day=by_day)


def greedy_start(p, m, ctx, purchase_policy="none"):
    """Feasible sequential policy, not an optimality claim. Never borrows today's revenue."""
    c, budget = ctx["config"], ctx["budget"]
    sol = np.zeros(len(m.names)); sol[ctx["B"][0]]=budget["cash"]
    cash, count, owned = budget["cash"], 0, set()
    for t in range(1,c.horizon+1):
        k = level_at(count,p["levels"]); sol[ctx["z"][t,k]]=1
        spending = 0
        if not c.no_rods:
            for rod,gate,allowed in (("fiberglass_rod",2,purchase_policy in ("F","both")), ("iridium_rod",6,purchase_policy in ("I","both"))):
                # Keep at least 200g for optional consumables.
                if allowed and rod not in owned and k>=gate and cash-spending>=p["rods"][rod]+200:
                    owned.add(rod); spending+=p["rods"][rod]; sol[ctx["buy"][t,rod]]=1
        for rod in owned: sol[ctx["own"][t,rod]]=1
        remaining_time, remaining_energy = budget["minutes"],budget["energy"]
        blocks = dict(p["blocks"]); revenue=0; casts=0
        options = [a for a in ctx["by_day"][t] if a["level"]==k and
                   (a["mode"]=="none" or a["mode"]=="bait" and owned or a["mode"] not in ("none","bait") and "iridium_rod" in owned)]
        for a in sorted(options,key=lambda a:a["v"]-a["cost"],reverse=True):
            b=a["time_block_id"]
            n=min(math.floor((remaining_energy+1e-8)/a["e"]), math.floor((remaining_time+1e-8)/a["tau"]),
                  math.floor((blocks[b]+1e-8)/a["tau"]), ctx["U"]-casts)
            if a["cost"]>0: n=min(n,math.floor((cash-spending+1e-8)/a["cost"]))
            n=max(0,n); sol[a["index"]]=n
            remaining_energy-=n*a["e"]; remaining_time-=n*a["tau"]; blocks[b]-=n*a["tau"]
            revenue+=n*a["v"]; spending+=n*a["cost"]; casts+=n
        count+=casts; cash+=revenue-spending
        sol[ctx["N"][t]]=count;sol[ctx["B"][t]]=cash
    return sol


def solve(m, ctx, p, backend="highs", time_limit=120, gap=1e-6, log_path=None, verbose=False, relax=False):
    A=m.matrix(); started=time.perf_counter()
    starts=[] if relax else [greedy_start(p,m,ctx,policy) for policy in ("none","F","I","both")]
    warm=max(starts,key=lambda s:s[ctx["B"][ctx["config"].horizon]]) if starts else None
    if backend=="highs":
        import highspy as hs
        h=hs.Highs(); h.setOptionValue("output_flag",verbose or log_path is not None)
        h.setOptionValue("log_to_console",verbose); h.setOptionValue("threads",1)
        h.setOptionValue("random_seed",0); h.setOptionValue("time_limit",float(time_limit))
        h.setOptionValue("mip_rel_gap",float(gap))
        if log_path: h.setOptionValue("log_file",str(log_path))
        lp=hs.HighsLp();lp.num_col_=len(m.names);lp.num_row_=len(m.rows)
        lp.col_cost_=np.asarray(m.obj);lp.col_lower_=np.asarray(m.lb);lp.col_upper_=np.asarray(m.ub)
        lp.row_lower_=np.asarray(m.row_lb);lp.row_upper_=np.asarray(m.row_ub)
        lp.col_names_=m.names;lp.row_names_=m.row_names;lp.sense_=hs.ObjSense.kMaximize
        lp.a_matrix_.format_=hs.MatrixFormat.kColwise
        lp.a_matrix_.start_=A.indptr;lp.a_matrix_.index_=A.indices;lp.a_matrix_.value_=A.data
        lp.integrality_=[hs.HighsVarType.kInteger if x and not relax else hs.HighsVarType.kContinuous for x in m.integer]
        h.passModel(lp)
        if warm is not None: h.setSolution(len(warm),np.arange(len(warm),dtype=np.int32),warm)
        h.run();status=h.modelStatusToString(h.getModelStatus());info=h.getInfo();sol=h.getSolution()
        incumbent=np.asarray(sol.col_value) if sol.value_valid else None
        objective=float(info.objective_function_value) if incumbent is not None else None
        bound=objective if relax and status=="Optimal" else (float(info.mip_dual_bound) if not relax else None)
        result=dict(backend="HiGHS",version=h.version(),status=status,objective=objective,best_bound=bound,
                    mip_gap=None if relax or incumbent is None else float(info.mip_gap),nodes=int(info.mip_node_count))
    elif backend=="gurobi":
        import gurobipy as gp
        g=gp.Model("Fishing_MILP");g.Params.OutputFlag=int(verbose or log_path is not None)
        g.Params.LogToConsole=int(verbose);g.Params.Threads=1;g.Params.Seed=0
        g.Params.TimeLimit=time_limit;g.Params.MIPGap=gap
        if log_path:g.Params.LogFile=str(log_path)
        x=g.addMVar(len(m.names),lb=m.lb,ub=m.ub,vtype=[gp.GRB.INTEGER if v and not relax else gp.GRB.CONTINUOUS for v in m.integer])
        g.setObjective(np.asarray(m.obj)@x,gp.GRB.MAXIMIZE)
        lo=np.asarray(m.row_lb);hi=np.asarray(m.row_ub);eq=lo==hi
        for mask,sense,rhs in ((eq,"=",hi),(~eq & np.isfinite(lo),">",lo),(~eq & np.isfinite(hi),"<",hi)):
            if mask.any():g.addMConstr(A[mask],x,sense,rhs[mask])
        if warm is not None:x.Start=warm
        g.optimize();incumbent=x.X if g.SolCount else None
        status={2:"Optimal",3:"Infeasible",9:"Time limit",11:"Interrupted"}.get(g.Status,str(g.Status))
        result=dict(backend="Gurobi",version=".".join(map(str,gp.gurobi.version())),status=status,
                    objective=float(g.ObjVal) if g.SolCount else None,best_bound=float(g.ObjBound),
                    mip_gap=float(g.MIPGap) if g.SolCount and not relax else None,nodes=int(g.NodeCount))
    else: raise ValueError("Unknown backend")
    result.update(solve_seconds=time.perf_counter()-started,variables=len(m.names),constraints=len(m.rows),relaxation=relax)
    return incumbent,result


def export_solution(p,ctx,sol,result,out):
    """Round integer decisions only; rebuild cash independently from CSV values."""
    from fishing_validate import audit_schedule
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if sol is None: raise RuntimeError(f"No feasible incumbent: {result}")
    if max(abs(sol[i]-round(sol[i])) for i,v in enumerate(ctx["model"].integer) if v)>1e-4:
        raise RuntimeError("Returned incumbent violates integrality")
    activities=[]; daily=[]; cash=ctx["budget"]["cash"];count=0
    for t in range(1,ctx["config"].horizon+1):
        acts=[a for a in ctx["by_day"][t] if round(sol[a["index"]])>0]
        for a in acts:
            activities.append(dict(Day=t,Season=SEASONS[(t-1)//28],Level_Start=a["level"],
                 Time_Block=a["time_block_id"],Location=a["fishing_location_id"],Equipment_Mode=a["mode"],Casts=int(round(sol[a["index"]]))))
        casts=sum(round(sol[a["index"]]) for a in acts)
        total=lambda key:sum(round(sol[a["index"]])*a[key] for a in acts)
        buys={r:int(round(sol[ctx["buy"][t,r]])) for r in ("fiberglass_rod","iridium_rod")}
        rod_cost=sum(p["rods"][r]*v for r,v in buys.items());spending=total("cost")+rod_cost
        revenue=total("v");opening=cash;cash+=revenue-spending
        row=dict(Day=t,Season=SEASONS[(t-1)//28],Season_Day=(t-1)%28+1,Level_Start=level_at(count,p["levels"]),
                 Casts=casts,Cum_Casts_End=count+casts,Buy_Fiberglass=buys["fiberglass_rod"],Buy_Iridium=buys["iridium_rod"],
                 Cash_Start_g=opening,Revenue_g=revenue,BaitCost_g=total("beta"),TackleCost_g=total("tackle_cost"),RodCost_g=rod_cost,
                 Cost_g=spending,Cash_End_g=cash,Time_Min=total("tau"),Energy=total("e"),
                 Time_Slack_Min=ctx["budget"]["minutes"]-total("tau"),Energy_Slack=ctx["budget"]["energy"]-total("e"))
        daily.append(row);count+=casts
    audit=audit_schedule(p,ctx["config"],daily,activities)
    if not audit["passed"]: raise RuntimeError(f"Independent schedule audit failed: {audit['errors']}")
    if abs(cash-result["objective"])>1e-3: raise RuntimeError("Exported cash differs from solver objective")
    for name,rows,columns in (("daily_schedule.csv",daily,None),("activity_schedule.csv",activities,["Day","Season","Level_Start","Time_Block","Location","Equipment_Mode","Casts"])):
        with (out/name).open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else columns);writer.writeheader();writer.writerows(rows)
    report=dict(result,config=asdict(ctx["config"]),budgets=ctx["budget"],cash_end_g=cash,
                gross_revenue_g=sum(r["Revenue_g"] for r in daily),total_cost_g=sum(r["Cost_g"] for r in daily),
                total_casts=count,first_100000_day=next((r["Day"] for r in daily if r["Cash_End_g"]>=100000),None),
                rod_purchase_days={r:next((t for t in range(1,ctx["config"].horizon+1) if round(sol[ctx["buy"][t,r]])),None) for r in ("fiberglass_rod","iridium_rod")},
                audit=audit,input_sha256=p["fingerprints"],python=platform.python_version())
    (out/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    (out/"validation.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--horizon",type=int,default=112);a.add_argument("--backend",choices=("highs","gurobi"),default="highs")
    a.add_argument("--time-limit",type=float,default=120);a.add_argument("--gap",type=float,default=1e-6)
    a.add_argument("--resource-share",type=float,default=1);a.add_argument("--energy-budget",type=float)
    a.add_argument("--fixed-location");a.add_argument("--no-rods",action="store_true")
    a.add_argument("--no-prune",action="store_true");a.add_argument("--relax",action="store_true")
    a.add_argument("--out",type=Path,default=MODULE/"results/baseline_112");a.add_argument("--verbose",action="store_true")
    args=a.parse_args()
    if not math.isfinite(args.time_limit) or args.time_limit<=0 or not math.isfinite(args.gap) or args.gap<0:
        a.error("time-limit must be positive; gap must be nonnegative")
    p=load_parameters();c=Config(args.horizon,args.resource_share,args.energy_budget,args.fixed_location,args.no_rods,not args.no_prune)
    m,ctx=build_model(p,c);ctx["model"]=m;args.out.mkdir(parents=True,exist_ok=True)
    sol,result=solve(m,ctx,p,args.backend,args.time_limit,args.gap,args.out/"solver.log",args.verbose,args.relax)
    if args.relax:
        result.update(config=asdict(c),input_sha256=p["fingerprints"])
        (args.out/"lp_bound.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
        print(json.dumps(result,indent=2))
    else:
        report=export_solution(p,ctx,sol,result,args.out)
        print(json.dumps({k:report[k] for k in ("status","cash_end_g","best_bound","mip_gap","solve_seconds","rod_purchase_days","audit")},ensure_ascii=False,indent=2))


if __name__=="__main__": main()
