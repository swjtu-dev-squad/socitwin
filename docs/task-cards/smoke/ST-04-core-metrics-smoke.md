# 任务卡：ST-04 三大指标最小可计算 Smoke Test

- **状态**：Ready
- **优先级**：P1
- **类型**：Smoke Test / 算法最小验证
- **负责人**：
- **协作人**：
- **创建日期**：2026-03-17
- **关联 Issue**：#22, #24
- **关联代码**：`oasis_dashboard/polarization_analyzer.py`, `src/pages/Analytics.tsx`
- **预期产出**：`artifacts/smoke/st04_metrics_smoke_result.csv`, `artifacts/smoke/st04_metrics_definition.md`

---

## 1. 背景与目标

Issue #22 和 #24 明确要求实现三大核心指标：**极化指数**、**传播速度**、**羊群指数**。首批 smoke 不要求做到研究级精确，而是要做到：有明确输入、有最小算法实现、有合理输出，并且可以记录或展示。

## 2. 范围

### In Scope
- 极化指数
- 传播速度
- 羊群指数（最小版）
- 指标定义文档
- 最小结果导出

### Out of Scope
- 完整传播图谱
- 因果归因 (SHAP / Sobol)
- 大规模性能优化

## 3. 执行步骤

**Step 1：收集 step trace**

最少 5 个 step，导出：`timestamp`, `totalPosts`, `polarization`，以及（若可用）动作类别/事件记录。

**Step 2：计算三项指标**

1.  **极化指数**: 直接读取 `status.polarization` 或 analyzer 输出。
2.  **传播速度**: 使用 `Δposts / Δtime` 近似计算。
3.  **羊群指数（最小版）**: 使用赫芬达尔-赫希曼指数 (HHI) `H = Σ(p_a)^2` 计算动作集中度，其中 `p_a` 为窗口内行为类别占比。若无行为分类，则标记为“未实现”。

**Step 3：与页面核对**

比较脚本输出与页面展示是否一致。

## 4. 通过标准 (Gate)

- [ ] 三项指标中至少两项可真实输出。
- [ ] 第三项若未完成，必须明确说明缺失输入或接口。
- [ ] 无硬编码神秘数字继续占位。
- [ ] 输出结果可重复计算。

## 5. 失败标准

- 三项都无法从现有数据导出。
- 同一输入多次运行结果不稳定。
- 前后端对定义理解不一致。
- 页面值与脚本值明显不一致。

## 6. 证据要求

- `artifacts/smoke/st04_metrics_smoke_result.csv`
- `artifacts/smoke/st04_metrics_definition.md` (包含计算公式)
- 计算脚本或 notebook
- 页面比对截图

---

## Gate

- [ ] 能按文档步骤复现
- [ ] 证据完整
- [ ] 结论明确（Pass / Fail / Blocked）
- [ ] 若 Fail，已给出定位方向
- [ ] 若涉及代码修改，已单独提交 commit
