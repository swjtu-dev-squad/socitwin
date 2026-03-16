# OASIS 数据格式要求文档

本文档详细说明了OASIS项目中用户画像、话题集、社交关系三大核心数据的格式要求。

---

## 📋 一、用户画像数据格式

### 1.1 核心数据结构

**Python后端结构**：
```python
@dataclass
class UserInfo:
    user_name: str              # 用户名（必填，唯一）
    name: str                    # 显示名称（必填）
    description: str             # 用户描述（必填）
    profile: Dict[str, Any]     # 用户画像字典（可选但推荐）
    recsys_type: str            # 推荐系统类型（reddit/twitter）
```

**详细Profile结构**：
```python
agent_profile = {
    "other_info": {
        "user_profile": str,     # ⭐ 最重要字段 - LLM内容生成核心指令
        "gender": str,           # 性别
        "age": int,              # 年龄
        "mbti": str,             # MBTI性格类型
        "country": str,          # 国家/地区
    }
}
```

### 1.2 完整示例

**JSON格式**：
```json
[
  {
    "agent_id": 0,
    "user_name": "user_alice",
    "name": "Alice Chen",
    "description": "Tech enthusiast from San Francisco",
    "profile": {
      "other_info": {
        "user_profile": "Discuss AI, technology, and digital innovation from US perspective.",
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
    "description": "Politics enthusiast from London",
    "profile": {
      "other_info": {
        "user_profile": "Discuss politics, government policies, and current events from UK perspective.",
        "gender": "male",
        "age": 35,
        "mbti": "ENTJ",
        "country": "UK"
      }
    },
    "recsys_type": "reddit"
  }
]
```

**CSV格式示例**：
```csv
agent_id,user_name,name,description,user_profile,gender,age,mbti,country,recsys_type
0,user_alice,Alice Chen,Tech enthusiast from San Francisco,"Discuss AI, technology, and digital innovation from US perspective.",female,28,INTJ,USA,reddit
1,user_bob,Bob Smith,Politics enthusiast from London,"Discuss politics, government policies, and current events from UK perspective.",male,35,ENTJ,UK,reddit
```

### 1.3 字段详细说明

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|:----:|------|--------|
| `agent_id` | `int` | ✅ | Agent的唯一ID，从0开始递增 | 0, 1, 2 |
| `user_name` | `str` | ✅ | 用户的唯一标识符，在整个模拟中必须唯一 | "agent_0", "user_alice" |
| `name` | `str` | ✅ | 用户的显示名称 | "Alice Chen" |
| `description` | `str` | ✅ | 对用户的简短描述 | "Tech enthusiast from SF" |
| `profile.other_info.user_profile` | `str` | ⭐ | **最重要的字段**，LLM生成内容时的核心指令 | "Discuss AI and technology..." |
| `profile.other_info.gender` | `str` | ❌ | 性别 | "male", "female", "unknown" |
| `profile.other_info.age` | `int` | ❌ | 年龄 | 25, 30, 45 |
| `profile.other_info.mbti` | `str` | ❌ | MBTI性格类型 | "INTJ", "ENFP", "UNKNOWN" |
| `profile.other_info.country` | `str` | ❌ | 国家/地区 | "USA", "UK", "China" |
| `recsys_type` | `str` | ❌ | 推荐系统类型，支持 `"reddit"` 或 `"twitter"`（小写） | "reddit", "twitter" |

### 1.4 数据验证规则

#### 必填字段验证
- ✅ `user_name`: 必须非空且在整个模拟中唯一
- ✅ `name`: 必须非空
- ✅ `description`: 必须非空
- ⚠️ `profile["other_info"]["user_profile"]`: 强烈推荐填写，这是LLM生成内容的核心指令

#### 唯一性要求
- 每个 `SocialAgent` 必须有唯一的 `agent_id`
- 每个 `user_name` 在整个模拟中必须唯一

#### 平台类型要求
- `recsys_type` 支持：`"reddit"` 或 `"twitter"`
- 必须使用**小写**

#### MBTI 类型规范
推荐使用标准的16种MBTI类型：
- **分析型**: INTJ, INTP
- **远见型**: ENTJ, ENTP
- **理想主义型**: INFJ, INFP
- **外交型**: ENFJ, ENFP
- **守护型**: ISTJ, ISFJ
- **公务型**: ESTJ, ESFJ
- **探索型**: ISTP, ISFP
- **表演型**: ESTP, ESFP

也可以使用 `"UNKNOWN"` 表示未知。

### 1.5 user_profile 字段的重要性

`user_profile` 是最重要的字段，它直接影响LLM生成的内容。建议：

1. **具体明确**: 清晰描述用户的兴趣和话题方向
2. **包含上下文**: 添加地区、文化背景等信息
3. **长度适中**: 1-2句话即可，避免过长导致token浪费

**好的示例**:
```python
"user_profile": "Discuss AI, technology, and digital innovation from US perspective."
```

**不好的示例**:
```python
"user_profile": "I like many things and want to talk about stuff."  # 太模糊
```

---

## 🏷️ 二、话题集数据格式

