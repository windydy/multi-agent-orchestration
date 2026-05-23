# verifier LLM 索引

## 适用范围

`src/verifier/` 定义执行后验证规则，用于判断工作流节点或整体执行是否满足质量门槛。

## 设计规范

- Verifier 应输出明确的 pass/fail/warn、severity、原因和建议动作。
- 验证规则应可配置，并能被 workflow 或 API 展示。
- 验证只判断结果，不直接修复；修复由 fixer 或 replan 路径处理。

## 约束

- 不要让 verifier 执行破坏性命令。
- 不要将验证失败静默降级为成功。
- 规则超时必须可控，避免阻塞整个 workflow。
- 修改 severity/action 枚举时同步 config schema 和 Web UI。

## 最佳实践

- 将 token、成本、超时、测试失败、安全风险拆成独立规则。
- 验证输出保持结构化，便于生成告警和审计日志。
- 测试覆盖通过、警告、失败、超时和规则配置错误路径。
