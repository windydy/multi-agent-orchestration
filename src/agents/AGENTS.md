# agents LLM 索引

## 适用范围

`src/agents/` 包含 Python Agent 实现和 `AgentLoader`；根目录 `agents/*.md` 是可配置 Agent 定义。

## 子功能索引

- `loader.py`：解析 Markdown frontmatter 和 system prompt，产出 `AgentDefinition`。
- `summarizer.py`：将执行结果整理为记忆条目。
- `requirements.py`、`designer.py`、`developer.py`、`reviewer.py`、`tester.py`、`fixer.py`：软件开发流水线核心角色。
- `architect.py`、`security.py`、`devops.py`、`data.py`、`product_manager.py`：领域扩展角色。

## 设计规范

- Agent 负责“做什么”和“如何表达结果”，不要直接承担 workflow 路由职责。
- Agent 输出应结构化，便于 Executor、Verifier、API 和 UI 消费。
- Markdown Agent 定义必须保持 YAML frontmatter 可解析，body 只放 system prompt。
- 工具权限要最小化，按角色列出必要工具。

## 约束

- 不要在 Agent prompt 或默认参数中硬编码密钥、组织私有路径或一次性上下文。
- 不要让 Agent 绕过 `ExecutorRegistry` 直接调用其他执行器。
- `AgentLoader` 的 frontmatter 字段变更必须兼容现有 `agents/*.md` 或同步迁移所有定义。
- Agent 失败时应返回可诊断错误，而不是伪造成功结果。

## 最佳实践

- 新增角色时同步：`agents/<name>.md`、Python 实现、能力映射、配置模板和测试。
- Prompt 中明确输入、输出格式、边界条件和禁止事项。
- 长任务拆成可验证阶段，便于 reviewer/tester/fixer 节点接续。
- 涉及安全、部署、数据处理的 Agent 默认保守，先计划和验证，再执行有副作用操作。
