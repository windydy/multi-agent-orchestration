# agents definitions LLM 索引

## 适用范围

根目录 `agents/` 存放 Markdown Agent 定义，由 `src/agents/loader.py` 加载。

## 文件格式

每个 Agent 文件使用 YAML frontmatter + system prompt body：

```markdown
---
name: developer
role: Code Developer
description: Implements code and tests
model: qwen3.6-plus
max_iterations: 10
timeout: 300
temperature: 0.1
tools:
  - read
  - write
---

System prompt...
```

## 设计规范

- 文件名应与 `name` 语义一致，方便配置和日志引用。
- `tools` 必须是 YAML list，按最小权限声明。
- Prompt 要明确角色目标、输入、输出格式、质量标准和失败处理。
- 输出格式应尽量结构化，便于 executor、verifier 和 summarizer 使用。

## 约束

- 不要写入真实密钥、内部 URL、用户私有目录或临时任务上下文。
- 不要给所有 Agent 默认 bash/write 权限；按角色需要赋权。
- 不要让 Agent prompt 指示绕过安全 Hook、测试或代码审查。
- frontmatter 字段变更必须同步 `AgentDefinition` 和测试。

## 最佳实践

- 新增 Agent 时同步能力映射、workflow 配置和 README 子功能说明。
- 对高风险角色如 security、devops、data 明确只在授权范围内执行。
- 保持 prompt 可复用，不绑定单一 demo 项目。
- 对 Agent loader 增加解析测试，覆盖缺失字段和非法 YAML。
