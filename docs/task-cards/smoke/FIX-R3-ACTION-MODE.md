# 任务卡：FIX-R3-ACTION-MODE 动作空间策略配置化修复

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P0 |
| **类型** | Behavior Policy / Runtime Config / Regression Safety |
| **负责人** | @引擎负责人 |
| **协作人** | @Smoke Test 负责人、@产品/仿真策略负责人 |
| **关联任务** | R3-01 |
| **关联 Issue** | #26 |
| **关联文件** | `oasis_dashboard/real_oasis_engine_v3.py`、`oasis_dashboard/config/behavior_modes.py`（可选新增） |
| **文档** | `docs/task-cards/`、测试手册 |

**预期产出：**
- 动作空间配置化实现
- smoke/high-density 模式与 default 模式
- 回归测试
- 文档说明

---

## 1. 背景

R3-01 为了提升行为密度，直接从 `available_actions` 中移除了 `REFRESH`，从而使 10 个 agents 都产生了行为输出。这对 smoke 很有效，但当前 OASIS 平台文档明确表明 Reddit 默认动作集本来包含 `REFRESH` 与 `DO_NOTHING` 等低成本动作。

与此同时，#26 明确把以下事项列为必须遵守的边界：

- 系统级设计基准应按 OASIS 完整动作空间 / 平台能力模型；
- 不把当前 dashboard 动作子集假设上升为系统级默认；
- 不以当前 dashboard 动作白名单定义系统级保真原则。

因此，当前"直接删掉 `REFRESH`"的做法，只适合 smoke 场景，不适合作为全局默认行为语义。

## 2. 目标

将当前动作空间调整升级为可配置策略，满足：

- 默认模式仍保留 OASIS 平台默认动作空间；
- smoke / high-density 模式可显式禁用 `REFRESH`、`DO_NOTHING` 等低产出动作；
- 不再通过硬编码删除默认动作来影响系统级语义；
- 行为增密成为测试策略，而不是系统默认世界观。

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| `available_actions` 的构造方式 | LLM prompt 全面重写 |
| behavior mode 配置 | Agent 奖励函数设计 |
| 不同 mode 的动作白名单/黑名单 | 平台能力模型重构 |
| 文档与测试更新 | 推荐算法联动 |

## 4. 当前问题

当前做法是直接修改 `available_actions`，让 `REFRESH` 从运行链路中消失。这样虽然提升了发帖密度，但会带来两个问题：

(1) smoke 需求和系统默认语义混在一起；
(2) 后续如果要做真实平台行为回放，"刷时间线 / 被动消费"类动作会被不当地抹去。

## 5. 修复方案

### 5.1 方案核心

引入显式行为模式：

| 模式 | 说明 |
|---|---|
| `default` | 保持平台默认动作空间 |
| `smoke_dense` | 禁用 `REFRESH`、`DO_NOTHING` 等低产出动作 |
| `social_only`（可选） | 只保留高互动/高产出行为，供更强压力测试使用 |

### 5.2 推荐字段

在引擎初始化配置中增加：

```python
behavior_mode: str = "default"
```

### 5.3 动作策略

**`default` 模式：**
- 直接使用平台默认动作集（如 Reddit 默认动作）
- 不主动删 `REFRESH`

**`smoke_dense` 模式：**
- 从默认动作集中移除：`REFRESH`、`DO_NOTHING`
- 保留：`CREATE_POST`、`LIKE_POST`、`FOLLOW` 以及平台允许的其他"有意义社交动作"

**`social_only` 模式（可选）：**
- 只保留明确会产生内容或关系变化的动作

## 6. 实现建议

### 6.1 新增动作过滤函数

```python
def _build_available_actions(self, platform: str, behavior_mode: str):
    base_actions = ActionType.get_default_reddit_actions() if platform == "reddit" else ...
    actions = list(base_actions)

    if behavior_mode == "smoke_dense":
        actions = [a for a in actions if a not in {ActionType.REFRESH, ActionType.DO_NOTHING}]
    elif behavior_mode == "social_only":
        actions = [a for a in actions if a in {
            ActionType.CREATE_POST,
            ActionType.LIKE_POST,
            ActionType.FOLLOW,
            ActionType.CREATE_COMMENT,
        }]
    return actions
```

### 6.2 在 `initialize` 中接入

```python
self.behavior_mode = config.get("behavior_mode", "default")
self.available_actions = self._build_available_actions(self.platform, self.behavior_mode)
```

### 6.3 在日志中打印当前模式

```python
print(f"🎛️ behavior_mode={self.behavior_mode}, available_actions={[a.name for a in self.available_actions]}", flush=True)
```

## 7. 测试用例

### T1：default 模式保留 REFRESH

**步骤：**
(1) 使用 `behavior_mode=default`
(2) 初始化 Reddit 场景
(3) 检查 `available_actions`

**预期：**
- `REFRESH` 在动作集中存在
- `DO_NOTHING` 在动作集中存在（若平台默认有）

### T2：smoke_dense 模式移除 REFRESH

**步骤：**
(1) 使用 `behavior_mode=smoke_dense`
(2) 初始化 Reddit 场景
(3) 检查 `available_actions`

**预期：**
- `REFRESH` 不存在
- `DO_NOTHING` 不存在

### T3：smoke_dense 行为密度回归

**步骤：**
(1) 10 agents / 20 steps
(2) `behavior_mode=smoke_dense`

**预期：**
- 行为密度显著高于 `default`
- 不出现 R3-01 的行为塌缩

### T4：default 模式不回退

**步骤：**
(1) `default` 模式运行
(2) 检查系统不报错

**预期：**
- 不破坏现有平台默认动作空间
- 不因恢复 `REFRESH` 导致初始化异常

## 8. 通过标准（Gate）

- [ ] 默认模式保留平台默认动作空间
- [ ] `smoke_dense` 模式能显式禁用 `REFRESH` / `DO_NOTHING`
- [ ] R3-01 的高密度行为在 `smoke_dense` 下仍可复现
- [ ] 系统不再依赖硬编码删除默认动作
- [ ] 文档中明确：行为增密属于 smoke/test 策略，不是系统级默认语义
- [ ] 不违背 #26 的动作空间边界约束

## 9. 失败标准

- 仍通过硬编码删除默认动作来提升行为密度
- `default` 模式下丢失 OASIS 默认动作
- 配置项存在但不生效
- `smoke_dense` 与 `default` 无差异

## 10. 证据要求

- `artifacts/smoke/fix_r3_action_mode_report.md`
- `artifacts/smoke/fix_r3_action_mode_compare.csv`
- `default` vs `smoke_dense` 的 `available_actions` 对比
- 10 agents / 20 steps 的行为统计对比

## 11. 风险与备注

这张卡的重点不是"让 agent 更活跃"本身，而是把测试策略和系统默认语义分层。不然以后很容易出现一种经典怪事：为了让 smoke 好看，把世界模型本身改窄了。

## 12. 建议提交信息

```
git commit -m "feat(behavior): make action-space density strategy configurable"
```
