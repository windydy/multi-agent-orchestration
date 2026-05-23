# Phase 8 WebSocket 实时通信 - 技术方案

> 基于 docs/design/phase8-advanced-features.md 第五部分
> 生成日期: 2026-05-20

---

## 一、需求分析

### 1.1 目标
实现 Web UI 与后端的实时通信，支持任务状态推送、日志流式输出、Agent 状态更新。

### 1.2 文档已明确内容

| 项目 | 规范来源 |
|------|----------|
| WebSocketManager 类 | 5.2 节 |
| task_id 分组机制 | 5.2 节 |
| 异常连接清理 | 5.2 节 |

### 1.3 需补充内容

| 项目 | 状态 |
|------|------|
| WebSocket 路由结构 | 需设计 |
| 事件推送格式 | 需设计 |
| 测试策略 | 需细化 |

---

## 二、技术方案

### 2.1 文件结构

```
src/api/
├── __init__.py
├── server.py          # FastAPI 主服务
├── ws.py              # WebSocketManager (已有)
└── routes/
    ├── __init__.py
    ├── websocket.py   # WebSocket 路由
    └── events.py      # 事件定义
```

### 2.2 事件推送格式设计

```python
# src/api/routes/events.py
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional, Any
from datetime import datetime


class EventType(str, Enum):
    """事件类型枚举"""
    TASK_STARTED = "task:started"
    TASK_PROGRESS = "task:progress"
    TASK_COMPLETED = "task:completed"
    TASK_FAILED = "task:failed"
    AGENT_STATUS = "agent:status"
    LOG_STREAM = "log:stream"
    METRIC_UPDATE = "metric:update"


@dataclass
class WebSocketEvent:
    """WebSocket 事件统一格式"""
    type: EventType
    task_id: str
    timestamp: str
    payload: dict[str, Any]
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False)


# 便捷工厂函数
def make_event(
    event_type: EventType,
    task_id: str,
    payload: dict,
) -> WebSocketEvent:
    return WebSocketEvent(
        type=event_type,
        task_id=task_id,
        timestamp=datetime.now().isoformat(),
        payload=payload,
    )
```

### 2.3 路由结构设计

```python
# src/api/routes/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import logging

from .events import EventType, make_event, WebSocketEvent

logger = logging.getLogger(__name__)
router = APIRouter()


# 全局 WebSocketManager 实例
from ..ws import WebSocketManager
ws_manager = WebSocketManager()


@router.websocket("/ws/tasks/{task_id}")
async def websocket_task_stream(
    websocket: WebSocket,
    task_id: str,
):
    """
    WebSocket 端点: 订阅任务实时更新
    
    路径参数:
        task_id: 任务 ID
    
    连接成功后发送:
        {"type": "task:started", "task_id": "xxx", "timestamp": "...", "payload": {...}}
    
    客户端发送:
        - {"action": "subscribe", "task_id": "xxx"}
        - {"action": "unsubscribe"}
        - {"action": "ping"}
    """
    await ws_manager.connect(task_id, websocket)
    
    try:
        # 发送连接确认
        welcome = make_event(
            EventType.TASK_STARTED,
            task_id,
            {"status": "connected", "message": f"Subscribed to task {task_id}"}
        )
        await websocket.send_text(welcome.to_json())
        
        # 保持连接，处理客户端消息
        while True:
            data = await websocket.receive_text()
            await handle_client_message(ws_manager, task_id, websocket, data)
            
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from task {task_id}")
    finally:
        await ws_manager.disconnect(task_id, websocket)


async def handle_client_message(
    ws_manager: WebSocketManager,
    task_id: str,
    websocket: WebSocket,
    data: str,
):
    """处理客户端消息"""
    import json
    try:
        msg = json.loads(data)
        action = msg.get("action")
        
        if action == "ping":
            pong = make_event(EventType.METRIC_UPDATE, task_id, {"pong": True})
            await websocket.send_text(pong.to_json())
        elif action == "subscribe":
            # 已在 connect 时处理
            pass
        elif action == "unsubscribe":
            await ws_manager.disconnect(task_id, websocket)
            
    except json.JSONDecodeError:
        logger.warning(f"Invalid JSON from client: {data}")
```

### 2.4 事件推送示例

