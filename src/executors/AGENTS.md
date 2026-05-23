# executors LLM 索引

## 适用范围

`src/executors/` 连接计划层和实际执行层，负责 executor 契约、Agent 适配和能力注册匹配。

## 子功能索引

- `base.py`：Executor 基类、状态、结果与能力契约。
- `agent_adapter.py`：将 Agent 定义适配为可执行 executor。
- `registry.py`：按 `ExecutorCapability` 注册、查询和选择 executor。

## 设计规范

- Executor 是执行边界：接收 `PlanNode` 和上下文，返回结构化结果。
- 能力匹配以 `ExecutorCapability` 为准，不应靠字符串散落判断。
- 执行结果必须包含成功/失败状态、错误信息和必要元数据。
- Executor 不应决定全局 workflow 路由，只提供节点执行结果。

## 约束

- 不要在 registry 中实例化具体外部客户端；实例化应在 executor/adapter 或上层配置完成。
- 不要让 executor 直接修改 `PlanGraph` 全局结构；replan 由 planner/workflow 处理。
- 并发执行时不得共享可变运行状态，除非有显式锁或隔离。
- 外部命令、文件写入和网络调用必须经过工具层或明确安全控制。

## 最佳实践

- 新增 executor 时声明清晰的 `executor_id`、`name`、`capabilities` 和 `match_score`。
- 为超时、取消、重试返回可诊断元数据。
- registry 选择策略保持简单可预测：过滤、评分、选择。
- 对无匹配 executor 的路径写测试，确保 workflow 能给出明确失败原因。
