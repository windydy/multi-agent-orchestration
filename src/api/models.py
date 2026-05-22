"""API response models for the Web UI."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class NodeEvent(BaseModel):
    """单个节点的执行事件"""
    node: str
    status: NodeStatus
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    output_summary: Optional[str] = None
    error: Optional[str] = None
    token_usage: Optional[dict] = None


class ExecutionItem(BaseModel):
    """执行列表中的一条"""
    thread_id: str
    workflow_name: str = "development"
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    node_count: int = 0
    completed_nodes: int = 0


class ExecutionListResponse(BaseModel):
    """执行列表响应"""
    total: int
    items: list[ExecutionItem]


class ExecutionDetail(BaseModel):
    """执行详情页"""
    thread_id: str
    workflow_name: str = "development"
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    nodes: list[NodeEvent] = []
    total_cost: Optional[float] = None
    total_tokens: Optional[int] = None
    task_input: Optional[str] = None


class OverviewStats(BaseModel):
    """系统概览"""
    total_executions: int = 0
    running: int = 0
    success: int = 0
    failed: int = 0
    interrupted: int = 0
    total_cost_24h: float = 0.0
    total_tokens_24h: int = 0


class DAGNode(BaseModel):
    """DAG graph node with execution status."""
    id: str
    label: str
    status: str
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    duration_ms: Optional[int] = None
    token_usage: Optional[dict] = None
    output_summary: Optional[str] = None
    cost: Optional[float] = None


class DAGEdge(BaseModel):
    """DAG graph edge representing a dependency."""
    from_node: str
    to_node: str


class DAGResponse(BaseModel):
    """DAG visualization response."""
    thread_id: str
    nodes: list[DAGNode]
    edges: list[DAGEdge]
