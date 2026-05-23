# plan LLM 索引

## 适用范围

`src/plan/` 负责把用户任务转换为可执行 DAG，包括 `PlanGraph`、`PlanNode`、`ExecutorCapability` 和 `PlannerAgent`。

## 核心模型

- `PlanGraph`：完整执行计划，包含节点、边、状态、元数据和序列化方法。
- `PlanNode`：单个任务节点，声明依赖、能力、超时、重试和运行态结果。
- `ExecutorCapability`：计划节点与 executor 匹配的稳定能力枚举。
- `PlannerAgent`：调用 LLM 输出 JSON，再解析为 `PlanGraph`。

## 设计规范

- 所有计划必须是 DAG，不能产生循环依赖。
- 节点 ID 应稳定、可读、适合日志和 API 展示。
- 规划输出必须可序列化；不要把函数、连接、客户端对象写入计划。
- 新任务类型应先映射到 `ExecutorCapability`，再进入 workflow/executor 层。

## 约束

- LLM 输出是不可信输入，解析时必须做 JSON 提取、字段校验和默认降级。
- 不要在 planner 中执行实际开发、文件写入或外部系统副作用。
- 依赖边和 `dependencies` 字段必须保持一致。
- replan 必须保留足够元数据说明原计划和失败原因。

## 最佳实践

- 为代码任务自动包含 `code_review` 和 `testing` 节点。
- 并行节点用 `parallel_group` 标记，但仍必须满足依赖完成后再运行。
- Planner 失败时使用保守默认计划，不要返回空成功。
- 修改能力枚举时同步 `src/executors`、`src/config`、`agents/*.md` 和测试。
