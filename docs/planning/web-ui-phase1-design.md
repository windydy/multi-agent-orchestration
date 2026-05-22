# Phase 1: Web UI MVP — 只读 Dashboard 技术方案

> 最小 MVP：能"看到"系统在做什么，不替代 CLI

---

## 一、架构概览

```
┌──────────────────────────────────────────────────┐
│  Browser (React + Vite)                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐ │
│  │ Home 列表  │  │ Detail 详情│  │ WS 实时流  │ │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘ │
│        │               │               │         │
│  ┌─────┴───────────────┴───────────────┴──────┐ │
│  │  HTTP REST          WebSocket             │ │
│  └─────┬──────────────────────┬──────────────┘ │
└────────┼──────────────────────┼────────────────┘
         │                      │
┌────────┴──────────────────────┴────────────────┐
│  FastAPI (src/api/server.py)                   │
│  ┌────────────────────┐  ┌───────────────────┐ │
│  │ REST Routes        │  │ WS Manager        │ │
│  │ GET /api/executions│  │ /ws/stream/{tid}  │ │
│  │ GET /api/exec/{id} │  │ broadcast events  │ │
│  │ GET /api/overview  │  │                   │ │
│  └────────┬───────────┘  └─────────┬─────────┘ │
│           │                        │            │
│  ┌────────┴────────────────────────┴──────────┐ │
│  │  Service Layer (复用现有代码)               │ │
│  │  - SQLite checkpointer (读取状态)          │ │
│  │  - MetricsCollector (读取指标)             │ │
│  │  - Workflow builder (读取图结构)            │ │
│  └───────────────────────────────────────────┘ │
└────────────────────────────────────────────────┘
```

**核心原则：**
- FastAPI 作为独立子应用挂载，不改动现有 CLI/工作流代码
- 只读 — 不写数据库、不触发执行、不修改配置
- 复用 SQLite checkpointer 作为唯一数据源

---

## 二、数据模型设计

### 2.1 SQLite 数据源分析

项目已有的 LangGraph SqliteSaver 在 `./checkpoints/pipeline.db` 中存储了：
- `checkpoints` 表 — 每次状态快照（thread_id, checkpoint, state blob）
- `writes` 表 — 节点写入记录

此外 MetricsCollector 在内存中维护了运行时指标。

### 2.2 API 响应模型 (Pydantic)

```python
# src/api/models.py

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class NodeEvent(BaseModel):
    """单个节点的执行事件"""
    node: str                    # 节点名: requirements/design/develop/...
    status: NodeStatus
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    output_summary: Optional[str] = None   # 截断的输出（前500字）
    error: Optional[str] = None
    token_usage: Optional[dict] = None     # {input: N, output: N}


class ExecutionItem(BaseModel):
    """执行列表中的一条"""
    thread_id: str
    workflow_name: str           # 默认 "development"
    status: str                  # running / success / failed / interrupted
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    node_count: int              # 总节点数
    completed_nodes: int         # 已完成节点数


class ExecutionDetail(BaseModel):
    """执行详情页"""
    thread_id: str
    workflow_name: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    nodes: list[NodeEvent]       # 按执行顺序
    total_cost: Optional[float] = None
    total_tokens: Optional[int] = None
    task_input: Optional[str] = None   # 用户输入的原始任务


class OverviewStats(BaseModel):
    """系统概览"""
    total_executions: int
    running: int
    success: int
    failed: int
    interrupted: int
    total_cost_24h: float
    total_tokens_24h: int
```

---

## 三、REST API 设计

### 3.1 接口列表

```
GET  /api/overview              # 系统概览统计
GET  /api/executions            # 执行列表（分页）
GET  /api/executions/{thread_id} # 执行详情
GET  /health                    # 健康检查
```

### 3.2 详细定义

#### `GET /api/overview`

```json
{
  "total_executions": 42,
  "running": 3,
  "success": 35,
  "failed": 2,
  "interrupted": 2,
  "total_cost_24h": 1.23,
  "total_tokens_24h": 45200
}
```

