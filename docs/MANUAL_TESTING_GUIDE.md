# OASIS Dashboard 人工测试验证手册

**版本**：1.0
**更新日期**：2026-03-17

---

## 1. 概述

本手册旨在为 `oasis-dashboard` 项目的核心功能提供一套标准的人工测试流程，以确保在代码变更后，系统的关键链路依然稳定可靠。本文档覆盖了从环境准备到功能验证的完整步骤。

## 2. 环境准备

在开始测试前，请确保您的本地环境满足以下要求：

*   **代码**：已从 `swjtu-dev-squad/oasis-dashboard` 仓库拉取最新 `main` 分支代码。
*   **依赖**：
    *   Node.js (v22+)
    *   pnpm (v10+)
    *   Python (v3.11+)
    *   uv (Python 包管理工具)
*   **API密钥**：已在项目根目录的 `.env` 文件中配置 `OPENAI_API_KEY`。

**首次启动步骤**：

1.  **安装前端依赖**：
    ```bash
    pnpm install
    ```
2.  **创建并激活 Python 虚拟环境**：
    ```bash
    uv venv
    source .venv/bin/activate
    ```
3.  **安装 Python 依赖**：
    ```bash
    uv pip install -e .[dev]
    ```

## 3. 启动服务

所有测试都依赖于后端 API 服务和前端应用的正常运行。请在项目根目录执行以下命令启动开发服务器：

```bash
pnpm dev
```

服务启动成功后，您应该能在终端看到类似以下的输出，并且浏览器可以访问 `http://localhost:3000`。

> ```
>   VITE v5.5.2  ready in 1.28s
> 
>   ➜  Local:   http://localhost:3000/
>   ➜  Network: use --host to expose
> ```

同时，后端 Python 引擎会作为子进程被启动，并显示 `✅ OASIS Engine ready!`。

## 4. 核心功能测试用例

以下是用例覆盖了系统的核心生命周期。

### 4.1. TC-01：仿真初始化与重置

*   **目标**：验证用户能否成功配置并启动一个新的仿真实例，以及能否将其重置为初始状态。

*   **测试步骤**：
    1.  打开浏览器，访问 `http://localhost:3000`。
    2.  在 **Configuration** 面板中，选择 `Agent Count: 3`，`Platform: Reddit`，`Topics: AI`。
    3.  点击 **Initialize** 按钮。
    4.  **验证点 1**：观察 **Status** 面板，`Current Step` 应为 `0`，`Active Agents` 应为 `3`，`OASIS Ready` 应为 `true`。
    5.  点击 **Reset** 按钮。
    6.  **验证点 2**：观察 **Status** 面板，所有状态应恢复到初始值（`Current Step: 0`, `Active Agents: 0`）。

### 4.2. TC-02：单步执行与日志验证

*   **目标**：验证仿真能否按步推进，以及前端日志流是否能正确、无重复地显示增量信息。

*   **测试步骤**：
    1.  完成 TC-01 的初始化步骤（1-3）。
    2.  点击 **Step** 按钮 5 次，每次点击间隔约 5-10 秒，以便观察。
    3.  **验证点 1**：观察 **Status** 面板，`Current Step` 应从 `1` 递增到 `5`。
    4.  **验证点 2**：观察 **Logs** 面板，日志应随每次 `Step` 而**增量**出现，不应有任何重复的帖子内容显示。
    5.  **验证点 3**：在浏览器开发者工具的 Console 中，不应出现与 WebSocket 或日志处理相关的错误。

### 4.3. TC-03：Analytics 页面数据可追溯性

*   **目标**：验证 Analytics 页面的核心指标是否基于真实仿真数据，而非硬编码或伪造数据。

*   **测试步骤**：
    1.  完成 TC-02 的所有步骤，确保已执行至少 5 步仿真。
    2.  导航到 **Analytics** 页面。
    3.  **验证点 1**：查看 **Polarization Trend** 图表，应能看到一条随 `Step` 变化的曲线。
    4.  **验证点 2**：将鼠标悬停在曲线上，应能看到每个 `Step` 对应的具体极化指数值。
    5.  **验证点 3**：对于明确标有 `Coming Soon` 或 `Not Implemented` 的图表，确认其内容为空或占位符，而非看似真实的伪造图表。

## 5. 异常情况处理

*   **服务无法启动**：检查 `.env` 文件是否存在且配置正确，并确认所有依赖已正确安装。
*   **Step 点击无反应**：打开浏览器开发者工具，检查 Console 和 Network 标签页是否有 API 请求失败的错误信息。
*   **日志重复**：这是 Issue #13 的典型症状。请确认您使用的是已修复该问题的最新代码。如果问题复现，请记录详细的复现步骤并提交新的 Issue。
