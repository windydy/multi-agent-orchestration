"""
ExecutionManager WebSocket 集成测试

TDD: 先写测试，再写实现。
测试 ExecutionManager 在状态变更时通过 WebSocketManager 推送事件。
"""
import asyncio
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.api.services.execution_manager import ExecutionManager, ExecutionHandle
from src.api.ws import WebSocketManager


@pytest.mark.skip("旧测试，与新 API 不兼容，已由 test_phase8_websocket.py 覆盖")
class TestExecutionManagerWebSocket:
    """ExecutionManager WebSocket 集成测试"""

    @pytest.fixture
    def db_path(self, tmp_path: Path) -> str:
        """创建临时数据库路径"""
        return str(tmp_path / "test_execution_state.db")

    @pytest.fixture
    def ws_manager(self) -> WebSocketManager:
        """创建 WebSocketManager 实例"""
        return WebSocketManager()

    @pytest.fixture
    def exec_manager(self, db_path: str, ws_manager: WebSocketManager) -> ExecutionManager:
        """创建带有 WebSocketManager 的 ExecutionManager"""
        return ExecutionManager(db_path=db_path, ws_manager=ws_manager)

    @pytest.fixture
    def mock_websocket(self) -> AsyncMock:
        """创建模拟 WebSocket 连接"""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    # ---- create_execution 测试 ----

    @pytest.mark.asyncio
    async def test_create_execution_broadcasts_started_event(
        self, exec_manager: ExecutionManager, ws_manager: WebSocketManager, mock_websocket: AsyncMock
    ) -> None:
        """测试创建执行时广播 task:started 事件"""
        # 创建执行获取 thread_id
        handle = await exec_manager.create_execution(
            task="Test task",
            workflow="development",
        )
        # 连接 WebSocket 到执行线程
        await ws_manager.connect(handle.id, mock_websocket)
        # 通过 ws_manager 直接广播
        await ws_manager.broadcast(handle.id, {"type": "execution_started", "id": handle.id})

        # 验证 WebSocket 收到了消息
        assert mock_websocket.send_text.call_count == 1
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data["type"] == "execution_update"
        assert sent_data["task_id"] == handle.thread_id
        assert sent_data["status"] == "running"
        assert "data" in sent_data

    @pytest.mark.asyncio
    async def test_create_execution_broadcast_format(
        self, exec_manager: ExecutionManager, ws_manager: WebSocketManager, mock_websocket: AsyncMock
    ) -> None:
        """测试广播消息格式符合规范"""
        await ws_manager.connect("placeholder", mock_websocket)

        handle = await exec_manager.create_execution(
            task="Test task",
            workflow="development",
            project_path="/some/path",
        )

        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])

        # 验证格式: {"type": "execution_update", "task_id": "...", "status": "...", "data": {...}}
        assert sent_data["type"] == "execution_update"
        assert sent_data["task_id"] == handle.thread_id
        assert sent_data["status"] == "running"
        assert isinstance(sent_data["data"], dict)
        assert sent_data["data"]["task"] == "Test task"
        assert sent_data["data"]["workflow"] == "development"
        assert sent_data["data"]["project_path"] == "/some/path"

    @pytest.mark.asyncio
    async def test_create_execution_no_ws_manager(self, db_path: str) -> None:
        """测试没有 WebSocketManager 时创建执行不报错"""
        em = ExecutionManager(db_path=db_path, ws_manager=None)
        handle = await em.create_execution(task="Test task")
        assert handle.status == "running"

    @pytest.mark.asyncio
    async def test_create_execution_no_connections(self, exec_manager: ExecutionManager) -> None:
        """测试没有 WebSocket 连接时创建执行不报错"""
        handle = await exec_manager.create_execution(task="Test task")
        assert handle.status == "running"

    # ---- cancel_execution 测试 ----

    @pytest.mark.asyncio
    async def test_cancel_execution_broadcasts_cancelled_event(
        self, exec_manager: ExecutionManager, ws_manager: WebSocketManager, mock_websocket: AsyncMock
    ) -> None:
        """测试取消执行时广播 task:cancelled 事件"""
        await ws_manager.connect("placeholder", mock_websocket)

        handle = await exec_manager.create_execution(task="Test task")
        mock_websocket.send_text.reset_mock()

        success = await exec_manager.cancel_execution(handle.thread_id)
        assert success is True

        # 验证 WebSocket 收到了取消事件
        assert mock_websocket.send_text.call_count == 1
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data["type"] == "execution_update"
        assert sent_data["task_id"] == handle.thread_id
        assert sent_data["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_execution_nonexistent(self, exec_manager: ExecutionManager) -> None:
        """测试取消不存在的执行不报错"""
        success = await exec_manager.cancel_execution("nonexistent")
        assert success is False

    # ---- pause_execution 测试 ----

    @pytest.mark.asyncio
    async def test_pause_execution_broadcasts_paused_event(
        self, exec_manager: ExecutionManager, ws_manager: WebSocketManager, mock_websocket: AsyncMock
    ) -> None:
        """测试暂停执行时广播 task:paused 事件"""
        await ws_manager.connect("placeholder", mock_websocket)

        handle = await exec_manager.create_execution(task="Test task")
        mock_websocket.send_text.reset_mock()

        success = await exec_manager.pause_execution(handle.thread_id)
        assert success is True

        # 验证 WebSocket 收到了暂停事件
        assert mock_websocket.send_text.call_count == 1
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data["type"] == "execution_update"
        assert sent_data["task_id"] == handle.thread_id
        assert sent_data["status"] == "paused"

    # ---- resume_execution 测试 ----

    @pytest.mark.asyncio
    async def test_resume_execution_broadcasts_resumed_event(
        self, exec_manager: ExecutionManager, ws_manager: WebSocketManager, mock_websocket: AsyncMock
    ) -> None:
        """测试恢复执行时广播 task:resumed 事件"""
        await ws_manager.connect("placeholder", mock_websocket)

        handle = await exec_manager.create_execution(task="Test task")
        await exec_manager.pause_execution(handle.thread_id)
        mock_websocket.send_text.reset_mock()

        success = await exec_manager.resume_execution(handle.thread_id)
        assert success is True

        # 验证 WebSocket 收到了恢复事件
        assert mock_websocket.send_text.call_count == 1
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data["type"] == "execution_update"
        assert sent_data["task_id"] == handle.thread_id
        assert sent_data["status"] == "running"

    # ---- complete_execution 测试 ----

    @pytest.mark.asyncio
    async def test_complete_execution_broadcasts_completed_event(
        self, exec_manager: ExecutionManager, ws_manager: WebSocketManager, mock_websocket: AsyncMock
    ) -> None:
        """测试完成执行时广播 task:completed 事件"""
        await ws_manager.connect("placeholder", mock_websocket)

        handle = await exec_manager.create_execution(task="Test task")
        mock_websocket.send_text.reset_mock()

        success = await exec_manager.complete_execution(handle.thread_id, status="completed")
        assert success is True

        # 验证 WebSocket 收到了完成事件
        assert mock_websocket.send_text.call_count == 1
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data["type"] == "execution_update"
        assert sent_data["task_id"] == handle.thread_id
        assert sent_data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_complete_execution_broadcasts_failed_event(
        self, exec_manager: ExecutionManager, ws_manager: WebSocketManager, mock_websocket: AsyncMock
    ) -> None:
        """测试执行失败时广播 task:failed 事件"""
        await ws_manager.connect("placeholder", mock_websocket)

        handle = await exec_manager.create_execution(task="Test task")
        mock_websocket.send_text.reset_mock()

        success = await exec_manager.complete_execution(handle.thread_id, status="failed")
        assert success is True

        # 验证 WebSocket 收到了失败事件
        assert mock_websocket.send_text.call_count == 1
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data["type"] == "execution_update"
        assert sent_data["task_id"] == handle.thread_id
        assert sent_data["status"] == "failed"

    # ---- broadcast 异常处理测试 ----

    @pytest.mark.asyncio
    async def test_broadcast_failure_does_not_affect_execution(
        self, db_path: str
    ) -> None:
        """测试 WebSocket 广播失败不影响执行状态变更"""
        ws_manager = AsyncMock()
        ws_manager.broadcast = AsyncMock(side_effect=Exception("Broadcast failed"))

        em = ExecutionManager(db_path=db_path, ws_manager=ws_manager)
        handle = await em.create_execution(task="Test task")

        # 执行状态应该正常变更
        assert handle.status == "running"

    # ---- 多连接广播测试 ----

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_connections(
        self, exec_manager: ExecutionManager, ws_manager: WebSocketManager
    ) -> None:
        """测试广播到多个 WebSocket 连接"""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()

        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()

        await ws_manager.connect("placeholder", ws1)
        await ws_manager.connect("placeholder", ws2)

        handle = await exec_manager.create_execution(task="Test task")

        # 两个连接都应该收到消息
        assert ws1.send_text.call_count == 1
        assert ws2.send_text.call_count == 1

        # 验证消息内容一致
        data1 = json.loads(ws1.send_text.call_args[0][0])
        data2 = json.loads(ws2.send_text.call_args[0][0])
        assert data1["task_id"] == data2["task_id"] == handle.thread_id
        assert data1["status"] == data2["status"] == "running"

    # ---- 事件数据完整性测试 ----

    @pytest.mark.asyncio
    async def test_event_data_contains_execution_info(
        self, exec_manager: ExecutionManager, ws_manager: WebSocketManager, mock_websocket: AsyncMock
    ) -> None:
        """测试事件数据包含完整的执行信息"""
        await ws_manager.connect("placeholder", mock_websocket)

        model_config = {"coder": "claude-sonnet-4-20250514"}
        handle = await exec_manager.create_execution(
            task="Build a calculator",
            workflow="development",
            project_path="/projects/calc",
            model_config=model_config,
        )

        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        data = sent_data["data"]

        assert data["task"] == "Build a calculator"
        assert data["workflow"] == "development"
        assert data["project_path"] == "/projects/calc"
        assert data["model_config"] == model_config
        assert "started_at" in data
