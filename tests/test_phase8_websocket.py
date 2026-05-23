"""
Phase 8 WebSocket 集成测试

使用 asyncio 和 mock websocket 对象测试 WebSocketManager 的连接、断开、
广播功能及异常处理，不启动真实服务器。

TDD: 先写测试，再写实现。
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.ws import WebSocketManager

logger = logging.getLogger(__name__)


# ============================================================================
# Mock WebSocket 工厂
# ============================================================================

def create_mock_websocket(
    accept_side_effect: Exception | None = None,
    send_text_side_effect: Exception | None = None,
    close_side_effect: Exception | None = None,
) -> AsyncMock:
    """创建模拟 WebSocket 连接

    Args:
        accept_side_effect: accept() 方法抛出的异常
        send_text_side_effect: send_text() 方法抛出的异常
        close_side_effect: close() 方法抛出的异常

    Returns:
        模拟的 WebSocket 对象
    """
    ws = AsyncMock()
    ws.accept = AsyncMock(side_effect=accept_side_effect)
    ws.send_text = AsyncMock(side_effect=send_text_side_effect)
    ws.close = AsyncMock(side_effect=close_side_effect)
    return ws


# ============================================================================
# 连接测试
# ============================================================================

class TestWebSocketConnect:
    """WebSocket 连接功能测试"""

    @pytest.fixture
    def manager(self) -> WebSocketManager:
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_connect_single_client(self, manager: WebSocketManager) -> None:
        """测试单个客户端连接"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        ws.accept.assert_called_once()
        assert manager.get_connection_count("task-001") == 1
        assert "task-001" in manager.get_all_tasks()

    @pytest.mark.asyncio
    async def test_connect_multiple_clients_same_task(self, manager: WebSocketManager) -> None:
        """测试同一任务多个客户端连接"""
        ws1 = create_mock_websocket()
        ws2 = create_mock_websocket()
        ws3 = create_mock_websocket()

        await manager.connect("task-001", ws1)
        await manager.connect("task-001", ws2)
        await manager.connect("task-001", ws3)

        assert manager.get_connection_count("task-001") == 3
        ws1.accept.assert_called_once()
        ws2.accept.assert_called_once()
        ws3.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_multiple_tasks(self, manager: WebSocketManager) -> None:
        """测试多个不同任务的连接"""
        ws1 = create_mock_websocket()
        ws2 = create_mock_websocket()
        ws3 = create_mock_websocket()

        await manager.connect("task-001", ws1)
        await manager.connect("task-002", ws2)
        await manager.connect("task-003", ws3)

        assert manager.get_connection_count("task-001") == 1
        assert manager.get_connection_count("task-002") == 1
        assert manager.get_connection_count("task-003") == 1
        assert set(manager.get_all_tasks()) == {"task-001", "task-002", "task-003"}

    @pytest.mark.asyncio
    async def test_connect_prevents_duplicate_websocket(self, manager: WebSocketManager) -> None:
        """测试防止重复添加同一 WebSocket 对象"""
        ws = create_mock_websocket()

        await manager.connect("task-001", ws)
        await manager.connect("task-001", ws)
        await manager.connect("task-001", ws)

        assert manager.get_connection_count("task-001") == 1
        # accept 被调用多次，但只添加一次
        assert ws.accept.call_count == 3

    @pytest.mark.asyncio
    async def test_connect_accept_failure_propagates(self, manager: WebSocketManager) -> None:
        """测试 accept 失败时异常向上传播"""
        ws = create_mock_websocket(accept_side_effect=RuntimeError("Accept failed"))

        with pytest.raises(RuntimeError, match="Accept failed"):
            await manager.connect("task-001", ws)

        # 连接不应被添加到管理器
        assert manager.get_connection_count("task-001") == 0
        assert "task-001" not in manager.get_all_tasks()

    @pytest.mark.asyncio
    async def test_connect_accept_failure_does_not_affect_others(self, manager: WebSocketManager) -> None:
        """测试 accept 失败不影响其他连接"""
        ws_good = create_mock_websocket()
        ws_bad = create_mock_websocket(accept_side_effect=ConnectionError("Bad connection"))

        await manager.connect("task-001", ws_good)

        with pytest.raises(ConnectionError):
            await manager.connect("task-001", ws_bad)

        assert manager.get_connection_count("task-001") == 1

    @pytest.mark.asyncio
    async def test_connect_asyncio_gather(self, manager: WebSocketManager) -> None:
        """测试使用 asyncio.gather 并发连接"""
        websockets = [create_mock_websocket() for _ in range(5)]

        tasks = [
            manager.connect("task-001", ws)
            for ws in websockets
        ]
        await asyncio.gather(*tasks)

        assert manager.get_connection_count("task-001") == 5

    @pytest.mark.asyncio
    async def test_connect_empty_task_id(self, manager: WebSocketManager) -> None:
        """测试空 task_id 连接"""
        ws = create_mock_websocket()
        await manager.connect("", ws)

        assert manager.get_connection_count("") == 1
        assert "" in manager.get_all_tasks()