**数据来源：** 遍历 SQLite checkpoints 表，按 thread_id 去重统计最新状态。

---

#### `GET /api/executions`

Query params: `limit=20`, `offset=0`, `status=running` (可选过滤)

```json
{
  "total": 42,
  "items": [
    {
      "thread_id": "thread_abc123",
      "workflow_name": "development",
      "status": "running",
      "started_at": "2026-05-22T10:30:00Z",
      "ended_at": null,
      "duration_ms": null,
      "node_count": 6,
      "completed_nodes": 3
    }
  ]
}
```

---

#### `GET /api/executions/{thread_id}`

```json
{
  "thread_id": "thread_abc123",
  "workflow_name": "development",
  "status": "running",
  "started_at": "2026-05-22T10:30:00Z",
  "ended_at": null,
  "duration_ms": null,
  "nodes": [
    {
      "node": "requirements",
      "status": "success",
      "started_at": "2026-05-22T10:30:01Z",
      "ended_at": "2026-05-22T10:30:15Z",
      "duration_ms": 14200,
      "output_summary": "需求分析完成：用户需要一个...",
      "error": null,
      "token_usage": {"input": 320, "output": 850}
    },
    {
      "node": "design",
      "status": "success",
      ...
    },
    {
      "node": "develop",
      "status": "running",
      "started_at": "2026-05-22T10:30:45Z",
      "ended_at": null,
      ...
    }
  ],
  "total_cost": 0.45,
  "total_tokens": 5200,
  "task_input": "实现一个用户管理API..."
}
```

---

## 四、WebSocket 实时流设计

### 4.1 连接

```
WS /ws/stream/{thread_id}     # 订阅特定执行的实时事件
WS /ws/stream                  # 订阅全局事件（新建执行、状态变更）
```

### 4.2 事件格式

```json
{
  "type": "node_started",       // 事件类型
  "thread_id": "thread_abc123",
  "timestamp": "2026-05-22T10:30:45Z",
  "data": {
    "node": "develop",
    "status": "running"
  }
}
```

### 4.3 事件类型枚举

| type | 触发时机 | data 字段 |
|------|---------|----------|
| `node_started` | 节点开始执行 | `{node, status}` |
| `node_completed` | 节点成功完成 | `{node, status, duration_ms, output_summary, token_usage}` |
| `node_failed` | 节点执行失败 | `{node, status, error}` |
| `execution_started` | 新执行开始 | `{thread_id, workflow_name, task_input}` |
| `execution_completed` | 执行结束 | `{thread_id, status, duration_ms, total_cost}` |
| `interrupted` | 人工审批中断 | `{thread_id, node, message}` |

### 4.4 与现有代码的集成方式

在 LangGraph 节点函数中通过 Hook 或回调发出事件：

```python
# 方案：使用 LangGraph 的 run-time 回调
# 在 cli/main.py 或 runner 层注入

async def stream_execution(app, thread_id: str, config: dict):
    """流式执行并广播事件"""
    async for event in app.astream_events(input, config=config, version="v2"):
        event_type = event["event"]
        
        if event_type == "on_chain_start":
            await ws_manager.broadcast(thread_id, {
                "type": "node_started",
                "thread_id": thread_id,
                "data": {"node": event["name"]}
            })
        
        elif event_type == "on_chain_end":
            await ws_manager.broadcast(thread_id, {
                "type": "node_completed",
                "thread_id": thread_id,
                "data": {
                    "node": event["name"],
                    "duration_ms": ...,
                    "output_summary": ...
                }
            })
```

**MVP 阶段简化方案：** 先用 polling 实现实时性（前端每 2 秒轮询 `/api/executions/{id}`），WebSocket 在 Phase 2 再做。理由是 LangGraph 的 `astream_events` 集成需要改动执行路径，MVP 先跑起来再优化。

---

## 五、前端架构

### 5.1 项目结构