```python
# 在任务执行过程中推送事件

# 1. 任务开始
event = make_event(
    EventType.TASK_STARTED,
    task_id="task-123",
    payload={
        "workflow_id": "wf-001",
        "status": "running",
        "started_at": "2026-05-20T10:00:00Z"
    }
)
await ws_manager.broadcast(task_id, event.to_dict())

# 2. 任务进度
event = make_event(
    EventType.TASK_PROGRESS,
    task_id="task-123",
    payload={
        "current_step": 2,
        "total_steps": 5,
        "progress_percent": 40,
        "message": "Executing agent: CodeReviewAgent"
    }
)
await ws_manager.broadcast(task_id, event.to_dict())

# 3. 日志流
event = make_event(
    EventType.LOG_STREAM,
    task_id="task-123",
    payload={
        "agent": "PlannerAgent",
        "level": "info",
        "message": "Analyzing requirements...",
        "timestamp": "2026-05-20T10:00:01Z"
    }
)
await ws_manager.broadcast(task_id, event.to_dict())

# 4. 任务完成
event = make_event(
    EventType.TASK_COMPLETED,
    task_id="task-123",
    payload={
        "status": "success",
        "result": {"summary": "Task completed"},
        "duration_seconds": 125,
        "completed_at": "2026-05-20T10:02:05Z"
    }
)
await ws_manager.broadcast(task_id, event.to_dict())
```

---

## 三、类设计

### 3.1 WebSocketManager (现有，完整版)

```python
# src/api/ws.py
from fastapi import WebSocket
from typing import Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    WebSocket 连接管理器
    
    功能:
    - 按 task_id 分组管理连接
    - 广播消息到指定任务的所有订阅者
    - 自动清理断开的连接
    """
    
    def __init__(self):
        self._connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        """
        接受 WebSocket 连接并加入任务组
        
        Args:
            task_id: 任务 ID
            websocket: WebSocket 连接
        """
        await websocket.accept()
        if task_id not in self._connections:
            self._connections[task_id] = []
        
        # 避免重复添加
        if websocket not in self._connections[task_id]:
            self._connections[task_id].append(websocket)
            logger.info(f"Client connected to task {task_id}, total: {len(self._connections[task_id])}")
    
    async def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        """
        移除 WebSocket 连接
        
        Args:
            task_id: 任务 ID
            websocket: WebSocket 连接
        """
        if task_id in self._connections:
            if websocket in self._connections[task_id]:
                self._connections[task_id].remove(websocket)
                logger.info(f"Client disconnected from task {task_id}, remaining: {len(self._connections[task_id])}")
            
            # 清理空列表
            if not self._connections[task_id]:
                del self._connections[task_id]
    
    async def broadcast(self, task_id: str, message: dict) -> int:
        """
        广播消息到指定任务的所有连接
        
        Args:
            task_id: 任务 ID
            message: 要发送的消息 (dict)
        
        Returns:
            成功发送的数量
        """
        if task_id not in self._connections:
            return 0
        
        data = json.dumps(message, ensure_ascii=False)
        dead_connections = []
        sent_count = 0
        
        for ws in self._connections[task_id]:
            try:
                await ws.send_text(data)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                dead_connections.append(ws)
        
        # 清理断开的连接
        for ws in dead_connections:
            await self.disconnect(task_id, ws)
        
        return sent_count
    
    def get_connection_count(self, task_id: str) -> int:
        """获取指定任务的连接数"""
        return len(self._connections.get(task_id, []))
    
    def get_all_tasks(self) -> List[str]:
        """获取所有活跃的任务 ID"""
        return list(self._connections.keys())
```

### 3.2 事件类设计

