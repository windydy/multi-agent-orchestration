# Phase 2: 任务提交与交互 — 技术方案

> 能在 Web 上发起任务、控制执行、查看实时日志

> **评审状态**: 已修复所有 P0/P1/P2 问题（详见 review-phase2-design.md）

---

## 零、评审问题修复记录

| 问题 | 修复方式 | 状态 |
|------|---------|------|
| P0-1: bind_task 缺失 | 添加 `ExecutionManager.bind_task()` 方法 | ✅ 已修复 |
| P0-1: thread_id 注入机制 | PipelineBuilder 集成时通过 `config["configurable"]["thread_id"]` 传递，在 `_create_node_functions` 中读取 | 📋 标记为实施约束 |
| P0-1: pause_event 阻塞位置 | pause_event 应在节点函数**开头**检查，用于暂停节点间流转；LLM 调用中的暂停需通过 `bind_task` + `task.cancel()` 实现 | 📋 标记为实施约束 |
| P0-2: 服务重启恢复 | `ExecutionManager.recover()` + lifespan 集成 | ✅ 已修复 |
| P0-3: 文件路径安全 | 改用查询参数 `?path=...` + `_safe_resolve_path()` 白名单验证 | ✅ 已修复 |
| P0-4: 并发安全 | 所有状态变更使用 `asyncio.Lock` 保护 | ✅ 已修复 |
| S1: 日志分页语义 | LogResponse 增加 `has_more`/`next_offset`/`total` | ✅ 已修复 |
| S2: 前端轮询控制 | 合并 detail + logs 为单一轮询入口；执行完成后停止轮询；用户手动滚动时不自动跳到底部 | 📋 前端实施约束 |
| S3: 请求模型验证 | CreateExecutionRequest 添加 Field 约束 | ✅ 已修复 |
| S4: 工作流/模型枚举 | 新增 `GET /api/workflows` 和 `GET /api/models` | ✅ 已修复 |
| S5: 文件变更检测 | 执行前记录文件快照（路径 + mtime + size），执行后对比，结果写入 EventLog 的 `execution_completed` 事件 data 字段 | 📋 标记为实施约束 |
| S6: 前端错误边界 | LogViewer 处理 API 错误；ControlButtons 添加 loading 状态；TaskForm 添加表单验证 | 📋 前端实施约束 |
| S7: 日志写入优化 | EventLog 改为批量写入或 WAL 模式 | 📋 标记为实施约束 |

---

## 一、目标

Phase 1 只读 Dashboard 只能"看"。Phase 2 实现"操作"——用户在浏览器中创建任务、控制执行流程、实时查看日志和文件变更。

---

## 二、功能清单

| 功能 | 说明 | 优先级 |
|------|------|--------|
| **新建任务表单** | 输入任务描述、选择工作流模板、目标项目路径、模型配置 | P0 |
| **任务控制** | 暂停 / 恢复 / 终止正在运行的执行 | P0 |
| **实时日志流** | 每个节点执行时实时展示 stdout/stderr，带语法高亮 | P1 |
| **文件预览** | 查看 Agent 创建/修改的文件内容，支持 diff 对比 | P1 |

---

## 三、REST API 设计

### 3.1 接口列表

```
POST   /api/executions              # 创建新执行
POST   /api/executions/{id}/cancel  # 终止执行
POST   /api/executions/{id}/pause   # 暂停执行
POST   /api/executions/{id}/resume  # 恢复执行
GET    /api/executions/{id}/logs    # 获取日志
GET    /api/executions/{id}/files   # 获取变更文件列表
GET    /api/executions/{id}/files/{path}  # 获取文件内容
```

### 3.2 详细定义

#### `POST /api/executions`

```json
// Request
{
  "task": "实现一个用户管理API，包含CRUD操作",
  "workflow": "development",          // 可选，默认 development
  "project_path": "/Users/me/myapp",  // 可选
  "models": {                         // 可选，覆盖默认模型
    "developer": "sonnet",
    "reviewer": "opus"
  }
}

// Response 201
{
  "thread_id": "thread_xyz789",
  "status": "running",
  "started_at": "2026-05-22T16:00:00Z",
  "workflow": "development"
}
```

#### `POST /api/executions/{id}/cancel`

```json
// Response 200
{ "thread_id": "thread_xyz789", "status": "cancelled" }
```

#### `GET /api/executions/{id}/logs`