```
web/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── tailwind.config.ts          # Tailwind CSS 配置
├── src/
│   ├── main.tsx                # 入口
│   ├── App.tsx                 # 路由
│   ├── lib/
│   │   └── api.ts              # fetch 封装
│   ├── types/
│   │   └── index.ts            # TypeScript 类型定义
│   ├── pages/
│   │   ├── HomePage.tsx        # 执行列表 + 概览
│   │   └── ExecutionPage.tsx   # 执行详情
│   └── components/
│       ├── Header.tsx          # 顶部导航
│       ├── StatsCards.tsx      # 概览 4 卡片
│       ├── ExecutionTable.tsx  # 执行列表表格
│       ├── StatusBadge.tsx     # 状态标签（颜色）
│       ├── NodeTimeline.tsx    # 节点时间线（详情页）
│       └── NodeCard.tsx        # 单个节点卡片
```

### 5.2 页面布局

```
┌─────────────────────────────────────────────────────┐
│  ◈ Multi-Agent Dashboard              [Refresh] ⚙ │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│
│  │ Running  │ │ Success  │ │ Failed   │ │ Total  ││
│  │    3     │ │   35     │ │    2     │ │   42   ││
│  └──────────┘ └──────────┘ └──────────┘ └────────┘│
│                                                     │
│  Executions                          [Search] [Filter]│
│  ┌─────────────────────────────────────────────┐  │
│  │ ID          │ Workflow  │ Status │ Duration │  │
│  ├─────────────────────────────────────────────┤  │
│  │ thread_abc  │ develop   │ 🟢 Done│ 2m 34s  │  │
│  │ thread_def  │ develop   │ 🔵 Run │ 1m 12s  │  │
│  │ thread_ghi  │ develop   │ 🔴 Fail│ 0m 45s  │  │
│  └─────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**执行详情页：**

```
┌─────────────────────────────────────────────────────┐
│  ← Back              thread_abc123    🟢 Completed  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Task: 实现一个用户管理API...                         │
│  Started: 2026-05-22 10:30   Duration: 2m 34s       │
│  Cost: $0.45    Tokens: 5,200                       │
│                                                     │
│  ─── Execution Timeline ────────────────────────   │
│                                                     │
│  ✅ requirements    需求分析         0:14   320→850 │
│     └ 需求分析完成：用户需要...（点击展开）            │
│                                                     │
│  ✅ design          技术设计         0:22   900→1200│
│     └ 架构方案：FastAPI + SQLite...                  │
│                                                     │
│  ✅ develop         开发实现         1:15   1500→3200│
│     └ 已创建 3 个文件: src/api/...                   │
│                                                     │
│  ✅ review          代码审查         0:28   2800→650 │
│     └ Approved: 代码质量良好...                      │
│                                                     │
│  ✅ test            测试验证         0:15   400→300  │
│     └ All 5 tests passed                             │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 5.3 技术选型

| 项目 | 选择 | 理由 |
|------|------|------|
| 框架 | React 18 + TypeScript | 生态成熟 |
| 构建 | Vite | 快，与 FastAPI 配合好 |
| UI | Tailwind CSS + 手写组件 | 轻量，不引入重量级 UI 库 |
| 路由 | React Router v6 | 标准 |
| HTTP | 原生 fetch | 接口简单，不需要 axios |
| 实时 | Phase 1: polling (2s) | 零依赖，MVP 够用 |

### 5.4 开发/生产模式

```
开发模式:
  FastAPI:  localhost:8000  (API)
  Vite:     localhost:5173  (前端，代理 API → 8000)

生产模式:
  FastAPI 直接 serve 前端静态文件:
  app.mount("/", StaticFiles(directory="web/dist", html=True))
  一条命令: hermes dashboard --port 8000
```

---

## 六、FastAPI 后端实现细节

### 6.1 文件结构

