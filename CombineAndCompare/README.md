# CombineAndCompare：独立基准与全局联立比较

本目录比较两种资源分配方案的 Year 1（112 天）日末现金：

| Notebook | 方案 | 目的 |
| --- | --- | --- |
| `benchmark.ipynb` | 固定平均分配 | 计算资源不能跨模块调配时的基准表现。 |
| `FullVersion.ipynb` | 全局联立优化 | 让模型在模块之间自由分配资源，计算最大可能日末现金。 |

当前有效模块为 `planting` 和 `mining`；`fishing` 完成后加入 `ACTIVE_MODULES` 即可。不得把模块数写死为 2 或 3。

## 1. 已确认的统一口径

- 规划期：112 天。
- 每日总时间：900 游戏分钟。
- 每日总体力：270。
- 初始现金：500g。
- 收入日末结算，次日才可用于支出。
- 不建立矿石、煤炭、金属锭库存；采矿产出直接转化为现金，工具升级使用各模块已确认的现金等价成本。
- 不引入跨模块物料转移。

## 2. Benchmark 定义：完全平均分配

令有效模块集合为 \(\mathcal M\)，模块数为 \(n=|\mathcal M|\)。每个模块 \(m\) 独立获得：

\[
B^m_0=\frac{500}{n},\qquad
T^m_t\le\frac{900}{n},\qquad
E^m_t\le\frac{270}{n}.
\]

每个模块维护自己的现金余额：

\[
B^m_t=B^m_{t-1}-Expense^m_t+Revenue^m_t.
\]

Benchmark 的比较值为：

\[
BenchmarkCash=\sum_{m\in\mathcal M}B^m_{112}.
\]

因此，当前两模块时每个模块有 250g、每天 450 分钟、135 体力；加入 fishing 后自动变为每模块 \(500/3\)g、300 分钟、90 体力。

## 3. FullVersion 定义：共享资源、自由分配

全部模块共享一份现金和每日预算：

\[
\sum_{m\in\mathcal M}T^m_t\le900,
\qquad
\sum_{m\in\mathcal M}E^m_t\le270,
\]

\[
B_t=B_{t-1}-\sum_{m\in\mathcal M}Expense^m_t
+\sum_{m\in\mathcal M}Revenue^m_t,
\qquad B_0=500.
\]

目标为：

\[
\max B_{112}.
\]

若各模块都有黑匠升级决策，FullVersion 还应增加全局每日送修容量：

\[
\sum_{m\in\mathcal M}\sum_k U^m_{k,t}\le1,
\qquad \forall t.
\]

这条约束只在各 adapter 明确导出升级交付变量后启用。

## 4. Adapter 接口：实现前必须遵守

不能直接 import 并运行独立 notebook／独立求解器，因为它们会各自创建 Gurobi Model、各自设目标并各自持有现金。每个模块需实现一个 adapter，向外提供：

- 每日时间表达式 `time_used[t]`；
- 每日体力表达式 `energy_used[t]`；
- 每日日初支出表达式 `expense[t]`；
- 每日日末收入表达式 `revenue[t]`；
- 可选的每日工具交付表达式 `upgrade_submissions[t]`；
- 模块内部变量与约束，但**不得**自行设置目标函数、日度现金余额或全局时间／体力约束。

`module_contract.py` 定义了 `ModuleFlows` 和共享约束构建函数。planting、mining、fishing 的 adapter 都必须遵循此接口。

## 5. 实现顺序

1. 将 planting notebook 的建模部分提取为 `add_planting_module(...)` adapter；保留作物生命周期和工具内部约束，输出四类日度流量。
2. 将 mining 独立求解器提取为 `add_mining_module(...)` adapter；保留矿区、升级、日度行动约束，输出四类日度流量。
3. 在 `benchmark.ipynb` 用独立模块现金和固定平均时间／体力上限运行两个 adapter。
4. 在 `FullVersion.ipynb` 用一个 Gurobi Model、共享现金和共享时间／体力运行两个 adapter。
5. 用同一组数据输出 `benchmark_cash`、`full_version_cash` 和二者差额。
6. fishing 完成后新增 `add_fishing_module(...)`，无需重写公共现金或资源约束。
