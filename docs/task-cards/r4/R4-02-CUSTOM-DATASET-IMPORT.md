# 任务卡：R4-02 自定义数据集导入最小闭环

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P0 |
| **类型** | Data Import / Validation / UX |
| **负责人** | 数据导入负责人 |
| **协作人** | 前端负责人、后端转换负责人 |
| **关联 Issue** | #34, #6 |

---

## 1. 背景

Issue #34 要求支持 JSON/CSV 导入，实现格式校验、完整性检查、错误提示，并将用户画像、社交关系、帖子内容等转换为 OASIS 格式，最终用于驱动三大核心图表。代码库文档中已有的 Reddit JSON 示例为转换路径提供了参照。

## 2. 目标

实现最小自定义数据集导入闭环，使用户可以上传 JSON/CSV，得到明确的格式校验反馈，将数据转换为 OASIS 所需结构，并用导入数据驱动基础模拟或直接生成三大图表。

## 3. 范围

### In Scope

- JSON/CSV 导入
- 基础 schema 校验
- 错误提示
- 数据清洗/去重
- 转换为 OASIS 用户与关系结构
- 导入后生成基础分析图表

### Out of Scope

- Excel 全支持
- 大规模文件分片上传
- 复杂知识图谱融合
- 完整数据标注工作流

## 4. 当前问题

系统目前缺少“用户自带数据”的标准入口，限制了实验、对比和演示的真实感，也使 #34 长期悬空。

## 5. 修复/实现方案

### 5.1 支持的输入结构

最小化支持三类实体：`users`, `relationships`, `posts`。

### 5.2 推荐统一格式

```typescript
type DatasetBundle = {
  users: Array<{
    username: string;
    realname?: string;
    bio?: string;
    persona?: string;
    age?: number;
    gender?: string;
    mbti?: string;
    country?: string;
  }>;
  relationships?: Array<{
    source: string;
    target: string;
    type: "follow";
  }>;
  posts?: Array<{
    username: string;
    content: string;
    topic?: string;
    created_at?: string;
  }>;
};
```

### 5.3 后端处理流程

1. 文件解析
2. Schema 校验
3. 缺失值/重复值检查
4. 转换为 OASIS agent 配置
5. 返回 preview + 错误列表 + 可导入数据

### 5.4 前端体验

- 上传组件
- 校验结果提示
- Preview 表格
- “导入并生成图表”按钮

## 6. 具体子任务

1. 新建 `dataset_import.ts` 处理 JSON/CSV。
2. 新增 `/api/dataset/validate`、`/api/dataset/import` 接口。
3. 前端补全上传与 preview 功能。
4. 导入成功后，生成观点分布、羊群指数、传播基础图表。

## 7. 测试用例

- **T1**: 合法 JSON 导入成功（validate 通过, preview 正确, 能生成 agent 配置）。
- **T2**: 合法 CSV 导入成功（能转成统一中间格式, 无致命错误）。
- **T3**: 字段缺失时报错明确（返回具体字段级错误, 不 silently fail）。
- **T4**: 重复用户被识别（给出警告或去重信息）。
- **T5**: 导入后图表可生成（至少一张核心图表能用导入数据渲染）。

## 8. 通过标准 (Gate)

- [ ] 支持 JSON 导入
- [ ] 支持 CSV 导入
- [ ] 有明确的校验结果与错误提示
- [ ] 数据可转换为 OASIS 所需结构
- [ ] 导入后能驱动基础图表
- [ ] 示例数据导入流程完整通过

## 9. 失败标准

- 文件可上传但无法验证
- 错误提示模糊
- 数据导入后无法转成 OASIS 结构
- 图表仍然只能依赖内置模拟数据

## 10. 证据要求

- `artifacts/r4/r4_02_dataset_validate.json`
- `artifacts/r4/r4_02_import_preview.png`
- `artifacts/r4/r4_02_report.md`
- 一份示例 JSON 与 CSV

## 11. 建议提交信息

```bash
git commit -m "feat(dataset): add minimal custom dataset import and validation flow"
```
