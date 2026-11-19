# Fishing：固定使用 1/3 资源的独立优化

本目录是供小组“种植、采矿、钓鱼各分配 1/3 资源，分别优化后汇总”使用的正式钓鱼情景。复用 `../src/fishing_milp.py` 与原数据，不复制或改写一套求解器，也不覆盖全资源结果。

**实际求解结果：期末现金 102,407.858616g，HiGHS 状态 Optimal，MIP gap=0；全年 1,328 竿，不购高级鱼竿、不用鱼饵或吊钩。** 独立日程核查、112 行整合接口检查及 5 项情景测试全部通过。

## 1. 已确认的资源口径

| 资源 | 全资源基线 | 本情景 |
| --- | --- | --- |
| 初始现金（仅分配一次） | 500g | 500/3g，展示约 166.67g |
| 每日总时间 | 900 游戏分钟 | 300 游戏分钟 |
| 每日体力 | 270 | 90 |
| 四个时间窗 | 180、240、180、300 分钟 | 保持原窗，额外受全日 300 分钟限制 |
| 规划期 | 112 天 | 112 天 |

`config.json` 用整数分子和分母保存 1/3，计算时不先把初始现金取成 166.67。价格、经验门槛、鱼竿资格、鱼池与每竿系数均不缩放。各模块现金独立递推，没有跨模块借用资源或收入融资。

## 2. 运行与复核

需要完整仓库、Python 3.10+。在仓库根目录运行：

```bash
python -m pip install -r fishing/one_third_resources/requirements.txt
python fishing/one_third_resources/run_optimization.py
python fishing/one_third_resources/run_optimization.py --validate-only
python -m unittest discover -s fishing/one_third_resources -p 'test_*.py' -v
```

默认使用无需许可证的 HiGHS，180 秒、relative gap=0、单线程、seed=0。结果写入本目录 `results/`。路径从脚本自身解析，因此也可在其他工作目录用脚本绝对路径启动。

```bash
# 另存个人复跑结果，不覆盖提交的证据
python fishing/one_third_resources/run_optimization.py --out fishing/one_third_resources/my_run
python fishing/one_third_resources/run_optimization.py --out fishing/one_third_resources/my_run --validate-only
```

如选 `--backend gurobi`，另装 gurobipy 并配置足够规模许可证；该入口继承原求解器，本次未实测。本次所有结果与最优性证据来自 HiGHS。若超时，只能按保存的状态与 gap 称为可行解；没有可行整数解会报错，不生成伪日程。

## 3. 文件导航

| 文件 | 内容 |
| --- | --- |
| [config.json](config.json) | 固定 1/3、112 天、基线漂移检查、求解设置 |
| [run_optimization.py](run_optimization.py) | 正式运行与复核入口，调用共享求解器与独立审核 |
| [constraints.md](constraints.md) | 全部设定、目标、资源、等级、装备、成本、现金和变量域 |
| [analysis.md](analysis.md) | 四季策略、解释、全资源比较和局限 |
| [test_one_third.py](test_one_third.py) | 5 项情景测试：精度/时间窗、份额、基线、真实结果和篡改检测 |
| [results/summary.json](results/summary.json) | 目标值、bound、gap、耗时、配置及数据/代码 SHA256 |
| [results/daily_schedule.csv](results/daily_schedule.csv) | 每日状态、竿数、成本、现金与资源 |
| [results/activity_schedule.csv](results/activity_schedule.csv) | 每个非零日—时段—地点—模式的竿数 |
| [results/integration_daily.csv](results/integration_daily.csv) | 小组按日期汇总的 R/C/T/E 与现金接口 |
| [results/validation.json](results/validation.json) | 原始活动系数独立重算与接口核查 |
| [results/solver.log](results/solver.log) / [results/tests.log](results/tests.log) | 原始求解与测试日志 |

共享依赖在 `../requirements.txt`，原输入位于 `../data/` 和 `../../shared/data/global_parameters.csv`；数学规格在 `../docs/`。原先 `../results/one_third_112/` 的初步情景保留，本目录是带独立配置、运行入口、约束说明与整合接口的正式交付。

## 4. 组员怎样整合

使用 `results/integration_daily.csv` 按 Day 对齐其他两模块。Revenue_g、Cost_g、Time_Min、Energy 分别是 R、C、T、E；Cash_End_g 已含本模块的初始 500/3g。三模块期末现金可直接相加，不再另外加 500g；全年的净增现金才是总期末现金减 500g。

固定份额汇总的最优性限于这个独立分配规则，不等于允许自由分配资源的联合最优。若需要真实分钟级日程，还须协调三模块的钟点窗口，避免同一玩家在同一时间段执行重叠活动。此次只新增本目录，不改 shared、planting、mining 或原求解器。
