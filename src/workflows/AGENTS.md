# workflows LLM 索引

## 适用范围

`src/workflows/` 负责 LangGraph 工作流的状态定义、构建和运行。

## 子功能索引

- `states.py`：静态和动态 workflow state 类型。
- `builder.py`：经典开发流水线构建器。
- `dynamic_builder.py`：从 `PlanGraph` 动态生成 LangGraph `StateGraph`。
- `config_builder.py`：从 YAML workflow 配置构建工作流。
- `runner.py`：统一执行入口、resume、history、list 等运行时操作。

## 设计规范

- Workflow 只负责编排和状态转移，不直接实现具体 Agent 业务逻辑。
- 节点函数返回局部状态增量，避免不可控地修改共享对象。
- 状态必须可序列化、可恢复、可被 API 展示。
- 所有终端路径都应经过验证或明确标记失败原因。

## 约束

- 不要把 API 路由、UI 展示逻辑或外部系统 SDK 细节写进 workflow builder。
- 不要在条件边中做长耗时操作；长任务放到 node function 或 executor。
- 失败、取消、暂停、重试和 replan 的状态字段必须一致。
- LangGraph 不可用时要显式报错，不要静默降级为未执行成功。

## 最佳实践

- 新增节点类型时先定义 state 字段和 executor 输出格式。
- `DynamicWorkflowBuilder` 中新增边路由时补充 cycle 和失败路径测试。
- `WorkflowRunner` 是 CLI/API 共用入口，改动后同时验证两条路径。
- 对后台任务保持幂等和可恢复，避免重复写入最终状态。
