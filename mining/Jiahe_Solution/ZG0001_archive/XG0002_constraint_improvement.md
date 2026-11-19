# Mining MILP — Validation and Resource-Share Results

Updated: 2026-11-16. Scope: standalone mining; deterministic expected yields; no farming/fishing income or transfers; no food; cash-equivalent upgrades. Results below use integer ordinary rocks, an optional partial final floor, two-day upgrade lockout, and no mandatory Floor 120 unless stated.


## Priority finding from the categorized constraint audit

**OPEN C03 — compact cross-zone ordering:** `OneMarg` limits the number of marginal floors but does not ensure that this floor is in the deepest visited zone. A forced T=28 Day-21 solution is solver-feasible with Zone 1 clears=2, Zone 1 marginal entry=1 and marginal rocks=8, plus Zone 2 clears=1; objective 11,079.592236g. This conflicts with the intended single continuous descent interpretation. The three selected annual baseline solutions did not exhibit this pattern in an additional raw-variable check, but a feasible counterexample disproves a general route-equivalence claim. Repair the ordering constraints and rerun before global integration or claiming full model/specification equivalence. No solver code was changed in this documentation task.

The Kami report now includes pages 4-8 with a constraint checklist, source/units dictionary for all 25 loaded parameter keys and 10 solver controls, the seven decision-variable families (1,620 annual variables), and a separation of expressions and CSV outputs. See `../XG0004_mining_comparison.pdf`.

## Reproduce and inspect

