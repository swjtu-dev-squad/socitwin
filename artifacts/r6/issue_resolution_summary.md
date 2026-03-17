
# OASIS Dashboard - Issue 解决情况统计报告

**统计时间**: 2026-03-17

本文档统计了自项目开始以来，通过各轮次（Round 1-6）修复和解决的关键 Issue。

---

## 统计总览

| 轮次 | 主要修复内容 | 涉及 Commit(s) | 状态 |
|---|---|---|---|
| **R6** | **前端实验对比面板折线图数据源 Bug** | `[待提交]` | **已修复** |
| **R5** | 推荐器指标差异化不足 | `02f4284` | **已修复** |
| **R4** | (新功能实现，无 Bug 修复) | `9f83b28` | N/A |
| **R3** | **极化分析 fallback 历史污染**、**Agent 行为密度低** | `615e62b`, `d9e601b` | **已修复** |
| **R2** | **4 个 Bug 批量修复** (具体见下文) | `79037ca` | **已修复** |
| **R1** | **日志去重回归 Bug (Issue #13)** | `72054b4`, `83dbf21` | **已修复** |

---

## 详细说明

### Round 6: 前端实验对比面板折线图数据源 Bug

- **问题描述**: `/experiments` 页面的“对比分析”面板中，极化和羊群指数的对比折线图为空，无法渲染时序数据。
- **根因分析**: 前端 `compareApi.ts` 读取了不存在的 `run.metrics.polarization_trace` 字段，而正确的时序数据存储在 `run.stepsTrace` 数组中。
- **修复方案**: 
    1. 在 `experimentApi.ts` 的 `ExperimentRun` 类型定义中补充 `stepsTrace` 字段。
    2. 修改 `compareApi.ts` 的 `extractCompareMetrics` 函数，使其从 `run.stepsTrace` 中正确提取时序数据。
- **状态**: **已在本地修复**，待随本次 R6 验证成果一同提交。

### Round 3: 极化分析与 Agent 行为密度问题

1.  **极化分析 fallback 历史污染 (FIX-R3-POLARIZATION-FALLBACK)**
    - **问题描述**: 极化分析的 fallback 动态值（高斯噪声）被错误地写回主历史，导致“噪声喂噪声”，分析基线逐步失真。
    - **修复方案**: 引入 `REAL_ANALYSIS_SOURCES` 集合，只有真实分析（LLM 或 heuristic）结果才写入主历史，fallback 值被显式隔离。

2.  **Agent 行为密度低 (FIX-R3-ACTION-MODE)**
    - **问题描述**: Agent 99% 的时间执行 `REFRESH` 动作，导致 `totalPosts` 等核心指标无法增长。
    - **修复方案**: 将硬编码的 `available_actions` 改造为可配置的 `behavior_mode`，允许在测试中切换到 `smoke_dense` 模式以禁用 `REFRESH` 和 `DO_NOTHING`。

### Round 2: 四个 Bug 批量修复

- **问题描述**: `79037ca` commit 中一次性修复了四个 Bug，包括但不限于 `camel` 补丁、`server.ts` 环境变量修复等。

### Round 1: 日志去重回归 Bug (Issue #13)

- **问题描述**: 在 ST-05 测试中发现，之前已修复的日志去重问题再次出现。
- **根因分析**: 核心引擎在读取增量日志时逻辑不严谨。
- **修复方案**: 引入 `watermark cursor`（水印游标）机制，确保每次只读取新的日志，从根本上解决了增量日志的重复读取问题。
