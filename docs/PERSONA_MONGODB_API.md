# Persona MongoDB 存储接口文档

本文档说明如何使用 Persona 模块的 MongoDB 存储接口，用于存储和管理用户画像数据。

## 概述

Persona 模块用于存储社交平台的用户画像数据，支持多平台数据隔离。数据存储在 MongoDB 中，按 `recsys_type` 字段区分不同平台。

### 支持的平台

| recsys_type | 平台 |
|-------------|------|
| `twitter` | X / Twitter |
| `reddit` | Reddit |
| `tiktok` | TikTok |
| `instagram` | Instagram |
| `facebook` | Facebook |

### 数据存储结构

| Collection | 说明 | recsys_type |
|-----------|------|-------------|
| `users` | 用户数据 | 原字段已有 |
| `posts` | 帖子数据 | 导入时自动添加 |
| `replies` | 回复数据 | 导入时自动添加 |
| `relationships` | 关注关系 | 导入时自动添加 |
| `networks` | 社交网络 | 导入时自动添加 |
| `topics` | 话题分类 | 导入时自动添加（拆成3条） |

---

## 环境配置

在 `.env` 文件中配置 MongoDB 连接：

```bash
MONGODB_URI=mongodb://username:password@host:port/dbname?authSource=admin
MONGODB_DATABASE=oasis_dataset
```

> 注意：密码中如含特殊字符（如 `@`），需进行 URL 编码，例如 `@` → `%40`。

---

## API 接口

### 1. 导入数据

**请求**

```
POST /api/persona/mongodb/import
Content-Type: multipart/form-data
```

**参数**

| 参数 | 类型 | 必填 | 可填值 | 说明 |
|-----|------|-----|--------|------|
| file | File | 是 | — | JSON 文件 |
| recsys_type | string | 是 | `twitter` `reddit` `tiktok` `instagram` `facebook` | 平台标识 |
| type | string | 是 | `users` `posts` `replies` `relationships` `networks` `topics` | 数据类型 |

**响应**

```json
{
  "status": "success",
  "recsys_type": "twitter",
  "type": "users",
  "imported": 36248
}
```

**示例：导入 Twitter 全部数据**

```bash
# 1. 用户数据
curl -X POST http://localhost:3000/api/persona/mongodb/import \
  -F "file=@dataset/twitter/users.json" \
  -F "recsys_type=twitter" \
  -F "type=users"

# 2. 帖子数据
curl -X POST http://localhost:3000/api/persona/mongodb/import \
  -F "file=@dataset/twitter/posts.json" \
  -F "recsys_type=twitter" \
  -F "type=posts"

# 3. 回复数据
curl -X POST http://localhost:3000/api/persona/mongodb/import \
  -F "file=@dataset/twitter/replies.json" \
  -F "recsys_type=twitter" \
  -F "type=replies"

# 4. 关注关系
curl -X POST http://localhost:3000/api/persona/mongodb/import \
  -F "file=@dataset/twitter/relationships.json" \
  -F "recsys_type=twitter" \
  -F "type=relationships"

# 5. 社交网络
curl -X POST http://localhost:3000/api/persona/mongodb/import \
  -F "file=@dataset/twitter/user_networks.json" \
  -F "recsys_type=twitter" \
  -F "type=networks"

# 6. 话题分类
curl -X POST http://localhost:3000/api/persona/mongodb/import \
  -F "file=@dataset/twitter/topics_classification.json" \
  -F "recsys_type=twitter" \
  -F "type=topics"
```

---

### 2. 获取平台统计

**请求**

```
GET /api/persona/:recsys_type/stats
```

**路径参数**

| 参数 | 类型 | 可填值 | 说明 |
|-----|------|--------|------|
| recsys_type | string | `twitter` `reddit` `tiktok` `instagram` `facebook` | 平台标识 |

**响应**

```json
{
  "recsys_type": "twitter",
  "stats": {
    "users": 36248,
    "posts": 22170,
    "replies": 198838,
    "relationships": 106498,
    "networks": 239115,
    "topics": 3
  }
}
```

**示例**

```bash
curl http://localhost:3000/api/persona/twitter/stats
curl http://localhost:3000/api/persona/reddit/stats
curl http://localhost:3000/api/persona/tiktok/stats
curl http://localhost:3000/api/persona/instagram/stats
curl http://localhost:3000/api/persona/facebook/stats
```

---

### 3. 获取指定类型数据

**请求**

```
GET /api/persona/:recsys_type/:type
```

**路径参数**

| 参数 | 类型 | 可填值 | 说明 |
|-----|------|--------|------|
| recsys_type | string | `twitter` `reddit` `tiktok` `instagram` `facebook` | 平台标识 |
| type | string | `users` `posts` `replies` `relationships` `networks` `topics` | 数据类型 |

