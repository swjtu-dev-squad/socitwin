# 行为配置示例文件

此目录包含Socitwin行为控制系统的配置示例文件。这些YAML文件展示了如何配置不同类型的智能体行为策略。

## 文件列表

### 1. 概率分布配置
- **文件**: `probabilistic_balanced_twitter.yaml`
- **描述**: Twitter平台的平衡概率分布配置
- **策略**: `probabilistic`
- **特点**: 20%发帖，30%点赞，25%评论，15%刷新，10%休息
- **适用场景**: 普通用户、内容消费者

### 2. 规则引擎配置
- **文件**: `rule_based_customer_support.yaml`
- **描述**: Twitter平台的规则引擎配置
- **策略**: `rule_based`
- **特点**: 基于条件和规则触发动作，如回应提及、处理投诉
- **适用场景**: 社区管理者

### 3. 调度引擎配置
- **文件**: `scheduled_marketing_campaign.yaml`
- **描述**: 舆论话题的时间线调度配置
- **策略**: `scheduled`
- **特点**: 按预定义时间线执行动作，支持重复事件
- **适用场景**: 话题发布、内容日历

### 4. 混合策略配置
- **文件**: `mixed_influencer_strategy.yaml`
- **描述**: 社交媒体影响者的混合策略配置
- **策略**: `mixed`
- **特点**: 70%概率模型 + 20%规则引擎 + 10%调度
- **适用场景**: 社交媒体影响者、内容创作者、社区领袖

## 配置结构

所有配置文件遵循以下基本结构：

```yaml
name: "配置名称"
description: "配置描述"
strategy: "策略类型"  # probabilistic, rule_based, scheduled, mixed
enabled: true
platform_filter: "平台"  # twitter, reddit

# 策略特定配置
probability_distribution:  # 概率策略
rule_set:                 # 规则策略  
schedule:                 # 调度策略
mixed_strategy:           # 混合策略

# 条件约束
step_range: [开始步骤, 结束步骤]
conditions:               # 额外条件

# 元数据
metadata:
  created: "时间戳"
  author: "作者"
  tags: ["标签列表"]
  version: "版本号"
```

## 使用方式

### 1. 通过API应用配置

使用行为控制API将配置应用到智能体：

```bash
# 应用概率分布配置到智能体0
curl -X POST "http://localhost:8000/api/behavior/config/preset/0" \
  -H "Content-Type: application/json" \
  -d '{
    "preset": "probabilistic",
    "platform": "twitter"
  }'
```

### 2. 直接使用配置文件

通过API上传并应用完整的YAML配置：

```python
import yaml
import requests

# 读取配置文件
with open('probabilistic_balanced_twitter.yaml', 'r') as f:
    config_data = yaml.safe_load(f)

# 转换为API请求格式
request = {
    "agent_id": 0,
    "behavior_config": config_data
}

# 发送到API
response = requests.post(
    "http://localhost:8000/api/behavior/config",
    json=request
)
```

### 3. 创建自定义配置

基于示例文件创建自定义配置：

1. 复制最接近的示例文件
2. 修改策略参数
3. 调整概率/规则/时间线
4. 通过API应用到智能体

## 策略选择指南

### 何时使用概率分布策略？
- 需要模拟自然、随机的人类行为
- 没有明确的业务规则或时间表
- 想要控制不同类型动作的相对频率
- 适用于：普通用户、内容消费者

### 何时使用规则引擎策略？
- 有明确的业务规则和条件
- 需要基于特定事件触发动作
- 想要实现if-then逻辑
- 适用于：客服机器人、自动化响应、业务逻辑

### 何时使用调度引擎策略？
- 有明确的时间表和计划
- 需要定期执行重复动作
- 活动或营销活动有明确时间线
- 适用于：营销活动、内容发布计划、定时任务

### 何时使用混合策略？
- 需要结合多种行为模式
- 不同场景需要不同策略
- 想要更复杂、真实的行为模拟
- 适用于：影响者、复杂角色、高级模拟

## 高级特性

### 条件配置
- `step_range`: 配置只在特定步骤范围内生效
- `conditions`: 基于模拟状态的额外条件
- `platform_filter`: 平台特定配置

### 动作参数
每个动作类型可以包含自定义参数，如：
- `content_templates`: 内容模板列表
- `engagement_strategy`: 互动策略
- `target_criteria`: 目标选择标准

### 元数据
- 跟踪配置来源和版本
- 标签便于分类和搜索
- 作者和创建时间信息

## 最佳实践

1. **从简单开始**: 先使用预设配置，再逐步自定义
2. **测试小规模**: 先应用到少量智能体测试效果
3. **监控统计**: 使用`/api/behavior/stats`端点监控策略效果
4. **迭代优化**: 根据模拟结果调整配置参数
5. **文档化**: 记录配置决策和预期效果

## 相关API端点

- `GET /api/behavior/strategies` - 获取可用策略
- `POST /api/behavior/config` - 更新智能体配置
- `GET /api/behavior/config/{agent_id}` - 获取智能体配置
- `GET /api/behavior/stats` - 获取行为统计
- `GET /api/behavior/engine/*` - 获取引擎状态

## 故障排除

### 配置不生效
1. 检查`enabled`是否为`true`
2. 验证`step_range`是否包含当前步骤
3. 检查`conditions`是否满足
4. 确认`platform_filter`匹配当前平台

### 动作不符合预期
1. 检查概率分布是否总和为1.0
2. 验证规则条件是否编写正确
3. 确认调度时间线步骤设置正确
4. 查看引擎统计信息了解执行情况

### API错误
1. 检查请求格式是否符合API文档
2. 验证智能体ID是否存在
3. 查看服务器日志获取详细错误信息