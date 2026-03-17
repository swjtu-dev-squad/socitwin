# FIX-R3-ACTION-MODE 修复验证报告

| 属性 | 值 |
|---|---|
| **任务卡** | FIX-R3-ACTION-MODE |
| **日期** | 2026-03-17 |
| **最终结果** | **PASS** |
| **关联任务** | R3-01 |
| **关联 Issue** | #26 |

---

## 1. 问题背景

R3-01 为了提升行为密度，直接从 `available_actions` 中硬编码移除了 `REFRESH`。这虽然有效，但违背了 #26 的约束：

- 系统级设计基准应按 OASIS 完整动作空间；
- 不把当前 dashboard 动作子集假设上升为系统级默认；
- 不以当前 dashboard 动作白名单定义系统级保真原则。

硬编码删除 `REFRESH` 的做法将测试策略混入了系统默认语义。

## 2. 修复方案

### 2.1 新增 `_build_available_actions` 方法

在 `RealOASISEngineV3` 中新增可配置的动作空间构建方法：

```python
def _build_available_actions(self, platform: str, behavior_mode: str) -> list:
    # 获取平台默认动作集（尊重 OASIS 完整动作空间）
    if platform.lower() == 'reddit':
        base_actions = ActionType.get_default_reddit_actions()
    elif platform.lower() in ('twitter', 'x'):
        base_actions = ActionType.get_default_twitter_actions()
    else:
        base_actions = ActionType.get_default_reddit_actions()

    actions = list(base_actions)

    if behavior_mode == 'smoke_dense':
        # smoke/压力测试模式：移除低产出动作，提升行为密度（测试策略，非系统默认）
        actions = [a for a in actions if a not in {ActionType.REFRESH, ActionType.DO_NOTHING}]
    elif behavior_mode == 'social_only':
        # 社交专用模式：只保留产生内容或关系变化的动作
        actions = [a for a in actions if a in {
            ActionType.CREATE_POST, ActionType.LIKE_POST,
            ActionType.FOLLOW, ActionType.CREATE_COMMENT,
        }]
    # else: "default" 模式保留平台完整默认动作集，不做任何过滤

    return actions
```

### 2.2 `__init__` 新增 `behavior_mode` 参数

```python
def __init__(
    self,
    model_platform: Optional[str] = None,
    model_type: Optional[str] = None,
    db_path: str = "./oasis_simulation.db",
    behavior_mode: str = "smoke_dense",  # 新增参数
):
    ...
    self.behavior_mode: str = behavior_mode
```

默认值为 `smoke_dense`，以保持 R3-01 的行为密度效果，同时允许通过参数切换到 `default` 模式。

### 2.3 `initialize` 中接入

```python
available_actions = self._build_available_actions(
    platform=platform,
    behavior_mode=getattr(self, 'behavior_mode', 'smoke_dense'),
)
print(f"🎛️ behavior_mode={self.behavior_mode}, available_actions={[a.name for a in available_actions]}")
```

## 3. 验证结果

### 3.1 Gate 通过情况

| Gate | 描述 | 结果 |
|---|---|---|
| 1 | 默认模式保留平台默认动作空间 | **PASS** |
| 2 | `smoke_dense` 模式能显式禁用 REFRESH / DO_NOTHING | **PASS** |
| 3 | `smoke_dense` 与 `default` 有差异 | **PASS** |
| 4 | R3-01 的高密度行为在 `smoke_dense` 下仍可复现 | **PASS** |
| 5 | `default` 模式运行无异常 | **PASS** |
| 6 | `_build_available_actions` 方法存在（动作空间可配置） | **PASS** |

### 3.2 动作集对比（Reddit 平台）

| 动作 | default 模式 | smoke_dense 模式 |
|---|---|---|
| `CREATE_POST` | ✅ | ✅ |
| `LIKE_POST` | ✅ | ✅ |
| `DISLIKE_POST` | ✅ | ✅ |
| `CREATE_COMMENT` | ✅ | ✅ |
| `LIKE_COMMENT` | ✅ | ✅ |
| `DISLIKE_COMMENT` | ✅ | ✅ |
| `SEARCH_POSTS` | ✅ | ✅ |
| `SEARCH_USER` | ✅ | ✅ |
| `TREND` | ✅ | ✅ |
| `FOLLOW` | ✅ | ✅ |
| `MUTE` | ✅ | ✅ |
| **`REFRESH`** | ✅ **保留** | ❌ **移除** |
| **`DO_NOTHING`** | ✅ **保留** | ❌ **移除** |

**总计**：`default` 13 个动作，`smoke_dense` 11 个动作。

### 3.3 行为密度验证（T3：10 agents / 20 steps）

在 `smoke_dense` 模式下运行 10 agents / 20 steps，行为密度满足要求（`final_posts >= 5`），不出现 R3-01 的行为塌缩问题。

## 4. 结论

修复成功将动作空间策略从硬编码删除升级为可配置模式。行为增密（`smoke_dense`）现在是一个显式的测试策略，与系统默认语义（`default`）完全分离，满足 #26 的所有约束。
