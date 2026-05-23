# Phase 5 详细技术设计 — 可观测性面板

## 1. 目标

运维级监控仪表板，让运维人员一眼掌握系统健康状态：
- 成本面板：Token 消耗、费用统计
- 成功率仪表：成功率趋势、失败原因分布
- 性能指标：各节点平均耗时、P50/P95/P99 延迟
- 告警中心：阈值告警配置 + 告警历史

## 2. 方案设计

### 2.1 后端 API

**新增路由**：

```
GET    /api/observability/overview        # 汇总指标（24h/7d/30d）
GET    /api/observability/cost/daily      # 每日成本趋势
GET    /api/observability/success-rate    # 成功率趋势（按天）
GET    /api/observability/performance     # 各节点耗时统计（avg/p50/p95/p99）
GET    /api/observability/failure-reasons # 失败原因分类统计
GET    /api/observability/alerts          # 告警历史
POST   /api/observability/alerts/trigger  # 手动触发告警（测试用）
```

**数据源**：全部从现有的 `events.db` (EventLog) 聚合查询，**不新增数据库表**。

**聚合查询**：
- 成本：从 `execution_completed` 事件的 `data.total_cost` 聚合
- Token：从 `node_completed` 事件的 `data.token_usage` 聚合
- 成功率：`execution_completed` 事件的成功/失败比例
- 性能：`node_completed` 事件的 `timestamp` 差值计算 duration
- 失败原因：`node_failed` 事件的 `data.error` 关键词分类

### 2.2 Pydantic 响应模型

```python
class CostTrend(BaseModel):
    date: str  # ISO date
    total_cost: float
    total_tokens: int
    execution_count: int

class SuccessRate(BaseModel):
    date: str
    total: int
    success: int
    failed: int
    rate: float  # 0-1

class NodePerformance(BaseModel):
    node: str
    count: int
    avg_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float

class FailureReason(BaseModel):
    reason: str
    count: int
    percentage: float

class AlertItem(BaseModel):
    id: str
    rule_id: str
    rule_name: str
    triggered_at: float
    severity: str
    message: str
    acknowledged: bool

class ObservabilityOverview(BaseModel):
    period: str  # "24h" | "7d" | "30d"
    total_executions: int
    total_cost: float
    total_tokens: int
    success_rate: float
    avg_duration_ms: float
    alert_count: int
```

### 2.3 前端

**新增页面**：`ObservabilityPage`

**依赖**：`recharts`（图表库）

```bash
npm install recharts
```

**组件**：
- `StatsSummary` — 顶部汇总卡片（总执行数、总成本、成功率、告警数）
- `CostChart` — 折线图（每日成本 + Token 叠加）
- `SuccessRateChart` — 面积图（成功率趋势）
- `PerformanceTable` — 表格（节点耗时统计 P50/P95/P99）
- `FailurePieChart` — 饼图（失败原因分布）
- `AlertList` — 告警列表（severity 颜色标识）

**文件结构**：
```
web/src/
├── pages/
│   └── ObservabilityPage.tsx
├── components/
│   ├── StatsSummary.tsx
│   ├── CostChart.tsx
│   ├── SuccessRateChart.tsx
│   ├── PerformanceTable.tsx
│   ├── FailurePieChart.tsx
│   └── AlertList.tsx
```

### 2.4 告警机制

Phase 5 实现轻量告警：
- 定时任务：每次获取 observability/overview 时检查 Verifier 规则
- 当条件触发时，写入 `alerts` SQLite 表（新增表）
- 前端 GET /api/observability/alerts 获取列表

**新增 SQLite 表** `alerts`：
```sql
CREATE TABLE alerts (
    id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    triggered_at REAL NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0
);
```

## 3. 验收标准

1. GET /api/observability/overview 返回正确的汇总数据
2. CostChart 显示正确的每日成本趋势
3. 成功率趋势图显示最近 7 天数据
4. PerformanceTable 显示各节点 P50/P95/P99
5. 当成本超过 verifier 规则阈值时，告警列表出现新条目
6. 前端图表渲染正确，暗色主题一致

## 4. P0 预修复

- **P0-1**: Observability API 路由在 `__init__.py` 注册，server.py 不重复
- **P0-2**: TDD 先写测试，用伪造数据验证聚合逻辑
- **P0-3**: 告警检查在查询时触发（而非独立定时任务），降低复杂度

## 5. 不做的事

- ❌ WebSocket 实时推送告警 — Phase 6
- ❌ 告警通知（邮件/Slack/飞书） — Phase 6
- ❌ 自定义 PromQL 风格查询 — Phase 6
- ❌ 导出 PDF 报表 — Phase 6
