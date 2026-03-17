# 任务卡：ST-02 初始化 → step → status 主链路 Smoke Test

- **状态**：Ready
- **优先级**：P0
- **类型**：Smoke Test / API / Dashboard 联调
- **负责人**：
- **协作人**：
- **创建日期**：2026-03-17
- **关联 Issue**：
- **关联代码**：`src/lib/api.ts`, `src/lib/socket.ts`, `src/lib/store.ts`, `server.ts`
- **预期产出**：API 调用记录、step 序列表、浏览器与后端日志截图

---

## 1. 背景与目标

前端代码中已经存在完整 API 客户端 (`updateConfig`, `getStatus`, `step`, `reset` 等) 和 Socket 事件处理器 (`stats_update`, `new_log`)。本任务的目标是验证最核心的用户路径：**配置模拟 → 初始化 → 连续 step → 读取状态 → reset** 是否完整通畅。

## 2. 范围

### In Scope
- `src/lib/api.ts`
- `src/lib/socket.ts`
- `src/lib/store.ts`
- `server.ts`
- Dashboard 最小页面联调

### Out of Scope
- Analytics 的复杂图表真值校验
- 推荐算法
- 长期记忆高级机制

## 3. 前置条件

1.  后端服务启动成功 (`pnpm dev`)。
2.  前端页面可打开。
3.  本地模型服务可正常响应。
4.  Store 初始状态正常。

## 4. 执行步骤

**Step 1：启动服务**
```bash
pnpm dev
```

**Step 2：配置最小模拟**

通过 UI 或直接请求，配置以下参数：
- **platform**: `reddit`
- **recsys**: `hot-score`
- **agentCount**: `1`
- **topic**: `AI`

**Step 3：执行主链路**

1.  **初始化**模拟。
2.  连续点击 **step** 3～5 次。
3.  读取当前 **status**。
4.  查看 **logs**。
5.  执行 **reset**。

**Step 4：记录状态**

每一步记录：`currentStep`, `activeAgents`, `totalPosts`, `polarization`, `logs.length`。

## 5. 通过标准 (Gate)

- [ ] UI 不白屏。
- [ ] 3～5 次 step 全部成功。
- [ ] 每次 status 都能正常刷新。
- [ ] reset 后状态归零或重置为默认值。
- [ ] 浏览器 console 与后端终端无严重错误。

## 6. 失败标准

- step 接口报 500
- 状态不刷新
- status 字段缺失或类型错乱
- reset 后残留旧状态

## 7. 证据要求

- 一份 API 调用记录
- 一份 step 序列表 (`step` vs `totalPosts` vs `polarization`)
- 浏览器 console 截图
- 后端日志截图
- reset 前后状态对比

---

## Gate

- [ ] 能按文档步骤复现
- [ ] 证据完整
- [ ] 结论明确（Pass / Fail / Blocked）
- [ ] 若 Fail，已给出定位方向
- [ ] 若涉及代码修改，已单独提交 commit
