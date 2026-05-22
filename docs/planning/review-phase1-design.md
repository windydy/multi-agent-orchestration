# Phase 1 (MVP Dashboard) 全面评审报告

> **评审日期**: 2026-05-22  
> **评审范围**: 方案文档 + 所有已写代码  
> **结论**: 🔴 存在 P0 级别问题，需修复后方可进入 Phase 2

---

## 一、总体评价

Phase 1 整体架构方向正确，"只读 + 独立事件日志" 的 MVP 策略务实。但代码实现与方案存在多处偏差，且在安全性、并发安全、数据一致性方面存在必须修复的问题。

| 维度 | 评分 | 说明 |
|------|------|------|
| 方案完整性 | ⚠️ 6/10 | 文件结构设计未落地、事件注入机制描述不完整 |
| 代码忠实度 | ⚠️ 5/10 | 方案中描述的 `routes/` 目录结构未实现，改为单文件 `routes.py` |
| 前端完整性 | ⚠️ 7/10 | 基本页面已实现，但缺少方案中描述的独立组件 |
| 安全性 | 🔴 3/10 | CORS 全开放、无认证、SQL 注入风险 |
| 并发安全 | 🔴 4/10 | SQLite 连接无锁保护、状态推断有竞态 |
| Phase 2 兼容性 | ⚠️ 5/10 | 缺少关键接口对齐、数据模型不完整 |

---

## 二、关键问题（P0 — 必须修复）

### 🔴 P0-1: CORS 全开放 + 无认证机制 — 安全漏洞

**位置**: `src/api/server.py` 第 43-48 行

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # ← 允许任何来源访问
    allow_credentials=True, # ← 允许携带 cookie
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**问题**:
1. `allow_origins=["*"]` 允许任何网页通过浏览器请求 API
2. `allow_credentials=True` 配合 `*` 在真实浏览器中会被拒绝，但配置本身说明安全意识缺失
3. 完全无认证机制 — 任何能访问端口的人都能看到所有执行记录、任务输入（可能包含敏感信息）
4. 无 CSRF 保护

**修复建议**:
```python
# 开发环境
allow_origins=["http://localhost:5173"]
# 生产环境使用配置项
allow_origins=os.getenv("ALLOWED_ORIGINS", "").split(",")
```
Phase 2 引入写操作后必须加认证，建议提前预留。

---

### 🔴 P0-2: EventLog 并发不安全 — 多线程写入竞态

**位置**: `src/api/services/event_log.py` 第 14-18 行

```python
def __init__(self, db_path: str = "./checkpoints/events.db"):
    self._conn = sqlite3.connect(db_path, check_same_thread=False)  # ← 危险
```

**问题**:
1. `check_same_thread=False` 绕过了 sqlite3 的线程安全保护
2. FastAPI 默认使用线程池处理请求，多个请求可能并发调用 `_conn.execute()`
3. `list_executions()` 在循环中为每个 thread_id 执行独立查询（N+1 查询），且每次查询都可能被其他请求中断
4. `log()` 方法每次调用都 `commit()`，高频场景下性能差且容易锁冲突

**修复建议**:
```python
import threading

class EventLog:
    def __init__(self, db_path: str = "./checkpoints/events.db"):
        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._db_path = db_path
        self._create_table()

    def _get_conn(self):
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def log(self, ...):
        with self._write_lock:  # 写操作加锁
            conn = self._get_conn()
            ...
```

---

### 🔴 P0-3: `get_overview()` 效率极低 — O(N²) 查询

**位置**: `src/api/services/event_log.py` 第 128-160 行

```python
def get_overview(self) -> dict:
    executions = self._conn.execute(
        "SELECT DISTINCT thread_id FROM execution_events"
    ).fetchall()  # ← 先获取所有 thread_id
    
    for row in executions:
        thread_id = row["thread_id"]
        events = self._conn.execute(
            "SELECT * FROM execution_events WHERE thread_id = ? ORDER BY timestamp ASC",
            (thread_id,),
        ).fetchall()  # ← 对每个 thread_id 再查一次
```

**问题**:
- 当有 100 个执行记录时，执行 101 次 SQL 查询
- 每次查询都 `ORDER BY timestamp ASC` 扫描全表
- 首页每次加载（3 秒轮询）都触发这个操作

