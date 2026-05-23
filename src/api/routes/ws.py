"""
WebSocket 路由端点

提供 /ws/{task_id} 端点，处理 WebSocket 连接生命周期。
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.ws import WebSocketManager

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局 WebSocketManager 实例（通过 set_ws_manager 初始化）
_ws_manager: WebSocketManager | None = None


def set_ws_manager(manager: WebSocketManager) -> None:
    """设置全局 WebSocketManager 实例

    Args:
        manager: WebSocketManager 实例
    """
    global _ws_manager
    _ws_manager = manager


def get_ws_manager() -> WebSocketManager:
    """获取全局 WebSocketManager 实例

    Returns:
        WebSocketManager 实例

    Raises:
        RuntimeError: 如果 WebSocketManager 未初始化
    """
    if _ws_manager is None:
        raise RuntimeError("WebSocketManager not initialized. Call set_ws_manager() first.")
    return _ws_manager


@router.websocket("/ws/{task_id}")
async def ws_endpoint(websocket: WebSocket, task_id: str) -> None:
    """WebSocket 端点

    处理客户端连接生命周期：
    1. 接受连接并注册到 WebSocketManager
    2. 保持连接活跃，处理 ping/pong 心跳
    3. 客户端断开时自动清理

    Args:
        websocket: WebSocket 连接对象
        task_id: 任务 ID（从 URL 路径参数获取）
    """
    manager = get_ws_manager()

    try:
        # 接受连接并注册到管理器
        await manager.connect(task_id, websocket)
        logger.info("WebSocket client connected to task %s", task_id)

        # 保持连接活跃，处理消息
        while True:
            try:
                # 等待客户端消息
                message = await websocket.receive_text()

                # 处理 ping/pong 心跳
                if message == "ping":
                    await websocket.send_text("pong")
                    logger.debug("Responded to ping from task %s", task_id)
                else:
                    # 其他消息可以扩展处理逻辑
                    logger.debug("Received message from task %s: %s", task_id, message)

            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected from task %s", task_id)
                break
            except Exception as e:
                logger.warning("WebSocket error for task %s: %s", task_id, e)
                break

    except Exception as e:
        logger.error("WebSocket connection failed for task %s: %s", task_id, e)
        # 如果 accept 失败，连接不会被添加到管理器，无需清理
        raise
    finally:
        # 确保连接从管理器中移除
        try:
            await manager.disconnect(task_id, websocket)
            logger.info("WebSocket client cleaned up for task %s", task_id)
        except Exception as e:
            logger.warning("Error during WebSocket cleanup for task %s: %s", task_id, e)
