# Supporting mining files

The [main solver](../XT0006_full_year_mining_milp.py) and [reading PDF](../XG0004_mining_comparison.pdf) are one level above. This archive preserves supporting work and runtime dependencies.

| Files | Purpose |
| --- | --- |
| [XT0005_mining_milp_solver.py](XT0005_mining_milp_solver.py) | Required by the main solver: CSV parameter loader and explicit Spring reference model. |
| [XT0007_resource_share_analysis.py](XT0007_resource_share_analysis.py) | Reproduces resource-share comparisons, earliest-target search, upgrade tests, and schedule validation. |
| [XG0002_constraint_improvement.md](XG0002_constraint_improvement.md) | Detailed assumptions, numerical results, and open constraint audit finding C03. |
| [XG0001_mining_milp_model.tex](XG0001_mining_milp_model.tex) | LaTeX mathematical formulation and solution discussion; read alongside the later C03 audit. |
| [XT0001_mining_eda.py](XT0001_mining_eda.py) | Baseline data and mining mechanics audit. |
| [XT0002_level_expected_returns.py](XT0002_level_expected_returns.py) | Expected returns by mine level and daily throughput. |
| [XT0003_pickaxe_upgrade_timing_eda.py](XT0003_pickaxe_upgrade_timing_eda.py) | Exploratory pickaxe payback calculations using embedded baseline values. |
| [XT0004_gem_nodes_eda.py](XT0004_gem_nodes_eda.py) | Gem frequencies, hit requirements, and energy returns. |
| [XG0004_mining_comparison/](XG0004_mining_comparison/) | Editable report HTML, content JSON, and chart JSON/SVG. Local render previews, when present, are intermediate files. |

`XT0009_extend_audit_report.py`, when present locally, is the report appendix authoring helper. It edits the archived HTML/content JSON; PDF regeneration is a separate step. It is not part of the solver.

## Saved results

| File | Contents |
| --- | --- |
| [XG0003_resource_share_summary.csv](XG0003_resource_share_summary.csv) | Spring and Year 1 scenario summaries. |
| [XG0003_daily_schedules.csv](XG0003_daily_schedules.csv) | Daily decisions; filter by `Scenario`, `Objective`, and `Horizon` before aggregating. |
| [XG0003_target_search.csv](XG0003_target_search.csv) | Terminal-cash bounds for the earliest 100,000g day. |
| [XG0003_upgrade_tests.csv](XG0003_upgrade_tests.csv) | Delayed upgrades and forced-Gold comparisons. |
| [XG0003_assumption_sensitivity.csv](XG0003_assumption_sensitivity.csv) | Floor-clearance and upgrade-lockout sensitivities. |

From the repository root, run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 mining/Jiahe_Solution/ZG0001_archive/XT0007_resource_share_analysis.py
```

This overwrites the five generated CSVs above in this archive. Input datasets remain in `mining/data/` and `shared/data/`. Reproduction requires the same Python packages and Gurobi license as the main solver. The open C03 ordering issue also applies to these saved results.