**修复建议**: 用单次 SQL 聚合查询替代循环：
```sql
SELECT thread_id, MAX(timestamp) as last_ts,
       GROUP_CONCAT(event_type ORDER BY timestamp) as events_seq
FROM execution_events
GROUP BY thread_id
```
或在应用层使用更高效的聚合逻辑。

---

### 🔴 P0-4: 状态推断逻辑有缺陷 — `execution_started` 但节点已完成时被误判为 running

**位置**: `src/api/services/event_log.py` 第 162-205 行 `_infer_status()`

```python
# Check if execution completed
if last_event_type == "execution_completed":
    has_failed = any(e["event_type"] == "node_failed" for e in events)
    return "failed" if has_failed else "success"

# ... 之后还有 running 检查

# execution_started but no nodes yet
if last_event_type == "execution_started":
    return "running"

return "running"  # ← 兜底永远是 running
```

**问题**:
1. 如果 `last_event_type` 是 `execution_completed` 且没有 `node_failed`，返回 `success` — 正确
2. 但如果有一个节点先 `node_started` 然后 `execution_completed` 发出（但节点未完成），状态会是 `success` — 错误
3. 兜底返回 `"running"` 意味着任何异常序列的事件都会被标记为 running
4. **路由层 `_infer_status` 和 EventLog `_infer_status` 逻辑不同**（routes.py 第 31-43 行），同样的事件数据通过不同路径可能得到不同状态

**修复建议**: 统一状态推断逻辑为单一函数，放在 EventLog 中供路由复用。

---

### 🔴 P0-5: 前端轮询永不停止 — 已完成执行仍在每 2 秒轮询

**位置**: `web/src/pages/ExecutionPage.tsx` 第 45-49 行

```tsx
useEffect(() => {
  const timer = setInterval(() => load(), 2000)
  return () => clearInterval(timer)
}, [threadId])
```

**问题**:
- 无论执行是否已完成（`success`/`failed`/`interrupted`），轮询都不会停止
- 方案中提到 "自动停止" 但未实现
- 当用户打开多个已完成执行的详情标签页时，每个都在持续轮询

**修复建议**:
```tsx
useEffect(() => {
  if (detail && ['success', 'failed', 'interrupted'].includes(detail.status)) return
  const timer = setInterval(() => load(), 2000)
  return () => clearInterval(timer)
}, [threadId, detail?.status])
```

---

## 三、重要问题（P1 — 应尽快修复）

### 🟡 P1-1: 方案文件结构与实际代码结构不一致

**方案描述** (`docs/planning/web-ui-phase1-design.md` 第 406-421 行):
```
src/api/
├── routes/
│   ├── __init__.py
│   ├── overview.py
│   ├── executions.py
│   └── health.py
└── services/
    ├── checkpoint_reader.py
    └── stats_aggregator.py
```

**实际代码**:
```
src/api/
├── routes.py          # 所有路由都在一个文件中
└── services/
    └── event_log.py   # 使用备选方案（独立事件日志）
```

**影响**:
- `routes.py` 201 行，职责混乱（包含路由 + 数据转换 + 状态推断）
- 缺少 `overview.py`（overview 逻辑内联在 `routes.py` 中）
- 缺少 `checkpoint_reader.py` 和 `stats_aggregator.py`
- 与 Phase 2 方案中的文件结构预期不一致

**修复建议**: 保持当前单文件也可接受，但应拆分为至少两个模块。

---

### 🟡 P1-2: `OverviewStats` 缺少 `total_cost_24h` 和 `total_tokens_24h`

**方案定义** (`web-ui-phase1-design.md` 第 112-121 行):
```python
class OverviewStats(BaseModel):
    total_executions: int
    running: int
    success: int
    failed: int
    interrupted: int
    total_cost_24h: float        # ← 方案有
    total_tokens_24h: int        # ← 方案有
```

**实际代码** (`src/api/models.py` 第 61-69 行):
```python
class OverviewStats(BaseModel):
    total_executions: int = 0
    running: int = 0
    success: int = 0
    failed: int = 0
    interrupted: int = 0
    # total_cost_24h: float = 0.0       # ← 缺失
    # total_tokens_24h: int = 0          # ← 缺失
```

**路由也未返回**: `routes.py` 第 99-110 行只返回了状态统计，没有 cost 和 tokens。

**修复建议**: 
- 在 EventLog 中添加 cost/tokens 聚合查询
- 更新 `OverviewStats` 模型和路由响应

---

### 🟡 P1-3: `list_executions` 中 `total` 计数不准确

**位置**: `src/api/routes.py` 第 148 行

