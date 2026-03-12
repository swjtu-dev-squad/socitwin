# OASIS 用户数据集格式说明

本文档详细说明 OASIS Dashboard 中用户数据集（UserInfo）的格式要求。

## 目录

1. [UserInfo 基本结构](#userinfo-基本结构)
2. [Profile 字典格式](#profile-字典格式)
3. [实际示例](#实际示例)
4. [JSON 数据集格式](#json-数据集格式)
5. [自定义模板](#自定义模板)
6. [注意事项](#注意事项)

---

## UserInfo 基本结构

`UserInfo` 是一个 dataclass，包含智能体的用户注册信息。

```python
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class UserInfo:
    user_name: str                    # 用户名（必填，唯一）
    name: str                          # 显示名称（必填）
    description: str                   # 用户描述（必填）
    profile: Dict[str, Any]           # 用户画像字典（可选但推荐）
    recsys_type: str                  # 推荐系统类型（reddit/twitter）
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_name` | `str` | ✔ | 用户的唯一标识符，在整个模拟中必须唯一 |
| `name` | `str` | ✔ | 用户的显示名称 |
| `description` | `str` | ✔ | 对用户的简短描述 |
| `profile` | `dict` | ✗ | 包含用户详细画像的字典 |
| `recsys_type` | `str` | ✗ | 推荐系统类型，支持 `"reddit"` 或 `"twitter"`（小写） |

---

## Profile 字典格式

`profile` 字典必须包含 `other_info` 键，内部字段结构如下：

### Reddit 风格模板（默认）

当使用默认的 Reddit 模板时，`profile` 应包含以下字段：

```python
agent_profile = {
    "other_info": {
        "user_profile": str,          # 用户个性/兴趣描述（核心）
        "gender": str,                # 性别
        "age": int,                   # 年龄
        "mbti": str,                  # MBTI 性格类型
        "country": str,               # 国家/地区
    }
}
```

### 字段详细说明

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| `user_profile` | `str` | ✔ | **最重要的字段**，LLM 生成内容时的核心指令 | "Discuss AI, technology, and digital innovation." |
| `gender` | `str` | ✗ | 性别 | "male", "female", "unknown" |
| `age` | `int` | ✗ | 年龄 | 25, 30, 45 |
| `mbti` | `str` | ✗ | MBTI 性格类型 | "INTJ", "ENFP", "UNKNOWN" |
| `country` | `str` | ✗ | 国家/地区 | "USA", "UK", "China" |

---

## 实际示例

### 示例 1：基础 AI 话题智能体

```python
agent_profile = {
    "other_info": {
        "user_profile": "Discuss AI, technology, and digital innovation from US.",
        "gender": "unknown",
        "age": 25,
        "mbti": "UNKNOWN",
        "country": "US",
    }
}

agent = SocialAgent(
    agent_id=0,
    user_info=UserInfo(
        user_name="agent_0",
        name="Agent 0",
        description="AI agent 0 - Topic: AI, Region: US",
        profile=agent_profile,
        recsys_type="reddit",
    ),
    agent_graph=agent_graph,
    model=model,
)
```

### 示例 2：政治话题智能体

```python
agent_profile = {
    "other_info": {
        "user_profile": "Discuss politics, government policies, and current events from European perspective.",
        "gender": "male",
        "age": 35,
        "mbti": "ENTJ",
        "country": "Germany",
    }
}

agent = SocialAgent(
    agent_id=1,
    user_info=UserInfo(
        user_name="political_user_de",
        name="Hans Mueller",
        description="Political science enthusiast from Berlin",
        profile=agent_profile,
        recsys_type="reddit",
    ),
    agent_graph=agent_graph,
    model=model,
)
```

### 示例 3：娱乐话题智能体

```python
agent_profile = {
    "other_info": {
        "user_profile": "Discuss movies, music, celebrities, and pop culture trends.",
        "gender": "female",
        "age": 22,
        "mbti": "ESFP",
        "country": "USA",
    }
}

agent = SocialAgent(
    agent_id=2,
    user_info=UserInfo(
        user_name="entertainment_fan",
        name="Sophia Chen",
        description="Pop culture blogger from Los Angeles",
        profile=agent_profile,
        recsys_type="twitter",
    ),
    agent_graph=agent_graph,
    model=model,
)
```

---

## JSON 数据集格式

如果准备外部数据集（如 JSON 文件），应按以下格式：

### 完整 JSON 示例

```json
[
  {
    "agent_id": 0,
    "user_name": "user_alice",
    "name": "Alice Chen",
    "description": "Tech enthusiast from San Francisco",
    "profile": {
      "other_info": {
        "user_profile": "Discuss technology, AI, and startup culture. Interested in innovation and digital trends from Silicon Valley perspective.",
        "gender": "female",
        "age": 28,
        "mbti": "INTJ",
        "country": "USA"
      }
    },
    "recsys_type": "reddit"
  },
  {
    "agent_id": 1,
    "user_name": "user_bob",
    "name": "Bob Smith",
    "description": "Political science student from London",
    "profile": {
      "other_info": {
        "user_profile": "Discuss politics, government policies, and current events from European perspective. Focus on UK politics and Brexit aftermath.",
        "gender": "male",
        "age": 22,
        "mbti": "ENFP",
        "country": "UK"
      }
    },
    "recsys_type": "reddit"
  },
  {
    "agent_id": 2,
    "user_name": "user_charlie",
    "name": "Charlie Davis",
    "description": "Health and wellness advocate from Australia",
    "profile": {
      "other_info": {
        "user_profile": "Discuss health, wellness, fitness, and medical topics. Promote healthy lifestyle and mental health awareness.",
        "gender": "male",
        "age": 31,
        "mbti": "INFJ",
        "country": "Australia"
      }
    },
    "recsys_type": "twitter"
  }
]
```

### CSV 格式示例

如果使用 CSV 格式，建议按以下结构：

```csv
agent_id,user_name,name,description,user_profile,gender,age,mbti,country,recsys_type
0,user_alice,Alice Chen,Tech enthusiast from San Francisco,"Discuss technology, AI, and startup culture.",female,28,INTJ,USA,reddit
1,user_bob,Bob Smith,Political science student from London,"Discuss politics and government policies.",male,22,ENFP,UK,reddit
2,user_charlie,Charlie Davis,Health advocate from Australia,"Discuss health and wellness topics.",male,31,INFJ,Australia,twitter
```

---

## 自定义模板

如果想使用自定义 `user_info_template`，可以定义任意字段：

### 自定义模板示例

```python
from camel.prompts import TextPrompt

# 定义自定义模板
seller_template = TextPrompt(
    'Your aim is: {aim} Your task is: {task}'
)

# 对应的 profile 字典
profile = {
    "aim": "Persuade people to buy GlowPod lamp.",
    "task": "Using roleplay to tell some story about the product.",
}

# 使用自定义模板创建 agent
agent = SocialAgent(
    agent_id=3,
    user_info=UserInfo(
        user_name="seller_1",
        name="Sales Agent",
        description="Product salesperson",
        profile=profile,  # profile 中的键必须与模板匹配
        recsys_type="reddit",  # 使用自定义模板时此参数被忽略
    ),
    agent_graph=agent_graph,
    model=model,
    user_info_template=seller_template,  # 传入自定义模板
)
```

---

## 注意事项

### 必填字段

- ✅ `user_name`: 必须非空且在整个模拟中唯一
- ✅ `name`: 必须非空
- ✅ `description`: 必须非空
- ⚠️ `profile["other_info"]["user_profile"]`: 强烈推荐填写，这是 LLM 生成内容的核心指令

### 唯一性要求

- 每个 `SocialAgent` 必须有唯一的 `agent_id`
- 每个 `user_name` 在整个模拟中必须唯一

### 平台类型

- `recsys_type` 支持：
  - `"reddit"` - 使用 Reddit 风格的系统提示
  - `"twitter"` - 使用 Twitter 风格的系统提示
- 必须使用**小写**

### MBTI 类型

推荐使用标准的 16 种 MBTI 类型：

| 类型 | 描述 |
|------|------|
| INTJ, INTP | 分析型 |
| ENTJ, ENTP | 远见型 |
| INFJ, INFP | 理想主义型 |
| ENFJ, ENFP | 外交型 |
| ISTJ, ISFJ | 守护型 |
| ESTJ, ESFJ | 公务型 |
| ISTP, ISFP | 探险型 |
| ESTP, ESFP | 表演型 |

也可以使用 `"UNKNOWN"` 表示未知。

### user_profile 字段的重要性

`user_profile` 是最重要的字段，它直接影响 LLM 生成的内容。建议：

1. **具体明确**: 清晰描述用户的兴趣和话题方向
2. **包含上下文**: 添加地区、文化背景等信息
3. **长度适中**: 1-2 句话即可，避免过长导致 token 浪费

**好的示例**:
```python
"user_profile": "Discuss AI, technology, and digital innovation from US perspective."
```

**不好的示例**:
```python
"user_profile": "I like many things and want to talk about stuff."  # 太模糊
```

---

## 参考资料

- [Social Agent - OASIS Documentation](https://docs.oasis.camel-ai.org/key_modules/social_agent)
- [CAMEL-AI OASIS GitHub](https://github.com/camel-ai/oasis)
- [项目 README](../README.md)
- [开发者手册](./DEVELOPER_MANUAL.md)

---

**文档版本**: v1.0.0
**最后更新**: 2026年3月12日
