"""Reproduce baseline, equipment ablation, fixed-location controls and LP bound."""
import argparse
import csv
import json
from pathlib import Path

from fishing_milp import MODULE,Config,build_model,export_solution,load_parameters,solve


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--time-limit",type=float,default=180)
    parser.add_argument("--gap",type=float,default=0)
    parser.add_argument("--out",type=Path,default=MODULE/"results")
    parser.add_argument("--reuse-baseline",action="store_true")
    args=parser.parse_args();p=load_parameters();reports=[]
    scenarios=[("baseline_112",Config()),("no_rods_112",Config(no_rods=True))]
    scenarios += [(f"fixed_{loc}_112",Config(fixed_location=loc)) for loc in sorted(p["locations"])]
    scenarios += [("one_third_112",Config(resource_share=1/3))]
    for name,c in scenarios:
        out=args.out/name;out.mkdir(parents=True,exist_ok=True)
        if name=="baseline_112" and args.reuse_baseline:
            report=json.loads((out/"summary.json").read_text())
            if report["input_sha256"]!=p["fingerprints"] or report["config"]!=dict(c.__dict__):
                raise ValueError("Stored baseline inputs/config differ")
        else:
            m,ctx=build_model(p,c);ctx["model"]=m
            sol,result=solve(m,ctx,p,time_limit=args.time_limit,gap=args.gap,log_path=out/"solver.log")
            report=export_solution(p,ctx,sol,result,out)
        reports.append(dict(Scenario=name,Cash_End_g=report["cash_end_g"],Status=report["status"],
                            Best_Bound=report["best_bound"],MIP_Gap=report["mip_gap"],
                            Solve_Seconds=report["solve_seconds"],Casts=report["total_casts"],
                            First_100000_Day=report["first_100000_day"],Audit_Passed=report["audit"]["passed"]))
        print(name,report["status"],report["cash_end_g"],flush=True)
    m,ctx=build_model(p);sol,lp=solve(m,ctx,p,time_limit=args.time_limit,relax=True,log_path=args.out/"lp_solver.log")
    (args.out/"lp_bound.json").write_text(json.dumps(lp,indent=2,allow_nan=False)+"\n")
    with (args.out/"comparison_summary.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(reports[0]));w.writeheader();w.writerows(reports)


if __name__=="__main__":main()