```python
return ExecutionListResponse(total=len(items), items=items)
```

**问题**:
- `total` 是过滤后的 items 数量，不是数据库中的总记录数
- 前端分页组件需要知道总记录数才能正确显示页码
- 当使用 `status` 过滤时，`total` 会小于实际总数

**修复建议**:
```python
total = log.get_total_count(status=status)  # 需要新增方法
return ExecutionListResponse(total=total, items=items)
```

---

### 🟡 P1-4: NodeTimeline 使用 `node.node` 作为 React key

**位置**: `web/src/components/NodeTimeline.tsx` 第 37 行

```tsx
key={node.node}
```

**问题**:
- 如果同一节点有重试或多次执行，`node.node` 会重复
- React 会渲染不正确的 DOM 更新

**修复建议**:
```tsx
key={`${node.node}-${i}`}  // 使用索引
// 或为 NodeEvent 添加 id 字段
```

---

### 🟡 P1-5: `datetime.fromtimestamp` 缺少时区信息

**位置**: `src/api/routes.py` 第 25-28 行

```python
def _ts_to_dt(ts: float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts)  # ← 本地时区，无 TZ 信息
```

**问题**:
- 方案文档示例中时间格式为 `"2026-05-22T10:30:00Z"` (UTC)
- `datetime.fromtimestamp(ts)` 返回的是本地时区的 naive datetime
- 前端 `new Date(iso)` 会按 UTC 解析，但如果服务端时间戳来自本地时区，前后端显示的时间会不一致
- 如果服务器和客户端在不同时区，时间显示会错误

**修复建议**:
```python
from datetime import datetime, timezone

def _ts_to_dt(ts: float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)
```

---

### 🟡 P1-6: 前端缺少方案中描述的独立组件

**方案描述** (`web-ui-phase1-design.md` 第 313-319 行):
```
components/
├── Header.tsx
├── StatsCards.tsx      ✅ 已实现
├── ExecutionTable.tsx  ✅ 已实现
├── StatusBadge.tsx     ❌ 缺失
├── NodeTimeline.tsx    ✅ 已实现
└── NodeCard.tsx        ❌ 缺失（内联在 NodeTimeline 中）
```

**影响**: 不是致命问题，但 StatusBadge 的缺失导致 ExecutionTable 中的状态显示逻辑重复（ExecutionTable 和 ExecutionPage 各自维护 status 映射）。

---

## 四、次要问题（P2 — 建议优化）

### 🟢 P2-1: Refresh 按钮实际跳转到健康检查页面

**位置**: `web/src/App.tsx` 第 19-24 行

```tsx
<a href="/api/health" className="...">↻ Refresh</a>
```

**问题**: 点击后跳转到空白 JSON 页面，不是刷新仪表盘。应使用 `onClick={() => window.location.reload()}` 或触发数据重载。

### 🟢 P2-2: `ExecutionTable` 使用 `<a href>` 而非 React Router `<Link>`

**位置**: `web/src/components/ExecutionTable.tsx` 第 61-66 行

```tsx
<a href={`/executions/${item.thread_id}`} className="...">
```

**问题**: 导致完整页面刷新而非 SPA 导航。应使用 `import { Link } from 'react-router-dom'`。

### 🟢 P2-3: 缺少错误边界

前端没有 React Error Boundary，任何组件崩溃会导致整个页面白屏。

### 🟢 P2-4: `node_count` 始终为默认值 6

**位置**: `src/api/models.py` 第 37 行

```python
node_count: int = 6
```

路由代码中从未设置实际的 `node_count`（routes.py 中创建 `ExecutionItem` 时未传此字段）。前端显示的进度（如 `3/6`）中 `6` 是硬编码值。

### 🟢 P2-5: `_infer_status` 函数在路由层和 EventLog 层重复

**位置**: `src/api/routes.py` 第 31-43 行 和 `src/api/services/event_log.py` 第 162-205 行

两处有不同版本的状态推断逻辑，应该统一。

### 🟢 P2-6: `__del__` 中使用 try/except 吞掉异常

**位置**: `src/api/services/event_log.py` 第 223-227 行

```python
def __del__(self) -> None:
    try:
        self._conn.close()
    except Exception:
        pass
```

`__del__` 在 Python 中行为不可靠（可能在 GC 时调用，也可能不调用）。应依赖 `close()` 和 lifespan。

---

## 五、Phase 2 兼容性分析