**响应**

```json
{
  "recsys_type": "twitter",
  "type": "users",
  "stats": {
    "count": 36248
  },
  "data": [
    {
      "agent_id": 0,
      "user_name": "thai_politics_analyst",
      "name": "Somsak Chaiyaporn",
      "description": "Political researcher...",
      "profile": { "other_info": { "topics": ["Thai Politics"], "gender": null, "age": null, "mbti": null, "country": null } },
      "recsys_type": "twitter",
      "user_type": "kol"
    }
  ]
}
```

> 注意：返回数据不含 MongoDB 的 `_id` 字段。

**示例**

```bash
# Twitter
curl http://localhost:3000/api/persona/twitter/users
curl http://localhost:3000/api/persona/twitter/posts
curl http://localhost:3000/api/persona/twitter/replies
curl http://localhost:3000/api/persona/twitter/relationships
curl http://localhost:3000/api/persona/twitter/networks
curl http://localhost:3000/api/persona/twitter/topics

# Reddit
curl http://localhost:3000/api/persona/reddit/users

# TikTok
curl http://localhost:3000/api/persona/tiktok/users

# Instagram
curl http://localhost:3000/api/persona/instagram/users

# Facebook
curl http://localhost:3000/api/persona/facebook/users
```

---

## 数据格式要求

### 标准文件结构

所有平台的数据文件结构统一，以 `dataset/twitter/` 为标准：

```
dataset/{platform}/
├── users.json                  # 用户数据
├── posts.json                  # 帖子数据
├── replies.json                # 回复数据
├── relationships.json          # 关注关系
├── user_networks.json          # 社交网络
└── topics_classification.json  # 话题分类
```

### users.json 格式

```json
[
  {
    "agent_id": 0,
    "user_name": "thai_politics_analyst",
    "name": "Somsak Chaiyaporn",
    "description": "Political researcher...",
    "profile": {
      "other_info": {
        "topics": ["Thai Politics"],
        "gender": null,
        "age": null,
        "mbti": null,
        "country": null
      }
    },
    "recsys_type": "twitter",
    "user_type": "kol"
  }
]
```

### posts.json 格式

```json
[
  {
    "post_id": 0,
    "post_user": "coalition_watch_th",
    "agent_id": "8",
    "content": "Anutin Charnvirakul secures a second term...",
    "createdAt": "2026-02-26T07:14:46.845526"
  }
]
```

### replies.json 格式

```json
[
  {
    "reply_id": 0,
    "reply_user": "Friendship_IL_TH",
    "re_agent_id": "1263",
    "post_id": 1,
    "post_user": "political_arch_th",
    "content": "@political_arch_th The real test is...",
    "createdAt": "2026-02-23T18:17:46.913648"
  }
]
```

### relationships.json 格式

```json
[
  {
    "id": "rel_000001",
    "fromUserId": "user_270",
    "toUserId": "user_7",
    "type": "follow",
    "createdAt": "2024-04-05T00:00:00Z",
    "updatedAt": "2024-11-15T00:00:00Z",
    "isActive": true
  }
]
```

### user_networks.json 格式

```json
[
  {
    "userId": "user_0",
    "followers": [
      {
        "id": "rel_000008",
        "fromUserId": "user_273",
        "toUserId": "user_0",
        "type": "follow",
        "createdAt": "2024-05-05T00:00:00Z",
        "updatedAt": "2024-10-29T00:00:00Z",
        "isActive": true
      }
    ]
  }
]
```

### topics_classification.json 格式

```json
{
  "Politics": ["Civic Engagement", "Thai Politics", "..."],
  "Economics": ["Digital Economy", "banking", "..."],
  "Society": ["Thai food", "travel", "..."]
}
```

> 注意：`topics_classification.json` 是对象结构（非数组），导入时会被自动拆成 3 条文档存储，每条对应一个分类（Politics / Economics / Society）。

---

## MongoDB 存储示例

### users Collection

```javascript
{
  "agent_id": 0,
  "user_name": "thai_politics_analyst",
  "name": "Somsak Chaiyaporn",
  "description": "Political researcher...",
  "profile": { ... },
  "recsys_type": "twitter",
  "user_type": "kol"
}
```

### posts / replies / relationships / networks Collection

```javascript
// 导入时自动添加 recsys_type
{
  "recsys_type": "twitter",
  "post_id": 0,
  "post_user": "coalition_watch_th",
  "agent_id": "8",
  "content": "...",
  "createdAt": "..."
}
```

### topics Collection

```javascript
// topics_classification.json 拆成 3 条文档
{ "recsys_type": "twitter", "category": "Politics",  "topics": ["Civic Engagement", "Thai Politics", "..."] }
{ "recsys_type": "twitter", "category": "Economics", "topics": ["Digital Economy", "banking", "..."] }
{ "recsys_type": "twitter", "category": "Society",   "topics": ["Thai food", "travel", "..."] }
```

