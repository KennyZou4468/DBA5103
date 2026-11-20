"""Shared interface for planting, mining, and fishing MILP adapters.

An adapter adds only its internal variables and constraints to the supplied
Gurobi model.  It returns daily resource and cash-flow expressions; the
benchmark or full-version notebook adds the cross-module constraints.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional

import gurobipy as gp
from gurobipy import GRB


@dataclass(frozen=True)
class ModuleFlows:
    """Daily linear expressions exported by one module adapter."""

    module_id: str
    time_used: Mapping[int, gp.LinExpr]
    energy_used: Mapping[int, gp.LinExpr]
    expense: Mapping[int, gp.LinExpr]
    revenue: Mapping[int, gp.LinExpr]
    upgrade_submissions: Optional[Mapping[int, gp.LinExpr]] = None
    blacksmith_service: Optional[Mapping[int, gp.LinExpr]] = None
    artifacts: Optional[Mapping[str, Any]] = None


def add_benchmark_constraints(
    model: gp.Model,
    flows_by_module: Mapping[str, ModuleFlows],
    days: range,
    initial_cash: float = 500.0,
    daily_time: float = 900.0,
    daily_energy: float = 270.0,
) -> tuple[dict[tuple[str, int], gp.Var], float]:
    """Add independent, equally allocated cash/time/energy benchmark constraints."""
    module_ids = tuple(flows_by_module)
    if not module_ids:
        raise ValueError("At least one active module is required.")
    share = 1.0 / len(module_ids)
    cash = model.addVars(module_ids, range(0, max(days) + 1), lb=0.0, name="BenchmarkCash")

    for module_id, flows in flows_by_module.items():
        model.addConstr(cash[module_id, 0] == initial_cash * share, name=f"benchmark_initial_cash[{module_id}]")
        for t in days:
            model.addConstr(flows.time_used[t] <= daily_time * share, name=f"benchmark_time[{module_id},{t}]")
            model.addConstr(flows.energy_used[t] <= daily_energy * share, name=f"benchmark_energy[{module_id},{t}]")
            model.addConstr(cash[module_id, t - 1] >= flows.expense[t], name=f"benchmark_cash_before_spend[{module_id},{t}]")
            model.addConstr(
                cash[module_id, t] == cash[module_id, t - 1] - flows.expense[t] + flows.revenue[t],
                name=f"benchmark_cash_balance[{module_id},{t}]",
            )

    terminal_cash = gp.quicksum(cash[module_id, max(days)] for module_id in module_ids)
    return cash, terminal_cash


def add_full_version_constraints(
    model: gp.Model,
    flows_by_module: Mapping[str, ModuleFlows],
    days: range,
    initial_cash: float = 500.0,
    daily_time: float = 900.0,
    daily_energy: float = 270.0,
    enforce_one_blacksmith_submission: bool = True,
    enforce_one_blacksmith_service: bool = True,
    blacksmith_submission_capacity: int = 1,
    blacksmith_service_capacity: int = 1,
) -> dict[int, gp.Var]:
    """Add shared cash, time, energy, and optional Blacksmith capacity constraints.

    ``blacksmith_submission_capacity`` limits new upgrade submissions per day,
    while ``blacksmith_service_capacity`` limits tools undergoing service.  The
    two constraints are deliberately separate: the sensitivity experiment
    changes only service capacity and preserves the one-submission rule.
    """
    if not flows_by_module:
        raise ValueError("At least one active module is required.")
    if blacksmith_submission_capacity < 0 or blacksmith_service_capacity < 0:
        raise ValueError("Blacksmith capacities must be non-negative.")
    cash = model.addVars(range(0, max(days) + 1), lb=0.0, name="SharedCash")
    model.addConstr(cash[0] == initial_cash, name="shared_initial_cash")

    for t in days:
        total_time = gp.quicksum(flows.time_used[t] for flows in flows_by_module.values())
        total_energy = gp.quicksum(flows.energy_used[t] for flows in flows_by_module.values())
        total_expense = gp.quicksum(flows.expense[t] for flows in flows_by_module.values())
        total_revenue = gp.quicksum(flows.revenue[t] for flows in flows_by_module.values())
        model.addConstr(total_time <= daily_time, name=f"shared_time[{t}]")
        model.addConstr(total_energy <= daily_energy, name=f"shared_energy[{t}]")
        model.addConstr(cash[t - 1] >= total_expense, name=f"shared_cash_before_spend[{t}]")
        model.addConstr(cash[t] == cash[t - 1] - total_expense + total_revenue, name=f"shared_cash_balance[{t}]")

        if enforce_one_blacksmith_submission:
            submissions = [
                flows.upgrade_submissions[t]
                for flows in flows_by_module.values()
                if flows.upgrade_submissions is not None
            ]
            if submissions:
                model.addConstr(
                    gp.quicksum(submissions) <= blacksmith_submission_capacity,
                    name=f"shared_blacksmith_capacity[{t}]",
                )

        if enforce_one_blacksmith_service:
            services = [
                flows.blacksmith_service[t]
                for flows in flows_by_module.values()
                if flows.blacksmith_service is not None
            ]
            if services:
                model.addConstr(
                    gp.quicksum(services) <= blacksmith_service_capacity,
                    name=f"shared_blacksmith_service[{t}]",
                )

    return cash
