# 种植模块 Git 协作流程（简化版）

本项目采用最简单的规则：**每位成员只在自己的分支修改；所有稳定改动通过 GitHub Pull Request 合并到 `main`。**

## 1. 团队约定

- `main` 是稳定版本，任何人不要直接在 `main` 修改或直接 push。
- 每位成员使用一个长期个人分支。例如：

  | 成员 | 分支示例 |
  | --- | --- |
  | Kaiyun | `planting-kaiyun` |
  | 同事 Alice | `planting-alice` |

- 每个人主要修改自己负责的文件。
- 同一时段不要由两个人编辑同一个 `.ipynb` notebook。
- 是否将某人的改动合并到 `main`，统一在 GitHub 网页通过 Pull Request 决定。

## 2. 第一次建立个人分支

在项目目录执行一次：

```bash
cd /Users/zoukaiyun/NUS/DBA5103/ProjectImplementation

git switch main
git pull origin main
git switch -c planting-kaiyun
git push -u origin planting-kaiyun
```

同事只需把最后两行中的 `planting-kaiyun` 换成自己的分支名，例如 `planting-alice`。

## 3. 日常修改与提交

每次工作时，只需使用自己的分支：

```bash
git switch planting-kaiyun
```

修改种植模块文件后，依次执行：

```bash
git add planting/
git commit -m "Update planting model"
git push
```

这三条命令分别表示：

1. `git add planting/`：选择本次要保存的种植模块改动；
2. `git commit -m "..."`：在本地保存一个带说明的版本；
3. `git push`：把自己的版本上传到 GitHub 上的个人分支。

常用提交说明示例：

```text
Add planting cash constraints
Fix planting daily-event parsing
Update planting documentation
Improve planting result chart
```

## 4. 合并到 main：只在 GitHub 网页操作

当一段工作完成并且 notebook 可以运行时：

1. 打开 GitHub 仓库；
2. 点击 **Compare & pull request**；
3. 确认方向为：

   ```text
   base: main
   compare: planting-kaiyun
   ```

4. 在 PR 描述中写清楚改了什么、是否运行了 Gurobi；
5. 由另一位同学简单检查后，点击 **Merge pull request**。

合并后，`main` 就成为包含这次改动的稳定版本。

## 5. 两个人同时修改的例子

假设：

- Kaiyun 修改 `planting/notebooks/planting_gurobi_milp.ipynb`；
- Alice 修改 `planting/docs/` 下的文档。

两个人各自在自己的分支执行“修改 → add → commit → push”。随后各自向 `main` 发 PR。

因为修改的是不同文件，GitHub 通常会自动合并。此时不需要双方反复 pull，也不需要手动合并彼此的分支。

## 6. Notebook 特别规则

- 同一个 notebook 不要被两个人同时编辑。
- notebook 运行时产生的大段 Gurobi 日志、临时表格和图像不应作为无意义差异频繁提交。
- 结果文件应放在 `planting/outputs/`；只有老师要求的最终结果才提交。
- 如果 GitHub 提示 notebook 冲突，先停止双方继续修改，再共同确认保留哪一版的代码内容。

## 7. 什么时候才需要额外处理

只有 GitHub 明确提示 PR 有 conflict 或分支落后于 `main` 时，才需要处理同步或冲突。不要自行使用：

```bash
git push --force
git reset --hard
```

遇到冲突时，保留提示页面或终端信息，再由负责该文件的成员一起处理。

## 8. GitHub 设置建议

仓库管理员可为 `main` 开启保护规则：

- 禁止直接 push 到 `main`；
- 要求通过 Pull Request 合并；
- 要求至少一位成员 review；
- 禁止 force push。

这样即使有人误操作，也不会覆盖团队已经确认的版本。