---

## 前端调用示例

```typescript
// 导入数据
const formData = new FormData();
formData.append("file", file);
formData.append("recsys_type", "twitter");
formData.append("type", "users");

await fetch("/api/persona/mongodb/import", {
  method: "POST",
  body: formData,
});

// 获取统计
const { stats } = await fetch("/api/persona/twitter/stats").then(r => r.json());

// 获取指定类型数据
const { data, stats: typeStats } = await fetch("/api/persona/twitter/users").then(r => r.json());
```

---

## 注意事项

1. **重复导入**：当前实现为直接插入，重复导入同一文件会导致数据重复，建议导入前确认数据库是否已有该平台数据。

2. **大数据量**：`replies` 和 `networks` 数据量较大（~20万条），`/api/persona/:recsys_type/:type` 接口会全量返回，请注意前端内存和网络开销。

3. **recsys_type 大小写**：平台标识统一使用小写（`twitter` 而非 `Twitter`），与 `users.json` 中的 `recsys_type` 字段保持一致。

4. **topics 特殊处理**：`topics_classification.json` 为对象结构，导入时自动拆成 3 条文档（Politics、Economics、Society）存入 `topics` Collection。

5. **返回数据**：所有查询接口返回数据均不含 MongoDB 内部 `_id` 字段。

---

**文档版本**: v1.1.0
**最后更新**: 2026-03-31


---

## 环境配置

在 `.env` 文件中配置 MongoDB 连接：

```bash
MONGODB_URI=mongodb://username:password@host:port
MONGODB_DATABASE=oasis_dataset
```

---

## API 接口

### 1. 导入数据

**请求**

```
POST /api/persona/mongodb/import
Content-Type: multipart/form-data
```

**参数**

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| file | File | 是 | JSON 文件 |
| recsys_type | string | 是 | 平台标识，如 `twitter`、`reddit` |
| type | string | 是 | 数据类型：`users`、`posts`、`replies`、`relationships`、`networks`、`topics` |

**响应**

```json
{
  "status": "success",
  "recsys_type": "twitter",
  "type": "users",
  "imported": 36248
}
```

**示例**

```bash
# 导入用户数据
curl -X POST http://localhost:3000/api/persona/mongodb/import \
  -F "file=@dataset/twitter/users.json" \
  -F "recsys_type=twitter" \
  -F "type=users"

# 导入帖子数据
curl -X POST http://localhost:3000/api/persona/mongodb/import \
  -F "file=@dataset/twitter/posts.json" \
  -F "recsys_type=twitter" \
  -F "type=posts"

# 导入回复数据
curl -X POST http://localhost:3000/api/persona/mongodb/import \
  -F "file=@dataset/twitter/replies.json" \
  -F "recsys_type=twitter" \
  -F "type=replies"

# 导入关注关系
curl -X POST http://localhost:3000/api/persona/mongodb/import \
  -F "file=@dataset/twitter/relationships.json" \
  -F "recsys_type=twitter" \
  -F "type=relationships"

# 导入社交网络
curl -X POST http://localhost:3000/api/persona/mongodb/import \
  -F "file=@dataset/twitter/user_networks.json" \
  -F "recsys_type=twitter" \
  -F "type=networks"

# 导入话题分类
curl -X POST http://localhost:3000/api/persona/mongodb/import \
  -F "file=@dataset/twitter/topics_classification.json" \
  -F "recsys_type=twitter" \
  -F "type=topics"
```

---

### 2. 获取平台统计

**请求**

```
GET /api/persona/:recsys_type/stats
```

**参数**

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| recsys_type | string | 是 | 平台标识（URL 路径参数） |

**响应**

```json
{
  "recsys_type": "twitter",
  "stats": {
    "users": 36248,
    "posts": 22170,
    "replies": 198838,
    "relationships": 106498,
    "networks": 239115,
    "topics": 3
  }
}
```

**示例**

```bash
curl http://localhost:3000/api/persona/twitter/stats
```

---

### 3. 获取指定类型数据

**请求**

```
GET /api/persona/:recsys_type/:type
```

**参数**

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| recsys_type | string | 是 | 平台标识（URL 路径参数） |
| type | string | 是 | 数据类型：`users`、`posts`、`replies`、`relationships`、`networks`、`topics` |

**响应**

```json
{
  "recsys_type": "twitter",
  "type": "users",
  "stats": {
    "count": 36248
  },
  "data": [
    {
      "agent_id": 0,
      "user_name": "thai_politics_analyst",
      "name": "Somsak Chaiyaporn",
      "description": "Political researcher...",
      "profile": { ... },
      "recsys_type": "twitter",
      "user_type": "kol"
    }
  ]
}
```

