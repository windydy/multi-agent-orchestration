# cli LLM 索引

## 适用范围

`src/cli/` 提供命令行入口，主要面向本地运行、调试和演示。

## 设计规范

- CLI 是 `WorkflowRunner` 的薄封装，不应复制 workflow 业务逻辑。
- 命令输出应适合终端阅读，并保留 thread id 方便恢复。
- 参数默认值要安全，尤其是人工审批、项目路径和 API Key。

## 约束

- 不要在 CLI 中硬编码 API Key 或读取非预期配置文件。
- 不要在 status/history/list 中触发新的执行副作用。
- 文件写入如 `.pipeline_thread_YYYYMMDD.txt` 应保持简单可预期。
- 修改命令参数时同步 README。

## 最佳实践

- 新命令先确认能复用 runner/API/service，而不是新建执行链路。
- 错误输出包含失败原因和下一步建议。
- 为参数解析和 runner 调用路径写轻量测试。