### 2.1 预定义话题类别

**支持的6大话题类别**：
```typescript
const TOPICS = [
  "POLITICS",      // 政治
  "AI",            // AI & 科技
  "ENTERTAINMENT", // 娱乐
  "HEALTH",        // 健康
  "TRAVEL",        // 旅行
  "FOOD"           // 美食
]
```

### 2.2 话题配置结构

**API请求格式**：
```typescript
interface TopicConfig {
  topics?: string[];        // 多话题数组
  regions?: string[];       // 多地区数组
  platform: string;         // 平台类型
  recsys: string;           // 推荐算法
  agentCount: number;       // Agent数量
}
```

**完整配置示例**：
```json
{
  "config": {
    "platform": "REDDIT",
    "recsys": "HOT",
    "agentCount": 1000,
    "topics": ["POLITICS", "AI"],
    "regions": ["THAILAND", "CAMBODIA"]
  },
  "topicInstructions": {
    "POLITICS": "Discuss politics, government policies, and current events from Thailand perspective.",
    "AI": "Discuss AI, technology, and digital innovation from Thailand perspective."
  },
  "regionContext": {
    "THAILAND": "Southeast Asian context",
    "CAMBODIA": "Southeast Asian context"
  }
}
```

### 2.3 话题指令映射

**话题生成指令**：
```python
topic_instructions = {
    "POLITICS": "Discuss politics, government policies, and current events.",
    "AI": "Discuss AI, technology, and digital innovation.",
    "ENTERTAINMENT": "Discuss movies, music, celebrities, and pop culture.",
    "HEALTH": "Discuss health, wellness, fitness, and medical topics.",
    "TRAVEL": "Discuss travel destinations and cultural experiences.",
    "FOOD": "Discuss recipes, restaurants, and food culture.",
}
```

### 2.4 支持的地区列表

```typescript
const REGIONS = [
  "THAILAND",    // 泰国
  "CAMBODIA",    // 柬埔寨
  "INDONESIA",   // 印度尼西亚
  "VIETNAM",     // 越南
  "MALAYSIA",    // 马来西亚
  "PHILIPPINES"  // 菲律宾
]
```

### 2.5 话题与用户的关联机制

- 每个用户在生成时会关联到指定的话题
- 话题影响用户的内容生成方向和兴趣
- 地区话题会添加本地化背景信息

**数据流向**：
1. **配置阶段**：选择话题和地区 → 生成用户画像
2. **模拟阶段**：话题约束 → Agent行为 → 内容生成
3. **分析阶段**：话题极化度 → 社会影响分析

---

## 🔗 三、社交关系数据格式

### 3.1 关系类型定义

**支持的关系类型**：
```typescript
export type RelationshipType =
  | 'follow'    // 关注（单向）
  | 'friend'    // 好友（双向）
  | 'mute'      // 静音
  | 'block'     // 拉黑
  | 'report';   // 举报
```

### 3.2 推荐的关系数据结构

**单个关系记录**：
```typescript
interface SocialRelationship {
  id: string;
  fromUserId: string;      // 关注者ID
  toUserId: string;        // 被关注者ID
  type: RelationshipType;
  createdAt: Date;         // 创建时间
  updatedAt: Date;         // 更新时间
  isActive: boolean;       // 是否活跃
  metadata?: Record<string, any>; // 额外属性
}
```

**用户网络结构**：
```typescript
interface UserNetwork {
  userId: string;
  followers: SocialRelationship[];    // 粉丝关系
  follows: SocialRelationship[];      // 关注关系
  friends: SocialRelationship[];      // 好友关系
  muted: SocialRelationship[];        // 静音关系
  blocked: SocialRelationship[];      // 拉黑关系
  statistics: {
    followersCount: number;
    followsCount: number;
    friendsCount: number;
    lastUpdated: Date;
  };
}
```

### 3.3 关系数据示例

**关系数据JSON格式**：
```json
[
  {
    "id": "rel_001",
    "fromUserId": "user_alice",
    "toUserId": "user_bob",
    "type": "follow",
    "createdAt": "2024-01-01T00:00:00Z",
    "updatedAt": "2024-01-01T00:00:00Z",
    "isActive": true
  },
  {
    "id": "rel_002",
    "fromUserId": "user_bob",
    "toUserId": "user_alice",
    "type": "follow",
    "createdAt": "2024-01-01T01:00:00Z",
    "updatedAt": "2024-01-01T01:00:00Z",
    "isActive": true
  },
  {
    "id": "rel_003",
    "fromUserId": "user_alice",
    "toUserId": "user_charlie",
    "type": "mute",
    "createdAt": "2024-01-02T00:00:00Z",
    "updatedAt": "2024-01-02T00:00:00Z",
    "isActive": true
  }
]
```

### 3.4 关系存储机制

**基于OASIS的AgentGraph**：
```python
from oasis import AgentGraph

# 关系更新操作
update_connections(agent, action)  # 动态更新代理连接

# 支持的动作
ActionType.FOLLOW      # 关注
ActionType.UNFOLLOW    # 取消关注
ActionType.MUTE        # 静音
ActionType.UNMUTE      # 取消静音
```