| Phase 1 现状 | Phase 2 需求 | 兼容性 | 风险 |
|-------------|-------------|--------|------|
| 只有 GET 路由 | POST /api/executions, 控制 API | 🔴 冲突 | Phase 2 的写操作需要认证，Phase 1 没有 |
| EventLog 独立存储 | EventLog 复用 + 新增 node_log | ✅ 可兼容 | 需扩展 EventLog 的 log 方法 |
| `execution_completed` 事件 | `execution_completed` + `total_cost` | ⚠️ 部分 | Phase 1 未在 completion 事件中存储 cost |
| 状态推断在两层 | ExecutionManager 独立状态 | 🔴 冲突 | Phase 2 的 ExecutionManager 有自己的状态机 |
| 无 WebSocket | Phase 2 短轮询, Phase 3 WS | ✅ 可兼容 | Phase 2 也用短轮询 |
| `datetime` 无时区 | 跨时区时间一致性 | ⚠️ 风险 | 两个 Phase 的时间处理应统一为 UTC |
| `allow_origins=["*"]` | 写操作需要 CSRF 保护 | 🔴 必须修 | Phase 2 的 POST 请求在宽松 CORS 下易受攻击 |

### 关键对齐点：

1. **EventLog 扩展**: Phase 2 需要 `log_node_event()` 方法，当前 `EventLog.log()` 已支持任意 event_type，兼容
2. **API 前缀**: Phase 1 使用 `/api/` 前缀，Phase 2 也使用 `/api/`，一致
3. **数据模型**: Phase 2 新增的 `CreateExecutionRequest` 不会与 Phase 1 冲突
4. **thread_id 格式**: Phase 1 使用原始 thread_id，Phase 2 生成 `thread_{uuid}`，一致

---

## 六、问题汇总表

| ID | 风险等级 | 问题 | 影响范围 | 修复复杂度 |
|----|---------|------|---------|-----------|
| P0-1 | 🔴 安全 | CORS 全开放 + 无认证 | 所有 API | 低 |
| P0-2 | 🔴 并发 | EventLog 无线程安全保护 | 所有写/读操作 | 中 |
| P0-3 | 🔴 性能 | get_overview() O(N²) 查询 | 首页轮询 | 中 |
| P0-4 | 🔴 数据 | 状态推断逻辑不一致 | 状态显示 | 低 |
| P0-5 | 🔴 性能 | 前端轮询永不停止 | 详情页 | 低 |
| P1-1 | 🟡 架构 | 文件结构与方案不一致 | 可维护性 | 低 |
| P1-2 | 🟡 功能 | OverviewStats 缺少 cost/tokens | 概览页 | 中 |
| P1-3 | 🟡 功能 | 分页 total 计数不准确 | 列表页 | 低 |
| P1-4 | 🟡 前端 | React key 可能重复 | 时间线渲染 | 低 |
| P1-5 | 🟡 数据 | 时间戳无时区信息 | 所有时间显示 | 低 |
| P1-6 | 🟡 前端 | 缺少独立组件 | 代码复用 | 低 |
| P2-1 | 🟢 体验 | Refresh 按钮行为错误 | Header | 低 |
| P2-2 | 🟢 体验 | 使用 `<a>` 而非 `<Link>` | SPA 导航 | 低 |
| P2-3 | 🟢 健壮 | 无错误边界 | 前端崩溃 | 低 |
| P2-4 | 🟢 数据 | node_count 始终为 6 | 进度显示 | 低 |
| P2-5 | 🟢 架构 | 状态推断逻辑重复 | 可维护性 | 低 |
| P2-6 | 🟢 健壮 | `__del__` 不可靠 | 资源泄漏 | 低 |

---

## 七、修复优先级建议

**立即修复（进入 Phase 2 前）:**
1. [P0-1] 限制 CORS 来源 + 预留认证接口
2. [P0-2] 增加 EventLog 线程安全保护
3. [P0-3] 优化 get_overview() 查询性能
4. [P0-4] 统一状态推断逻辑
5. [P0-5] 添加轮询停止条件

**尽快修复:**
6. [P1-2] 补全 OverviewStats 的 cost/tokens 字段
7. [P1-3] 修复分页 total 计数
8. [P1-5] 统一使用 UTC 时间戳

**后续优化:**
9. [P1-1] 重构路由模块结构
10. [P1-4] 修复 React key
11. [P2-1 ~ P2-6] 体验优化项

---

*报告生成时间: 2026-05-22 20:37*
