# Planting Module

This folder contains the planting component of the DBA5103 Stardew Valley optimization project.  The module chooses when and how many tiles of each crop to plant, while respecting crop calendars, land availability, daily watering/harvest events, tool upgrades, time, energy, and cash.

## Folder map

| Path | Purpose | Main contents |
| --- | --- | --- |
| `data/` | Input data used by the planting model. | Crop economics and growth information, daily crop-event coefficients, planting feasibility calendar, harvest schedule, and the authoritative tool catalogue. |
| `docs/` | Model documentation and agreed assumptions. | The approved formulation, data guide, standalone-optimization notes, and tool/resource state modelling notes. |
| `notebooks/` | Executable optimization implementation. | `planting_gurobi_milp.ipynb`, which reads the CSV inputs, builds the Gurobi MILP, solves it, audits the solution, and exports outputs. |
| `outputs/` | Generated results; do not edit these manually. | Daily decisions, planting batches, and the daily cash-balance chart from the latest notebook run. |

## File guide

### `data/`

- `crops.csv`: crop-level economic and biological input data.
- `crop_planting_calendar.csv`: whether crop `c` may be planted on each day `t`; this supports planting-feasibility constraints.
- `crop_daily_events.csv`: daily coefficients for planting batches, including tilling, planting, watering, harvesting, revenue, and land-release events; this supports land, time, energy, and cash constraints.
- `crop_harvest_schedule.csv`: batch harvest timing reference used for checking and communicating crop timing.
- `planting_tool_catalog.csv`: authoritative Hoe and Watering Can tiers, coverage, time/energy use, upgrade fees, and other tool parameters.

### `docs/`

- `种植模块_最优化问题与约束_审核稿.md`: **authoritative source** for the planting formulation, variables, assumptions, and full constraint collection.
- `种植模块_数据使用指南.md`: definitions, provenance, and intended use of each input CSV.
- `种植模块_独立优化说明.md`: how the planting module is solved in isolation and how it connects to the full model.
- `种植模块_资源平衡与工具状态建模笔记.md`: derivation notes for resource balances and upgrade/tool-state logic.

### `notebooks/`

Run `planting_gurobi_milp.ipynb` from top to bottom.  It requires a working Gurobi installation and a valid license.  The notebook must be run after any change to `data/` or model logic so that `outputs/` is refreshed.

### `outputs/`

- `daily_decisions.csv`: one row per day, summarizing planting, watering, harvest, tilling, tool-service, resource, and cash decisions.
- `planting_batches.csv`: non-zero crop planting decisions by crop and planting day.
- `daily_cash_balance.png`: daily end-of-day cash trajectory.

## Working conventions

1. Treat `planting_tool_catalog.csv` and `种植模块_最优化问题与约束_审核稿.md` as the current sources of truth for tool data and model assumptions.
2. Do not hand-edit files in `outputs/`; regenerate them through the notebook.
3. If an input or constraint changes, update the relevant document in `docs/` in the same pull request.
4. Work on a personal feature branch and submit changes through a Pull Request; avoid simultaneous edits to the same `.ipynb` file.