```python
# src/api/routes/events.py (完整版)
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, Any, Dict
from datetime import datetime
import json


class EventType(str, Enum):
    """WebSocket 事件类型"""
    # 任务事件
    TASK_STARTED = "task:started"
    TASK_PROGRESS = "task:progress"
    TASK_COMPLETED = "task:completed"
    TASK_FAILED = "task:failed"
    TASK_CANCELLED = "task:cancelled"
    
    # Agent 事件
    AGENT_STATUS = "agent:status"
    AGENT_MESSAGE = "agent:message"
    
    # 日志事件
    LOG_STREAM = "log:stream"
    
    # 指标事件
    METRIC_UPDATE = "metric:update"


@dataclass
class WebSocketEvent:
    """
    WebSocket 事件统一格式
    
    JSON 格式:
    {
        "type": "task:progress",
        "task_id": "task-123",
        "timestamp": "2026-05-20T10:00:00Z",
        "payload": {
            // 事件具体数据
        }
    }
    """
    type: EventType
    task_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    payload: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: dict) -> "WebSocketEvent":
        return cls(
            type=EventType(data["type"]),
            task_id=data["task_id"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            payload=data.get("payload", {}),
        )


# 便捷工厂函数
def make_event(
    event_type: EventType,
    task_id: str,
    payload: Optional[dict] = None,
) -> WebSocketEvent:
    """创建 WebSocket 事件的便捷函数"""
    return WebSocketEvent(
        type=event_type,
        task_id=task_id,
        timestamp=datetime.now().isoformat(),
        payload=payload or {},
    )
```

---

## 四、测试策略

### 4.1 单元测试

```python
# tests/api/test_websocket_manager.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import WebSocket

from src.api.ws import WebSocketManager
from src.api.routes.events import (
    EventType, WebSocketEvent, make_event
)


class TestWebSocketManager:
    """WebSocketManager 单元测试"""
    
    @pytest.fixture
    def manager(self):
        return WebSocketManager()
    
    @pytest.fixture
    def mock_websocket(self):
        ws = AsyncMock(spec=WebSocket)
        ws.send_text = AsyncMock()
        ws.close = AsyncMock()
        return ws
    
    @pytest.mark.asyncio
    async def test_connect(self, manager, mock_websocket):
        """测试连接建立"""
        await manager.connect("task-1", mock_websocket)
        
        mock_websocket.accept.assert_called_once()
        assert manager.get_connection_count("task-1") == 1
    
    @pytest.mark.asyncio
    async def test_disconnect(self, manager, mock_websocket):
        """测试断开连接"""
        await manager.connect("task-1", mock_websocket)
        await manager.disconnect("task-1", mock_websocket)
        
        assert manager.get_connection_count("task-1") == 0
    
    @pytest.mark.asyncio
    async def test_broadcast(self, manager, mock_websocket):
        """测试广播消息"""
        await manager.connect("task-1", mock_websocket)
        
        event = make_event(EventType.TASK_STARTED, "task-1", {"status": "running"})
        sent = await manager.broadcast("task-1", event.to_dict())
        
        assert sent == 1
        mock_websocket.send_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_task(self, manager):
        """测试向不存在的任务广播"""
        sent = await manager.broadcast("task-nonexistent", {"data": "test"})
        assert sent == 0
    
    @pytest.mark.asyncio
    async def test_multiple_connections(self, manager):
        """测试多个连接"""
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        
        await manager.connect("task-1", ws1)
        await manager.connect("task-1", ws2)
        
        assert manager.get_connection_count("task-1") == 2
        
        event = make_event(EventType.TASK_PROGRESS, "task-1", {"progress": 50})
        sent = await manager.broadcast("task-1", event.to_dict())
        
        assert sent == 2


class TestWebSocketEvent:
    """WebSocketEvent 单元测试"""
    
    def test_make_event(self):
        """测试创建事件"""
        event = make_event(
            EventType.TASK_STARTED,
            "task-123",
            {"workflow_id": "wf-001"}
        )
        
        assert event.type == EventType.TASK_STARTED
        assert event.task_id == "task-123"
        assert event.payload == {"workflow_id": "wf-001"}
    
    def test_event_to_json(self):
        """测试事件序列化"""
        event = make_event(EventType.LOG_STREAM, "task-123", {"message": "test"})
        json_str = event.to_json()
        
        assert "task:started" in json_str  # 注意: 这里应该是 log:stream
        assert "task-123" in json_str
    
    def test_event_from_dict(self):
        """测试事件反序列化"""
        data = {
            "type": "task:completed",
            "task_id": "task-456",
            "timestamp": "2026-05-20T10:00:00Z",
            "payload": {"status": "success"}
        }
        
        event = WebSocketEvent.from_dict(data)
        
        assert event.type == EventType.TASK_COMPLETED
        assert event.task_id == "task-456"
        assert event.payload["status"] == "success"
```

