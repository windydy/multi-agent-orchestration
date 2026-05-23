# observability LLM 索引

## 适用范围

`src/observability/` 负责运行态指标、追踪和告警数据。

## 子功能索引

- `metrics.py`：执行、节点、成本、token、成功率等指标模型或聚合逻辑。
- `tracing.py`：执行链路追踪和事件关联。

相关 API 与持久化服务位于 `src/api/routes/observability.py` 和 `src/api/services/observability.py`。

## 设计规范

- 指标应从事件日志和执行状态派生，避免重复维护相互矛盾的事实源。
- 时间窗口、成本、token、成功率和耗时字段要明确单位。
- 告警必须可去重、可确认，并保留触发规则和时间。

## 约束

- 不要把 prompt 原文、密钥或敏感文件内容写入 tracing。
- 聚合查询必须有限定时间范围或分页，避免无界扫描。
- 可观测性失败不应导致核心 workflow 成功路径崩溃，但必须记录诊断信息。
- 修改指标名称或结构时同步 Web UI 图表和 API 类型。

## 最佳实践

- 优先记录结构化事件，UI 再做展示转换。
- 为成本趋势、成功率、节点性能、失败原因和告警列表写测试。
- 保持 severity 枚举稳定，避免前端样式和过滤器失效。
- 对时间使用 epoch seconds 或 ISO 字符串时保持同一接口内一致。
