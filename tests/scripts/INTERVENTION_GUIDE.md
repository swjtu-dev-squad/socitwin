# 干预系统使用指南

## 功能概述

干预系统允许在 OASIS 模拟运行时动态添加受控制的 agents (controlled agents)，用于研究人工舆论引导的效果。

## 配置文件

### `prompts/intervention.json`

定义了不同类型的 controlled agents 配置：

- **peace_messenger** - 和平使者：促进对话和理解
- **fact_checker** - 事实核查员：强调证据和事实
- **moderator** - 中立调解员：缓和冲突
- **context_provider** - 背景提供者：提供历史和背景信息
- **humanitarian** - 人道主义者：关注平民影响

每个配置包含：
- `name` - 类型名称
- `description` - 描述
- `user_name_prefix` - 用户名前缀
- `bio` - 个人简介
- `system_message` - 系统提示词
- `initial_posts` - 初始帖子列表（随机选择一个）
- `comment_style` - 评论风格

## 使用方法

### 1. 通过 Python API 使用

```python
from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3

# 初始化引擎
engine = RealOASISEngineV3()
await engine.initialize(agent_count=10, platform="reddit", topic="MiddleEast")

# 执行几步建立基线
for i in range(5):
    await engine.step()

# 批量添加 controlled agents（从配置文件）
result = await engine.add_controlled_agents_batch(
    intervention_types=["peace_messenger", "fact_checker", "moderator"],
    initial_step=True  # 是否立即执行初始发帖
)

# 继续执行步骤
for i in range(5):
    await engine.step()
```

### 2. 使用测试脚本

#### 方法 A：使用配置文件测试（推荐）

```bash
# 基础测试：默认配置
.venv/bin/python tests/scripts/test_intervention_config.py

# 自定义干预类型
.venv/bin/python tests/scripts/test_intervention_config.py \
  --types peace_messenger,fact_checker \
  --step 3 \
  --num-normal-agents 15 \
  --num-steps 10

# 使用所有干预类型
.venv/bin/python tests/scripts/test_intervention_config.py \
  --types peace_messenger,fact_checker,moderator,context_provider,humanitarian \
  --step 5 \
  --num-normal-agents 20 \
  --num-steps 15
```

#### 方法 B：使用 E2E 测试（需要后端服务）

```bash
# 启动后端服务（需要另一个终端）
# npm run dev

# 运行测试（无干预）
python tests/scripts/test_e2e_simulation.py 10 10

# 运行测试（带干预）
python tests/scripts/test_e2e_simulation.py 10 10 http://localhost:3000 "MiddleEast" --intervention

# 自定义干预
python tests/scripts/test_e2e_simulation.py 15 20 http://localhost:3000 "MiddleEast" \
  --intervention \
  --intervention-step 5 \
  --intervention-types peace_messenger,fact_checker,moderator,humanitarian
```

### 3. 命令行参数说明

#### `test_intervention_config.py`

- `--types` - 干预类型列表（逗号分隔），默认：`peace_messenger,fact_checker,moderator`
- `--step` - 在第几步添加干预（默认：2）
- `--num-normal-agents` - 普通 agents 数量（默认：10）
- `--num-steps` - 总步骤数（默认：5）

#### `test_e2e_simulation.py`

- `agent_count` - 普通 agents 数量（第1个参数）
- `num_steps` - 总步骤数（第2个参数）
- `base_url` - 后端 API 地址（第3个参数）
- `topics` - 话题（第4个参数）
- `--intervention` - 启用干预功能
- `--intervention-step N` - 在第 N 步添加干预（默认：2）
- `--intervention-types T1,T2,T3` - 干预类型列表（默认：`peace_messenger,fact_checker,moderator`）

## 扩展配置

### 添加新的干预类型

编辑 `oasis_dashboard/prompts/intervention.json`：

```json
{
  "intervention_profiles": [
    {
      "name": "your_new_type",
      "description": "描述",
      "user_name_prefix": "prefix",
      "bio": "个人简介",
      "system_message": "系统提示词",
      "initial_posts": ["帖子1", "帖子2"],
      "comment_style": "评论风格"
    }
  ]
}
```

## 核心方法

### `add_controlled_agents_batch(intervention_types, initial_step=True)`

批量添加 controlled agents（从配置文件加载）

**参数：**
- `intervention_types`: List[str] - 干预类型列表
- `initial_step`: bool - 是否执行初始发帖

**返回：**
```python
{
    "status": "ok",
    "created_agents": [...],
    "total": 3
}
```

### `add_controlled_agent(user_name, content, bio)`

添加单个 controlled agent（自定义）

**参数：**
- `user_name`: str - 用户名
- `content`: str - 首次发帖内容
- `bio`: str - 个人简介

### `force_agent_post(agent_id, content, refresh_recsys=True)`

强制指定 agent 发帖

### `force_agent_comment(agent_id, post_id, content, refresh_recsys=True)`

强制指定 agent 评论

### `list_controlled_agents()`

列出所有 controlled agents

## 验证标准

### 功能正确性
- ✅ Controlled agents 成功添加并执行初始发帖
- ✅ 配置文件正确加载和解析
- ✅ 不同类型的 agents 有不同的行为风格

### 干预效果
- ✅ 极化率有可观察的变化
- ✅ Controlled agents 的帖子对其他 agents 可见

### 推荐系统刷新
- ✅ 其他 agents 能看到 controlled agents 的帖子
- ✅ 可能产生评论和互动

## 故障排除

### 问题：配置文件未加载

**解决方法：** 检查 `oasis_dashboard/prompts/intervention.json` 是否存在，格式是否正确。

### 问题：Controlled agents 的帖子不可见

**解决方法：** 确保 `refresh_recsys=True`（默认为 True）

### 问题：Agent ID 冲突

**解决方法：** 使用 `_get_next_agent_id()` 方法自动分配不冲突的 ID

## 相关文件

- `oasis_dashboard/real_oaseis_engine_v3.py` - 核心引擎
- `oasis_dashboard/prompts/intervention.json` - 干预配置
- `tests/scripts/test_intervention_config.py` - 配置测试脚本
- `tests/scripts/test_e2e_simulation.py` - E2E 测试（已集成干预功能）
