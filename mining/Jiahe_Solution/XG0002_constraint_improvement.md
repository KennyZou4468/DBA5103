# Mining MILP — Constraint Improvements

Status: review only. No changes applied to `XT0005`, `XT0006` or `XG0001` yet.

Units: g = gold coins, E = energy, block = ordinary rock. Minimum blocks to pass a floor: Zone 1 = 33, Zone 2 = 29, Zone 3 = 33 (half the average blocks per floor, rounded up).

## To fix

1. **Time constraint**
   - Missing in `XT0006`.
   - Wrong in `XT0005` and the `.tex`: it uses Basic-pickaxe swing counts and leaves out Zone 2/3 blocks.
   - Fix: `0.7·energy_t + 1.4·containers_t ≤ 900` per day. This is exact, because every swing costs 2E and 1.4 min.
   - It doesn't bind standalone (max 264.6 min), but it will once fishing and farming are added.

2. **One uncleared floor per day**
   - The `OneMarg` row enforces this, but the assumption isn't written down anywhere.
   - State it explicitly: the player enters the mine once a day and goes down; only the last floor may be left uncleared.
   - Without it, leaving and re-entering a Zone 2 floor (~313g for ~1.3E each) breaks the model.

3. **Cash ≥ 0**
   - It is only enforced for Days 1–60 (`if t <= 60`).
   - Apply it every day; seed purchases in the merged model need it.

4. **Depth 120**
   - Scenario B requires 41 Zone 3 clears, but 40 clears take you from floor 80 to floor 120.
   - Changing it to 40 leaves the result unchanged (150,806.63g).

5. **Integer blocks (optional)**
   - Make `r_marg` integer. This adds no variables and removes fractional blocks such as "0.26 blocks".

## To confirm with the team or professor

6. **Lockout day**
   - The mining doc says the pickaxe can't be used on the drop-off day or the next day (current model).
   - `mining_pickaxe_catalog.csv` (`tool_unavailable_intervening_days = 1`) and V1 say only the one day in between is lost.
   - If mining is allowed on the drop-off day, the model gains ~1.4k g in total (about one day's income per upgrade).

7. **Partial last floor**
   - Supported by mining doc §3 (the minimum applies to *passing through* a floor) and the professor's guidance.
   - V1 §4.1 is stricter: every floor entered must meet the minimum.
   - Cite mining doc §3 in the report.
   - Sensitivity at T=84: strict rule gives 99,385g vs 120,208g.

## For the merge with farming and fishing

8. **Ore/bar tracking**
   - If hoe and watering can upgrades also need metal bars, ore, coal and bar stock must be tracked.
   - The current schedule is then infeasible:

     | Upgrade | Ore mined before it | Needed |
     |---|---|---|
     | Steel, Day 25 | 10.1 iron | 25 |
     | Gold, Scenario B Day 32 | 1.8 gold | 25 |
     | Gold, Scenario A whole year | 23.1 gold | 25 |

   - Also remove the material-balance section (§D.6) from `WORKLOG.md`, because the standalone spec excludes it.

9. **Gurobi license**
   - The model uses 1,790 of 2,000 allowed constraints, and the merged model will exceed the limit.
   - The license expires in about 12 days (from 2026-11-11). Get the free academic license.
