# E2E测试配置文件目录

本目录包含用于端到端测试的示例配置文件，用于配置受控agents和行为策略。

## 配置文件

### 1. controlled_agents_example.yaml

定义要添加到模拟中的受控agents。受控agents是用于测试舆论引导功能的特殊agents。

**字段说明：**

- `check_polarization` (bool): 是否在添加前检查极化率阈值
- `polarization_threshold` (float): 极化率阈值 (0.0-1.0)
- `agents` (list): 受控agents列表
  - `user_name` (str, 必需): 用户名（唯一标识）
  - `name` (str, 必需): 显示名称
  - `description` (str, 必需): agent描述
  - `bio` (str, 可选): 详细传记
  - `profile` (dict, 可选): agent配置（政治倾向、性格等）
  - `interests` (list, 可选): 兴趣标签列表
  - `behavior_strategy` (str, 可选): 行为策略类型
    - `llm_autonomous`: LLM自主决策
    - `probabilistic`: 概率分布模型
    - `rule_based`: 规则引擎模型
    - `scheduled`: 时间调度模型
    - `mixed`: 混合策略模型

**使用示例：**

```bash
python backend/tests/e2e/e2e_simulation_test.py \
    --controlled-agents-file backend/tests/e2e/configs/controlled_agents_example.yaml \
    --agent-count 5 \
    --max-steps 20
```

### 2. behavior_config_example.yaml

定义如何为智能体应用行为策略配置。

**字段说明：**

- `preset` (str, 可选): 预设配置名称
  - `default`: LLM自主决策
  - `probabilistic`: 概率分布模型
  - `rule_based`: 规则引擎模型
  - `scheduled`: 时间调度模型
- `platform` (str, 可选): 平台类型 (`twitter` 或 `reddit`)
- `target_agents` (str): 目标agents
  - `controlled`: 仅应用于受控agents
  - `all`: 应用于所有agents
  - 逗号分隔的ID: 应用于指定IDs的agents
- `custom_config` (dict, 可选): 自定义配置（覆盖preset）

**使用示例：**

```bash
python backend/tests/e2e/e2e_simulation_test.py \
    --controlled-agents-file backend/tests/e2e/configs/controlled_agents_example.yaml \
    --behavior-config-file backend/tests/e2e/configs/behavior_config_example.yaml \
    --agent-count 5 \
    --max-steps 20
```

## 完整测试示例

### 示例1: 基础测试（不使用受控agents）

```bash
python backend/tests/e2e/e2e_simulation_test.py \
    --agent-count 5 \
    --max-steps 10
```

### 示例2: 仅使用受控agents

```bash
python backend/tests/e2e/e2e_simulation_test.py \
    --controlled-agents-file backend/tests/e2e/configs/controlled_agents_example.yaml \
    --agent-count 5 \
    --max-steps 20
```

### 示例3: 受控agents + 行为配置

```bash
python backend/tests/e2e/e2e_simulation_test.py \
    --controlled-agents-file backend/tests/e2e/configs/controlled_agents_example.yaml \
    --behavior-config-file backend/tests/e2e/configs/behavior_config_example.yaml \
    --agent-count 5 \
    --max-steps 20
```

### 示例4: 自定义配置文件

```bash
# 创建自己的配置文件
cp backend/tests/e2e/configs/controlled_agents_example.yaml my_agents.yaml
cp backend/tests/e2e/configs/behavior_config_example.yaml my_behavior.yaml

# 使用自定义配置
python backend/tests/e2e/e2e_simulation_test.py \
    --controlled-agents-file my_agents.yaml \
    --behavior-config-file my_behavior.yaml \
    --agent-count 10 \
    --max-steps 30
```

## 测试结果

测试完成后，结果将保存在 `backend/test-results/e2e/{timestamp}/` 目录下：

- `test-result-{timestamp}.json`: 完整的测试结果JSON文件
- `propagation-metrics-{timestamp}.png`: 信息传播指标图表
- `polarization-metrics-{timestamp}.png`: 群体极化指标图表
- `herd-effect-metrics-{timestamp}.png`: 羊群效应指标图表

JSON结果文件中包含：
- 受控agents添加结果 (`controlled_agents_result`)
- 行为配置应用结果 (`behavior_config_result`)
- 行为统计信息 (`behavior_statistics`)

## 依赖要求

配置文件使用YAML格式，需要安装 `pyyaml`：

```bash
pip install pyyaml
```

如果未安装，也可以使用JSON格式配置文件（将 `.yaml` 改为 `.json` 即可）。
