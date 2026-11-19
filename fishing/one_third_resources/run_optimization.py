"""Run the approved 1/3-resource fishing scenario using the shared fishing MILP.

From repo root: python fishing/one_third_resources/run_optimization.py
Audit saved results: add --validate-only. Never writes the full-resource results.
"""
from __future__ import annotations

import argparse
import csv
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
FISHING = HERE.parent
sys.path.insert(0, str(FISHING / "src"))
from fishing_milp import Config, build_model, export_solution, load_parameters, read_csv, solve
from fishing_validate import audit_schedule


def read_config(path=HERE / "config.json"):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    r = cfg["resource_share"]
    if type(r["numerator"]) is not int or type(r["denominator"]) is not int:
        raise ValueError("Resource share must be an integer numerator/denominator")
    if Fraction(r["numerator"], r["denominator"]) != Fraction(1, 3):
        raise ValueError("This approved scenario requires exactly 1/3 of resources")
    if type(cfg["horizon_days"]) is not int or cfg["horizon_days"] != 112:
        raise ValueError("The approved horizon is 112 days")
    if cfg["daily_time_allocation"] != "total_cap_with_full_clock_windows":
        raise ValueError("Keep full clock windows and limit TOTAL daily time to 300")
    if cfg["scenario"] != "fishing_one_third_resources":
        raise ValueError("Unknown scenario id")
    solver = cfg["solver"]
    if solver["backend"] not in ("highs", "gurobi"):
        raise ValueError("Unsupported solver backend")
    if (not math.isfinite(solver["time_limit_seconds"]) or solver["time_limit_seconds"] <= 0
            or not math.isfinite(solver["relative_gap"]) or solver["relative_gap"] < 0):
        raise ValueError("Invalid solver limit/gap")
    return cfg


def prepare(cfg, parameters=None):
    p = load_parameters() if parameters is None else parameters
    expected = cfg["baseline_expected"]
    for name, field in (("cash", "initial_cash_g"), ("minutes", "daily_time_game_minutes"),
                        ("energy", "daily_energy")):
        if p[name] != expected[field]:
            raise ValueError(f"Baseline drift in {name}: {p[name]} != {expected[field]}")
    if (p["cash"], p["minutes"], p["energy"]) != (500, 900, 270):
        raise ValueError("Approved baseline is 500g / 900 minutes / 270 energy")
    config = Config(horizon=112, resource_share=float(Fraction(1, 3)))
    model, ctx = build_model(p, config)
    ctx["model"] = model
    if abs(ctx["budget"]["cash"] - 500 / 3) > 1e-10 or ctx["budget"]["minutes"] != 300 or ctx["budget"]["energy"] != 90:
        raise ValueError("Effective resource budgets differ from approved scenario")
    return p, model, ctx


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_fingerprints():
    return {str(p.relative_to(FISHING)): sha256(p) for p in (
        FISHING / "src/fishing_milp.py", FISHING / "src/fishing_validate.py", Path(__file__))}


