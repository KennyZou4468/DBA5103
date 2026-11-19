"""Run: python -m unittest discover -s fishing/tests -v"""
import copy
import itertools
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fishing_milp import Config,build_model,export_solution,greedy_start,level_at,load_parameters,solve
from fishing_validate import audit_schedule


class FishingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.p=load_parameters()

    def run_model(self,c,seconds=15,mutate=None):
        m,ctx=build_model(self.p,c);ctx["model"]=m
        if mutate:mutate(m,ctx)
        sol,result=solve(m,ctx,self.p,time_limit=seconds,gap=0)
        self.assertIsNotNone(sol,result)
        return m,ctx,sol,result

    def test_day_one_matches_exhaustive_enumeration(self):
        # No rod can be bought at level 0; all locations share time/energy cost.
        p=self.p;rows=[r for r in p["rows"] if r["season"]=="spring" and r["level"]==0 and r["mode"]=="none"]
        best={b:max((r for r in rows if r["time_block_id"]==b),key=lambda r:r["v"]) for b in p["blocks"]}
        bounds=[int(p["blocks"][b]/best[b]["tau"]) for b in p["blocks"]]
        objective=max(500+sum(n*best[b]["v"] for n,b in zip(ns,p["blocks"]))
                      for ns in itertools.product(*(range(n+1) for n in bounds)) if sum(ns)*8<=270)
        _,_,_,r=self.run_model(Config(horizon=1))
        self.assertEqual(r["status"],"Optimal");self.assertAlmostEqual(r["objective"],objective,places=4)

    def test_exact_projection_thresholds(self):
        # The actual level constraints are tested at every threshold, including the cap.
        import highspy as hs
        for k,threshold in self.p["levels"].items():
            for n in {max(0,threshold-1),threshold}:
                expected=level_at(n,self.p["levels"])
                eligible=[j for j,a in self.p["levels"].items()
                          if a<=n<=self.p["levels"].get(j+1,4257)-1]
                self.assertEqual(eligible,[expected])
        # Fix day-2 N[1] on either side of level 2, then attempt the wrong level.
        for n,wrong in ((29,2),(30,1)):
            m,ctx=build_model(self.p,Config(horizon=2))
            m.lb[ctx["N"][1]]=m.ub[ctx["N"][1]]=n
            m.lb[ctx["z"][2,wrong]]=1
            _,r=solve(m,ctx,self.p,time_limit=5,gap=0)
            self.assertEqual(r["status"],"Infeasible")

    def test_pruning_preserves_two_day_optimum(self):
        a=self.run_model(Config(horizon=2,prune=True))[3]
        b=self.run_model(Config(horizon=2,prune=False))[3]
        self.assertEqual(a["status"],"Optimal");self.assertEqual(b["status"],"Optimal")
        self.assertAlmostEqual(a["objective"],b["objective"],places=4)

    def test_opening_cash_blocks_same_day_financing(self):
        # Day 2 has eligibility, but a forced 1,800g rod must fit actual day-1 cash.
        def force(m,c):
            m.lb[c["buy"][2,"fiberglass_rod"]]=1
            m.row("test_cash_limit",{c["B"][1]:1},ub=1799)
        m,ctx=build_model(self.p,Config(horizon=2));force(m,ctx)
        _,r=solve(m,ctx,self.p,time_limit=5,gap=0)
        self.assertEqual(r["status"],"Infeasible")

    def test_iridium_without_fiberglass_can_use_bait(self):
        # This construction has enough time to reach level 6 before day 10.
        def force(m,c):
            for t in range(1,11):m.ub[c["buy"][t,"fiberglass_rod"]]=0
            m.lb[c["buy"][10,"iridium_rod"]]=1
            m.row("test_iridium_bait",{a["index"]:1 for a in c["by_day"][10] if a["mode"]=="bait"},lb=1)
        m,ctx,sol,r=self.run_model(Config(horizon=10),seconds=25,mutate=force)
        with tempfile.TemporaryDirectory() as out:
            report=export_solution(self.p,ctx,sol,r,out)
            self.assertTrue(report["audit"]["passed"])
            self.assertIsNone(report["rod_purchase_days"]["fiberglass_rod"])
            self.assertEqual(report["rod_purchase_days"]["iridium_rod"],10)

    def test_all_warm_starts_feasible_and_audit_detects_corruption(self):
        from fishing_milp import read_csv
        m,ctx=build_model(self.p,Config(horizon=40));ctx["model"]=m
        A=m.matrix()
        for policy in ("none","F","I","both"):
            s=greedy_start(self.p,m,ctx,policy);v=A@s
            self.assertLessEqual(max((v-m.row_ub).max(),(m.row_lb-v).max()),1e-6)
        sol=greedy_start(self.p,m,ctx,"both")
        with tempfile.TemporaryDirectory() as out:
            export_solution(self.p,ctx,sol,dict(objective=sol[ctx["B"][40]]),out)
            daily=read_csv(Path(out)/"daily_schedule.csv");acts=read_csv(Path(out)/"activity_schedule.csv")
            daily[0]["Cash_End_g"]=str(float(daily[0]["Cash_End_g"])+100)
            self.assertFalse(audit_schedule(self.p,ctx["config"],daily,acts)["passed"])

    def test_invalid_config_rejected(self):
        for c in (Config(horizon=0),Config(horizon=113),Config(resource_share=0),Config(energy_budget=-1),Config(fixed_location="invalid")):
            with self.assertRaises(ValueError):build_model(self.p,c)


if __name__=="__main__":unittest.main()