**示例**

```bash
# 获取用户数据
curl http://localhost:3000/api/persona/twitter/users

# 获取帖子数据
curl http://localhost:3000/api/persona/twitter/posts

# 获取回复数据
curl http://localhost:3000/api/persona/twitter/replies

# 获取关注关系
curl http://localhost:3000/api/persona/twitter/relationships

# 获取社交网络
curl http://localhost:3000/api/persona/twitter/networks

# 获取话题分类
curl http://localhost:3000/api/persona/twitter/topics
```

---

## 数据格式要求

### 标准文件结构

```
dataset/{platform}/
├── users.json                  # 用户数据
├── posts.json                  # 帖子数据
├── replies.json                # 回复数据
├── relationships.json          # 关注关系
├── user_networks.json          # 社交网络
└── topics_classification.json  # 话题分类
```

### users.json 格式

```json
[
  {
    "agent_id": 0,
    "user_name": "thai_politics_analyst",
    "name": "Somsak Chaiyaporn",
    "description": "Political researcher...",
    "profile": {
      "other_info": {
        "topics": ["Thai Politics"],
        "gender": null,
        "age": null,
        "mbti": null,
        "country": null
      }
    },
    "recsys_type": "twitter",
    "user_type": "kol"
  }
]
```

### posts.json 格式

```json
[
  {
    "post_id": 0,
    "post_user": "coalition_watch_th",
    "agent_id": "8",
    "content": "Anutin Charnvirakul secures a second term...",
    "createdAt": "2026-02-26T07:14:46.845526"
  }
]
```

### replies.json 格式

```json
[
  {
    "reply_id": 0,
    "reply_user": "Friendship_IL_TH",
    "re_agent_id": "1263",
    "post_id": 1,
    "post_user": "political_arch_th",
    "content": "@political_arch_th The real test is...",
    "createdAt": "2026-02-23T18:17:46.913648"
  }
]
```

### relationships.json 格式

```json
[
  {
    "id": "rel_000001",
    "fromUserId": "user_270",
    "toUserId": "user_7",
    "type": "follow",
    "createdAt": "2024-04-05T00:00:00Z",
    "updatedAt": "2024-11-15T00:00:00Z",
    "isActive": true
  }
]
```

### user_networks.json 格式

```json
[
  {
    "userId": "user_0",
    "followers": [
      {
        "id": "rel_000008",
        "fromUserId": "user_273",
        "toUserId": "user_0",
        "type": "follow",
        "createdAt": "2024-05-05T00:00:00Z",
        "updatedAt": "2024-10-29T00:00:00Z",
        "isActive": true
      }
    ]
  }
]
```

### topics_classification.json 格式

```json
{
  "Politics": ["Civic Engagement", "Thai Politics", ...],
  "Economics": ["Digital Economy", "banking", ...],
  "Society": ["Thai food", "travel", ...]
}
```

> 注意：topics_classification.json 会被拆成 3 条文档存储，每条对应一个分类。

---

## MongoDB 存储示例

### users Collection

```javascript
{
  "_id": ObjectId("..."),
  "agent_id": 0,
  "user_name": "thai_politics_analyst",
  "name": "Somsak Chaiyaporn",
  "description": "Political researcher...",
  "profile": { ... },
  "recsys_type": "twitter",
  "user_type": "kol"
}
```

### posts Collection

```javascript
{
  "_id": ObjectId("..."),
  "recsys_type": "twitter",  // 导入时自动添加
  "post_id": 0,
  "post_user": "coalition_watch_th",
  "agent_id": "8",
  "content": "...",
  "createdAt": "..."
}
```

### topics Collection

```javascript
// topics 会被拆成 3 条文档
[
  {
    "_id": ObjectId("..."),
    "recsys_type": "twitter",
    "category": "Politics",
    "topics": ["Civic Engagement", "Thai Politics", ...]
  },
  {
    "_id": ObjectId("..."),
    "recsys_type": "twitter",
    "category": "Economics",
    "topics": ["Digital Economy", "banking", ...]
  },
  {
    "_id": ObjectId("..."),
    "recsys_type": "twitter",
    "category": "Society",
    "topics": ["Thai food", "travel", ...]
  }
]
```

---

## 前端调用示例

```typescript
// 导入数据
const formData = new FormData();
formData.append("file", file);
formData.append("recsys_type", "twitter");
formData.append("type", "users");

const response = await fetch("/api/persona/mongodb/import", {
  method: "POST",
  body: formData,
});

// 获取统计
const stats = await fetch("/api/persona/twitter/stats").then((r) => r.json());

// 获取用户数据
const users = await fetch("/api/persona/twitter/users").then((r) => r.json());
```