# ============================================================================
# 断开连接测试
# ============================================================================

class TestWebSocketDisconnect:
    """WebSocket 断开连接功能测试"""

    @pytest.fixture
    def manager(self) -> WebSocketManager:
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_disconnect_single_client(self, manager: WebSocketManager) -> None:
        """测试单个客户端断开"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)
        await manager.disconnect("task-001", ws)

        assert manager.get_connection_count("task-001") == 0

    @pytest.mark.asyncio
    async def test_disconnect_cleans_empty_task_group(self, manager: WebSocketManager) -> None:
        """测试断开后清理空任务组"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)
        await manager.disconnect("task-001", ws)

        assert "task-001" not in manager.get_all_tasks()

    @pytest.mark.asyncio
    async def test_disconnect_partial_removal(self, manager: WebSocketManager) -> None:
        """测试部分断开（保留其他连接）"""
        ws1 = create_mock_websocket()
        ws2 = create_mock_websocket()
        ws3 = create_mock_websocket()

        await manager.connect("task-001", ws1)
        await manager.connect("task-001", ws2)
        await manager.connect("task-001", ws3)

        await manager.disconnect("task-001", ws2)

        assert manager.get_connection_count("task-001") == 2
        assert "task-001" in manager.get_all_tasks()

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_task(self, manager: WebSocketManager) -> None:
        """测试断开不存在的任务（不应报错）"""
        ws = create_mock_websocket()
        await manager.disconnect("task-nonexistent", ws)
        # 不应抛出异常

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_websocket(self, manager: WebSocketManager) -> None:
        """测试断开不存在的 WebSocket（不应报错）"""
        ws = create_mock_websocket()
        ws_other = create_mock_websocket()

        await manager.connect("task-001", ws)
        await manager.disconnect("task-001", ws_other)

        assert manager.get_connection_count("task-001") == 1

    @pytest.mark.asyncio
    async def test_disconnect_all_clients(self, manager: WebSocketManager) -> None:
        """测试断开所有客户端"""
        websockets = [create_mock_websocket() for _ in range(3)]

        for ws in websockets:
            await manager.connect("task-001", ws)

        for ws in websockets:
            await manager.disconnect("task-001", ws)

        assert manager.get_connection_count("task-001") == 0
        assert "task-001" not in manager.get_all_tasks()

    @pytest.mark.asyncio
    async def test_disconnect_multiple_tasks(self, manager: WebSocketManager) -> None:
        """测试多任务断开"""
        ws1 = create_mock_websocket()
        ws2 = create_mock_websocket()
        ws3 = create_mock_websocket()

        await manager.connect("task-001", ws1)
        await manager.connect("task-002", ws2)
        await manager.connect("task-003", ws3)

        await manager.disconnect("task-002", ws2)

        assert manager.get_connection_count("task-001") == 1
        assert manager.get_connection_count("task-002") == 0
        assert manager.get_connection_count("task-003") == 1
        assert set(manager.get_all_tasks()) == {"task-001", "task-003"}

    @pytest.mark.asyncio
    async def test_disconnect_asyncio_gather(self, manager: WebSocketManager) -> None:
        """测试使用 asyncio.gather 并发断开"""
        websockets = [create_mock_websocket() for _ in range(5)]

        for ws in websockets:
            await manager.connect("task-001", ws)

        tasks = [
            manager.disconnect("task-001", ws)
            for ws in websockets
        ]
        await asyncio.gather(*tasks)

        assert manager.get_connection_count("task-001") == 0


