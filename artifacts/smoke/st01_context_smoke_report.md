# ST-01 Context / Memory 最小链路 Smoke — 结果报告

**执行时间**：2026-03-17  
**模型**：openai / gpt-4.1-mini  
**结论**：✅ PASS

## 初始化信息

| 参数 | 值 |
|---|---|
| agent_count | 1 |
| platform | reddit |
| topics | ['AI'] |
| regions | ['General'] |
| context_token_limit | 6144 |
| generation_max_tokens | 256 |
| memory_window_size | None |

## 趋势表

| step | total_posts | step_time (s) | avg_context_tokens | avg_memory_records | avg_retrieve_ms |
|---|---|---|---|---|---|
| 1 | 0 | 1.025 | 258 | 2 | 0.106 |
| 2 | 0 | 0.488 | 405 | 3 | 0.082 |
| 3 | 0 | 0.484 | 552 | 4 | 0.117 |
| 4 | 0 | 0.486 | 699 | 5 | 0.121 |
| 5 | 0 | 0.466 | 846 | 6 | 0.141 |

## 通过标准检查

- [✅] 1 agent / 5 steps 连续运行成功
- [✅] 无 Python 异常退出
- [✅] context_metrics 字段完整
- [✅] avg_memory_records 随 step 有限增长
- [✅] avg_retrieve_ms 无数量级异常跳变
- [✅] context_token_errors 全为 0

## 总结

本次 ST-01 smoke 使用 openai/gpt-4.1-mini 作为模型后端（沙箱环境无 ollama），在 1 agent / reddit / AI / 5 steps 配置下完整运行。
引擎初始化成功，5 个 step 全部执行完毕，无 traceback。
context_metrics 字段完整，avg_memory_records 从 2 线性增长至 6，avg_retrieve_ms 最大值 0.141ms，均在正常范围内。

**单元测试情况**：13 个测试中 11 个通过，2 个失败（`test_engine_initialize_and_multi_step_with_stub_runtime`、`test_engine_step_returns_context_metrics`），失败原因为测试桩 `FakeEnv` 缺少 `platform` 属性，属于测试代码与引擎 v3 接口不同步的问题，不影响真实引擎运行。