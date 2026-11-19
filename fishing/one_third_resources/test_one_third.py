"""Run after solving: python -m unittest discover -s fishing/one_third_resources -p 'test_*.py' -v"""
import copy
import csv
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_optimization import HERE, read_config, prepare, validate_results


class OneThirdTests(unittest.TestCase):
    def test_unrounded_initial_cash_and_full_windows(self):
        p, model, ctx = prepare(read_config())
        self.assertEqual(ctx["budget"]["cash"], 500 / 3)
        self.assertNotEqual(ctx["budget"]["cash"], 166.67)
        self.assertEqual(ctx["budget"]["minutes"], 300)
        self.assertEqual(ctx["budget"]["energy"], 90)
        self.assertEqual(list(p["blocks"].values()), [180, 240, 180, 300])
        self.assertEqual(ctx["U"], 12)
        index = model.row_names.index("G1_time[1]")
        self.assertEqual(model.row_ub[index], 300)
        index = model.row_names.index("C3_block_time[1,morning_09_12]")
        self.assertEqual(model.row_ub[index], 180)

    def test_other_resource_share_rejected(self):
        cfg = read_config()
        cfg["resource_share"]["denominator"] = 2
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):
                read_config(path)

    def test_changed_baseline_rejected(self):
        cfg = read_config()
        cfg["baseline_expected"]["daily_energy"] = 300
        with self.assertRaises(ValueError):
            prepare(cfg)

    def test_saved_schedule_and_integration_are_audited(self):
        audit = validate_results(HERE / "results")
        self.assertTrue(audit["passed"])
        self.assertTrue(audit["yearly_cash_reconciles"])
        self.assertEqual(audit["integration_rows_verified"], 112)
        summary = json.loads((HERE / "results/summary.json").read_text())
        self.assertEqual(summary["status"], "Optimal")
        self.assertEqual(summary["mip_gap"], 0)

    def test_tampered_integration_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "results"
            shutil.copytree(HERE / "results", dst)
            path = dst / "integration_daily.csv"
            with path.open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            rows[0]["Time_Min"] = str(float(rows[0]["Time_Min"]) + 1)
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            with self.assertRaises(ValueError):
                validate_results(dst)


if __name__ == "__main__":
    unittest.main()
