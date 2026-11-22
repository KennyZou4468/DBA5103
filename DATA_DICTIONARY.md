# Data Dictionary

This document records the principal input files, model parameters, and output artifacts used by the Stardew Valley resource-allocation models. It replaces the long data-dictionary appendix in the report.

All monetary quantities are measured in gold (g), time in game minutes, and effort in energy units. Input files are converted into fixed coefficients before the MILP is constructed.

Repository: [KennyZou4468/DBA5103](https://github.com/KennyZou4468/DBA5103)

## Shared Input Data


### Shared input data files

| File | Main contents | Model use |
|---|---|---|
| `shared/data/global_parameters.csv` | Initial cash, planning horizon, daily time limit, and daily energy limit. | Defines the baseline values $B_0=500$, $|\mathcal{T}|=112$, a 900-minute daily time limit, and a 270-unit daily energy limit. Sensitivity scenarios modify selected baseline values in the solver configuration. |
| `shared/data/activity_time_rules.csv` | Time-related activity assumptions. | Provides common timing conventions used when constructing module-specific time coefficients. |
| `shared/data/activity_energy_rules.csv` | Energy-related activity assumptions. | Provides common energy conventions used when constructing module-specific energy coefficients. |

## Planting Input Data


### Planting input data files

| File | Main contents | Model use |
|---|---|---|
| `planting/data/crops.csv` | Crop identifier, crop name, seed price, normal selling price, growth duration, planting seasons, regrowth interval, and base yield. | Defines crop-level economic and biological parameters, including seed cost $p_c$. |
| `planting/data/crop_planting_calendar.csv` | Crop identifier and feasible planting day. | Constructs the binary feasibility parameter $A_{c,t}$, indicating whether crop $c$ may be newly planted on day $t$. |
| `planting/data/crop_daily_events.csv` | Crop identifier, planting day, calendar day, watering requirement, harvest indicator, land-release indicator, and revenue per tile. | Constructs $w^{\mathrm{need}}_{c,s,t}$, $h_{c,s,t}$, $f_{c,s,t}$, and $r_{c,s,t}$. |
| `planting/data/crop_harvest_schedule.csv` | Audit table for crop-harvest events and revenue. | Used to validate the daily-event construction, particularly for multiple-yield and regrowable crops. |
| `planting/data/planting_tool_catalog.csv` | Hoe and watering-can tier, time per tile, energy per tile, coverage, upgrade cost, and service information. | Defines $\tau_k^H$, $\tau_k^W$, $e_k^H$, $e_k^W$, and $\kappa_k$. |

## Mining Input Data


### Mining input data files

| File | Main contents | Model use |
|---|---|---|
| `mining/data/mining_node_profiles.csv` | Mine-zone resource profile and ordinary-rock information. | Defines zone-specific ordinary-rock activity and mine-floor resource assumptions. |
| `mining/data/mining_gem_node_profiles.csv` | Expected gem-node profile by mine zone. | Defines expected gem-node rewards associated with mine-floor activities. |
| `mining/data/mine_container_profiles.csv` | Expected container frequency and contents by mine zone. | Defines expected container rewards, particularly for Zone 2. |
| `mining/data/mining_resource_cash_values.csv` | Normal selling values of rocks, gems, and container outputs. | Converts expected mining resources directly into cash revenue. |
| `mining/data/mining_ordinary_rock_hit_requirements.csv` | Required pickaxe swings for ordinary rocks. | Used to construct ordinary-rock time and energy coefficients by pickaxe tier. |
| `mining/data/mining_gem_hit_requirements.csv` | Required pickaxe swings for gem nodes. | Used to construct gem-node time and energy coefficients by pickaxe tier. |
| `mining/data/mining_pickaxe_catalog.csv` | Pickaxe tier, upgrade cost, and mining efficiency parameters. | Defines pickaxe-upgrade cost, eligibility, and tier-specific mining coefficients. |

## Fishing Input Data


### Fishing input data files

| File | Main contents | Model use |
|---|---|---|
| `fishing/data/fishing_solver_parameters.csv` | Expected revenue, waiting time, energy use, bait cost, and expected tackle loss for each feasible fishing activity. | Defines activity-level parameters $v_i$, $\tau_i$, $e_i$, $\beta_i$, and $\delta_i$. |
| `fishing/data/fishing_time_blocks.csv` | Daily fishing time blocks and their durations. | Defines the within-day fishing time-block limits $H_b$. |
| `fishing/data/fishing_locations.csv` | Fishing locations and location characteristics. | Defines the feasible fishing locations used to construct activity combinations. |
| `fishing/data/fishing_experience_levels.csv` | Fishing levels and cumulative experience thresholds. | Defines fishing-level progression states. |
| `fishing/data/fishing_experience_rules.csv` | Experience accumulation and level-transition rules. | Ensures that casts on day $t$ affect fishing level from day $t+1$. |
| `fishing/data/fishing_rod_catalog.csv` | Rod type, price, minimum level, and equipment compatibility. | Defines rod-purchase decisions and rod ownership states. |
| `fishing/data/fishing_equipment_catalog.csv` | Bait and tackle prices, eligibility, and compatibility conditions. | Defines equipment-purchase and equipment-eligibility constraints. |
| `fishing/data/fishing_equipment_modes.csv` | Permitted rod, bait, and tackle combinations. | Defines feasible fishing equipment modes. |
| `fishing/data/fishing_timing_rules.csv` | Timing assumptions for fishing activities. | Supports construction and validation of feasible fishing activity rows. |

## Main Model Parameters


### Main mathematical parameters

| File | Main contents | Model use |
|---|---|---|
| $B_0$ | Baseline initial cash balance, equal to 500g. | `shared/data/global_parameters.csv` |
| $T^{\max}$ | Baseline daily time limit, equal to 900 game minutes. | `shared/data/global_parameters.csv` |
| $E^{\max}$ | Baseline daily energy limit, equal to 270 units. | `shared/data/global_parameters.csv` |
| $p_c$ | Seed cost of crop $c$. | `planting/data/crops.csv` |
| $A_{c,t}$ | Indicator equal to one if crop $c$ may be newly planted on day $t$. | `planting/data/crop_planting_calendar.csv` |
| $h_{c,s,t}$ | Harvest-event indicator for crop batch $(c,s)$ on day $t$. | `planting/data/crop_daily_events.csv` |
| $f_{c,s,t}$ | Land-release indicator for crop batch $(c,s)$ on day $t$. | `planting/data/crop_daily_events.csv` |
| $w^{\mathrm{need}}_{c,s,t}$ | Watering-requirement indicator for crop batch $(c,s)$ on day $t$. | `planting/data/crop_daily_events.csv` |
| $r_{c,s,t}$ | Crop revenue per tile for batch $(c,s)$ on day $t$. | `planting/data/crop_daily_events.csv` |
| $\tau_k^H,\tau_k^W$ | Hoe and watering-can time per tile at tool tier $k$. | `planting/data/planting_tool_catalog.csv` |
| $e_k^H,e_k^W$ | Hoe and watering-can energy per tile at tool tier $k$. | `planting/data/planting_tool_catalog.csv` |
| $\kappa_k$ | Cash-equivalent cost of upgrading a tool to tier $k$. | Tool catalog files. |
| $v_i$ | Expected gross revenue from fishing activity $i$. | `fishing/data/fishing_solver_parameters.csv` |
| $\tau_i$ | Expected duration of fishing activity $i$. | `fishing/data/fishing_solver_parameters.csv` |
| $e_i$ | Expected energy use of fishing activity $i$. | `fishing/data/fishing_solver_parameters.csv` |
| $\beta_i$ | Bait cost of fishing activity $i$. | `fishing/data/fishing_solver_parameters.csv` |
| $\delta_i$ | Expected tackle consumption of fishing activity $i$. | `fishing/data/fishing_solver_parameters.csv` |

## Main Output Files

The following output files are stored in `CombineAndCompare/outputs/full_version/`.

### Main optimization output files

| File | Main contents | Model use |
|---|---|---|
| `integrated_daily_decisions.csv` | One row per day containing shared cash, resource use, and summary decisions for all three modules. | Provides the primary day-by-day integrated schedule. |
| `integrated_planting_daily_decisions.csv` | Daily planting, tilling, watering, harvesting, farming-tool service, expenditure, revenue, time, and energy information. | Used to analyse planting decisions and construct planting cash-flow figures. |
| `integrated_mining_daily_decisions.csv` | Daily mine-zone activity, pickaxe service, mining expenditure, expected revenue, time, and energy information. | Used to analyse mine progression and mining cash flow. |
| `integrated_fishing_daily_decisions.csv` | Daily fishing activities, cast counts, rod purchases, expenditure, expected revenue, time, and energy information. | Used to analyse fishing decisions and fishing cash flow. |
| `integrated_total_cash_flow.csv` | Module-level and total revenue, expenditure, net cash flow, initial cash, and terminal cash. | Used to compare the financial contributions of the three modules. |
| `summary.json` | Solver status, objective value, best bound, MIP gap, and total resource-use summary. | Used to report solution quality and solver performance. |

## Sensitivity-Analysis Workflow and Outputs

The sensitivity analysis re-solves the integrated model under alternative shared-resource settings. The baseline values are varied one at a time for initial cash, daily time capacity, daily energy capacity, and Blacksmith service capacity. Each scenario has its own auditable folder containing the corresponding integrated decisions, cash-flow outputs, solver summary, and figures.

### Sensitivity-analysis workflow and output files

| File | Main contents | Model use |
|---|---|---|
| `CombineAndCompare/SensitivityAnalysis.ipynb` | Notebook that defines the scenarios, executes repeated integrated solves, and produces comparison tables and figures. | Provides the reproducible computational workflow for the sensitivity analysis. |
| `CombineAndCompare/sensitivity_analysis.py` | Reusable Python implementation for executing the sensitivity scenarios and exporting their summaries. | Separates the scenario-running logic from the notebook interface. |
| `CombineAndCompare/outputs/sensitivity_analysis/sensitivity_summary.csv` | Tabular summary of scenario parameters, terminal cash, module revenue, best bound, MIP gap, and solution status. | Primary numerical source for the report's sensitivity-results table. |
| `CombineAndCompare/outputs/sensitivity_analysis/sensitivity_summary.json` | Machine-readable version of the scenario-level sensitivity summary. | Supports reproducibility and programmatic verification of reported results. |
| `CombineAndCompare/outputs/sensitivity_analysis/terminal_cash_by_scenario.png` | Bar chart comparing terminal cash across the baseline and alternative scenarios. | Provides the terminal-cash sensitivity chart used in the report. |
| `CombineAndCompare/outputs/sensitivity_analysis/module_revenue_by_scenario.png` | Stacked bar chart of cumulative planting, mining, and fishing gross revenue by scenario. | Provides the module-revenue sensitivity chart; the stacked total is gross revenue, not net profit or terminal cash. |
| `CombineAndCompare/outputs/sensitivity_analysis/<scenario>/` | Scenario-specific directory containing daily integrated decisions, module-level decisions, total cash flow, solver summary, and cash-flow figures. | Provides an auditable record for each scenario: `baseline`, `cash_250`, `cash_1000`, `time_720`, `time_1080`, `energy_216`, `energy_324`, and `blacksmith_service_2`. |

## Notes

- The paths are repository-relative.
- The optimization results use deterministic expected values for mining and fishing; output files should therefore be interpreted as expected-value policy results.
- Scenario outputs under `CombineAndCompare/outputs/sensitivity_analysis/<scenario>/` contain daily decisions, cash-flow files, solver summaries, and generated figures for the named scenario.


