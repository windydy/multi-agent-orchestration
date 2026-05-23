# claude LLM 索引

## 适用范围

`src/claude/` 封装 Claude/Anthropic 兼容执行层，包括 wrapper、tool registry 和 hooks。

## 子功能索引

- `wrapper.py`：把 Claude Agent SDK 或兼容 API 适配到项目 `BaseAgent` 契约。
- `tools.py`：注册读写、编辑、bash、搜索等工具能力。
- `hooks.py`：安全、日志、成本等 Hook 控制。

## 设计规范

- 该目录是模型供应商边界，内部细节不要泄露到 planner/workflow/API 层。
- 工具调用必须经过注册表和 Hook，不要直接暴露任意 shell 或文件系统能力。
- 模型、base URL、API Key 等配置来自环境或显式参数，不写死在代码中。
- 对外返回统一结构，便于 Agent/Executor 处理成功、失败、token 和成本信息。

## 约束

- 不要记录完整 API Key、请求 Authorization header 或敏感 prompt 上下文。
- 危险命令和高风险文件操作必须被 SafetyHook 拦截或要求上层授权。
- 外部 SDK 异常要转换为可诊断错误，保留原因但避免泄露敏感信息。
- 修改工具名称或参数时必须同步 Agent prompt、测试和文档。

## 最佳实践

- 新工具先定义最小输入 schema，再接入权限和日志。
- 对模型调用设置超时、最大轮次和成本限制。
- 保持 wrapper 可替换，方便 DashScope Anthropic-compatible 和官方 Anthropic 间切换。
- 针对 Hook 增加单元测试，特别是阻断危险命令和成本阈值路径。
