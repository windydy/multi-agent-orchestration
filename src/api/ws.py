"""
WebSocket 连接管理器

提供按 task_id 分组的 WebSocket 连接管理，支持广播消息、
自动清理死连接和连接异常捕获。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """WebSocket 连接管理器

    功能:
    - 按 task_id 分组管理 WebSocket 连接
    - 广播消息到指定任务的所有订阅者
    - 自动清理断开的/死连接
    - 连接异常捕获

    使用示例:
        manager = WebSocketManager()
        await manager.connect("task-123", websocket)
        await manager.broadcast("task-123", {"type": "task:progress", "data": ...})
        await manager.disconnect("task-123", websocket)
    """

    def __init__(self) -> None:
        # task_id -> [WebSocket, ...]
        self._connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        """接受 WebSocket 连接并加入任务组

        Args:
            task_id: 任务 ID
            websocket: WebSocket 连接对象

        Raises:
            如果 websocket.accept() 失败，异常会向上传播，
            连接不会被添加到管理器中。
        """
        # 先 accept，失败则不添加到管理器
        await websocket.accept()

        if task_id not in self._connections:
            self._connections[task_id] = []

        # 避免重复添加同一连接
        if websocket not in self._connections[task_id]:
            self._connections[task_id].append(websocket)
            logger.info(
                "Client connected to task %s, total: %d",
                task_id,
                len(self._connections[task_id]),
            )

    async def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        """移除 WebSocket 连接

        如果任务组变为空，会自动清理该任务组。

        Args:
            task_id: 任务 ID
            websocket: WebSocket 连接对象
        """
        if task_id not in self._connections:
            return

        connections = self._connections[task_id]
        if websocket in connections:
            connections.remove(websocket)
            logger.info(
                "Client disconnected from task %s, remaining: %d",
                task_id,
                len(connections),
            )

        # 清理空列表
        if not connections:
            del self._connections[task_id]

    async def broadcast(self, task_id: str, message: dict[str, Any]) -> int:
        """广播消息到指定任务的所有连接

        自动捕获发送异常并清理死连接。

        Args:
            task_id: 任务 ID
            message: 要发送的消息字典

        Returns:
            成功发送的连接数量
        """
        if task_id not in self._connections:
            return 0

        data = json.dumps(message, ensure_ascii=False)
        connections = self._connections[task_id]
        dead_connections: List[WebSocket] = []
        sent_count = 0

        for ws in connections:
            try:
                await ws.send_text(data)
                sent_count += 1
            except Exception as e:
                logger.warning("Failed to send to client for task %s: %s", task_id, e)
                dead_connections.append(ws)

        # 清理断开的连接
        for ws in dead_connections:
            await self.disconnect(task_id, ws)

        return sent_count

    def get_connection_count(self, task_id: str) -> int:
        """获取指定任务的活跃连接数

        Args:
            task_id: 任务 ID

        Returns:
            连接数量，如果任务不存在则返回 0
        """
        return len(self._connections.get(task_id, []))

    def get_all_tasks(self) -> List[str]:
        """获取所有有活跃连接的任务 ID

        Returns:
            任务 ID 列表
        """
        return list(self._connections.keys())
