"""
Phase 4: PlanGraph — DAG 执行计划

src/plan/graph.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import json


class NodeStatus(Enum):
    """节点执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class NodeType(Enum):
    """节点类型"""
    TASK = "task"
    PARALLEL_GROUP = "parallel_group"
    CONDITION = "condition"
    SUB_PLAN = "sub_plan"


class ExecutorCapability(Enum):
    """Executor 能力声明"""
    # Phase 4 基础能力
    REQUIREMENTS_ANALYSIS = "requirements_analysis"
    TECHNICAL_DESIGN = "technical_design"
    CODE_DEVELOPMENT = "code_development"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    BUG_FIXING = "bug_fixing"
    DOCUMENTATION = "documentation"
    SECURITY_AUDIT = "security_audit"
    DEPLOYMENT = "deployment"
    GENERIC = "generic"
    # Phase 6 扩展能力
    DEVOPS_CI_CD = "devops_ci_cd"
    DEVOPS_CONTAINER = "devops_container"
    DEVOPS_INFRA = "devops_infra"
    DATA_ENGINEERING = "data_engineering"
    ARCHITECTURE_DESIGN = "architecture_design"
    PRODUCT_MANAGEMENT = "product_management"


@dataclass
class PlanNode:
    """执行计划 DAG 中的节点"""

    id: str
    """节点唯一标识"""

    name: str
    """节点名称"""

    node_type: NodeType = NodeType.TASK
    description: str = ""
    required_capability: ExecutorCapability = ExecutorCapability.GENERIC
    dependencies: list[str] = field(default_factory=list)
    parallel_group: Optional[str] = None
    condition: Optional[str] = None
    executor_name: Optional[str] = None
    max_retries: int = 3
    timeout_seconds: int = 300

    # 运行时状态
    status: NodeStatus = NodeStatus.PENDING
    retry_count: int = 0
    result: Optional[dict] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # 元数据
    metadata: dict = field(default_factory=dict)

    @property
    def is_entry(self) -> bool:
        return len(self.dependencies) == 0

    @property
    def is_terminal(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "node_type": self.node_type.value,
            "description": self.description,
            "required_capability": self.required_capability.value,
            "dependencies": self.dependencies,
            "parallel_group": self.parallel_group,
            "condition": self.condition,
            "executor_name": self.executor_name,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PlanNode:
        return cls(
            id=data["id"],
            name=data["name"],
            node_type=NodeType(data.get("node_type", "task")),
            description=data.get("description", ""),
            required_capability=ExecutorCapability(
                data.get("required_capability", "generic")
            ),
            dependencies=data.get("dependencies", []),
            parallel_group=data.get("parallel_group"),
            condition=data.get("condition"),
            executor_name=data.get("executor_name"),
            max_retries=data.get("max_retries", 3),
            timeout_seconds=data.get("timeout_seconds", 300),
            status=NodeStatus(data.get("status", "pending")),
            retry_count=data.get("retry_count", 0),
            result=data.get("result"),
            error=data.get("error"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PlanGraph:
    """完整的执行计划（有向无环图）"""

    id: str
    task: str
    nodes: dict[str, PlanNode] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)
    plan_type: str = "default"
    status: str = "draft"

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    planner_model: str = ""
    metadata: dict = field(default_factory=dict)

    def add_node(self, node: PlanNode) -> None:
        self.nodes[node.id] = node
        for dep_id in node.dependencies:
            if dep_id in self.nodes:
                self.edges.append((dep_id, node.id))
        self.updated_at = datetime.now().isoformat()

    def remove_node(self, node_id: str) -> Optional[PlanNode]:
        if node_id not in self.nodes:
            return None
        node = self.nodes.pop(node_id)
        self.edges = [
            (s, t) for s, t in self.edges if s != node_id and t != node_id
        ]
        self.updated_at = datetime.now().isoformat()
        return node

    def get_entry_nodes(self) -> list[PlanNode]:
        return [n for n in self.nodes.values() if not n.dependencies]

    def get_ready_nodes(self, completed: set[str]) -> list[PlanNode]:
        ready = []
        for node in self.nodes.values():
            if node.status == NodeStatus.PENDING and node.id not in completed:
                if all(dep in completed for dep in node.dependencies):
                    ready.append(node)
        return ready

    def get_parallel_groups(self) -> dict[str, list[PlanNode]]:
        groups: dict[str, list[PlanNode]] = {}
        for node in self.nodes.values():
            if node.parallel_group:
                groups.setdefault(node.parallel_group, []).append(node)
        return groups

    def topological_sort(self) -> list[str]:
        in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}
        adj: dict[str, list[str]] = {nid: [] for nid in self.nodes}

        for src, tgt in self.edges:
            if src in adj and tgt in in_degree:
                adj[src].append(tgt)
                in_degree[tgt] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result: list[str] = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)
            for neighbor in adj[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self.nodes):
            raise ValueError("图中检测到循环依赖（cycle detected）")

        return result

    def to_json(self) -> str:
        data = {
            "id": self.id,
            "task": self.task,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": [list(e) for e in self.edges],
            "plan_type": self.plan_type,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "planner_model": self.planner_model,
            "metadata": self.metadata,
        }
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> PlanGraph:
        data = json.loads(json_str)
        nodes = {}
        for nid, ndata in data.get("nodes", {}).items():
            nodes[nid] = PlanNode.from_dict(ndata)
        edges = [tuple(e) for e in data.get("edges", [])]
        return cls(
            id=data["id"],
            task=data["task"],
            nodes=nodes,
            edges=edges,
            plan_type=data.get("plan_type", "default"),
            status=data.get("status", "draft"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            planner_model=data.get("planner_model", ""),
            metadata=data.get("metadata", {}),
        )
