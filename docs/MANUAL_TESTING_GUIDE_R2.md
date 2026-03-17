# 第二轮人工测试验证手册

| 属性 | 值 |
|---|---|
| **手册版本** | R2 |
| **更新时间** | 2026-03-17 |
| **核心目标** | 提供手动验证 R2 轮次关键修复和发现的步骤 |

---

## 1. 环境准备

1.  **启动服务**：
    ```bash
    cd /home/ubuntu/oasis-dashboard
    fuser -k 3000/tcp  # 确保端口未被占用
    pnpm dev
    ```
2.  **确认服务就绪**：
    打开新终端，执行以下命令，直到 `oasis_ready` 为 `true`：
    ```bash
    curl -s http://localhost:3000/api/sim/status | python3.11 -c "import json,sys; print(json.load(sys.stdin).get(\'oasis_ready\'))"
    ```

---

## 2. 核心测试用例

### TC-R2-01：验证 LLM 真实调用（修复后）

**目标**：确认 `step` 耗时 > 1s，且 `totalPosts` 有真实增长。

**步骤**：

1.  **初始化**：
    ```bash
    curl -s -X POST -H "Content-Type: application/json" -d '{"num_agents": 3, "topic": "AI", "platform": "reddit"}' http://localhost:3000/api/sim/config
    ```
2.  **执行单步**：
    ```bash
    time curl -s -X POST http://localhost:3000/api/sim/step
    ```
3.  **观察结果**：
    *   **预期耗时**：`real` 时间应 **> 1.0s**（通常在 3-5s 之间）。
    *   **检查状态**：
        ```bash
        curl -s http://localhost:3000/api/sim/status | python3.11 -c "import json,sys; print(json.load(sys.stdin).get(\'totalPosts\'))"
        ```
        预期 `totalPosts` **> 0**。

**通过标准**：耗时 > 1s 且 `totalPosts` > 0。

---

### TC-R2-04：验证极化值恒定 Bug

**目标**：复现 R2-04 发现的极化值在多步仿真中保持不变的问题。

**步骤**：

1.  **初始化**：
    ```bash
    curl -s -X POST -H "Content-Type: application/json" -d '{"num_agents": 5, "topic": "AI", "platform": "reddit"}' http://localhost:3000/api/sim/config
    ```
2.  **记录初始极化值**：
    ```bash
    curl -s http://localhost:3000/api/sim/status | python3.11 -c "import json,sys; print(f\"Initial Polarization: {json.load(sys.stdin).get(\'polarization\')}\")"
    ```
3.  **连续执行 5 步**：
    ```bash
    for i in {1..5}; do
        echo -n "Step $i: "
        curl -s -X POST http://localhost:3000/api/sim/step > /dev/null
        curl -s http://localhost:3000/api/sim/status | python3.11 -c "import json,sys; print(f\"Polarization: {json.load(sys.stdin).get(\'polarization\')}\")"
        sleep 1
    done
    ```

**通过标准**：连续 5 步的 `Polarization` 值与初始值完全相同。

---

## 3. 阻塞项验证

### TC-R2-02/03：确认功能未实现

**目标**：验证 `EpisodeRecord` 和 `LongTermSidecar` 相关接口不存在。

**步骤**：

1.  **检查代码**：
    ```bash
    grep -rn "EpisodeRecord\|LongTermSidecar" /home/ubuntu/oasis-dashboard/oasis_dashboard/
    ```
    预期无任何匹配。

**通过标准**：无任何相关代码实现。

---

## 4. 异常处理

*   **服务启动失败**：检查 `pnpm dev` 日志，确认 `OPENAI_API_KEY` 等环境变量是否正确设置。
*   **`disk I/O error`**：确认没有其他 Python 脚本正在直接访问 `oasis_simulation.db`。
*   **`content: null` 400 错误**：确认 `.venv/lib/python3.11/site-packages/camel/messages/base.py` 的 patch 是否正确应用。
