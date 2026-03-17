# 第一批 Smoke Test 清单

**执行顺序建议**：

1.  **ST-01**：确认引擎和模型服务没炸。
2.  **ST-02**：确认 API 和 dashboard 基本生命体征正常。
3.  **ST-05**：防止旧 bug 复活，污染后续所有观察。
4.  **ST-03**：先打假，再谈展示。
5.  **ST-04**：在可信输入上做最小算法验证。

---

## 执行清单

- [ ] **ST-01 Context / Memory 最小链路 Smoke**
  - **任务卡**：[docs/task-cards/smoke/ST-01-context-memory-smoke.md](docs/task-cards/smoke/ST-01-context-memory-smoke.md)
  - **状态**：
  - **负责人**：
  - **产出**：

- [ ] **ST-02 初始化 → step → status 主链路 Smoke**
  - **任务卡**：[docs/task-cards/smoke/ST-02-main-pipeline-smoke.md](docs/task-cards/smoke/ST-02-main-pipeline-smoke.md)
  - **状态**：
  - **负责人**：
  - **产出**：

- [ ] **ST-05 WebSocket 增量日志与去重回归 Smoke**
  - **任务卡**：[docs/task-cards/smoke/ST-05-log-increment-regression-smoke.md](docs/task-cards/smoke/ST-05-log-increment-regression-smoke.md)
  - **状态**：
  - **负责人**：
  - **产出**：

- [ ] **ST-03 Analytics 真数据/假数据甄别 Smoke**
  - **任务卡**：[docs/task-cards/smoke/ST-03-analytics-truth-audit-smoke.md](docs/task-cards/smoke/ST-03-analytics-truth-audit-smoke.md)
  - **状态**：
  - **负责人**：
  - **产出**：

- [ ] **ST-04 三大指标最小可计算 Smoke**
  - **任务卡**：[docs/task-cards/smoke/ST-04-core-metrics-smoke.md](docs/task-cards/smoke/ST-04-core-metrics-smoke.md)
  - **状态**：
  - **负责人**：
  - **产出**：

---

## 完成标准

- [ ] 1 agent / reddit / AI / 5 steps 能稳定跑通
- [ ] 无 traceback / 白屏 / step 卡死
- [ ] status / history / logs / analytics 数据源可追溯
- [ ] 未实现指标不再伪装成真实数据
- [ ] 历史重复日志 bug 未回归
