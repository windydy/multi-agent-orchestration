# Phase 5 设计评审报告

> **评审对象**: `docs/planning/web-ui-phase5-design.md`
> **评审时间**: 2026-05-23

## 评审结论：✅ 通过，修复 3 个问题后开始实现

---

## P0 问题

### P0-1: Observability API 路由注册方式

设计说"在 `__init__.py` 注册"，但 Phase 4 的 config_router 是在 `server.py` 直接注册的。需要统一约定。

**修复**: 使用 `server.py` 直接注册（与 config_router 一致），但路径用 `/observability/...` 不加 `/api` 前缀，由 server.py 的 include_router prefix 处理。

### P0-2: 告警表应该用 ConfigStore 还是独立服务？

设计中新建 `alerts` 表，但没有对应的 Service 类。应该复用 ConfigStore 还是新建 ObservabilityStore？

**修复**: 新建 `ObservabilityStore`，包含 alerts CRUD + 聚合查询方法。

### P0-3: 聚合查询性能问题

设计说"全部从 events.db 聚合查询"，但 events.db 没有针对聚合查询的索引。如果数据量大，每次查询会很慢。

**修复**: 添加 `idx_events_thread_time` 索引：`(thread_id, timestamp)`。聚合查询用 WHERE timestamp > ? 限定时间范围。

---

## P1 问题

### P1-1: 告警检查在查询时触发会重复告警

"每次获取 overview 时检查 Verifier 规则"会导致重复告警。应该加去重逻辑（同一规则 N 分钟内不重复触发）。

**修复**: 在 INSERT alert 前检查最近 5 分钟内是否已有同 rule_id 的未确认告警。

### P1-2: recharts 包体积

recharts ~170KB gzipped。可以考虑更轻量的方案如 chart.js，但 recharts React 集成更好。

**修复**: 保持 recharts，Phase 5 规模下可接受。

### P1-3: FailureReason 的 error 分类太简单

"关键词分类"容易误匹配。应该用更结构化的方式，比如从 `data.error` 提取错误类型前缀。

**修复**: Phase 5 先用关键词简单分类（OOM/Timeout/API Error/Network Error），Phase 6 升级。
