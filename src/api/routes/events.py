"""
WebSocket 事件定义模块

定义统一的事件格式和事件类型枚举。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class EventType(str, Enum):
    """WebSocket 事件类型枚举

    所有事件类型遵循 namespace:event 格式。
    """

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
    """WebSocket 事件统一格式

    JSON 格式示例:
    {
        "type": "task:progress",
        "task_id": "task-123",
        "timestamp": "2026-05-20T10:00:00Z",
        "payload": {
            "current_step": 2,
            "total_steps": 5,
            "progress_percent": 40
        }
    }

    Attributes:
        type: 事件类型
        task_id: 关联的任务 ID
        timestamp: ISO 8601 格式时间戳
        payload: 事件具体数据
    """

    type: EventType
    task_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WebSocketEvent:
        """从字典创建事件

        Args:
            data: 包含 type, task_id, timestamp(可选), payload(可选) 的字典

        Returns:
            WebSocketEvent 实例
        """
        return cls(
            type=EventType(data["type"]),
            task_id=data["task_id"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            payload=data.get("payload", {}),
        )


def make_event(
    event_type: EventType,
    task_id: str,
    payload: Optional[dict[str, Any]] = None,
) -> WebSocketEvent:
    """创建 WebSocket 事件的便捷工厂函数

    Args:
        event_type: 事件类型
        task_id: 任务 ID
        payload: 事件数据，默认为空字典

    Returns:
        WebSocketEvent 实例
    """
    return WebSocketEvent(
        type=event_type,
        task_id=task_id,
        timestamp=datetime.now().isoformat(),
        payload=payload if payload is not None else {},
    )