def validate_results(out, cfg_path=HERE / "config.json"):
    out = Path(out)
    cfg = read_config(cfg_path)
    p = load_parameters()
    saved = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    if saved["input_sha256"] != p["fingerprints"]:
        raise ValueError("Current input files differ from saved input SHA256")
    if saved["scenario_config_sha256"] != sha256(cfg_path):
        raise ValueError("Scenario configuration differs from the saved run")
    if saved["code_sha256"] != code_fingerprints():
        raise ValueError("Code differs from the saved run; rerun before claiming reproduction")
    config = Config(horizon=112, resource_share=float(Fraction(1, 3)))
    if saved["config"] != dict(config.__dict__):
        raise ValueError("Saved run is not the approved 1/3-resource scenario")
    budgets = {"cash": 500 / 3, "minutes": 300, "energy": 90}
    if any(abs(saved["budgets"][k] - v) > 1e-10 for k, v in budgets.items()):
        raise ValueError("Saved budgets mismatch")
    days = read_csv(out / "daily_schedule.csv")
    activities = read_csv(out / "activity_schedule.csv")
    audit = audit_schedule(p, config, days, activities)
    if not audit["passed"]:
        raise ValueError(f"Independent schedule audit failed: {audit['errors']}")
    if abs(float(days[-1]["Cash_End_g"]) - saved["cash_end_g"]) > 1e-4:
        raise ValueError("Summary does not match final daily cash")
    if abs(500 / 3 + sum(float(d["Revenue_g"]) - float(d["Cost_g"]) for d in days) - saved["cash_end_g"]) > 1e-4:
        raise ValueError("Yearly cash reconciliation failed")
    interface = read_csv(out / "integration_daily.csv")
    if len(interface) != 112:
        raise ValueError("Integration output must contain exactly 112 days")
    mapping = {"Revenue_g": "Revenue_g", "Cost_g": "Cost_g", "Time_Min": "Time_Min",
               "Energy": "Energy", "Cash_Start_g": "Cash_Start_g", "Cash_End_g": "Cash_End_g"}
    for i, (row, day) in enumerate(zip(interface, days), 1):
        if int(row["Day"]) != i or row["Module"] != "fishing":
            raise ValueError("Integration day/module mismatch")
        for col, source in mapping.items():
            if abs(float(row[col]) - float(day[source])) > 1e-6:
                raise ValueError(f"Integration mismatch in day {i}: {col}")
        if abs(float(row["Time_Budget_Min"]) - 300) > 1e-10 or abs(float(row["Energy_Budget"]) - 90) > 1e-10:
            raise ValueError("Integration resource budget mismatch")
    return dict(audit, input_and_code_hashes_match=True, scenario_config_matches=True,
                integration_rows_verified=112, yearly_cash_reconciles=True)


def write_integration(days, out):
    fields = ["Day", "Module", "Revenue_g", "Cost_g", "Time_Min", "Energy", "Cash_Start_g", "Cash_End_g",
              "Time_Budget_Min", "Energy_Budget"]
    with (Path(out) / "integration_daily.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for d in days:
            row = {k: d[k] for k in fields if k in d}
            row.update(Module="fishing", Time_Budget_Min=300, Energy_Budget=90)
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=HERE / "config.json")
    parser.add_argument("--out", type=Path, default=HERE / "results")
    parser.add_argument("--backend", choices=("highs", "gurobi"))
    parser.add_argument("--time-limit", type=float)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    cfg = read_config(args.config)
    if args.validate_only:
        print(json.dumps(validate_results(args.out, args.config), ensure_ascii=False, indent=2))
        return
    p, model, ctx = prepare(cfg)
    backend = args.backend or cfg["solver"]["backend"]
    limit = cfg["solver"]["time_limit_seconds"] if args.time_limit is None else args.time_limit
    if not math.isfinite(limit) or limit <= 0:
        parser.error("--time-limit must be positive and finite")
    args.out.mkdir(parents=True, exist_ok=True)
    # Keep each run's solver log separate from previous invocations.
    log = args.out / "solver.log"
    if log.exists():
        log.write_text("", encoding="utf-8")
    sol, result = solve(model, ctx, p, backend=backend, time_limit=limit,
                        gap=cfg["solver"]["relative_gap"], log_path=log)
    report = export_solution(p, ctx, sol, result, args.out)
    write_integration(read_csv(args.out / "daily_schedule.csv"), args.out)
    report.update(scenario=cfg["scenario"], resource_share_exact="1/3", initial_cash_exact_g="500/3",
                  scenario_config_sha256=sha256(args.config), scenario_configuration=cfg,
                  code_sha256=code_fingerprints(), effective_solver=dict(backend=backend, time_limit_seconds=limit,
                      relative_gap=cfg["solver"]["relative_gap"], threads=1, random_seed=0),
                  accounting_note="Ending cash includes initial 500/3g; do not add initial capital again when summing modules.")
    path = args.out / "summary.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    audit = validate_results(args.out, args.config)
    (args.out / "validation.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "cash_end_g", "best_bound", "mip_gap", "solve_seconds",
                    "total_casts", "rod_purchase_days", "first_100000_day")}, ensure_ascii=False, indent=2))
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