Run from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 mining/Jiahe_Solution/ZG0001_archive/XT0007_resource_share_analysis.py
```

The script uses existing pandas, numpy and gurobipy. It writes these files beside itself:

- `XG0003_resource_share_summary.csv`: independently optimized Spring and Year 1 results.
- `XG0003_daily_schedules.csv`: daily decisions for each horizon, the earliest-target solution, and assumption sensitivities. Filter by `Scenario`, `Objective`, and `Horizon` before summing rows.
- `XG0003_target_search.csv`: optimal-cash bounds used to certify the earliest target day.
- `XG0003_upgrade_tests.csv`: upgrade-delay and forced-Gold counterfactuals.
- `XG0003_assumption_sensitivity.csv`: alternate floor-clearance and lockout assumptions.

The runner overwrites only these generated analysis CSVs. It does not modify input data. `XT0006` accepts `resource_share` (scales daily energy, daily time, and initial cash together) and `upgrade_days` (fix a tier to a day, or use `None` to prohibit it). `daily_energy_budget` can override energy alone while preserving the share-scaled time and starting cash.

## Resource allocation and main results

The one-third case reserves exactly one third of all three starting resources for mining: 90 energy/day, 300 game minutes/day, and 500/3g initial cash. Initial cash is not rounded internally. Upgrade costs, floor-clearance requirements, and the 100,000g target are unchanged. Unused daily budgets cannot be carried forward or borrowed from another activity. These are fixed standalone allocations, not a jointly optimized farming/fishing/mining solution.

| Metric | Full resources | One-third resources |
|---|---:|---:|
| Starting cash | 500.00g | 166.67g |
| Daily energy / game minutes | 270 / 900 | 90 / 300 |
| Optimal Day-28 cash | 11,372.77g | 1,856.26g |
| Copper submission, Year 1 plan | Day 14 | Day 36 |
| First Zone 2 visit, Year 1 plan | Day 21 | Day 76 |
| Steel submission, Year 1 plan | Day 25 | Day 77 |
| Gold purchase, cash-only objective | Skip | Skip |
| Optimal Day-112 cash | 177,440.85g | 26,946.02g |
| Earliest 100,000g day within Year 1 | Day 75 | Unreachable |
| Maximum observed daily mining time, Year 1 plan | 263.38 min | 92.19 min |

Dates describe the selected optimal schedules, not a uniqueness claim. The Spring plans are reoptimized for Day 28: the full-resource plan omits Steel, and the one-third plan buys no upgrades.

### What changes when the budget is divided?

At 90 energy/day, clearing a Zone 1 floor with Basic needs at least 33 × 2 swings × 2 energy = 132 energy. Daily progress cannot accumulate across regenerated floors, so the player cannot descend before upgrading.

- Days 5–35: revisit the initial Zone 1 floor, break 22 rocks/day, and sell expected yields for about 70.40g/day. No floor is cleared.
- Day 36: submit Copper for 2,300g; Days 36–37 are unavailable.
- Days 38–75: progress through Zone 1 with Copper, clearing one floor/day and using remaining energy on the next floor.
- Day 76: clear the last Zone 1 floor and enter Zone 2; end cash is 5,829.55g.
- Day 77: submit Steel for 5,600g; Days 77–78 are unavailable.
- Days 79–112: farm Zone 2 with Steel, earning about 785.78g/day (43 ordinary rocks, 21.6 expected containers); skip Gold.

The reduction is nonlinear: fixed upgrade costs and indivisible ladder-clearance thresholds delay access to higher-return activities. The year-end result is much less than one third of the full-resource result. Energy, capital accumulation, and floor thresholds drive the change; the 300-minute budget remains slack.

## Minimum energy for a floor: additional controlled case

The minimum for ordinary rocks on the first Zone 1 floor with Basic is **132 energy** (33 rocks × 2 swings × 2 energy). If the optional gems are skipped, that is enough to find the ladder under the deterministic half-rock rule. The existing compact solver collects all expected gems on an entered floor; those add 1.65776 expected energy, so its first-floor clearance threshold is **133.65776 energy**. The smallest whole-number energy budget covering that bundle is **134**. This is an expected-value model threshold, not a guarantee for randomly generated real-game floors.

The `minimum_floor` scenario raises only the one-third case's energy from 90 to 134; time remains 300 game minutes/day and initial cash remains exactly 500/3g. This is a controlled energy sensitivity, not an equal one-third split. Upgrade prices, floor requirements and the target remain unchanged. Floors must still be cleared within one day; neither energy nor a partially broken layout carries over.

| Metric, 134-energy case | Result |
|---|---:|
| Starting cash / time budget | 166.67g / 300 minutes |
| Copper submission | Day 27 |
| First Zone 2 visit | Day 37 |
| Steel submission | Day 43 |
| Gold purchase | Skip |
| Optimal Day-28 cash | 2,522.02g; no upgrade in this short-horizon plan |
| Optimal Day-112 cash | 80,467.45g |
| Earliest 100,000g within Year 1 | Unreachable |

The selected Year 1 schedule clears one Zone 1 floor/day with Basic on Days 5–26, upgrades on Days 27–28, clears two floors/day with Copper from Day 29, enters Zone 2 on Day 37, upgrades Steel on Days 43–44, then farms Zone 2 from Day 45 for about 1,180.51g/day. Time usage peaks at 138.99 of 300 minutes. Raising energy from 90 to 134 increases year-end cash by 53,521.43g by removing the initial progression barrier and accelerating access to Zone 2.

The same upgrade pattern survives the stricter full-clearance rule at 134 energy: Copper Day 27, Steel Day 48, no Gold, and 53,391.54g at Day 112. Under one-day submission lockout it yields 82,828.48g, with Copper Day 27 and Steel Day 42. Thus the policy is stable across the tested feasible floor/lockout variants, while timing and profits change substantially.

## Certifying the earliest target day

Define F(T) as the maximum terminal cash attainable by Day T using exactly the same rules. F(T) is nondecreasing because any earlier feasible schedule can be extended with idle days. Therefore the earliest target date is the first T with F(T) ≥ 100,000g; binary search avoids changing the model into a larger time-minimization MILP.

For full resources, independently solved optimal bounds are F(74) = 99,494.50g and F(75) = 101,545.72g. Hence Day 75 is the earliest feasible day under this model, not merely the first target crossing in a Day-112 solution.

For one-third resources, F(112) = 26,946.02g < 100,000g; for the 134-energy case, F(112) = 80,467.45g < 100,000g. Monotonicity proves that no earlier date within Year 1 can reach the target in either constrained case. No earliest date after Year 1 is claimed. The mining target stays 100,000g; contributions from the other two activities are excluded.

## Can the strategy be one sentence?

**With enough time for the investment to pay back, buy Copper and Steel as soon as affordable, unlock and repeatedly farm Zone 2, and skip Gold unless deeper progression is required.**

This describes the tested Year 1 cash-only optima. It is an evidence-backed policy summary, not a proof for every possible constraint or horizon.

### Evidence for prompt useful upgrades

Each selected upgrade occurs on the first affordable morning along its selected optimal cash path. Fixing that purchase one day later and reoptimizing all other actions gives:

| One-day delay | Full-resource cash loss | One-third cash loss | 134-energy cash loss |
|---|---:|---:|---:|
| Copper | 435.35g | 715.38g | 807.93g |
| Steel | 867.01g | 391.04g | 435.35g |

The date tests fix only the delayed tier; other decisions remain free. These tests establish the cost of those particular delays. They do not exhaustively prove that every later date is worse or that every affordable upgrade is desirable.

### Why “upgrade everything immediately” fails

Forcing Gold at its first affordable morning along the baseline path (Day 32 full; Day 94 one-third), while retaining baseline Copper/Steel dates and reoptimizing mining actions, reduces Day-112 cash by 15,060.73g and 12,821.56g respectively. In the 134-energy case, forcing Gold on the first affordable morning (Day 55) costs 13,611.03g relative to the baseline. Gold's fee and downtime outweigh its small improvement in Zone 2 returns. A Floor 120 requirement can justify Gold; the cash-only objective does not.

Even Steel is horizon-dependent: in the full-resource Spring optimum it is affordable on Day 25, but the solver skips it because there is insufficient remaining time to recover the investment.

### Constraint sensitivity and the limit of the rule

| Alternative assumption, Day 112 | Full resources | One-third resources |
|---|---:|---:|
| Require every entered floor to be cleared | 142,047.30g | 166.67g |
| One-day submission lockout | 181,543.29g | 28,517.57g |

With one-day submission lockout the Copper → Steel → Zone 2 pattern survives (full: Copper Day 14, Steel Day 24; one-third: Copper Day 36, Steel Day 76). This sensitivity means no mining on submission day and the new tier available the following day. It does not model mining before drop-off followed by an intervening unavailable day; that timing requires a separate within-day formulation.

Requiring full clearance on every entered floor makes the one-third case a deadlock: Basic cannot clear a floor, no income is possible, and Copper cannot be afforded. Thus partial-floor harvesting is essential for that case. The strategic rule cannot survive arbitrary constraint changes. Confirm the intended partial-floor interpretation with the team/professor and state it explicitly in the report.

## Constraint audit status

1. **Time:** XT0005 includes explicit daily energy/time coupling. XT0006 omits time rows only when a valid bound proves redundancy. At most four cleared Zone 2 floors plus one marginal floor yield at most 54 containers; time is 0.7 × energy + 1.4 × containers. Bounds are 264.6 ≤ 900 minutes full and 138.6 ≤ 300 minutes one-third. For smaller shares where redundancy is not established, XT0006 adds explicit tier-conditioned time rows. The runner independently recomputes actual time.
2. **One uncleared final floor:** the count is enforced by `OneMarg`; cross-zone position is not fully enforced (OPEN C03 above). The player has one descending mine run/day, avoiding repeated zero-energy resets to collect containers. This remains a modeling assumption.
3. **Cash ≥ 0:** enforced every active day. Under two-day submission lockout there is no mining revenue on upgrade days, so end-of-day solvency also ensures start-of-day affordability.
4. **Floor 120:** the optional quest requires 39 Zone 1, 40 Zone 2 and 40 Zone 3 clears. The prior off-by-one issue is corrected.
5. **Integer rocks:** enabled for all new comparisons. Expected gem counts, containers and resource yields remain fractional by design. XT0006 retains the existing compact-model simplification of collecting all generated gems/containers on entered floors; it is not a universal replacement for a model with independently optional node collection.
6. **Lockout:** the baseline follows the mining specification: submission day plus following day unavailable; new tool on day +2. The conflicting one-intervening-day interpretation still needs a team decision.
7. **Ore/bar tracking:** `Cum_*` columns are informational gross expected production, not inventory. All yields have already been sold. Do not count these same ores again as available upgrade material. The standalone specification uses cash-equivalent upgrades; physical smelting/inventory is a separate future extension if the integrated specification requires it.
8. **Solver limits:** each base Day-112 comparison uses 1,620 variables and 1,842 constraints. The current restricted Gurobi license reports expiry 2026-11-23. No dependency or license changes were made.

## Verification and remaining teammate work

Every analysis solve must reach Gurobi OPTIMAL with zero requested relative gap. An independent validator reconstructs cash, revenue, tool availability, upgrade affordability/order, zone prerequisites, ordinary-rock integrality, floor bounds, daily energy/time and marginal-floor limits from unrounded solver variables. Exported cash and resource use are reconciled against those calculations. Earliest-day bounds and counterfactual schedules are validated in the same way.

Your teammate can independently audit the assumptions above, review the exported daily schedules and sensitivity table, and prepare the mining results/slides. Before global integration, agree on the shared-cash/upgrade-material rules and obtain an appropriate solver license. This analysis does not claim to optimize resource allocation among all three activities.

Additional checks: forcing one Basic-cleared floor at 133.65776 energy is feasible; at 133.65766 it is infeasible (dual reductions disabled to distinguish infeasibility from an ambiguous presolve status). Explicit time-row activation was checked on a small resource allocation. Legacy continuous Spring cash and integer Floor-120 cash remain unchanged. All 1,167 exported daily rows have complete day sequences and unique scenario/objective/horizon/day keys; totals reconcile with the summary. LaTeX source was updated; no PDF was built.