```
src/api/
├── __init__.py
├── server.py              # FastAPI app 入口
├── models.py              # Pydantic 响应模型
├── routes/
│   ├── __init__.py
│   ├── overview.py        # GET /api/overview
│   ├── executions.py      # GET /api/executions, /api/executions/{id}
│   └── health.py          # GET /health
└── services/
    ├── __init__.py
    ├── checkpoint_reader.py   # 读取 SQLite checkpointer
    └── stats_aggregator.py    # 聚合统计数据
```

### 6.2 SQLite 数据读取策略

```python
# src/api/services/checkpoint_reader.py

import sqlite3
import json
from typing import Optional

class CheckpointReader:
    """从 LangGraph SqliteSaver 的数据库读取执行状态"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def _conn(self):
        return sqlite3.connect(self.db_path)
    
    def list_threads(self, limit=20, offset=0, status=None) -> list[dict]:
        """列出所有 thread_id 及最新状态"""
        conn = self._conn()
        # LangGraph checkpoints 表结构:
        # (thread_id, checkpoint_ns, checkpoint_id, type, checkpoint, metadata, parent_id)
        query = """
            SELECT DISTINCT thread_id, 
                   MAX(checkpoint_id) as latest_cp
            FROM checkpoints
            GROUP BY thread_id
            ORDER BY latest_cp DESC
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(query, (limit, offset)).fetchall()
        conn.close()
        # 对每个 thread_id 取最新 state 解析 status
        ...
    
    def get_thread_state(self, thread_id: str) -> dict:
        """获取指定 thread 的完整状态"""
        conn = self._conn()
        query = """
            SELECT checkpoint, metadata
            FROM checkpoints
            WHERE thread_id = ?
            ORDER BY checkpoint_id DESC
            LIMIT 1
        """
        row = conn.execute(query, (thread_id,)).fetchone()
        conn.close()
        if row:
            checkpoint = json.loads(row[0])  # or pickle，取决于序列化方式
            metadata = json.loads(row[1])
            return {"checkpoint": checkpoint, "metadata": metadata}
        return {}
    
    def get_node_events(self, thread_id: str) -> list[dict]:
        """从 writes 表提取节点执行事件"""
        conn = self._conn()
        # LangGraph writes 表结构:
        # (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value)
        query = """
            SELECT task_id, channel, type, value
            FROM writes
            WHERE thread_id = ?
            ORDER BY checkpoint_id, idx
        """
        rows = conn.execute(query, (thread_id,)).fetchall()
        conn.close()
        # 解析为 NodeEvent 列表
        ...
```

**注意：** 需要根据实际 SqliteSaver 的表结构做适配。LangGraph 的 SqliteSaver 使用 pickle 序列化 checkpoint，需要反序列化后才能读取状态。

### 6.3 备选方案：独立事件日志

如果直接读取 SqliteSaver 的 pickle 数据太复杂，MVP 阶段采用更简单的方案：

**在执行层注入一个轻量事件日志：**

```python
# src/api/services/event_log.py

import sqlite3
import json
import time
from dataclasses import dataclass

@dataclass
class ExecutionEvent:
    thread_id: str
    event_type: str      # node_started / node_completed / ...
    node_name: str
    timestamp: float
    data: dict           # 任意 JSON 数据

class EventLog:
    """独立的事件日志表，与 LangGraph checkpointer 分离"""
    
    def __init__(self, db_path: str = "./checkpoints/events.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                node_name TEXT,
                timestamp REAL NOT NULL,
                data TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_thread 
            ON execution_events(thread_id)
        """)
        conn.commit()
        conn.close()
    
    def log(self, event: ExecutionEvent):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO execution_events (thread_id, event_type, node_name, timestamp, data) VALUES (?, ?, ?, ?, ?)",
            (event.thread_id, event.event_type, event.node_name, event.timestamp, json.dumps(event.data))
        )
        conn.commit()
        conn.close()
    
    def get_execution(self, thread_id: str) -> dict:
        """聚合一个执行的所有事件为完整视图"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT event_type, node_name, timestamp, data FROM execution_events WHERE thread_id = ? ORDER BY timestamp",
            (thread_id,)
        ).fetchall()
        conn.close()
        # 聚合为 ExecutionDetail
        ...
    
    def list_executions(self, limit=20, offset=0) -> list[dict]:
        """列出最近执行（每个 thread_id 取最新）"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT thread_id, 
                   MIN(timestamp) as started,
                   MAX(timestamp) as ended,
                   COUNT(*) as event_count
            FROM execution_events
            GROUP BY thread_id
            ORDER BY started DESC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()
        conn.close()
        ...
```

