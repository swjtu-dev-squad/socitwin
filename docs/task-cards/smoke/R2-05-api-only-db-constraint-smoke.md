# 任务卡：R2-05 API-only / 单进程数据库约束 Smoke Test

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P1 |
| **类型** | Smoke Test / Runtime Constraint Validation |
| **负责人** | @工程负责人 |
| **协作人** | @测试负责人 |
| **关联 Issue** | 无（来源于第一轮遗留观察） |

---

## 1. 背景

第一轮已观察到：当 `pnpm dev` 启动的服务与独立 Python 脚本同时操作同一个 SQLite 数据库文件时，会出现 `disk I/O error` 风险。第二轮应将其正式写成工程约束并验证：运行中数据库只允许单进程写入，任何仿真交互优先通过 API 服务完成。

## 2. 目标

验证并固化以下约束：

*   Dashboard 运行时，不再让独立脚本直接写同一运行中的数据库。
*   API 路由是唯一默认写入入口。
*   离线脚本使用单独的 fixture 数据库。
*   文档中明确单进程写入原则。

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| SQLite 写入约束 | 切换数据库后端 |
| API-only 测试方式 | SQLite 并发优化 |
| 文档补充 | 分布式执行 |
| fixture 数据库使用规范 | |

## 4. 前置条件

*   当前开发流程使用 SQLite。
*   有第一轮观测到的冲突现象作为背景依据。

## 5. 执行步骤

**(1) 规范测试方式**

将所有第二轮 smoke 的默认路径设为：`pnpm dev` -> 浏览器/API 操作 -> 不直连运行中的主数据库。

**(2) 离线脚本改用 fixture 数据库**

例如 CLI smoke 使用 `/tmp/oasis-context-smoke.db`，这和当前 `context_smoke.py` 默认参数一致。

**(3) 补充文档**

在人工测试手册 / README / 测试规范中加入：单进程写入原则、API-only 首选路径、fixture 数据库用法说明。

## 6. 通过标准 (Gate)

*   [ ] 第二轮 smoke 全程不因数据库并发触发 I/O error
*   [ ] CLI smoke 使用独立数据库
*   [ ] Dashboard 交互通过 API 完成
*   [ ] 文档中已写明约束
*   [ ] 团队测试流程可复现

## 7. 失败标准

*   仍允许脚本和 dashboard 并发写同一数据库。
*   测试过程出现 I/O error。
*   文档中无此约束说明。

## 8. 证据要求

*   `artifacts/smoke/r2_05_db_constraint.md`
*   测试流程截图
*   更新后的文档片段

## 9. 备注

这张卡看起来不炫，但它很值钱。它不是在增加功能，而是在防止测试手段本身把系统搞出玄学故障。
