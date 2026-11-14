#!/usr/bin/env python3
"""Generate daily planting-batch events for the crop MILP.

The optimizer plants x[c,s] tiles.  This script converts the existing
planting calendar and harvest schedule into one auditable row per feasible
crop-batch/day, so that harvest, final land release, and watering requirements
are fixed parameters rather than logic inside the optimization model.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CALENDAR = DATA / "canonical" / "crop_planting_calendar.csv"
HARVESTS = DATA / "canonical" / "crop_harvest_schedule.csv"
OUTPUT = DATA / "canonical" / "crop_daily_events.csv"


def main() -> None:
    with CALENDAR.open(newline="", encoding="utf-8") as stream:
        calendar = list(csv.DictReader(stream))
    with HARVESTS.open(newline="", encoding="utf-8") as stream:
        harvests = list(csv.DictReader(stream))

    harvests_by_batch: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in harvests:
        harvests_by_batch[(row["crop_key"], int(row["plant_day"]))].append(row)
    for rows in harvests_by_batch.values():
        rows.sort(key=lambda row: int(row["harvest_sequence"]))

    output_rows: list[dict[str, object]] = []
    for row in calendar:
        if row["plant_allowed_A_ct"] != "true":
            continue
        crop_key = row["crop_key"]
        plant_day = int(row["plant_day"])
        scheduled = harvests_by_batch[(crop_key, plant_day)]
        if not scheduled:
            raise ValueError(f"eligible batch lacks harvest schedule: {crop_key}, day {plant_day}")

        by_harvest_day = {int(event["harvest_day"]): event for event in scheduled}
        final_harvest_day = int(scheduled[-1]["harvest_day"])
        # Water from the planting day through the day before the final harvest.
        # Thus a single-harvest crop is not watered on harvest day; a regrow crop
        # is watered on intermediate harvest days to support the next regrowth.
        for calendar_day in range(plant_day, final_harvest_day + 1):
            event = by_harvest_day.get(calendar_day)
            is_harvest = event is not None
            releases_land = is_harvest and calendar_day == final_harvest_day
            output_rows.append({
                "crop_key": crop_key,
                "crop_id": row["crop_id"],
                "seed_id": row["seed_id"],
                "crop_name": row["crop_name"],
                "plant_day": plant_day,
                "calendar_day": calendar_day,
                "needs_water": str(calendar_day < final_harvest_day).lower(),
                "is_harvest": str(is_harvest).lower(),
                "releases_land": str(releases_land).lower(),
                "harvest_sequence": event["harvest_sequence"] if event else "",
                "harvest_yield_per_tile": event["harvest_yield_per_tile"] if event else "0",
                "normal_sell_price_g": event["normal_sell_price_g"] if event else "0",
                "base_revenue_g_per_tile_harvest": (
                    event["base_revenue_g_per_tile_harvest"] if event else "0"
                ),
                "parameter_definition": (
                    "One fixed crop-batch/day event. needs_water is true from planting "
                    "through the day before final harvest; intermediate regrow harvests "
                    "do not release land."
                ),
                "source_type": "derived_from_crop_planting_calendar_and_harvest_schedule",
                "source_url_or_file": (
                    "data/canonical/crop_planting_calendar.csv | "
                    "data/canonical/crop_harvest_schedule.csv"
                ),
                "review_status": "derived_ready_for_solver",
            })

    fields = [
        "crop_key", "crop_id", "seed_id", "crop_name", "plant_day", "calendar_day",
        "needs_water", "is_harvest", "releases_land", "harvest_sequence",
        "harvest_yield_per_tile", "normal_sell_price_g", "base_revenue_g_per_tile_harvest",
        "parameter_definition", "source_type", "source_url_or_file", "review_status",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Wrote {len(output_rows)} crop daily-event rows to {OUTPUT}.")


if __name__ == "__main__":
    main()
