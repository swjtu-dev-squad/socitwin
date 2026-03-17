# 任务卡：ST-01 Context / Memory 最小链路 Smoke Test

- **状态**：Ready
- **优先级**：P0
- **类型**：Smoke Test / CLI / Python 引擎
- **负责人**：
- **协作人**：
- **创建日期**：2026-03-17
- **关联 Issue**：
- **关联代码**：`oasis_dashboard/context_smoke.py`, `oasis_dashboard/real_oasis_engine_v3.py`, `oasis_dashboard/context/*`
- **预期产出**：`artifacts/smoke/st01_context_smoke.json`, `artifacts/smoke/st01_context_smoke.log`, 趋势表

---

## 1. 背景与目标

项目代码中已经提供了专门的 smoke runner：`oasis_dashboard/context_smoke.py`，它会初始化 `RealOASISEngineV3`，执行若干步模拟，并输出 `context_metrics`，包括上下文 token、memory 记录数和 retrieval 耗时等关键指标。它天然适合作为第一张任务卡，用于确认“引擎是否活着、记忆链路是否在最小配置下稳定”。

本任务的目标是验证：

- 引擎可正常初始化。
- 在最小配置下能连续 step。
- context / memory 指标能正常产出。
- 不因环境变量缺失、模型 URL 异常或 memory 增长而快速崩溃。

## 2. 范围

### In Scope
- `oasis_dashboard/context_smoke.py`
- `oasis_dashboard/real_oasis_engine_v3.py`
- `oasis_dashboard/context/*`
- 环境变量配置验证
- CLI 运行结果记录

### Out of Scope
- 前端页面展示
- 复杂推荐算法
- 数据导入
- 传播图可视化

## 3. 前置条件

1.  本地模型服务可访问。
2.  Python 虚拟环境可用。
3.  设置好以下环境变量（根据文档推荐配置）：
    ```bash
    export OASIS_MODEL_URL=http://127.0.0.1:11434/v1
    export OASIS_MODEL_CONTEXT_WINDOW=8192
    export OASIS_CONTEXT_TOKEN_LIMIT=6144
    export OASIS_MODEL_GENERATION_MAX_TOKENS=256
    ```

## 4. 执行步骤

**Step 1：静态检查**
```bash
# 检查代码语法
.venv/bin/python -m py_compile oasis_dashboard/context/*.py oasis_dashboard/real_oasis_engine_v3.py oasis_dashboard/context_smoke.py tests/test_context_integration.py

# 运行单元测试
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

**Step 2：运行最小 smoke**
```bash
.venv/bin/python -m oasis_dashboard.context_smoke \
  --model-platform ollama \
  --model-type qwen3:8b \
  --agent-count 1 \
  --steps 5 \
  --platform reddit \
  --topic AI \
  --json
```

**Step 3：记录结果**

保存标准输出到：
- `artifacts/smoke/st01_context_smoke.json`
- `artifacts/smoke/st01_context_smoke.log`

## 5. 通过标准 (Gate)

- [ ] 1 agent / 5 steps 连续运行成功。
- [ ] 无 Python 异常退出或 traceback。
- [ ] `context_metrics` 字段完整。
- [ ] `avg_memory_records` 随 step 有限增长，不出现爆炸式增长。
- [ ] `avg_retrieve_ms` 保持在可接受范围，不出现数量级异常跳变。

## 6. 失败标准

- 初始化失败
- 中途 step 失败
- `context_metrics` 缺失
- 明显的 token / memory 失控
- 模型 URL / fallback 相关错误

## 7. 证据要求

- 完整的 `st01_context_smoke.json` 输出文件
- 终端日志截图
- 一张趋势表：`step` vs `total_posts` / `avg_memory_records` / `avg_retrieve_ms`
- 若失败，附 traceback

---

## Gate

- [ ] 能按文档步骤复现
- [ ] 证据完整
- [ ] 结论明确（Pass / Fail / Blocked）
- [ ] 若 Fail，已给出定位方向
- [ ] 若涉及代码修改，已单独提交 commit
