# Jiahe's mining solution

Standalone mining optimization for DBA5103 Group Project 1. Start with these two files:

| File | Purpose |
| --- | --- |
| [XT0006_full_year_mining_milp.py](XT0006_full_year_mining_milp.py) | Main code: builds and solves the Year 1 mining MILP and returns terminal cash, a daily schedule, and the Gurobi model. |
| [XG0004_mining_comparison.pdf](XG0004_mining_comparison.pdf) | Main reading: eight-page comparison of resource allocations, upgrade strategies, constraints, parameters, and decision variables. |

Supporting scripts, exported results, mathematical formulation, and editable report sources are in [ZG0001_archive](ZG0001_archive/README.md). Keep this folder: the main solver imports its parameter loader and Spring reference solver from the archive.

## Run the code

Requires Python with the existing `pandas`, `numpy`, and `gurobipy` packages and a valid Gurobi license. From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 mining/Jiahe_Solution/XT0006_full_year_mining_milp.py
```

This runs the solver's built-in comparisons and sensitivities. For a single case, import `build_and_solve_full_year_mining_milp` and pass `horizon_days`, `integer_rocks`, `resource_share`, and optionally `daily_energy_budget` or `upgrade_days`. Its default uses continuous ordinary rocks; the report comparisons use `integer_rocks=True`.

The loader reads the existing CSVs in `mining/data/` and `shared/data/`. See the archive README to reproduce the five analysis CSVs.

## Scope and known limitation

This model optimizes mining alone with deterministic expected yields. Farming, fishing, food, and transfers between activities are excluded.

**Current compact resource convention:** `XT0006_full_year_mining_milp.py` represents each entered level by a full expected resource bundle. A cleared level contributes its required ordinary rocks; a single optional marginal level may contribute zero or more ordinary rocks. Both cleared and marginal entered levels automatically collect the zone's expected gem nodes and, in Zone 2, its expected containers. Gem swings consume time and energy; containers consume 1.4 game minutes each and zero energy. The implementation permits at most four cleared levels per zone plus one marginal entered level across all zones on a day. It does not model unlimited same-day re-entry loops.

**Open audit finding C03:** the compact model can allow a marginal floor in a shallower zone while also clearing floors in a deeper zone on the same day. The audit found a feasible counterexample. Treat the report results as results under the current model; repair ordering constraints and rerun before global integration or claiming full equivalence to the intended mine route. Details and the witness are in [the constraint audit](ZG0001_archive/XG0002_constraint_improvement.md).
