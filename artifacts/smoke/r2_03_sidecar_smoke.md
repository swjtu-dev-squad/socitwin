# R2-03 A/B Long-term Sidecar 联调 Smoke Test 报告

| 属性 | 值 |
|---|---|
| **执行时间** | 2026-03-17 |
| **结论** | ❌ BLOCKED（前置依赖未实现） |
| **关联 Issue** | #7, #26, #27 |

---

## 执行结果

### 前置条件检查

| 前置条件 | 状态 | 说明 |
|---|---|---|
| #26 产出的 `EpisodeRecord` 已可样本化输出 | ❌ 未满足 | R2-02 已确认 Episodic Compaction 尚未实现，无 EpisodeRecord 产物 |
| B 侧 Sidecar 最小接口（`longterm.py`）已存在 | ❌ 未满足 | 仓库中不存在 `longterm.py`、`sidecar.py` 或任何相关接口文件 |
| `write_episode` / `retrieve_relevant` 接口可调用 | ❌ 未满足 | 接口未实现 |

### 代码搜索结果

```
$ find oasis_dashboard/ -name "longterm*" -o -name "sidecar*" -o -name "episode*"
(无输出)

$ grep -rn "EpisodeRecord|write_episode|retrieve_relevant" oasis_dashboard/
(无匹配)
```

**结论**：Issue #26（A 侧 Episodic Compaction）和 Issue #27（B 侧 Long-term Sidecar）均处于 Open 状态，相关接口代码尚未提交到仓库。R2-03 的所有执行步骤均无法进行。

---

## Gate 验收状态

| 验收项 | 状态 |
|---|---|
| `write_episode()` 正常 | ❌ BLOCKED（接口不存在） |
| `write_episodes()` 正常 | ❌ BLOCKED（接口不存在） |
| `retrieve_relevant()` 返回非空或合理空结果 | ❌ BLOCKED（接口不存在） |
| 结果结构兼容 `EpisodeRecord` | ❌ BLOCKED（EpisodeRecord 未定义） |
| `query_source` 合法 | ❌ BLOCKED（无法验证） |
| `clear()` 正常工作 | ❌ BLOCKED（接口不存在） |
| 不要求原始观察直接入库 | ❌ BLOCKED（无法验证） |

**总体结论：❌ BLOCKED — Issue #26 和 #27 均未实现，A/B 侧握手链路不存在。**

---

## 依赖关系分析

```
R2-03 依赖链：
  R2-03 (Sidecar 联调)
    └── Issue #27 (B侧 Sidecar 接口)
          └── Issue #26 (A侧 EpisodeRecord 契约)
                └── Issue #7 (记忆机制基础)
```

三个 Issue 形成串行依赖，需按 #7 → #26 → #27 的顺序推进。

---

## 建议

1. **优先推进 Issue #26**：定义 `EpisodeRecord` 数据结构和 `compact()` 方法，这是 A/B 两侧的共同契约。
2. **并行实现 Issue #27 最小接口**：可先实现 `InMemoryLongTermSidecar`，仅需满足 `write_episode` / `retrieve_relevant` / `clear` 三个方法。
3. **接口契约建议**：
   ```python
   class EpisodeRecord(TypedDict):
       episode_id: str
       step_range: tuple[int, int]
       summary: str
       topic: str
       agent_ids: list[int]
       created_at: str

   class LongTermSidecar:
       def write_episode(self, episode: EpisodeRecord) -> None: ...
       def write_episodes(self, episodes: list[EpisodeRecord]) -> None: ...
       def retrieve_relevant(self, query: str, limit: int = 3) -> list[EpisodeRecord]: ...
       def clear(self) -> None: ...
   ```

---

## 产出物

| 文件 | 说明 |
|---|---|
| `r2_03_sidecar_smoke.md` | 本报告 |
| `r2_03_retrieve_samples.json` | 检索样本（空，接口未实现） |
