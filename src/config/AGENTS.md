# config LLM 索引

## 适用范围

`src/config/` 负责 workflow YAML 配置的 schema、加载、变量解析和校验。

## 子功能索引

- `schema.py`：Pydantic v2 模型，定义 planner、executors、verifiers、flow template、human review、cost、checkpoint、logging。
- `loader.py`：从文件系统读取配置、解析变量并实例化 `WorkflowConfig`。

## 设计规范

- 配置 schema 是运行时契约，优先显式字段和 `extra="forbid"`。
- 所有 flow 节点依赖必须存在，entry point 必须存在，流程必须无环。
- 默认值要安全保守，尤其是 timeout、retry、cost control 和 human review。
- 配置变量替换应可预测，不要执行任意表达式。

## 约束

- 不要在示例 YAML 中放真实 token、私有路径或内部系统地址。
- 新增配置字段必须同步 API config store、示例 YAML、README 和测试。
- 加载失败要暴露具体字段和原因，不要返回半初始化配置。
- 配置只描述意图，不应包含 Python 代码或可执行脚本。

## 最佳实践

- 给新字段提供合理默认值和边界校验。
- 对 DAG 校验、变量替换、未知字段和类型错误写单元测试。
- 保持 workflow name 只包含字母、数字、横线和下划线。
- 示例配置应体现最小可运行路径，而不是所有高级能力堆叠。
