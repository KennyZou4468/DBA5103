# CombineAndCompare：独立基准与全局联立比较

本目录比较两种资源分配方案的 Year 1（112 天）日末现金：

| Notebook | 方案 | 目的 |
| --- | --- | --- |
| `benchmark.ipynb` | 固定平均分配 | 计算资源不能跨模块调配时的基准表现。 |
| `FullVersion.ipynb` | 全局联立优化 | 在一个 Gurobi 模型中联立 planting、mining、fishing，并自由分配共享资源。 |
| `SensitivityAnalysis.ipynb` | 单因素敏感性分析 | 在初始现金、每日时间、每日体力及黑匠服务容量上逐项改变设定，并比较联立模型结果。 |

当前有效模块为 `planting`、`mining` 和 `fishing`。`FullVersion.ipynb` 调用
`full_version_solver.py`，由三个 adapter 将内部变量与约束加入**同一个** Gurobi
`Model`；它不是把三个独立解相加。

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

因此，三个模块时每个模块在 benchmark 中各有 \(500/3\)g、每天 300 分钟、90 体力。

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

FullVersion 对黑匠增加全局容量：同一天最多交付一把升级工具，且同一服务日
最多有一把工具不在手上。fishing 竿属于商店购买，不占黑匠容量：

\[
\sum_{m\in\mathcal M}\sum_k U^m_{k,t}\le1,
\qquad \forall t.
\]

\[
\sum_{m\in\mathcal M}D^m_t\le1,
\qquad \forall t.
\]

## 4. Adapter 接口：实现前必须遵守

不能直接 import 并运行独立 notebook／独立求解器，因为它们会各自创建 Gurobi Model、各自设目标并各自持有现金。每个模块需实现一个 adapter，向外提供：

- 每日时间表达式 `time_used[t]`；
- 每日体力表达式 `energy_used[t]`；
- 每日日初支出表达式 `expense[t]`；
- 每日日末收入表达式 `revenue[t]`；
- 可选的每日工具交付表达式 `upgrade_submissions[t]`；
- 模块内部变量与约束，但**不得**自行设置目标函数、日度现金余额或全局时间／体力约束。

`module_contract.py` 定义了 `ModuleFlows` 和共享约束构建函数。planting、mining、fishing 的 adapter 都必须遵循此接口。

## 5. 当前实现

1. `adapters/planting_adapter.py`：保留作物生命周期和锄头／水壶升级约束，输出种植日度流量。
2. `adapters/mining_adapter.py`：保留矿区、镐子升级、开矿日和日度采矿约束，输出采矿日度流量。
3. `adapters/fishing_adapter.py`：保留可行钓鱼活动、鱼竿购买、诱饵／配件约束，输出钓鱼日度流量。
4. `full_version_solver.py`：添加唯一现金路径、共享时间／体力和铁匠容量，并导出报告。
5. `sensitivity_analysis.py`：调用同一个 full-version solver 运行预先定义的单因素情景，并汇总可审计的比较结果。

## 6. FullVersion 输出

运行 `FullVersion.ipynb` 后，结果写入 `outputs/full_version/`：

- `integrated_daily_decisions.csv`：112 天逐日的三模块行动、收入、支出、资源使用及共享现金；
- `integrated_planting_daily_decisions.csv`、`integrated_mining_daily_decisions.csv`、`integrated_fishing_daily_decisions.csv`：按模块拆分的逐日决策、资源使用、每日及累计净现金流；
- `integrated_total_cash_flow.csv`：按模块及 overall 汇总的收入、支出、净现金流、初始及期末现金；
- `integrated_planting_batches.csv`：种植批次明细；
- `integrated_fishing_activities.csv`：钓鱼活动明细；
- `integrated_cash_balance.png`：共享日末现金曲线；
- `integrated_planting_profit_flow.png`、`integrated_mining_profit_flow.png`、`integrated_fishing_profit_flow.png`：各模块单独的每日与累计净现金流图；
- `summary.json`：目标值、MIP gap、资源峰值和各模块累计收入／支出。

若 Gurobi 因设置的 `TimeLimit` 停止，`summary.json` 的 `status=9` 表示保留了可行解；此时
`mip_gap` 必须随结果一起报告，不能称该解为已证明最优。

## 7. SensitivityAnalysis 输出

`SensitivityAnalysis.ipynb` 默认采用 180 秒的单情景时限，依次运行
8 个情景：baseline、初始现金 250g/1,000g、每日时间 720/1,080 分钟、每日体力
216/324，以及黑匠服务容量为 2 把工具。每次只改变一个输入；黑匠容量情景仍保留
“每天最多提交一把工具”的限制。

结果写入 `outputs/sensitivity_analysis/`：

- `sensitivity_summary.csv` 与 `sensitivity_summary.json`：情景参数、日末现金、best bound、MIP gap、分模块收入／支出和资源峰值；
- `terminal_cash_by_scenario.png`：各情景的 Day-112 现金比较；
- `module_revenue_by_scenario.png`：三模块总收入构成比较；
- 每个情景的子文件夹：该情景完整的日度决策、现金流和模块利润流文件。

这是 MIP 的重复求解实验，而不是 LP shadow-price 分析；读取结果时应将每个情景的
`mip_gap` 一并报告。
