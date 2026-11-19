# 模块 Adapter 目录

未来文件：

- `planting_adapter.py`：将种植模块内部变量与约束添加到传入的 Gurobi Model，并返回 `ModuleFlows`。
- `mining_adapter.py`：将采矿模块内部变量与约束添加到传入的 Gurobi Model，并返回 `ModuleFlows`。
- `fishing_adapter.py`：钓鱼模型完成后按同一接口新增。

每个 adapter 不得自行调用 `model.optimize()`、`model.setObjective()`，也不得自行建立独立的全局现金、时间或体力约束。它只负责本模块内部规则，并通过 `ModuleFlows` 导出逐日的时间、体力、日初支出、日末收入和可选升级交付表达式。
