"""
WebSocket 路由端点单元测试

TDD: 先写测试，再写实现。
测试 /ws/{task_id} 端点的连接生命周期管理。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, WebSocket

from src.api.ws import WebSocketManager
from src.api.routes.ws import router as ws_router, get_ws_manager, set_ws_manager


# ============================================================================
# 辅助函数测试
# ============================================================================

class TestWebSocketManagerDependency:
    """测试 WebSocketManager 依赖注入"""

    def test_set_and_get_ws_manager(self) -> None:
        """测试设置和获取 WebSocketManager 实例"""
        manager = WebSocketManager()
        set_ws_manager(manager)
        assert get_ws_manager() is manager

    def test_get_ws_manager_raises_if_not_set(self) -> None:
        """测试未设置时获取抛出异常"""
        # 先设置为 None 模拟未初始化状态
        original = get_ws_manager()
        try:
            set_ws_manager(None)  # type: ignore
            with pytest.raises(RuntimeError, match="WebSocketManager not initialized"):
                get_ws_manager()
        finally:
            set_ws_manager(original)


# ============================================================================
# 路由端点测试
# ============================================================================

@pytest.mark.skip("旧测试，与新 API 不兼容，已由 test_phase8_websocket.py 覆盖")
class TestWebSocketRoute:
    """WebSocket 路由端点测试"""

    @pytest.fixture
    def app(self) -> FastAPI:
        """创建包含 WebSocket 路由的测试应用"""
        app = FastAPI()
        app.include_router(ws_router)
        # 初始化 WebSocketManager
        set_ws_manager(WebSocketManager())
        return app

    @pytest.fixture
    def manager(self) -> WebSocketManager:
        """创建 WebSocketManager 实例"""
        return WebSocketManager()

    @pytest.fixture
    def client(self, app: FastAPI, manager: WebSocketManager) -> TestClient:
        """创建测试客户端"""
        set_ws_manager(manager)
        return TestClient(app)

    def test_websocket_endpoint_exists(self, client: TestClient) -> None:
        """测试 WebSocket 端点存在"""
        # 使用 TestClient 测试 WebSocket 连接
        with client.websocket_connect("/ws/task-123") as websocket:
            # 连接应该成功
            websocket.send_text("ping")
            data = websocket.receive_text()
            assert data is not None

    @pytest.mark.asyncio
    async def test_connect_adds_to_manager(self, manager: WebSocketManager) -> None:
        """测试连接后添加到管理器"""
        from src.api.routes.ws import ws_endpoint
        from fastapi import WebSocket

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.receive_text = AsyncMock(side_effect=[
            "ping",
            Exception("disconnect")  # 模拟断开
        ])
        mock_ws.send_text = AsyncMock()

        # 直接调用端点函数（注意参数顺序：websocket, task_id）
        import asyncio
        task = asyncio.create_task(ws_endpoint(mock_ws, "task-test"))

        # 等待连接建立
        await asyncio.sleep(0.1)
        mock_ws.accept.assert_called_once()

        # 验证连接已添加到管理器
        assert manager.get_connection_count("task-test") == 1

        # 等待任务完成
        await task

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_manager(self, manager: WebSocketManager) -> None:
        """测试断开后从管理器移除"""
        from src.api.routes.ws import ws_endpoint

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))
        mock_ws.send_text = AsyncMock()

        import asyncio
        task = asyncio.create_task(ws_endpoint(mock_ws, "task-disconnect"))

        await asyncio.sleep(0.1)
        assert manager.get_connection_count("task-disconnect") == 1

        await task

        # 等待断开处理
        await asyncio.sleep(0.1)
        assert manager.get_connection_count("task-disconnect") == 0

    @pytest.mark.asyncio
    async def test_websocket_handles_client_disconnect(self, manager: WebSocketManager) -> None:
        """测试处理客户端断开连接"""
        from src.api.routes.ws import ws_endpoint

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        # WebSocketDisconnect 异常
        from fastapi import WebSocketDisconnect
        mock_ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect(code=1000))
        mock_ws.send_text = AsyncMock()

        import asyncio
        task = asyncio.create_task(ws_endpoint(mock_ws, "task-client-disc"))

        await asyncio.sleep(0.1)
        assert manager.get_connection_count("task-client-disc") == 1

        await task  # 应该正常结束

        await asyncio.sleep(0.1)
        assert manager.get_connection_count("task-client-disc") == 0

    @pytest.mark.asyncio
    async def test_websocket_handles_unexpected_error(self, manager: WebSocketManager) -> None:
        """测试处理意外错误"""
        from src.api.routes.ws import ws_endpoint

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.receive_text = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        mock_ws.send_text = AsyncMock()

        import asyncio
        task = asyncio.create_task(ws_endpoint(mock_ws, "task-error"))

        await asyncio.sleep(0.1)
        assert manager.get_connection_count("task-error") == 1

        await task  # 应该正常结束（异常被捕获）

        await asyncio.sleep(0.1)
        assert manager.get_connection_count("task-error") == 0

    @pytest.mark.asyncio
    async def test_websocket_ping_pong(self, manager: WebSocketManager) -> None:
        """测试 ping/pong 心跳机制"""
        from src.api.routes.ws import ws_endpoint

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.receive_text = AsyncMock(side_effect=[
            "ping",
            "ping",
            Exception("disconnect")
        ])
        mock_ws.send_text = AsyncMock()

        import asyncio
        task = asyncio.create_task(ws_endpoint(mock_ws, "task-ping"))

        await asyncio.sleep(0.2)

        # 应该收到 pong 响应
        assert mock_ws.send_text.call_count >= 2
        mock_ws.send_text.assert_any_call("pong")

        await task


# ============================================================================
# 集成测试
# ============================================================================

class TestWebSocketIntegration:
    """WebSocket 集成测试"""

    @pytest.fixture
    def app(self) -> FastAPI:
        """创建测试应用"""
        app = FastAPI()
        app.include_router(ws_router)
        return app

    @pytest.fixture
    def manager(self) -> WebSocketManager:
        """创建管理器"""
        return WebSocketManager()

    @pytest.fixture
    def client(self, app: FastAPI, manager: WebSocketManager) -> TestClient:
        """创建测试客户端"""
        set_ws_manager(manager)
        return TestClient(app)

    def test_full_connection_lifecycle(self, client: TestClient, manager: WebSocketManager) -> None:
        """测试完整连接生命周期"""
        # 初始状态
        assert manager.get_connection_count("task-lifecycle") == 0

        # 连接
        with client.websocket_connect("/ws/task-lifecycle") as websocket:
            # 连接后应该在管理器中
            assert manager.get_connection_count("task-lifecycle") == 1

            # 发送 ping
            websocket.send_text("ping")
            data = websocket.receive_text()
            assert data == "pong"

        # 断开后应该从管理器中移除
        assert manager.get_connection_count("task-lifecycle") == 0

    def test_multiple_connections_same_task(self, client: TestClient, manager: WebSocketManager) -> None:
        """测试同一任务多个连接"""
        with client.websocket_connect("/ws/task-multi") as ws1:
            with client.websocket_connect("/ws/task-multi") as ws2:
                assert manager.get_connection_count("task-multi") == 2

                ws1.send_text("ping")
                assert ws1.receive_text() == "pong"

                ws2.send_text("ping")
                assert ws2.receive_text() == "pong"

            # ws2 断开
            assert manager.get_connection_count("task-multi") == 1

        # ws1 断开
        assert manager.get_connection_count("task-multi") == 0

    def test_broadcast_to_connected_clients(self, client: TestClient, manager: WebSocketManager) -> None:
        """测试广播到已连接客户端"""
        import asyncio

        with client.websocket_connect("/ws/task-broadcast") as ws1:
            with client.websocket_connect("/ws/task-broadcast") as ws2:
                # 广播消息（在事件循环中运行异步方法）
                sent = asyncio.get_event_loop().run_until_complete(
                    manager.broadcast("task-broadcast", {
                        "type": "task:progress",
                        "task_id": "task-broadcast",
                        "payload": {"progress": 50}
                    })
                )

                assert sent == 2

                # 两个客户端都应该收到消息
                import json
                msg1 = json.loads(ws1.receive_text())
                msg2 = json.loads(ws2.receive_text())

                assert msg1["type"] == "task:progress"
                assert msg2["type"] == "task:progress"
                assert msg1["payload"]["progress"] == 50

    def test_connection_cleanup_on_error(self, client: TestClient, manager: WebSocketManager) -> None:
        """测试错误时连接清理"""
        # 连接
        with client.websocket_connect("/ws/task-cleanup") as websocket:
            assert manager.get_connection_count("task-cleanup") == 1

        # 正常断开后应该清理
        assert manager.get_connection_count("task-cleanup") == 0

    def test_different_tasks_isolated(self, client: TestClient, manager: WebSocketManager) -> None:
        """测试不同任务隔离"""
        import asyncio

        with client.websocket_connect("/ws/task-a") as ws_a:
            with client.websocket_connect("/ws/task-b") as ws_b:
                assert manager.get_connection_count("task-a") == 1
                assert manager.get_connection_count("task-b") == 1

                # 广播到 task-a 不应影响 task-b
                sent = asyncio.get_event_loop().run_until_complete(
                    manager.broadcast("task-a", {"type": "test"})
                )
                assert sent == 1

            assert manager.get_connection_count("task-b") == 0

        assert manager.get_connection_count("task-a") == 0
