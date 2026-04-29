# Evaluation Runtime Docs

- Status: active runtime reference
- Audience: implementers, evaluators
- Doc role: index for harness usage, validation scenarios, and whitebox flow

## Reading Order

1. [testing-and-evaluation.md](./testing-and-evaluation.md)
   - 测试层级、harness phase、常用命令和结果读取。
2. [validation-scenarios.md](./validation-scenarios.md)
   - `VAL-*` 回归和保真验证场景目录。
3. [action-v1-memory-whitebox-flow.md](./action-v1-memory-whitebox-flow.md)
   - `action_v1` 写入、检索、rerank、过滤和 prompt 注入白盒流程。

## Boundary

本目录回答“怎么运行、怎么验证、当前链路事实是什么”。

KPI 和 benchmark 设计在：

- [../design/README.md](../design/README.md)
