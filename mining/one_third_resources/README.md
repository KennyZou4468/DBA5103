# Mining: one-third resource scenario

This directory is the standardized, reproducible one-third-resource benchmark for the mining module.  It has the same resource allocation rule as the planting and fishing benchmark scenarios:

| Resource | Full shared baseline | Mining allocation |
| --- | ---: | ---: |
| Daily time | 900 game minutes | 300 game minutes |
| Daily energy | 270 | 90 |
| Initial cash | 500g | 166.67g |

The model maximizes mining-only Day 112 terminal cash.  Revenue earned by planting or fishing cannot be used here; those cross-module transfers belong only in the future integrated model.

## Contents

| Path | Purpose |
| --- | --- |
| `config.json` | Explicit scenario settings and allocation definition. |
| `run_optimization.py` | Reproducibly calls the active mining MILP with `resource_share=1/3`. |
| `results/daily_schedule.csv` | One row per day of the optimized mining decisions. |
| `results/summary.json` | Terminal cash, resource usage, upgrades, and milestones. |
| `results/daily_cash_balance.png` | End-of-day mining cash path. |

## Run

From the repository root, with a valid Gurobi license:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 mining/one_third_resources/run_optimization.py
```

The runner reads the active solver at `mining/Jiahe_Solution/XT0006_full_year_mining_milp.py` and writes only inside `mining/one_third_resources/results/`.

## Modelling convention and limitation

The scenario uses 112 days, integer ordinary rocks, a two-day pickaxe-service lockout, and the solver's default partial-final-floor policy. A cleared level automatically carries its required ordinary rocks and its full expected gem/container bundle; the single optional marginal entered level also carries the full expected gem/container bundle but may have zero ordinary rocks. Zone 2 containers consume collection time but no energy. The solver allows at most one marginal entered level across all zones per day, so it does not represent unlimited same-day re-entry loops. It is a fixed standalone allocation benchmark rather than a joint optimization.

The active mining README documents audit finding **C03**: the compact formulation may allow a marginal floor in a shallower zone while clearing floors in a deeper zone on the same day.  Treat these results as outputs of the current mining formulation; resolve C03 before using this schedule as an exact global route.