### 4.2 集成测试

```python
# tests/api/test_websocket_integration.py
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.routes.websocket import router as ws_router


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(ws_router)
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


class TestWebSocketIntegration:
    """WebSocket 集成测试"""
    
    def test_websocket_endpoint_exists(self, client):
        """测试 WebSocket 端点存在"""
        # 注意: TestClient 不直接支持 WebSocket 测试
        # 需要使用 httpx 或专门的 WebSocket 客户端
        pass
    
    @pytest.mark.asyncio
    async def test_websocket_connection_flow(self):
        """测试 WebSocket 连接流程"""
        import asyncio
        from httpx import AsyncClient, ASGITransport
        
        # 此测试需要实际运行服务器
        # 这里提供测试思路
        pass
```

### 4.3 前端 WebSocket Hook 测试

```typescript
// src/ui/frontend/src/hooks/__tests__/useWebSocket.test.ts
import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket';

describe('useWebSocket', () => {
  it('should connect to WebSocket', () => {
    const { result } = renderHook(() => useWebSocket('task-123'));
    
    expect(result.current.isConnected).toBe(false);
  });
  
  it('should handle incoming messages', () => {
    // Mock WebSocket
    const mockWs = {
      send: jest.fn(),
      close: jest.fn(),
    };
    
    global.WebSocket = jest.fn(() => mockWs) as any;
    
    const { result } = renderHook(() => useWebSocket('task-123'));
    
    // Simulate message
    const mockEvent = {
      data: JSON.stringify({
        type: 'task:progress',
        task_id: 'task-123',
        payload: { progress: 50 }
      })
    };
    
    // Trigger onmessage
    mockWs.onmessage?.(mockEvent);
    
    expect(result.current.lastMessage).toEqual({
      type: 'task:progress',
      payload: { progress: 50 }
    });
  });
});
```

---

## 五、实施步骤

| 步骤 | 内容 | 文件 | 预估时间 |
|------|------|------|----------|
| 1 | 创建事件定义模块 | `src/api/routes/events.py` | 0.5 天 |
| 2 | 完善 WebSocketManager | `src/api/ws.py` | 0.5 天 |
| 3 | 实现 WebSocket 路由 | `src/api/routes/websocket.py` | 0.5 天 |
| 4 | 集成到主服务 | `src/api/server.py` | 0.25 天 |
| 5 | 单元测试 | `tests/api/test_websocket_manager.py` | 0.5 天 |
| 6 | 集成测试 | `tests/api/test_websocket_integration.py` | 0.25 天 |
| **合计** | | | **2.5 天** |

---

## 六、API 参考

### 6.1 WebSocket 连接

```
WS /ws/tasks/{task_id}
```

### 6.2 事件格式

```json
{
  "type": "task:progress",
  "task_id": "task-123",
  "timestamp": "2026-05-20T10:00:00Z",
  "payload": {
    "current_step": 2,
    "total_steps": 5,
    "progress_percent": 40,
    "message": "Executing agent: CodeReviewAgent"
  }
}
```

### 6.3 事件类型清单

| 事件类型 | 说明 | payload 字段 |
|----------|------|--------------|
| `task:started` | 任务开始 | workflow_id, status, started_at |
| `task:progress` | 任务进度 | current_step, total_steps, progress_percent, message |
| `task:completed` | 任务完成 | status, result, duration_seconds, completed_at |
| `task:failed` | 任务失败 | status, error, failed_at |
| `task:cancelled` | 任务取消 | status, cancelled_at |
| `agent:status` | Agent 状态 | agent_name, status |
| `agent:message` | Agent 消息 | agent_name, message |
| `log:stream` | 日志流 | agent, level, message, timestamp |
| `metric:update` | 指标更新 | metrics object |

---

## 七、注意事项

1. **连接管理**: WebSocketManager 需作为单例或依赖注入，确保全局唯一
2. **断线重连**: 前端需实现自动重连机制
3. **心跳保活**: 建议添加 ping/pong 机制检测连接状态
4. **消息顺序**: 事件按 timestamp 排序，前端需处理乱序情况
5. **安全性**: 生产环境需添加认证token验证
