"""
WebSocketManager 和 WebSocketEvent 单元测试

TDD: 先写测试，再写实现。
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.api.ws import WebSocketManager
from src.api.routes.events import (
    EventType,
    WebSocketEvent,
    make_event,
)


# ============================================================================
# WebSocketManager 测试
# ============================================================================

class TestWebSocketManager:
    """WebSocketManager 单元测试"""

    @pytest.fixture
    def manager(self) -> WebSocketManager:
        return WebSocketManager()

    @pytest.fixture
    def mock_websocket(self) -> AsyncMock:
        """创建模拟 WebSocket 连接"""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.close = AsyncMock()
        return ws

    # ---- connect 测试 ----

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, manager: WebSocketManager, mock_websocket: AsyncMock) -> None:
        """测试连接时调用 websocket.accept()"""
        await manager.connect("task-1", mock_websocket)
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_adds_to_task_group(self, manager: WebSocketManager, mock_websocket: AsyncMock) -> None:
        """测试连接后加入任务组"""
        await manager.connect("task-1", mock_websocket)
        assert manager.get_connection_count("task-1") == 1

    @pytest.mark.asyncio
    async def test_connect_creates_new_task_group(self, manager: WebSocketManager, mock_websocket: AsyncMock) -> None:
        """测试连接新任务时创建新组"""
        await manager.connect("task-new", mock_websocket)
        assert "task-new" in manager.get_all_tasks()

    @pytest.mark.asyncio
    async def test_connect_prevents_duplicate(self, manager: WebSocketManager, mock_websocket: AsyncMock) -> None:
        """测试防止重复添加同一连接"""
        await manager.connect("task-1", mock_websocket)
        await manager.connect("task-1", mock_websocket)
        assert manager.get_connection_count("task-1") == 1

    @pytest.mark.asyncio
    async def test_connect_multiple_tasks(self, manager: WebSocketManager) -> None:
        """测试多个不同任务的连接"""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()

        await manager.connect("task-1", ws1)
        await manager.connect("task-2", ws2)

        assert manager.get_connection_count("task-1") == 1
        assert manager.get_connection_count("task-2") == 1
        assert len(manager.get_all_tasks()) == 2

    @pytest.mark.asyncio
    async def test_connect_multiple_clients_same_task(self, manager: WebSocketManager) -> None:
        """测试同一任务多个客户端连接"""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()

        await manager.connect("task-1", ws1)
        await manager.connect("task-1", ws2)

        assert manager.get_connection_count("task-1") == 2

    # ---- disconnect 测试 ----

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, manager: WebSocketManager, mock_websocket: AsyncMock) -> None:
        """测试断开连接后移除"""
        await manager.connect("task-1", mock_websocket)
        await manager.disconnect("task-1", mock_websocket)
        assert manager.get_connection_count("task-1") == 0

    @pytest.mark.asyncio
    async def test_disconnect_cleans_empty_task_group(self, manager: WebSocketManager, mock_websocket: AsyncMock) -> None:
        """测试断开后清理空任务组"""
        await manager.connect("task-1", mock_websocket)
        await manager.disconnect("task-1", mock_websocket)
        assert "task-1" not in manager.get_all_tasks()

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_task(self, manager: WebSocketManager, mock_websocket: AsyncMock) -> None:
        """测试断开不存在的任务（不应报错）"""
        await manager.disconnect("task-nonexistent", mock_websocket)
        # 不应抛出异常

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_websocket(self, manager: WebSocketManager, mock_websocket: AsyncMock) -> None:
        """测试断开不存在的连接（不应报错）"""
        await manager.connect("task-1", mock_websocket)
        ws_other = AsyncMock()
        await manager.disconnect("task-1", ws_other)
        assert manager.get_connection_count("task-1") == 1

    @pytest.mark.asyncio
    async def test_disconnect_partial_removal(self, manager: WebSocketManager) -> None:
        """测试部分移除（保留其他连接）"""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()

        await manager.connect("task-1", ws1)
        await manager.connect("task-1", ws2)
        await manager.disconnect("task-1", ws1)

        assert manager.get_connection_count("task-1") == 1
        assert "task-1" in manager.get_all_tasks()

    # ---- broadcast 测试 ----

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self, manager: WebSocketManager, mock_websocket: AsyncMock) -> None:
        """测试广播消息到所有连接"""
        await manager.connect("task-1", mock_websocket)

        message = {"type": "task:progress", "data": "test"}
        sent = await manager.broadcast("task-1", message)

        assert sent == 1
        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_serializes_to_json(self, manager: WebSocketManager, mock_websocket: AsyncMock) -> None:
        """测试广播消息序列化为 JSON"""
        await manager.connect("task-1", mock_websocket)

        message = {"type": "task:progress", "payload": {"progress": 50}}
        await manager.broadcast("task-1", message)

        call_args = mock_websocket.send_text.call_args[0][0]
        parsed = json.loads(call_args)
        assert parsed["type"] == "task:progress"
        assert parsed["payload"]["progress"] == 50

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_task(self, manager: WebSocketManager) -> None:
        """测试向不存在的任务广播返回 0"""
        sent = await manager.broadcast("task-nonexistent", {"data": "test"})
        assert sent == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_clients(self, manager: WebSocketManager) -> None:
        """测试广播到多个客户端"""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()

        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()

        await manager.connect("task-1", ws1)
        await manager.connect("task-1", ws2)

        sent = await manager.broadcast("task-1", {"type": "test"})

        assert sent == 2
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

    # ---- 死连接清理测试 ----

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self, manager: WebSocketManager) -> None:
        """测试广播时自动清理死连接"""
        ws_good = AsyncMock()
        ws_good.accept = AsyncMock()
        ws_good.send_text = AsyncMock()

        ws_dead = AsyncMock()
        ws_dead.accept = AsyncMock()
        ws_dead.send_text = AsyncMock(side_effect=ConnectionError("Connection lost"))

        await manager.connect("task-1", ws_good)
        await manager.connect("task-1", ws_dead)

        sent = await manager.broadcast("task-1", {"type": "test"})

        assert sent == 1
        assert manager.get_connection_count("task-1") == 1

    @pytest.mark.asyncio
    async def test_broadcast_removes_all_dead_connections(self, manager: WebSocketManager) -> None:
        """测试广播时清理所有死连接"""
        ws_dead1 = AsyncMock()
        ws_dead1.accept = AsyncMock()
        ws_dead1.send_text = AsyncMock(side_effect=RuntimeError("Error 1"))

        ws_dead2 = AsyncMock()
        ws_dead2.accept = AsyncMock()
        ws_dead2.send_text = AsyncMock(side_effect=RuntimeError("Error 2"))

        await manager.connect("task-1", ws_dead1)
        await manager.connect("task-1", ws_dead2)

        sent = await manager.broadcast("task-1", {"type": "test"})

        assert sent == 0
        assert manager.get_connection_count("task-1") == 0

    @pytest.mark.asyncio
    async def test_broadcast_cleans_empty_group_after_dead_removal(self, manager: WebSocketManager) -> None:
        """测试死连接清理后空组被删除"""
        ws_dead = AsyncMock()
        ws_dead.accept = AsyncMock()
        ws_dead.send_text = AsyncMock(side_effect=Exception("Dead"))

        await manager.connect("task-1", ws_dead)
        await manager.broadcast("task-1", {"type": "test"})

        assert "task-1" not in manager.get_all_tasks()

    @pytest.mark.asyncio
    async def test_broadcast_handles_various_exceptions(self, manager: WebSocketManager) -> None:
        """测试广播处理各种异常类型"""
        ws_ok = AsyncMock()
        ws_ok.accept = AsyncMock()
        ws_ok.send_text = AsyncMock()

        ws_exc = AsyncMock()
        ws_exc.accept = AsyncMock()
        ws_exc.send_text = AsyncMock(side_effect=Exception("Any exception"))

        await manager.connect("task-1", ws_ok)
        await manager.connect("task-1", ws_exc)

        # 不应抛出异常
        sent = await manager.broadcast("task-1", {"type": "test"})
        assert sent == 1

    # ---- 连接异常捕获测试 ----

    @pytest.mark.asyncio
    async def test_connect_handles_accept_failure(self, manager: WebSocketManager) -> None:
        """测试连接时 accept 失败的处理"""
        ws = AsyncMock()
        ws.accept = AsyncMock(side_effect=RuntimeError("Accept failed"))

        # 不应抛出异常到外部
        with pytest.raises(RuntimeError, match="Accept failed"):
            await manager.connect("task-1", ws)

        # 连接不应被添加到管理器
        assert manager.get_connection_count("task-1") == 0

    # ---- 辅助方法测试 ----

    @pytest.mark.asyncio
    async def test_get_connection_count_empty(self, manager: WebSocketManager) -> None:
        """测试获取空任务连接数"""
        assert manager.get_connection_count("task-nonexistent") == 0

    @pytest.mark.asyncio
    async def test_get_all_tasks_empty(self, manager: WebSocketManager) -> None:
        """测试获取空任务列表"""
        assert manager.get_all_tasks() == []

    @pytest.mark.asyncio
    async def test_get_all_tasks_returns_all(self, manager: WebSocketManager) -> None:
        """测试获取所有任务"""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()

        await manager.connect("task-1", ws1)
        await manager.connect("task-2", ws2)

        tasks = manager.get_all_tasks()
        assert set(tasks) == {"task-1", "task-2"}


# ============================================================================
# WebSocketEvent 测试
# ============================================================================

class TestWebSocketEvent:
    """WebSocketEvent 单元测试"""

    def test_make_event_creates_event(self) -> None:
        """测试创建事件"""
        event = make_event(
            EventType.TASK_STARTED,
            "task-123",
            {"workflow_id": "wf-001"},
        )

        assert event.type == EventType.TASK_STARTED
        assert event.task_id == "task-123"
        assert event.payload == {"workflow_id": "wf-001"}
        assert event.timestamp is not None

    def test_make_event_default_payload(self) -> None:
        """测试默认空 payload"""
        event = make_event(EventType.TASK_STARTED, "task-123")
        assert event.payload == {}

    def test_make_event_custom_timestamp(self) -> None:
        """测试自定义时间戳"""
        event = make_event(
            EventType.TASK_STARTED,
            "task-123",
            payload={},
        )
        # 时间戳应该是 ISO 格式
        datetime.fromisoformat(event.timestamp)

    def test_event_to_dict(self) -> None:
        """测试事件转字典"""
        event = WebSocketEvent(
            type=EventType.TASK_PROGRESS,
            task_id="task-456",
            timestamp="2026-05-20T10:00:00",
            payload={"progress": 50},
        )

        d = event.to_dict()
        assert d["type"] == "task:progress"
        assert d["task_id"] == "task-456"
        assert d["timestamp"] == "2026-05-20T10:00:00"
        assert d["payload"] == {"progress": 50}

    def test_event_to_json(self) -> None:
        """测试事件转 JSON"""
        event = WebSocketEvent(
            type=EventType.LOG_STREAM,
            task_id="task-789",
            timestamp="2026-05-20T10:00:00",
            payload={"message": "test log"},
        )

        json_str = event.to_json()
        parsed = json.loads(json_str)

        assert parsed["type"] == "log:stream"
        assert parsed["task_id"] == "task-789"
        assert parsed["payload"]["message"] == "test log"

    def test_event_from_dict(self) -> None:
        """测试从字典创建事件"""
        data = {
            "type": "task:completed",
            "task_id": "task-456",
            "timestamp": "2026-05-20T10:00:00Z",
            "payload": {"status": "success"},
        }

        event = WebSocketEvent.from_dict(data)

        assert event.type == EventType.TASK_COMPLETED
        assert event.task_id == "task-456"
        assert event.payload["status"] == "success"

    def test_event_from_dict_missing_timestamp(self) -> None:
        """测试从字典创建事件时缺少时间戳"""
        data = {
            "type": "task:failed",
            "task_id": "task-999",
            "payload": {"error": "something went wrong"},
        }

        event = WebSocketEvent.from_dict(data)
        assert event.timestamp is not None

    def test_event_from_dict_missing_payload(self) -> None:
        """测试从字典创建事件时缺少 payload"""
        data = {
            "type": "task:started",
            "task_id": "task-111",
            "timestamp": "2026-05-20T10:00:00Z",
        }

        event = WebSocketEvent.from_dict(data)
        assert event.payload == {}

    def test_all_event_types(self) -> None:
        """测试所有事件类型"""
        expected_types = [
            "task:started",
            "task:progress",
            "task:completed",
            "task:failed",
            "task:cancelled",
            "agent:status",
            "agent:message",
            "log:stream",
            "metric:update",
        ]

        for type_str in expected_types:
            event_type = EventType(type_str)
            assert event_type.value == type_str

    def test_event_type_is_string(self) -> None:
        """测试事件类型是字符串枚举"""
        assert isinstance(EventType.TASK_STARTED.value, str)
        assert EventType.TASK_STARTED == "task:started"

    def test_event_serialization_roundtrip(self) -> None:
        """测试事件序列化/反序列化往返"""
        original = WebSocketEvent(
            type=EventType.AGENT_STATUS,
            task_id="task-abc",
            timestamp="2026-05-20T12:00:00",
            payload={"agent": "coder", "status": "running"},
        )

        json_str = original.to_json()
        restored = WebSocketEvent.from_dict(json.loads(json_str))

        assert restored.type == original.type
        assert restored.task_id == original.task_id
        assert restored.payload == original.payload


# ============================================================================
# 集成场景测试
# ============================================================================

class TestWebSocketIntegrationScenarios:
    """WebSocket 集成场景测试"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self) -> None:
        """测试完整生命周期: 连接 -> 广播 -> 断开"""
        manager = WebSocketManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()

        # 连接
        await manager.connect("task-1", ws)
        assert manager.get_connection_count("task-1") == 1

        # 广播
        event = make_event(EventType.TASK_STARTED, "task-1", {"status": "running"})
        sent = await manager.broadcast("task-1", event.to_dict())
        assert sent == 1

        # 断开
        await manager.disconnect("task-1", ws)
        assert manager.get_connection_count("task-1") == 0

    @pytest.mark.asyncio
    async def test_concurrent_broadcasts(self) -> None:
        """测试并发广播"""
        manager = WebSocketManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()

        await manager.connect("task-1", ws)

        # 并发广播
        import asyncio
        tasks = [
            manager.broadcast("task-1", {"seq": i})
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks)

        assert all(r == 1 for r in results)
        assert ws.send_text.call_count == 5

    @pytest.mark.asyncio
    async def test_mixed_good_and_dead_connections(self) -> None:
        """测试混合正常和死连接"""
        manager = WebSocketManager()

        ws_good1 = AsyncMock()
        ws_good1.accept = AsyncMock()
        ws_good1.send_text = AsyncMock()

        ws_dead = AsyncMock()
        ws_dead.accept = AsyncMock()
        ws_dead.send_text = AsyncMock(side_effect=ConnectionResetError())

        ws_good2 = AsyncMock()
        ws_good2.accept = AsyncMock()
        ws_good2.send_text = AsyncMock()

        await manager.connect("task-1", ws_good1)
        await manager.connect("task-1", ws_dead)
        await manager.connect("task-1", ws_good2)

        sent = await manager.broadcast("task-1", {"type": "test"})

        assert sent == 2
        assert manager.get_connection_count("task-1") == 2
