# src LLM 索引

## 适用范围

本文件适用于 `src/` 下所有 Python 代码。进入更具体子目录时，优先遵循该子目录的 `AGENTS.md`。

## 子功能地图

- `core/`：框架无关的基础抽象，定义 Agent、Workflow、Tool、State、Orchestrator 的最小契约。
- `agents/`：内置 Agent 类与 Markdown Agent 定义加载器。
- `plan/`：任务规划、DAG 数据模型与 LLM Planner。
- `workflows/`：静态/动态 LangGraph 工作流构建、运行与状态定义。
- `executors/`：执行器基类、Agent 适配器与能力注册/匹配。
- `api/`：FastAPI 后端、路由、服务层、WebSocket 与 Dashboard 数据接口。
- `config/`：YAML workflow schema、加载、校验与变量解析。
- `claude/`：Claude/Anthropic 兼容封装、工具注册和安全 Hooks。
- `knowledge/`：Agent 记忆、结构化检索与可选语义检索。
- `integrations/`：GitHub、Jira、Slack 等外部系统适配。
- `workspace/`：多项目工作区与 `.workspace.yaml` 管理。
- `observability/`：指标、追踪、告警与运行态统计。
- `resilience/`：重试策略与熔断器。
- `tools/`：供 Agent/Executor 调用的领域工具。
- `verifier/`：执行后验证规则。
- `cost/`：成本统计和阈值控制。
- `bug/`：Bug 分类、报告与跟踪模型。
- `cli/`：命令行入口。

## 全局设计规范

- 以 `PlanGraph -> Workflow -> Executor -> Agent/Tool` 为主链路组织改动，避免跨层直接耦合。
- API 边界和配置边界必须使用 Pydantic、dataclass 或显式校验，不信任外部输入。
- 优先通过能力枚举、配置或注册表扩展功能，不要在工作流里硬编码具体 Agent 名称。
- 运行时状态应可序列化、可检查点恢复；不要把不可序列化对象写入 workflow state。
- 默认使用异步接口承载长任务、外部 API 和 I/O。
- 不要吞掉异常；内部可记录上下文，边界层返回清晰错误。
- 不要在源码中写入 API Key、token、用户私有路径或临时机器配置。

## 修改建议

- 新增任务能力：先扩展 `plan.ExecutorCapability`，再接入 executor/agent/config/workflow。
- 新增 API：优先放在 `src/api/routes`，业务状态放在 `src/api/services`。
- 新增配置项：先改 `src/config/schema.py`，再改 loader、示例 YAML 和测试。
- 新增持久化数据：明确 SQLite 表结构、索引和关闭连接策略。
- 修改 UI 依赖的返回结构时，同步检查 `web/src/lib/api.ts` 与 `web/src/types`。

## 验证

- Python：`pytest`、`ruff check src tests`、必要时 `mypy src`。
- API：覆盖成功、校验失败、资源不存在和执行失败路径。
- 涉及 Web UI 时，还要运行前端构建并实际打开页面验证主要流程。
