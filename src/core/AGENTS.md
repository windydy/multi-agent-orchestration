# core LLM 索引

## 适用范围

`src/core/` 定义跨实现共享的基础抽象：`BaseAgent`、`BaseWorkflow`、`BaseTool`、`BaseState`、`BaseOrchestrator`。

## 设计定位

- 这里是稳定契约层，不应依赖 FastAPI、LangGraph、Claude SDK、具体 Agent 或外部集成。
- 抽象只表达最小必要行为；具体实现放到 `agents/`、`workflows/`、`executors/` 或 `claude/`。
- 公共类型要保持易测试、可替换、可组合。

## 约束

- 不要把运行时配置、密钥读取、数据库连接或网络请求放入 core。
- 不要引入循环依赖；core 可以被其他模块依赖，但不要反向依赖其他功能目录。
- 抽象方法签名变更属于破坏性变更，必须同步所有实现和测试。
- 状态对象要可序列化，方便 checkpoint、日志和 API 展示。

## 最佳实践

- 新抽象先证明至少有两个真实调用方，否则优先放在具体模块。
- 基类只处理通用生命周期和契约校验，不做业务策略判断。
- 错误类型要让上层能区分配置错误、执行错误和外部依赖错误。

## 常见改动入口

- Agent 行为契约：`agent.py`
- Workflow 生命周期：`workflow.py`
- Orchestrator 协调契约：`orchestrator.py`
- Tool 调用契约：`tool.py`
- 状态存储抽象：`state.py`