**注入点：** 在 PipelineBuilder 的节点函数中调用 `event_log.log()`：

```python
# 在 _create_node_functions 中：
async def node_func(state: WorkflowState, agent_name=name, field_name=field) -> dict:
    event_log.log(ExecutionEvent(
        thread_id=config.get("thread_id"),
        event_type="node_started",
        node_name=agent_name,
        timestamp=time.time(),
        data={}
    ))
    
    result = await agent.run(state.get("task", ""), context)
    
    event_log.log(ExecutionEvent(
        thread_id=config.get("thread_id"),
        event_type="node_completed",
        node_name=agent_name,
        timestamp=time.time(),
        data={
            "success": result.success,
            "output_summary": str(result.output)[:500],
            "token_usage": result.metadata.get("token_usage"),
        }
    ))
    ...
```

**MVP 选择：独立事件日志方案**（更可控、不影响现有 checkpointer）。

---

## 七、实施步骤

### Step 1: FastAPI 后端骨架（0.5 天）

- [ ] 创建 `src/api/` 目录结构
- [ ] `server.py` — FastAPI app + CORS + 路由注册
- [ ] `models.py` — Pydantic 模型
- [ ] `services/event_log.py` — 事件日志服务
- [ ] `routes/health.py` — GET /health
- [ ] 集成测试：curl 验证 API 返回

### Step 2: 事件日志注入（0.5 天）

- [ ] 在 PipelineBuilder 节点函数中注入 event_log.log()
- [ ] 添加 execution_started / execution_completed 事件
- [ ] 验证：运行一次 CLI 执行后，events.db 中有记录

### Step 3: REST API 实现（0.5 天）

- [ ] GET /api/overview — 聚合统计
- [ ] GET /api/executions — 列表
- [ ] GET /api/executions/{id} — 详情
- [ ] 错误处理：thread_id 不存在返回 404

### Step 4: 前端项目搭建（0.5 天）

- [ ] `npm create vite@latest web -- --template react-ts`
- [ ] 安装依赖：react-router-dom, tailwindcss
- [ ] 配置 Vite 代理 → localhost:8000
- [ ] 创建基础布局（Header + 页面框架）

### Step 5: 前端页面开发（1 天）

- [ ] HomePage — StatsCards + ExecutionTable
- [ ] ExecutionPage — NodeTimeline + NodeCard
- [ ] StatusBadge 颜色映射
- [ ] 自动刷新（每 2 秒 polling）

### Step 6: 启动脚本（0.5 天）

- [ ] CLI 命令：`hermes dashboard [--port 8000]`
- [ ] 开发模式：concurrently 启动 FastAPI + Vite
- [ ] 生产模式：FastAPI serve static

---

## 八、依赖清单

### Python (后端)

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
pydantic>=2.0
```

### Node.js (前端)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.1.0",
    "typescript": "^5.3.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0"
  }
}
```

---

## 九、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| LangGraph SqliteSaver 表结构不透明 | 无法直接读 checkpoint | 使用独立 events.db 方案 |
| 大执行记录导致 API 慢 | 详情页加载慢 | 限制输出摘要长度，分页加载节点 |
| 前端轮询增加后端负载 | 多用户同时访问时 | 2s 间隔 + 条件请求（ETag） |
| pickle 反序列化安全问题 | events.db 方案不涉及 | — |

---

*创建时间: 2026-05-22*
