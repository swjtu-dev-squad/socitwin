# E2E 测试脚本使用指南

## 测试脚本说明

### 1. `test_metrics_quick.py` - 快速测试（推荐）

快速验证 velocity 和 HHI 指标是否正常工作。

**功能**：
- 重置模拟
- 初始化 3 个 agents
- 执行 3 步
- 验证指标是否返回

**运行方式**：
```bash
python test_metrics_quick.py
```

**预期输出**：
```
============================================================
  Quick Metrics Test
============================================================

[1/4] Resetting simulation...
  ✅ Reset OK

[2/4] Initializing simulation (3 agents, AI topic)...
  ✅ Init OK: 3 agents

[3/4] Executing 3 steps...
  Step 1...
    ✅ OK (1.23s)
    ✅ Velocity: 0.2041 posts/s
    ✅ HHI: 25.00%

  Step 2...
    ✅ OK (0.95s)
    ✅ Velocity: 0.0000 posts/s
    ✅ HHI: 30.00%

  Step 3...
    ✅ OK (0.96s)
    ✅ Velocity: 0.0000 posts/s
    ✅ HHI: 35.00%

[4/4] Verification...
  Results:
    Total steps: 3
    Velocity measurements: 3
    HHI measurements: 3
    ✅ Velocity is working!
    ✅ HHI is working!

============================================================
  ✅ ALL TESTS PASSED!
============================================================
```

---

### 2. `test_e2e_simulation.py` - 完整测试

完整的端到端测试，模拟前端完整工作流程。

**功能**：
- 完整的初始化流程
- 可配置的 agent 数量和步数
- 详细的指标验证
- 结果保存到 JSON 文件
- 趋势分析

**运行方式**：
```bash
# 默认配置：5 agents, 5 steps
python test_e2e_simulation.py

# 自定义配置
python test_e2e_simulation.py 10 3    # 10 agents, 3 steps
python test_e2e_simulation.py 5 10 http://localhost:3000  # 完整参数
```

**参数说明**：
- 第1个参数：agent 数量（默认 5）
- 第2个参数：步数（默认 5）
- 第3个参数：服务器 URL（默认 http://localhost:3000）

**输出文件**：
测试结果会保存到 `test_results_e2e_<timestamp>.json`

---

## 使用场景

### 场景 1：开发时快速验证
```bash
# 快速测试指标是否工作
python test_metrics_quick.py
```

### 场景 2：完整的功能测试
```bash
# 运行完整的测试流程
python test_e2e_simulation.py
```

### 场景 3：压力测试
```bash
# 更多 agents 和 steps
python test_e2e_simulation.py 20 10
```

---

## 故障排查

### 错误：Connection refused
```
❌ Request failed: Connection refused
```
**解决方案**：
```bash
# 确保服务器正在运行
pnpm dev

# 或者检查端口
lsof -ti:3000
```

### 错误：Step 执行超时
```
❌ Request failed: Read timeout
```
**解决方案**：
- 减少 agent 数量
- 检查后端日志是否有错误
- 确认 LLM 服务正常

### 错误：指标为 None
```
⚠️  Velocity: None
⚠️  HHI: None
```
**解决方案**：
- 检查后端日志
- 确认 MetricsAnalyzer 是否初始化成功
- 查看 dev-logs 中的错误信息

---

## 示例输出

### 成功的测试
```
🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀
  OASIS Dashboard E2E Test
  Simulating Frontend Workflow
🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀

============================================================
  Resetting Simulation
============================================================
  ✅ Simulation reset successful

============================================================
  Initializing Simulation
============================================================
  Configuration:
    • Agents: 5
    • Platform: reddit
    • RecSys: hot-score
    • Topics: AI
    • Regions: General
  ⏳ Initializing...
  ✅ Initialization successful (1.23s)
  ⏳ Waiting for agents to settle...

============================================================
  Executing 5 Steps
============================================================

  📍 Step 1
  ⏳ Executing...
  ✅ Step 1 completed (1.45s)
     Metrics:
  • Current Step: 1
  • Total Posts: 1
  • Active Agents: 5
  • Polarization: 16.00%
  • Velocity: 0.6897 posts/s
  • Herd HHI: 25.00%

  ...

============================================================
  Verifying Metrics
============================================================
  ✅ Velocity: 5 measurements
     Range: 0.0000 - 0.6897 posts/s
     Average: 0.1379 posts/s
  ✅ Herd HHI: 5 measurements
     Range: 0.2000 - 0.3500
     Average: 0.2700
  ✅ All HHI values in valid range [0, 1]

============================================================
  Test Summary
============================================================
  Initialization: ✅ Success
  Steps Executed: 5
  Metrics Collected: 5
  Errors: 0

  💾 Results saved to: test_results_e2e_20260317-132845.json
```
