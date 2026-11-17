# 种植模块 Git 协作流程

本指南适用于仓库 `DBA5103` 的种植模块。目标是避免多人直接在 `main` 修改，减少反复 pull／push 产生的覆盖和冲突。

## 1. 分支规则

- `main`：只保留可运行、已确认的版本；不直接开发。
- `feature/planting`：种植模块的长期集成分支。
- `feature/planting-*`：多人并行时的个人或子任务分支，例如 `feature/planting-solver`、`feature/planting-results`、`feature/planting-docs`。
- 种植相关变更只应修改 `planting/` 下的文件；共享数据或全局文档的改动需在 Pull Request 中明确说明。

## 2. 首次建立种植模块分支

在项目目录执行：

```bash
cd /Users/zoukaiyun/NUS/DBA5103/ProjectImplementation

git switch main
git pull --ff-only origin main
git switch -c feature/planting
git push -u origin feature/planting
```

之后，种植模块的日常修改均在 `feature/planting` 或其子分支进行，而不是直接在 `main` 进行。

## 3. 单人负责种植模块时的日常流程

每次开始工作前，先将最新主分支合入种植分支：

```bash
git switch feature/planting
git fetch origin
git merge origin/main
```

完成一项小而完整的改动后提交：

```bash
git status
git add planting/
git commit -m "Add planting daily decision export"
git push
```

提交信息应描述实际改动，例如 `Fix planting event parsing`、`Document planting tool constraints`，避免使用无含义的 `update`。

## 4. 多人同时负责种植模块时的流程

每位成员从最新 `feature/planting` 创建自己的任务分支：

```bash
git switch feature/planting
git pull --ff-only origin feature/planting
git switch -c feature/planting-solver
git push -u origin feature/planting-solver
```

个人任务完成后：

1. 将 `feature/planting` 的最新改动合入个人分支：

   ```bash
   git fetch origin
   git merge origin/feature/planting
   ```

2. 处理自己分支中的冲突、运行相关验证。
3. 在 GitHub 创建 Pull Request：`feature/planting-solver` → `feature/planting`。
4. 由种植模块负责人审阅并合并。

只有已经集成和验证过的 `feature/planting` 才通过 Pull Request 合并至 `main`。

## 5. 合并到主分支

当种植模块达到一个可运行的阶段，在 GitHub 创建 Pull Request：

```text
base: main
compare: feature/planting
```

Pull Request 描述至少应说明：

- 修改了哪些种植数据、文档、代码或 notebook；
- 使用了哪些输入文件；
- 是否运行了 Gurobi 求解、数据校验或其他测试；
- 是否改变了模型假设、变量或约束。

合并完成后，每位成员在下一次工作前执行第 3 节的同步步骤。

## 6. Notebook 的特殊规则

`planting/notebooks/planting_gurobi_milp.ipynb` 容易因 cell 输出、执行编号和自动生成的 cell ID 产生无意义的 Git 差异。

- 同一时段最好只由一位成员编辑同一个 notebook。
- 提交前清除临时输出，避免将大段求解日志、调试表格或缓存写入 Git。
- 运行后的结果应写入 `planting/outputs/`，不要把每次试验结果都提交为代码变更。
- 后续较稳定的 Gurobi 模型逻辑建议迁移到 `planting/src/` 下的 `.py` 文件；notebook 只负责运行、说明和可视化。

## 7. 冲突处理原则

- 先执行 `git status`，确认本地修改的文件。
- 只解决自己负责文件中的冲突；若冲突涉及他人模块或共享数据，应联系对应负责人共同处理。
- 不使用 `git push --force` 覆盖远端共享分支。
- 不使用 `git reset --hard` 清除未确认的本地工作。
- 合并后运行种植模块的 notebook 或相关数据验证，再继续提交。

## 8. GitHub 主分支保护建议

仓库管理员应在 GitHub 为 `main` 建立 branch protection / ruleset：

1. 要求通过 Pull Request 合并；
2. 至少需要一位成员 review；
3. 合并前要求分支已同步最新 `main`；
4. 禁止 force push；
5. 如有自动校验，要求校验通过后才可合并。

这些规则使 `main` 始终是团队可共同拉取的稳定版本。