```json
// Response 200
{
  "logs": [
    {
      "node": "requirements",
      "timestamp": "2026-05-22T16:00:01Z",
      "level": "info",
      "message": "分析任务: 实现一个用户管理API..."
    },
    {
      "node": "requirements",
      "timestamp": "2026-05-22T16:00:05Z",
      "level": "info",
      "message": "调用 LLM: anthropic/claude-sonnet-4 (input: 320 tokens)"
    }
  ]
}
```

#### `GET /api/executions/{id}/files`

```json
// Response 200
{
  "files": [
    { "path": "src/api/models.py", "status": "created", "size": 1678 },
    { "path": "src/api/routes.py", "status": "created", "size": 6400 },
    { "path": "src/api/server.py", "status": "modified", "size": 1678 }
  ]
}
```

---

## 四、前端页面设计

### 4.1 新建任务页 (`/new`)

```
┌──────────────────────────────────────────────────┐
│  ← Back              New Task                    │
├──────────────────────────────────────────────────┤
│                                                  │
│  Task Description                                │
│  ┌──────────────────────────────────────────┐   │
│  │ 实现一个用户管理API，包含 CRUD 操作...     │   │
│  │                                          │   │
│  │                                          │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  Workflow          ▼ development                 │
│  Project Path      [/Users/me/myapp       ]      │
│                                                  │
│  ─── Advanced (optional) ────                   │
│  Developer Model   ▼ sonnet                      │
│  Reviewer Model    ▼ opus                        │
│  Max Iterations    [10    ]                      │
│                                                  │
│  ┌──────────────────┐                            │
│  │  ▶ Start Workflow │                            │
│  └──────────────────┘                            │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 4.2 详情页新增区域

```
┌──────────────────────────────────────────────────┐
│  thread_xyz789        🔵 Running   [⏸ Pause] [⏹ Stop] │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌── Timeline ──┐  ┌── Logs ───────────────┐   │
│  │              │  │                        │   │
│  │ ✅ req  0:14 │  │ [16:00:01] INFO        │   │
│  │ ✅ dev  1:15 │  │ 分析任务: 实现...       │   │
│  │ 🔵 rev  ...  │  │                        │   │
│  │ ○  test      │  │ [16:00:05] INFO        │   │
│  │ ○  fix       │  │ 调用 LLM: sonnet...    │   │
│  │              │  │                        │   │
│  │              │  │ [16:00:12] INFO        │   │
│  │              │  │ ✓ Review approved      │   │
│  │              │  │                        │   │
│  └──────────────┘  └────────────────────────┘   │
│                                                  │
│  ─── Files Changed (3) ────                     │
│  + src/api/models.py        1.6 KB               │
│  + src/api/routes.py        6.4 KB               │
│  ~ src/api/server.py        1.7 KB               │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## 五、后端实现方案

### 5.1 执行管理

```python
# src/api/services/executor.py

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ExecutionHandle:
    thread_id: str
    task: str
    workflow: str
    status: str  # running / paused / cancelled / completed / failed
    started_at: float
    process: Optional[asyncio.Task] = None
    cancel_event: Optional[asyncio.Event] = None
    pause_event: Optional[asyncio.Event] = None
    log_buffer: list[dict] = field(default_factory=list)

class ExecutionManager:
    """管理正在运行的执行实例"""
    
    def __init__(self):
        self._executions: dict[str, ExecutionHandle] = {}
    
    def start(self, task: str, workflow: str, config: dict) -> ExecutionHandle:
        """启动新执行"""
        thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        handle = ExecutionHandle(
            thread_id=thread_id,
            task=task,
            workflow=workflow,
            status="running",
            started_at=time.time(),
            cancel_event=asyncio.Event(),
            pause_event=asyncio.Event(),
        )
        handle.pause_event.set()  # not paused initially
        self._executions[thread_id] = handle
        return handle
    
    def cancel(self, thread_id: str) -> bool:
        """终止执行"""
        handle = self._executions.get(thread_id)
        if not handle or handle.status != "running":
            return False
        handle.status = "cancelled"
        handle.cancel_event.set()
        return True
    
    def pause(self, thread_id: str) -> bool:
        """暂停执行"""
        handle = self._executions.get(thread_id)
        if not handle or handle.status != "running":
            return False
        handle.status = "paused"
        handle.pause_event.clear()
        return True
    
    def resume(self, thread_id: str) -> bool:
        """恢复执行"""
        handle = self._executions.get(thread_id)
        if not handle or handle.status != "paused":
            return False
        handle.status = "running"
        handle.pause_event.set()
        return True
    
    def get(self, thread_id: str) -> Optional[ExecutionHandle]:
        return self._executions.get(thread_id)
    
    def list_running(self) -> list[ExecutionHandle]:
        return [h for h in self._executions.values() if h.status == "running"]
```