### 3.5 关系特征

- ✅ **方向性**：单向关注关系（A关注B ≠ B关注A）
- ✅ **时序性**：记录创建时间
- ✅ **动态性**：可在模拟中动态建立/解除
- ✅ **多类型**：支持follow、mute、block等多种关系类型

### 3.6 关系数据在模拟中的作用

1. **信息传播路径**：影响信息传播模式和速度
2. **社交影响计算**：基于关系网络计算影响力和极化程度
3. **群体行为预测**：通过关系结构预测群体决策和趋势
4. **实时监控**：动态追踪关系变化和网络演化
5. **可视化展示**：提供直观的社交网络图谱展示

---

## 📊 四、数据格式总结对比

| 数据类型 | 存储格式 | 必填字段 | 核心作用 | 文件位置示例 |
|---------|---------|---------|----------|-------------|
| **用户画像** | JSON/CSV | user_name, name, description, user_profile | 定义Agent身份和行为 | `reddit_user_data_36.json` |
| **话题集** | 配置数组 | topics (可选) | 约束内容生成方向 | 配置在API请求中 |
| **社交关系** | Graph/JSON | fromUserId, toUserId, type | 构建社交网络结构 | 动态构建/可导入 |

### 数据层级结构

```
Simulation Level
├── Platform (Reddit/X/Facebook/TikTok/Instagram)
├── Recommendation System (Hot-score/TwHIN-BERT/ForYou/EdgeRank)
├── Topics Array (支持多话题)
│   ├── Topic ID (字符串标识符)
│   ├── Topic Instructions (生成指令)
│   └── Region Context (地区背景)
├── Regions Array (支持多地区)
│   ├── Region ID (字符串标识符)
│   └── Cultural Context (文化背景)
└── Agent Graph
    ├── User Profiles (用户画像)
    ├── Social Relationships (社交关系)
    └── Agent States (Agent状态)
```

---

## 🔑 五、关键要点

### 用户画像关键点
- ⭐ `user_profile` 是最重要的字段，直接影响LLM内容生成
- 需要**具体明确**的描述，避免模糊表述
- 建议包含**地区和文化背景**信息
- 保持1-2句话的长度，避免token浪费

### 话题集关键点
- 支持多话题、多地区的**组合配置**
- 话题与地区结合，实现**本地化内容生成**
- 预定义6大话题类别，覆盖主要社交场景
- 话题指令会被添加到每个Agent的系统提示中

### 社交关系关键点
- 基于有向图结构，支持**单向关注关系**
- 关系数据影响**信息传播和极化分析**
- 可结合Neo4j等图数据库进行**可视化展示**
- 支持动态更新，可在模拟过程中实时变化

---

## 📁 六、相关文件位置

| 文件路径 | 描述 |
|---------|------|
| `/src/lib/types.ts` | TypeScript类型定义 |
| `/src/pages/Profiles.tsx` | 用户画像生成界面 |
| `/docs/USER_DATASET_FORMAT.md` | 用户数据集格式说明 |
| `/oasis_dashboard/context/config.py` | 运行时配置 |
| `/oasis_dashboard/real_oasis_engine_v3.py` | OASIS引擎核心逻辑 |
| `/oasis_dashboard/polarization_analyzer.py` | 极化分析器 |

---

## 📝 七、数据准备建议

### 7.1 用户画像准备
1. 确保每个用户有唯一的 `user_name`
2. `user_profile` 字段要具体、明确
3. 建议添加年龄、性别、MBTI等属性增加多样性
4. 根据目标地区设置合适的 `country` 字段

### 7.2 话题集准备
1. 从预定义的6个话题类别中选择
2. 可以组合多个话题进行模拟
3. 结合地区配置实现本地化
4. 测试不同话题组合对极化的影响

### 7.3 社交关系准备
1. 基于真实社交网络数据或随机生成
2. 确保关系数据的方向性正确
3. 记录关系的创建时间用于时序分析
4. 考虑不同关系类型对传播的影响

---

## 🚀 八、快速开始示例

### 8.1 创建用户数据集

```bash
# 生成100个Reddit用户，关注AI和POLITICS话题
POST /api/users/generate
{
  "platform": "REDDIT",
  "count": 100,
  "seed": 42,
  "topics": ["AI", "POLITICS"],
  "regions": ["THAILAND"]
}
```

### 8.2 配置模拟环境

```bash
# 配置模拟参数
POST /api/sim/config
{
  "platform": "REDDIT",
  "recsys": "HOT",
  "agentCount": 1000,
  "topics": ["AI", "POLITICS"],
  "regions": ["THAILAND", "CAMBODIA"]
}
```

### 8.3 导入社交关系

社交关系通常在模拟过程中动态生成，也可以通过ManualAction预置：

```python
from oasis import ManualAction, ActionType

# 让agent_0关注agent_1
action = ManualAction(
    action_type=ActionType.FOLLOW,
    action_args={"followee_id": 1}
)
```

---

*文档版本: v1.0*
*最后更新: 2026-03-16*
*基于项目: oasis-dashboard*
