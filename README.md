# Optimizing Year 1 Farm Resource Allocation in *Stardew Valley*

This repository contains the DBA5103 Group 10 term-project implementation for optimizing a player's first-year resource allocation in *Stardew Valley*. The project models planting, mining, and fishing as interconnected activities that compete for the same daily time, energy, cash, and Blacksmith capacity.

Our main decision problem is to maximize end-of-horizon cash over a 112-day planning horizon. The full model is a mixed-integer linear program (MILP) that jointly determines planting batches, crop-care activities, mining progression, fishing activities, equipment purchases, and tool upgrades.

## Project overview

The repository provides two complementary experiments:

1. **Equal-allocation benchmark.** Each module independently receives one third of the initial cash, daily time, and daily energy budget.
2. **Integrated full-version model.** Planting, mining, and fishing share one cash balance and daily resource budget, allowing the optimizer to allocate resources dynamically across activities.

The baseline setting uses 112 days, initial cash of 500g, 900 game minutes per day, and 270 daily energy units. Revenues are credited at the end of each day and may be spent from the following day.

The project also includes a one-at-a-time sensitivity analysis that changes initial cash, daily time, daily energy, and Blacksmith service capacity. Since the full model is a MILP, its scenario results are repeated time-limited solves rather than LP shadow-price estimates; the reported MIP gap should therefore be read with every reported incumbent solution.

## Repository structure

| Path | Contents |
| --- | --- |
| [planting/](planting/) | Crop data, standalone planting MILP notebooks, formulation documents, and scenario outputs. |
| [mining/](mining/) | Mining data, standalone mining implementation, documentation, and one-third-resource benchmark materials. |
| [fishing/](fishing/) | Fishing MILP, input data, tests, documentation, and standalone results. |
| [CombineAndCompare/](CombineAndCompare/) | Benchmark and integrated model notebooks, shared model contract, adapters, solver, sensitivity analysis, and exported comparison outputs. |
| [shared/data/](shared/data/) | Shared baseline assumptions for initial cash, planning horizon, time, and energy. |
| [docs/](docs/) | Cross-module formulation and project documentation. |

For detailed module-specific instructions, see the README files within the corresponding module folders. The integrated-model workflow is documented in [CombineAndCompare/README.md](CombineAndCompare/README.md).

## Running the integrated experiments

The integrated notebooks require Python, gurobipy, and a valid Gurobi license. From the repository root, open and run the following notebooks from top to bottom:

| Notebook | Purpose | Main output directory |
| --- | --- | --- |
| [CombineAndCompare/benchmark.ipynb](CombineAndCompare/benchmark.ipynb) | Runs the fixed one-third-resource benchmark. | Module-specific one-third-resource folders |
| [CombineAndCompare/FullVersion.ipynb](CombineAndCompare/FullVersion.ipynb) | Solves the integrated shared-resource MILP. | CombineAndCompare/outputs/full_version/ |
| [CombineAndCompare/SensitivityAnalysis.ipynb](CombineAndCompare/SensitivityAnalysis.ipynb) | Runs the eight one-at-a-time integrated sensitivity scenarios. | CombineAndCompare/outputs/sensitivity_analysis/ |

The full-version and sensitivity-analysis outputs include daily decisions, cash-flow files, solver summaries, and figures. Generated files should be regenerated through the notebooks or Python runners rather than edited by hand.

## Team members and responsibilities

| Member | Primary responsibility |
| --- | --- |
| Kaiyi Zou | Planting module; integrated-model and report coordination. |
| Xiaotong Huang | Planting module. |
| Jiahe Wang | Mining module. |
| Xiyue Liang | Mining module. |
| Yuhao Xu | Fishing module. |

All team members contribute to the integrated formulation, computational experiments, review, and final report.

## Interpretation and reproducibility notes

- The model is a deterministic expected-value approximation of the game, not a simulation of one exact playthrough.
- Crop, fish, mining-item, and container values use the assumptions recorded in the module data and documentation.
- Outputs from a run that ends due to a Gurobi time limit are feasible solutions, but are not proven optimal. Always report the accompanying MIP gap and best bound.
- Please use feature branches and Pull Requests for changes. If an input, assumption, or constraint changes, update the corresponding module documentation in the same Pull Request.

## Course context

DBA5103 Term Project, Group 10  
Semester I, 2026/2027