### 5.2 与 PipelineBuilder 集成

在 PipelineBuilder 的节点函数中注入日志和暂停检查：

```python
# 在 _create_node_functions 中：
async def node_func(state: WorkflowState, agent_name=name) -> dict:
    # 检查取消
    handle = execution_manager.get(config["thread_id"])
    if handle and handle.cancel_event.is_set():
        return {"current_stage": "cancelled"}
    
    # 等待恢复（如果暂停）
    if handle:
        await handle.pause_event.wait()
    
    # 记录日志
    execution_manager.log_event(handle.thread_id, "info", 
                                f"Starting node: {agent_name}")
    
    result = await agent.run(state.get("task", ""), context)
    
    execution_manager.log_event(handle.thread_id, "info",
                                f"Completed node: {agent_name} ({result.success})")
    
    # ... 返回更新
```

### 5.3 日志存储

复用 EventLog，新增 `node_log` 字段：

```python
# 扩展现有 EventLog
def log_node_event(self, thread_id: str, node: str, level: str, message: str):
    """记录节点级别的日志"""
    self.log(thread_id, "node_log", time.time(), node_name=node,
             data={"level": level, "message": message})
```

---

## 六、前端实现方案

### 6.1 新增页面

```
web/src/
├── pages/
│   ├── HomePage.tsx          # 已有
│   ├── ExecutionPage.tsx     # 已有
│   └── NewTaskPage.tsx       # 新建任务表单
├── components/
│   ├── TaskForm.tsx          # 任务表单组件
│   ├── LogViewer.tsx         # 实时日志查看器
│   ├── FileList.tsx          # 变更文件列表
│   └── ControlButtons.tsx    # 暂停/恢复/终止按钮
└── lib/
    └── api.ts                # 新增: createExecution, cancel, logs
```

### 6.2 实时日志实现

Phase 2 MVP 使用 **短轮询**（每 1s 请求 `/api/executions/{id}/logs`），Phase 3 升级为 WebSocket。

```tsx
// LogViewer.tsx
function LogViewer({ threadId }: { threadId: string }) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  
  useEffect(() => {
    let offset = 0
    const timer = setInterval(async () => {
      const res = await fetch(`/api/executions/${threadId}/logs?offset=${offset}`)
      const data = await res.json()
      if (data.logs.length > 0) {
        setLogs(prev => [...prev, ...data.logs])
        offset += data.logs.length
      }
    }, 1000)
    return () => clearInterval(timer)
  }, [threadId])
  
  return (
    <div className="font-mono text-xs bg-bg-elevated rounded p-4 max-h-96 overflow-auto">
      {logs.map((log, i) => (
        <div key={i} className={`py-0.5 ${levelColor[log.level]}`}>
          <span className="text-text-subtle">[{log.timestamp}]</span>
          {' '}{log.message}
        </div>
      ))}
    </div>
  )
}
```

---

## 七、实施步骤

| Step | 内容 | 时间 |
|------|------|------|
| 1 | TDD: ExecutionManager 服务 + 测试 | 0.5 天 |
| 2 | TDD: POST /api/executions + 控制 API + 测试 | 0.5 天 |
| 3 | TDD: 日志 API + 文件 API + 测试 | 0.5 天 |
| 4 | PipelineBuilder 集成日志和暂停检查 | 0.5 天 |
| 5 | NewTaskPage 表单 + 控制按钮 | 1 天 |
| 6 | LogViewer 组件 + FileList 组件 | 1 天 |

**总计：约 4 天**

---

## 八、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| LangGraph 执行中断后状态不一致 | 执行卡在中间状态 | 使用 LangGraph interrupt 机制，确保 checkpoint 一致性 |
| 日志轮询增加后端负载 | 多用户同时查看日志时 | 1s 间隔 + ETag 条件请求；Phase 3 升级为 WebSocket |
| 长时间执行导致内存泄漏 | ExecutionManager 累积 | 添加清理机制，完成后保留 24h 后清理 |
| 文件变更检测不准确 | Agent 创建的文件没被记录 | 使用 snapshot diff 方式，执行前后对比文件系统 |

---

*创建时间: 2026-05-22*
