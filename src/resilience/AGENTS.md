# resilience LLM 索引

## 适用范围

`src/resilience/` 提供可靠性策略，包括 retry policy 和 circuit breaker。

## 设计规范

- 韧性策略应独立于具体业务，供 executor、integration、API service 组合使用。
- 重试只用于临时性失败，不应用于校验错误、权限错误或不可恢复错误。
- 熔断器状态应可观察，便于日志、指标和告警展示。

## 约束

- 不要无限重试；必须有最大次数、退避策略和总超时。
- 不要吞掉最终异常；超过策略后向调用方返回明确失败。
- 不要在通用策略中硬编码某个外部服务名称。
- 并发场景下状态更新必须安全。

## 最佳实践

- 对 retryable/non-retryable 错误做明确分类。
- 使用指数退避和抖动，避免外部服务恢复时的请求尖峰。
- 为 closed/open/half-open 状态转换写测试。
- 将重试次数、耗时和熔断状态写入 observability 元数据。
