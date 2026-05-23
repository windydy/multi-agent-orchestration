# config LLM 索引

## 适用范围

根目录 `config/` 存放项目运行配置，当前主要是 `workflows/*.yaml`。

## 设计规范

- Workflow YAML 必须匹配 `src/config/schema.py`。
- 节点 ID、executor ID、verifier ID 要稳定可读，适合日志和 UI 展示。
- `flow_template.entry_point` 必须引用存在的节点。
- `depends_on` 和 `edges` 必须表达无环流程。
- 成本、超时、重试和人工审批默认值要保守。

## 约束

- 不要提交真实 API Key、token、私有 webhook、内部域名或用户本机绝对路径。
- 不要在 YAML 中嵌入可执行脚本或动态表达式。
- 变量应通过 `vars` 或环境变量引用，避免复制到多个位置。
- 修改配置结构时同步 README、`src/config/AGENTS.md` 和测试。

## 最佳实践

- 示例配置保持最小可运行，并把高级能力拆成独立示例。
- 为每个 executor 标注必要工具，不给过宽权限。
- verifier 用明确 action 和 severity，方便 UI 告警展示。
- 新增 workflow 后至少通过 schema loader 校验一次。