# ============================================================================
# 广播测试
# ============================================================================

class TestWebSocketBroadcast:
    """WebSocket 广播功能测试"""

    @pytest.fixture
    def manager(self) -> WebSocketManager:
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_broadcast_single_client(self, manager: WebSocketManager) -> None:
        """测试向单个客户端广播"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        message = {"type": "task:progress", "data": {"progress": 50}}
        sent = await manager.broadcast("task-001", message)

        assert sent == 1
        ws.send_text.assert_called_once()

        # 验证消息内容
        call_args = ws.send_text.call_args[0][0]
        parsed = json.loads(call_args)
        assert parsed["type"] == "task:progress"
        assert parsed["data"]["progress"] == 50

    @pytest.mark.asyncio
    async def test_broadcast_multiple_clients(self, manager: WebSocketManager) -> None:
        """测试向多个客户端广播"""
        websockets = [create_mock_websocket() for _ in range(5)]

        for ws in websockets:
            await manager.connect("task-001", ws)

        message = {"type": "task:started", "data": {"status": "running"}}
        sent = await manager.broadcast("task-001", message)

        assert sent == 5
        for ws in websockets:
            ws.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_nonexistent_task(self, manager: WebSocketManager) -> None:
        """测试向不存在的任务广播"""
        sent = await manager.broadcast("task-nonexistent", {"type": "test"})
        assert sent == 0

    @pytest.mark.asyncio
    async def test_broadcast_empty_task_group(self, manager: WebSocketManager) -> None:
        """测试向空任务组广播"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)
        await manager.disconnect("task-001", ws)

        sent = await manager.broadcast("task-001", {"type": "test"})
        assert sent == 0

    @pytest.mark.asyncio
    async def test_broadcast_json_serialization(self, manager: WebSocketManager) -> None:
        """测试广播消息的 JSON 序列化"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        message = {
            "type": "task:progress",
            "task_id": "task-001",
            "payload": {
                "progress": 75,
                "details": {"step": "processing", "items": [1, 2, 3]},
            },
        }
        await manager.broadcast("task-001", message)

        call_args = ws.send_text.call_args[0][0]
        parsed = json.loads(call_args)
        assert parsed == message

    @pytest.mark.asyncio
    async def test_broadcast_unicode_content(self, manager: WebSocketManager) -> None:
        """测试广播包含 Unicode 的内容"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        message = {"type": "log:stream", "data": {"message": "处理中... 完成 ✓"}}
        await manager.broadcast("task-001", message)

        call_args = ws.send_text.call_args[0][0]
        parsed = json.loads(call_args)
        assert parsed["data"]["message"] == "处理中... 完成 ✓"

    @pytest.mark.asyncio
    async def test_broadcast_asyncio_gather(self, manager: WebSocketManager) -> None:
        """测试使用 asyncio.gather 并发广播"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        tasks = [
            manager.broadcast("task-001", {"seq": i})
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)

        assert all(r == 1 for r in results)
        assert ws.send_text.call_count == 10

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_tasks(self, manager: WebSocketManager) -> None:
        """测试向多个任务广播"""
        ws1 = create_mock_websocket()
        ws2 = create_mock_websocket()

        await manager.connect("task-001", ws1)
        await manager.connect("task-002", ws2)

        sent1 = await manager.broadcast("task-001", {"type": "test"})
        sent2 = await manager.broadcast("task-002", {"type": "test"})

        assert sent1 == 1
        assert sent2 == 1
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()


# ============================================================================
# 异常处理测试
# ============================================================================

class TestWebSocketExceptionHandling:
    """WebSocket 异常处理测试"""

    @pytest.fixture
    def manager(self) -> WebSocketManager:
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_broadcast_handles_connection_error(self, manager: WebSocketManager) -> None:
        """测试广播时处理 ConnectionError"""
        ws_good = create_mock_websocket()
        ws_dead = create_mock_websocket(send_text_side_effect=ConnectionError("Connection lost"))

        await manager.connect("task-001", ws_good)
        await manager.connect("task-001", ws_dead)

        sent = await manager.broadcast("task-001", {"type": "test"})

        assert sent == 1
        assert manager.get_connection_count("task-001") == 1

    @pytest.mark.asyncio
    async def test_broadcast_handles_runtime_error(self, manager: WebSocketManager) -> None:
        """测试广播时处理 RuntimeError"""
        ws_good = create_mock_websocket()
        ws_dead = create_mock_websocket(send_text_side_effect=RuntimeError("Runtime error"))

        await manager.connect("task-001", ws_good)
        await manager.connect("task-001", ws_dead)

        sent = await manager.broadcast("task-001", {"type": "test"})

        assert sent == 1
        assert manager.get_connection_count("task-001") == 1

    @pytest.mark.asyncio
    async def test_broadcast_handles_connection_reset(self, manager: WebSocketManager) -> None:
        """测试广播时处理 ConnectionResetError"""
        ws_good = create_mock_websocket()
        ws_dead = create_mock_websocket(send_text_side_effect=ConnectionResetError())

        await manager.connect("task-001", ws_good)
        await manager.connect("task-001", ws_dead)

        sent = await manager.broadcast("task-001", {"type": "test"})

        assert sent == 1
        assert manager.get_connection_count("task-001") == 1

    @pytest.mark.asyncio
    async def test_broadcast_handles_generic_exception(self, manager: WebSocketManager) -> None:
        """测试广播时处理通用 Exception"""
        ws_good = create_mock_websocket()
        ws_dead = create_mock_websocket(send_text_side_effect=Exception("Generic error"))

        await manager.connect("task-001", ws_good)
        await manager.connect("task-001", ws_dead)

        sent = await manager.broadcast("task-001", {"type": "test"})

        assert sent == 1
        assert manager.get_connection_count("task-001") == 1

    @pytest.mark.asyncio
    async def test_broadcast_removes_all_dead_connections(self, manager: WebSocketManager) -> None:
        """测试广播时移除所有死连接"""
        ws_dead1 = create_mock_websocket(send_text_side_effect=ConnectionError("Error 1"))
        ws_dead2 = create_mock_websocket(send_text_side_effect=RuntimeError("Error 2"))
        ws_dead3 = create_mock_websocket(send_text_side_effect=Exception("Error 3"))

        await manager.connect("task-001", ws_dead1)
        await manager.connect("task-001", ws_dead2)
        await manager.connect("task-001", ws_dead3)

        sent = await manager.broadcast("task-001", {"type": "test"})

        assert sent == 0
        assert manager.get_connection_count("task-001") == 0
        assert "task-001" not in manager.get_all_tasks()

    @pytest.mark.asyncio
    async def test_broadcast_cleans_empty_group_after_dead_removal(self, manager: WebSocketManager) -> None:
        """测试死连接清理后空组被删除"""
        ws_dead = create_mock_websocket(send_text_side_effect=Exception("Dead"))

        await manager.connect("task-001", ws_dead)
        await manager.broadcast("task-001", {"type": "test"})

        assert "task-001" not in manager.get_all_tasks()

    @pytest.mark.asyncio
    async def test_broadcast_mixed_good_and_dead(self, manager: WebSocketManager) -> None:
        """测试混合正常和死连接的广播"""
        ws_good1 = create_mock_websocket()
        ws_dead = create_mock_websocket(send_text_side_effect=ConnectionResetError())
        ws_good2 = create_mock_websocket()
        ws_dead2 = create_mock_websocket(send_text_side_effect=RuntimeError("Error"))
        ws_good3 = create_mock_websocket()

        await manager.connect("task-001", ws_good1)
        await manager.connect("task-001", ws_dead)
        await manager.connect("task-001", ws_good2)
        await manager.connect("task-001", ws_dead2)
        await manager.connect("task-001", ws_good3)

        sent = await manager.broadcast("task-001", {"type": "test"})

        assert sent == 3
        assert manager.get_connection_count("task-001") == 3

    @pytest.mark.asyncio
    async def test_broadcast_does_not_propagate_send_errors(self, manager: WebSocketManager) -> None:
        """测试广播不向外传播发送错误"""
        ws_dead = create_mock_websocket(send_text_side_effect=Exception("Send failed"))

        await manager.connect("task-001", ws_dead)

        # 不应抛出异常
        sent = await manager.broadcast("task-001", {"type": "test"})
        assert sent == 0

    @pytest.mark.asyncio
    async def test_connect_accept_failure_not_added(self, manager: WebSocketManager) -> None:
        """测试 accept 失败时连接不被添加"""
        ws = create_mock_websocket(accept_side_effect=RuntimeError("Accept failed"))

        with pytest.raises(RuntimeError):
            await manager.connect("task-001", ws)

        assert manager.get_connection_count("task-001") == 0


# ============================================================================
# 并发测试
# ============================================================================

class TestWebSocketConcurrency:
    """WebSocket 并发操作测试"""

    @pytest.fixture
    def manager(self) -> WebSocketManager:
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_concurrent_connect_and_broadcast(self, manager: WebSocketManager) -> None:
        """测试并发连接和广播"""
        websockets = [create_mock_websocket() for _ in range(5)]

        # 并发连接
        connect_tasks = [
            manager.connect("task-001", ws)
            for ws in websockets
        ]
        await asyncio.gather(*connect_tasks)

        assert manager.get_connection_count("task-001") == 5

        # 并发广播
        broadcast_tasks = [
            manager.broadcast("task-001", {"seq": i})
            for i in range(5)
        ]
        results = await asyncio.gather(*broadcast_tasks)

        assert all(r == 5 for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_disconnect(self, manager: WebSocketManager) -> None:
        """测试并发断开"""
        websockets = [create_mock_websocket() for _ in range(5)]

        for ws in websockets:
            await manager.connect("task-001", ws)

        # 并发断开
        disconnect_tasks = [
            manager.disconnect("task-001", ws)
            for ws in websockets
        ]
        await asyncio.gather(*disconnect_tasks)

        assert manager.get_connection_count("task-001") == 0

    @pytest.mark.asyncio
    async def test_concurrent_broadcast_with_dead_connections(self, manager: WebSocketManager) -> None:
        """测试并发广播时有死连接"""
        ws_good = create_mock_websocket()
        ws_dead = create_mock_websocket(send_text_side_effect=ConnectionError("Dead"))

        await manager.connect("task-001", ws_good)
        await manager.connect("task-001", ws_dead)

        # 并发广播
        tasks = [
            manager.broadcast("task-001", {"seq": i})
            for i in range(3)
        ]
        results = await asyncio.gather(*tasks)

        # 第一次广播后死连接被清理，后续广播只发送到好连接
        assert results[0] == 1  # 第一次：好连接成功，死连接被清理
        # 后续广播只发送到好连接
        assert all(r == 1 for r in results[1:])

    @pytest.mark.asyncio
    async def test_rapid_connect_disconnect_cycle(self, manager: WebSocketManager) -> None:
        """测试快速连接断开循环"""
        for i in range(10):
            ws = create_mock_websocket()
            await manager.connect("task-001", ws)
            assert manager.get_connection_count("task-001") == 1
            await manager.disconnect("task-001", ws)
            assert manager.get_connection_count("task-001") == 0

        assert "task-001" not in manager.get_all_tasks()


# ============================================================================
# 边界条件测试
# ============================================================================

class TestWebSocketEdgeCases:
    """WebSocket 边界条件测试"""

    @pytest.fixture
    def manager(self) -> WebSocketManager:
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_broadcast_empty_message(self, manager: WebSocketManager) -> None:
        """测试广播空消息"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        sent = await manager.broadcast("task-001", {})
        assert sent == 1

        call_args = ws.send_text.call_args[0][0]
        assert json.loads(call_args) == {}

    @pytest.mark.asyncio
    async def test_broadcast_nested_dict(self, manager: WebSocketManager) -> None:
        """测试广播嵌套字典"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        message = {
            "type": "task:progress",
            "data": {
                "nested": {
                    "level1": {
                        "level2": {"value": 42}
                    }
                }
            }
        }
        sent = await manager.broadcast("task-001", message)
        assert sent == 1

        call_args = ws.send_text.call_args[0][0]
        parsed = json.loads(call_args)
        assert parsed["data"]["nested"]["level1"]["level2"]["value"] == 42

    @pytest.mark.asyncio
    async def test_broadcast_with_list_payload(self, manager: WebSocketManager) -> None:
        """测试广播包含列表的 payload"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        message = {"type": "task:progress", "items": [1, 2, 3, 4, 5]}
        sent = await manager.broadcast("task-001", message)
        assert sent == 1

        call_args = ws.send_text.call_args[0][0]
        parsed = json.loads(call_args)
        assert parsed["items"] == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_many_connections(self, manager: WebSocketManager) -> None:
        """测试大量连接"""
        num_connections = 100
        websockets = [create_mock_websocket() for _ in range(num_connections)]

        for ws in websockets:
            await manager.connect("task-001", ws)

        assert manager.get_connection_count("task-001") == num_connections

        sent = await manager.broadcast("task-001", {"type": "test"})
        assert sent == num_connections

    @pytest.mark.asyncio
    async def test_special_characters_in_task_id(self, manager: WebSocketManager) -> None:
        """测试 task_id 包含特殊字符"""
        ws = create_mock_websocket()
        task_id = "task/with/slashes-and_special.chars:123"

        await manager.connect(task_id, ws)
        assert manager.get_connection_count(task_id) == 1

        sent = await manager.broadcast(task_id, {"type": "test"})
        assert sent == 1

    @pytest.mark.asyncio
    async def test_disconnect_twice(self, manager: WebSocketManager) -> None:
        """测试重复断开同一连接"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        await manager.disconnect("task-001", ws)
        await manager.disconnect("task-001", ws)  # 第二次不应报错

        assert manager.get_connection_count("task-001") == 0


# ============================================================================
# 状态一致性测试
# ============================================================================

class TestWebSocketStateConsistency:
    """WebSocket 状态一致性测试"""

    @pytest.fixture
    def manager(self) -> WebSocketManager:
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_state_after_connect_disconnect_cycle(self, manager: WebSocketManager) -> None:
        """测试连接断开循环后的状态"""
        ws1 = create_mock_websocket()
        ws2 = create_mock_websocket()

        await manager.connect("task-001", ws1)
        await manager.connect("task-001", ws2)
        await manager.disconnect("task-001", ws1)
        await manager.connect("task-002", ws1)

        assert manager.get_connection_count("task-001") == 1
        assert manager.get_connection_count("task-002") == 1
        assert set(manager.get_all_tasks()) == {"task-001", "task-002"}

    @pytest.mark.asyncio
    async def test_broadcast_does_not_modify_good_connections(self, manager: WebSocketManager) -> None:
        """测试广播不修改正常连接"""
        websockets = [create_mock_websocket() for _ in range(3)]

        for ws in websockets:
            await manager.connect("task-001", ws)

        await manager.broadcast("task-001", {"type": "test"})

        assert manager.get_connection_count("task-001") == 3
        assert set(manager.get_all_tasks()) == {"task-001"}

    @pytest.mark.asyncio
    async def test_manager_isolation(self, manager: WebSocketManager) -> None:
        """测试管理器隔离性"""
        ws1 = create_mock_websocket()
        ws2 = create_mock_websocket()

        await manager.connect("task-001", ws1)
        await manager.connect("task-002", ws2)

        # 向 task-001 广播不应影响 task-002
        await manager.broadcast("task-001", {"type": "test"})

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_manager_state(self, manager: WebSocketManager) -> None:
        """测试空管理器状态"""
        assert manager.get_connection_count("any-task") == 0
        assert manager.get_all_tasks() == []

        sent = await manager.broadcast("any-task", {"type": "test"})
        assert sent == 0


# ============================================================================
# 消息格式测试
# ============================================================================

class TestWebSocketMessageFormat:
    """WebSocket 消息格式测试"""

    @pytest.fixture
    def manager(self) -> WebSocketManager:
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_broadcast_task_started_event(self, manager: WebSocketManager) -> None:
        """测试广播 task:started 事件"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        event = {
            "type": "task:started",
            "task_id": "task-001",
            "timestamp": "2026-05-23T10:00:00",
            "payload": {"workflow_id": "wf-001"},
        }
        await manager.broadcast("task-001", event)

        call_args = ws.send_text.call_args[0][0]
        parsed = json.loads(call_args)
        assert parsed["type"] == "task:started"
        assert parsed["task_id"] == "task-001"

    @pytest.mark.asyncio
    async def test_broadcast_task_progress_event(self, manager: WebSocketManager) -> None:
        """测试广播 task:progress 事件"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        event = {
            "type": "task:progress",
            "task_id": "task-001",
            "payload": {"progress": 50, "step": "processing"},
        }
        await manager.broadcast("task-001", event)

        call_args = ws.send_text.call_args[0][0]
        parsed = json.loads(call_args)
        assert parsed["payload"]["progress"] == 50

    @pytest.mark.asyncio
    async def test_broadcast_task_completed_event(self, manager: WebSocketManager) -> None:
        """测试广播 task:completed 事件"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        event = {
            "type": "task:completed",
            "task_id": "task-001",
            "payload": {"status": "success", "duration": 120},
        }
        await manager.broadcast("task-001", event)

        call_args = ws.send_text.call_args[0][0]
        parsed = json.loads(call_args)
        assert parsed["type"] == "task:completed"
        assert parsed["payload"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_broadcast_task_failed_event(self, manager: WebSocketManager) -> None:
        """测试广播 task:failed 事件"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        event = {
            "type": "task:failed",
            "task_id": "task-001",
            "payload": {"error": "Something went wrong", "code": 500},
        }
        await manager.broadcast("task-001", event)

        call_args = ws.send_text.call_args[0][0]
        parsed = json.loads(call_args)
        assert parsed["type"] == "task:failed"
        assert parsed["payload"]["error"] == "Something went wrong"

    @pytest.mark.asyncio
    async def test_broadcast_agent_status_event(self, manager: WebSocketManager) -> None:
        """测试广播 agent:status 事件"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        event = {
            "type": "agent:status",
            "task_id": "task-001",
            "payload": {"agent": "coder", "status": "running"},
        }
        await manager.broadcast("task-001", event)

        call_args = ws.send_text.call_args[0][0]
        parsed = json.loads(call_args)
        assert parsed["type"] == "agent:status"
        assert parsed["payload"]["agent"] == "coder"

    @pytest.mark.asyncio
    async def test_broadcast_log_stream_event(self, manager: WebSocketManager) -> None:
        """测试广播 log:stream 事件"""
        ws = create_mock_websocket()
        await manager.connect("task-001", ws)

        event = {
            "type": "log:stream",
            "task_id": "task-001",
            "payload": {"level": "INFO", "message": "Processing step 1"},
        }
        await manager.broadcast("task-001", event)

        call_args = ws.send_text.call_args[0][0]
        parsed = json.loads(call_args)
        assert parsed["type"] == "log:stream"
        assert parsed["payload"]["level"] == "INFO"
