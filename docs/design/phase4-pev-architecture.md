# Phase 4 详细技术设计：Planner/Executor/Verifier (P/E/V) 核心架构

> **版本**: v1.0
> **日期**: 2026-05-20
> **状态**: 设计评审中
> **作者**: Multi-Agent Orchestration Team

---

## 目录

1. [概述](#1-概述)
2. [架构设计](#2-架构设计)
3. [数据模型](#3-数据模型)
4. [接口设计](#4-接口设计)
5. [工作流程](#5-工作流程)
6. [与现有代码的集成](#6-与现有代码的集成)
7. [文件变更清单](#7-文件变更清单)
8. [测试策略](#8-测试策略)
9. [实施步骤](#9-实施步骤)
10. [风险与缓解](#10-风险与缓解)

---

## 1. 概述

### 1.1 Phase 4 目标

Phase 4 引入 **Planner / Executor / Verifier (P/E/V)** 三层核心架构，从根本上替代 Phase 1-3 中硬编码在 `builder.py` 中的开发流水线。

**核心目标**：

| 目标 | 描述 | 对应现有痛点 |
|------|------|-------------|
| 动态规划 | Planner 根据用户意图自动拆解任务，生成有向无环执行计划(DAG) | 工作流硬编码，无法适应不同类型任务 |
| 细粒度执行 | Executor 作为原子任务执行单元，支持能力声明和实例池管理 | 角色边界模糊，Agent 职责过大 |
| 独立验证 | Verifier 独立于 Executor，支持多维度质量评分和自定义验证规则 | 缺乏系统化验证，质量不可度量 |
| 动态构建 | 从 PlanGraph 动态构建 LangGraph StateGraph | builder.py 中节点/边全部手动编排 |

### 1.2 与 Phase 1-3 的关系

```
Phase 1-3 (已完成)              Phase 4 (本阶段)
┌──────────────────────┐        ┌──────────────────────────────────┐
│ BaseAgent            │  继承  │ BaseExecutor (通过适配器复用)     │
│ ClaudeAgentWrapper   │  ──►   │ AgentExecutor (Adapter模式)       │
│                      │        │                                  │
│ DevelopmentPipeline  │  替代  │ DynamicWorkflowBuilder            │
│ (硬编码流水线)        │  ──►   │ (从PlanGraph动态构建LangGraph)    │
│                      │        │                                  │
│ 6个Agent角色          │  增强  │ PlannerAgent + ExecutorRegistry   │
│                      │        │ + VerifierFramework               │
│                      │        │                                  │
│ WorkflowState        │  扩展  │ WorkflowState + PlanGraph状态字段  │
│ (TypedDict)          │  ──►   │ + ExecutorResult + VerifierResult │
└──────────────────────┘        └──────────────────────────────────┘
```

**兼容性原则**：
- Phase 1-3 的所有公开 API 保持向后兼容
- 现有 6 个 Agent 通过 `AgentExecutor` 适配器可直接作为 Executor 使用
- `DevelopmentPipelineBuilder` 保留但标记为 `@deprecated`
- 新增 `DynamicWorkflowBuilder` 作为推荐入口

### 1.3 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| LLM | qwen3.6-plus (DashScope) | 通过 Anthropic-compatible 接口调用 |
| 编排引擎 | LangGraph StateGraph | 保持与 Phase 1-3 一致 |
| 状态持久化 | SqliteSaver / MemorySaver | 复用现有 checkpointer |
| 并发模型 | asyncio (事件循环) | Python 原生异步 |
| 图结构 | networkx (可选) | 用于 PlanGraph 的拓扑分析 |

---

## 2. 架构设计

### 2.1 整体三层架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER TASK (自然语言)                          │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1: PLANNER (规划层)                                          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      PlannerAgent                              │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐              │  │
│  │  │ 任务分析    │─►│ 任务分解    │─►│ 依赖构建    │              │  │
│  │  │ Analysis   │  │ Decompose  │  │ Dependency │              │  │
│  │  └────────────┘  └────────────┘  └────────────┘              │  │
│  │       │               │               │                        │  │
│  │       ▼               ▼               ▼                        │  │
│  │  ┌───────────────────────────────────────────────────────┐    │  │
│  │  │              PlanGraph (DAG 执行计划)                    │    │  │
│  │  │  ┌─────┐    ┌─────┐    ┌─────┐                        │    │  │
│  │  │  │ N1  │───►│ N2  │───►│ N5  │                         │    │  │
│  │  │  │需求  │    │设计  │    │测试  │                        │    │  │
│  │  │  └──┬──┘    └──┬──┘    └──┬──┘                        │    │  │
│  │  │     │          │          │                            │    │  │
│  │  │     ▼          ▼          │                            │    │  │
│  │  │  ┌─────────────┐         │                            │    │  │
│  │  │  │    N3/N4    │         │                            │    │  │
│  │  │  │ (并行:开发)  │────────►│                            │    │  │
│  │  │  └─────────────┘         │                            │    │  │
│  │  └───────────────────────────────────────────────────────┘    │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ PlanGraph
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 2: EXECUTOR (执行层)                                         │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   ExecutorRegistry                             │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │  │
│  │  │ Executor │ │ Executor │ │ Executor │ │ Executor │  ...    │  │
│  │  │ (需求)    │ │ (设计)    │ │ (开发)    │ │ (测试)    │        │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │  │
│  │       ▲              ▲              ▲              ▲          │  │
│  │       └──────────────┴──────────────┴──────────────┘          │  │
│  │                        │                                      │  │
│  │              ┌─────────▼──────────┐                           │  │
│  │              │  Dispatcher        │                           │  │
│  │              │  (能力匹配+负载均衡) │                          │  │
│  │              └─────────┬──────────┘                           │  │
│  └────────────────────────┼──────────────────────────────────────┘  │
└────────────────────────────┼────────────────────────────────────────┘
                             │ ExecutorResult
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 3: VERIFIER (验证层)                                         │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                  VerifierFramework                             │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐              │  │
│  │  │ 规则引擎    │  │ 评分系统    │  │ 结果聚合    │              │  │
│  │  │ RuleEngine │  │ Scorer     │  │ Aggregator │              │  │
│  │  └──────┬─────┘  └──────┬─────┘  └──────┬─────┘              │  │
│  │         │               │               │                    │  │
│  │  ┌──────▼───────────────▼───────────────▼──────┐             │  │
│  │  │              验证规则库                        │             │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐     │             │  │
│  │  │  │代码质量   │ │安全扫描   │ │依赖检查   │ ...  │             │  │
│  │  │  │Quality    │ │Security   │ │Dependency │     │             │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘     │             │  │
│  │  └─────────────────────────────────────────────┘             │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ VerificationResult (pass/fail + scores)
                           ▼
                    ┌──────────────┐
                    │ 是否通过？    │
                    └──────┬───────┘
                      ┌────┴────┐
                      │         │
                  pass│      fail│
                      ▼         ▼
              ┌──────────┐  ┌──────────┐
              │ COMPLETE │  │ REPLAN   │
              │ 完成     │  │ → 修正计划 │
              └──────────┘  └──────────┘
```

### 2.2 各层职责边界

| 层 | 核心职责 | 不负责 |
|----|---------|--------|
| **Planner** | 理解用户意图、任务分解、构建依赖 DAG、动态调度（根据反馈调整计划） | 不执行具体任务、不做代码级验证 |
| **Executor** | 执行原子任务、调用工具(文件读写/bash/搜索)、返回执行结果 | 不做任务规划、不做质量验证 |
| **Verifier** | 验证执行结果质量、多维度评分、判定 pass/fail | 不修改代码、不执行任务 |

**关键设计原则**：

1. **关注点分离**: Planner 只产出计划，Executor 只执行，Verifier 只验证
2. **接口稳定**: 三层之间通过结构化数据(PlanGraph/ExecutorResult/VerificationResult)通信
3. **可替换性**: 每层都可以独立替换实现（如替换 Planner 的 LLM 模型）
4. **可观测性**: 每层都输出结构化日志和指标

### 2.3 与 LangGraph 的集成策略

P/E/V 架构不是替代 LangGraph，而是在 LangGraph 之上构建智能调度层：

```
用户请求
  │
  ▼
PlannerAgent ──(生成)──► PlanGraph
  │
  ▼
DynamicWorkflowBuilder ──(转换)──► LangGraph StateGraph
  │                                   │
  ▼                                   ▼
ExecutorRegistry ──(注册)──► LangGraph 节点函数
  │                                   │
  ▼                                   ▼
VerifierFramework ──(注册)──► LangGraph 条件边/验证节点
                                  │
                                  ▼
                         compiled LangGraph app
                                  │
                                  ▼
                           WorkflowRunner.run()
```

**转换过程**：
- PlanNode → LangGraph 节点函数（调用对应 Executor）
- PlanGraph 依赖边 → LangGraph 有向边
- 并行节点 → LangGraph 的并行执行机制（通过 State 的 Annotated 字段聚合）
- 条件分支 → LangGraph 的 conditional_edges
- 验证失败分支 → LangGraph 的条件路由到 replan 节点

---

## 3. 数据模型

### 3.1 PlanNode — DAG 中的节点

```python
"""src/plan/graph.py — PlanNode 定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class NodeStatus(Enum):
    """节点执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"       # 条件分支跳过
    CANCELLED = "cancelled"   # 被上游失败取消


class NodeType(Enum):
    """节点类型"""
    TASK = "task"             # 普通原子任务
    PARALLEL_GROUP = "parallel_group"  # 并行节点组
    CONDITION = "condition"   # 条件分支点
    SUB_PLAN = "sub_plan"     # 嵌套子计划（用于 replan）


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
    GENERIC = "generic"       # 通用能力（兜底）
    # Phase 6 扩展能力
    DEVOPS_CI_CD = "devops_ci_cd"
    DEVOPS_CONTAINER = "devops_container"
    DEVOPS_INFRA = "devops_infra"
    DATA_ENGINEERING = "data_engineering"
    ARCHITECTURE_DESIGN = "architecture_design"
    PRODUCT_MANAGEMENT = "product_management"


@dataclass
class PlanNode:
    """
    执行计划 DAG 中的节点。

    每个节点代表一个原子任务，包含：
    - 任务描述和所需能力
    - 依赖关系（上游节点 ID 列表）
    - 执行条件（可选的条件判断函数名）
    - 运行时状态追踪
    """

    id: str
    """节点唯一标识，如 'node-001' 或语义化 ID 如 'req-analysis'"""

    name: str
    """节点名称，如 '需求分析'、'数据库设计'"""

    node_type: NodeType = NodeType.TASK

    description: str = ""
    """任务详细描述，将作为 Executor 的输入"""

    required_capability: ExecutorCapability = ExecutorCapability.GENERIC
    """执行此节点所需的 Executor 能力"""

    dependencies: list[str] = field(default_factory=list)
    """上游依赖节点 ID 列表。空列表表示入口节点"""

    parallel_group: Optional[str] = None
    """并行组标识。同一 parallel_group 的节点可并发执行"""

    condition: Optional[str] = None
    """条件表达式名称。仅当条件为真时执行此节点。
    例如: 'review.approved == True'"""

    executor_name: Optional[str] = None
    """指定的 Executor 名称。如果为 None，由 Registry 自动匹配"""

    max_retries: int = 3
    """最大重试次数"""

    timeout_seconds: int = 300
    """执行超时（秒）"""

    # ---- 运行时状态 ----
    status: NodeStatus = NodeStatus.PENDING
    retry_count: int = 0
    result: Optional[dict] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # ---- 元数据 ----
    metadata: dict = field(default_factory=dict)

    @property
    def is_entry(self) -> bool:
        """是否入口节点（无依赖）"""
        return len(self.dependencies) == 0

    @property
    def is_terminal(self) -> bool:
        """是否终端节点（在 PlanGraph 中无下游）"""
        # 由 PlanGraph 计算
        return False

    def to_dict(self) -> dict:
        """序列化为 dict（用于持久化和传输）"""
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
        """从 dict 反序列化"""
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
```

### 3.2 PlanGraph — 完整执行计划

```python
"""src/plan/graph.py — PlanGraph 定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json


@dataclass
class PlanGraph:
    """
    完整的执行计划（有向无环图）。

    由 PlannerAgent 生成，包含所有节点及其依赖关系。
    支持：
    - 拓扑排序获取执行顺序
    - 并行组检测
    - 动态增删节点（用于 replan）
    - 序列化和持久化
    """

    id: str
    """计划唯一标识"""

    task: str
    """原始任务描述"""

    nodes: dict[str, PlanNode] = field(default_factory=dict)
    """节点映射: node_id -> PlanNode"""

    edges: list[tuple[str, str]] = field(default_factory=list)
    """边列表: (source_id, target_id)"""

    plan_type: str = "default"
    """计划类型: default / iterative / exploratory"""

    status: str = "draft"
    """计划状态: draft / approved / executing / completed / failed"""

    # ---- 元数据 ----
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    planner_model: str = ""
    metadata: dict = field(default_factory=dict)

    # ---- 图操作 ----

    def add_node(self, node: PlanNode) -> None:
        """添加节点到图中"""
        self.nodes[node.id] = node
        for dep_id in node.dependencies:
            if dep_id in self.nodes:
                self.edges.append((dep_id, node.id))
        self.updated_at = datetime.now().isoformat()

    def remove_node(self, node_id: str) -> Optional[PlanNode]:
        """移除节点及其相关边"""
        if node_id not in self.nodes:
            return None
        node = self.nodes.pop(node_id)
        self.edges = [
            (s, t) for s, t in self.edges if s != node_id and t != node_id
        ]
        self.updated_at = datetime.now().isoformat()
        return node

    def get_entry_nodes(self) -> list[PlanNode]:
        """获取入口节点（无依赖的节点）"""
        return [n for n in self.nodes.values() if not n.dependencies]

    def get_ready_nodes(self, completed: set[str]) -> list[PlanNode]:
        """
        获取当前可执行的节点。

        Args:
            completed: 已完成节点 ID 集合

        Returns:
            所有依赖已满足且未执行的节点
        """
        ready = []
        for node in self.nodes.values():
            if node.status in (NodeStatus.PENDING,):
                if all(dep in completed for dep in node.dependencies):
                    ready.append(node)
        return ready

    def get_parallel_groups(self) -> dict[str, list[PlanNode]]:
        """
        按并行组分组节点。

        Returns:
            {group_name: [nodes]}，不含并行组的节点不在结果中
        """
        groups: dict[str, list[PlanNode]] = {}
        for node in self.nodes.values():
            if node.parallel_group:
                groups.setdefault(node.parallel_group, []).append(node)
        return groups

    def topological_sort(self) -> list[str]:
        """
        拓扑排序返回节点执行顺序。

        Raises:
            ValueError: 如果检测到环
        """
        in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}
        adj: dict[str, list[str]] = {nid: [] for nid in self.nodes}

        for src, tgt in self.edges:
            if src in adj and tgt in in_degree:
                adj[src].append(tgt)
                in_degree[tgt] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result: list[str] = []

        while queue:
            # 同一批次的节点可并行执行
            queue.sort()  # 确定性排序
            result.extend(queue)
            next_queue = []
            for nid in queue:
                for neighbor in adj[nid]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
            queue = next_queue

        if len(result) != len(self.nodes):
            raise ValueError("PlanGraph 包含环，无法拓扑排序")

        return result

    def get_downstream(self, node_id: str) -> list[str]:
        """获取节点的所有下游节点 ID（BFS）"""
        adj: dict[str, list[str]] = {}
        for nid in self.nodes:
            adj[nid] = []
        for src, tgt in self.edges:
            adj.setdefault(src, []).append(tgt)

        visited = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            for neighbor in adj.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return list(visited)

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(
            {
                "id": self.id,
                "task": self.task,
                "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
                "edges": self.edges,
                "plan_type": self.plan_type,
                "status": self.status,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "planner_model": self.planner_model,
                "metadata": self.metadata,
            },
            ensure_ascii=False,
            indent=indent,
        )

    @classmethod
    def from_json(cls, json_str: str) -> PlanGraph:
        """从 JSON 字符串反序列化"""
        data = json.loads(json_str)
        nodes = {
            nid: PlanNode.from_dict(nd)
            for nid, nd in data.get("nodes", {}).items()
        }
        return cls(
            id=data["id"],
            task=data["task"],
            nodes=nodes,
            edges=[tuple(e) for e in data.get("edges", [])],
            plan_type=data.get("plan_type", "default"),
            status=data.get("status", "draft"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            planner_model=data.get("planner_model", ""),
            metadata=data.get("metadata", {}),
        )

    def visualize_ascii(self) -> str:
        """ASCII 可视化执行计划"""
        lines = [f"PlanGraph: {self.id}", f"Task: {self.task}", ""]

        # 获取拓扑排序批次
        try:
            order = self.topological_sort()
        except ValueError:
            return "ERROR: 检测到环"

        # 按并行组分组
        groups = self.get_parallel_groups()
        group_map = {}
        for gname, gnodes in groups.items():
            for n in gnodes:
                group_map[n.id] = gname

        visited = set()
        for nid in order:
            node = self.nodes[nid]
            prefix = "  " * len(node.dependencies)
            group_tag = f" [{group_map[nid]}]" if nid in group_map else ""
            status_icon = {
                NodeStatus.PENDING: "○",
                NodeStatus.RUNNING: "◐",
                NodeStatus.COMPLETED: "●",
                NodeStatus.FAILED: "✗",
                NodeStatus.SKIPPED: "⊘",
            }.get(node.status, "?")

            lines.append(f"{prefix}{status_icon} {node.name}{group_tag}")
            visited.add(nid)

        return "\n".join(lines)
```

### 3.3 ExecutorCapability — 能力声明

```python
"""src/executors/base.py — ExecutorCapability 定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class CapabilityLevel(Enum):
    """能力等级"""
    BASIC = "basic"       # 基本能力，可完成简单任务
    STANDARD = "standard" # 标准能力，可完成大多数任务
    EXPERT = "expert"     # 专家级，可完成复杂任务


@dataclass
class ExecutorCapability:
    """
    Executor 能力声明。

    每个 Executor 声明其支持的能力集合，
    供 ExecutorRegistry 进行能力匹配。
    """

    capability: ExecutorCapability  # 复用 PlanNode 中的枚举
    level: CapabilityLevel = CapabilityLevel.STANDARD
    description: str = ""
    """能力的详细描述"""

    supported_languages: list[str] = field(default_factory=list)
    """支持的编程语言: ['python', 'javascript', 'go']"""

    max_complexity: Optional[int] = None
    """可处理的最大任务复杂度（由 Planner 评估）"""


@dataclass
class ExecutorStatus:
    """Executor 运行时状态"""
    is_busy: bool = False
    current_task: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_error: Optional[str] = None
    uptime_seconds: float = 0.0


@dataclass
class ExecutorResult:
    """
    Executor 执行结果。

    这是 Executor 执行原子任务后的标准化输出，
    将写入 WorkflowState 供后续节点和 Verifier 使用。
    """

    node_id: str
    """对应的 PlanNode ID"""

    success: bool
    """执行是否成功"""

    output: Any = None
    """执行输出（结构化数据或文本）"""

    artifacts: dict = field(default_factory=dict)
    """产生的产物: {'files': [...], 'tests': [...], 'docs': [...]}"""

    error: Optional[str] = None
    """错误信息（仅在 success=False 时设置）"""

    execution_time: float = 0.0
    """执行耗时（秒）"""

    cost: float = 0.0
    """执行成本（美元）"""

    metadata: dict = field(default_factory=dict)
    """额外元数据"""

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "success": self.success,
            "output": self.output,
            "artifacts": self.artifacts,
            "error": self.error,
            "execution_time": self.execution_time,
            "cost": self.cost,
            "metadata": self.metadata,
        }
```

### 3.4 VerificationResult — 验证结果

```python
"""src/verifiers/base.py — VerificationResult 定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class VerificationStatus(Enum):
    """验证状态"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"       # 通过但有警告
    SKIPPED = "skipped"       # 规则不适用


class VerificationDimension(Enum):
    """验证维度"""
    CORRECTNESS = "correctness"       # 功能正确性
    CODE_QUALITY = "code_quality"     # 代码质量
    SECURITY = "security"             # 安全性
    PERFORMANCE = "performance"       # 性能
    COVERAGE = "coverage"             # 测试覆盖率
    STYLE = "style"                   # 代码风格
    DOCUMENTATION = "documentation"   # 文档完整性


@dataclass
class VerificationItem:
    """单条验证结果"""

    rule_id: str
    """验证规则 ID，如 'lint-no-unused-imports'"""

    dimension: VerificationDimension
    status: VerificationStatus
    score: float = 1.0
    """单项得分 0.0-1.0"""

    message: str = ""
    """验证结果描述"""

    details: dict = field(default_factory=dict)
    """详细信息（如违规文件列表、行号等）"""


@dataclass
class VerificationResult:
    """
    完整的验证结果。

    由 VerifierFramework 聚合所有验证规则的结果产出。
    """

    node_id: str
    """被验证的 PlanNode ID"""

    executor_result: Optional[ExecutorResult] = None
    """对应的 Executor 结果引用"""

    items: list[VerificationItem] = field(default_factory=list)
    """所有验证条目"""

    overall_status: VerificationStatus = VerificationStatus.PASSED
    """总体状态（由聚合逻辑决定）"""

    overall_score: float = 1.0
    """总体得分 0.0-1.0"""

    # ---- 多维度评分 ----
    dimension_scores: dict[str, float] = field(default_factory=dict)
    """各维度得分: {'correctness': 0.95, 'security': 0.8, ...}"""

    summary: str = ""
    """人类可读的验证总结"""

    metadata: dict = field(default_factory=dict)

    @property
    def is_passed(self) -> bool:
        return self.overall_status in (
            VerificationStatus.PASSED,
            VerificationStatus.WARNING,
        )

    def add_item(self, item: VerificationItem) -> None:
        self.items.append(item)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "overall_status": self.overall_status.value,
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "items": [
                {
                    "rule_id": i.rule_id,
                    "dimension": i.dimension.value,
                    "status": i.status.value,
                    "score": i.score,
                    "message": i.message,
                    "details": i.details,
                }
                for i in self.items
            ],
            "summary": self.summary,
            "metadata": self.metadata,
        }
```

---

## 4. 接口设计

### 4.1 BaseExecutor 抽象

```python
"""src/executors/base.py — BaseExecutor 抽象基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional
import asyncio
import time
import uuid

from src.core.agent import BaseAgent, AgentConfig, AgentResult, AgentRole
from src.plan.graph import ExecutorCapability, CapabilityLevel
from src.executors.base import ExecutorResult, ExecutorStatus


class BaseExecutor(ABC):
    """
    Executor 抽象基类。

    Executor 是实际执行原子任务的单元。与 BaseAgent 的区别：
    - 更细粒度：每个 Executor 专注于单一能力
    - 能力声明：显式声明 capabilities 供 Registry 匹配
    - 实例池管理：支持多实例和负载均衡
    - 标准化输出：统一返回 ExecutorResult

    与现有 Agent 的集成：
    - 通过 AgentExecutor 适配器将 BaseAgent 包装为 BaseExecutor
    - 新的 Executor 可直接继承 BaseExecutor 并实现 execute()
    """

    def __init__(
        self,
        executor_id: str = None,
        capabilities: list[ExecutorCapability] = None,
    ):
        self.executor_id = executor_id or f"exec-{uuid.uuid4().hex[:8]}"
        self._capabilities = capabilities or []
        self._status = ExecutorStatus()
        self._created_at = time.time()

    @property
    def capabilities(self) -> list[ExecutorCapability]:
        return self._capabilities

    @property
    def status(self) -> ExecutorStatus:
        return self._status

    @abstractmethod
    async def execute(
        self,
        node_description: str,
        context: dict[str, Any] = None,
    ) -> ExecutorResult:
        """
        执行原子任务。

        Args:
            node_description: PlanNode 的任务描述
            context: 执行上下文，包含：
                - project_path: 项目路径
                - upstream_results: 上游节点的 ExecutorResult 映射
                - plan_graph: 完整 PlanGraph（可选引用）
                - node_id: 当前节点 ID

        Returns:
            ExecutorResult: 标准化执行结果
        """
        pass

    async def can_handle(self, capability: ExecutorCapability) -> bool:
        """
        检查是否能处理指定能力。

        Args:
            capability: 所需能力

        Returns:
            是否支持
        """
        for cap in self._capabilities:
            if cap.capability == capability:
                return True
        return False

    def match_score(self, capability: ExecutorCapability) -> float:
        """
        计算与所需能力的匹配分数。

        Returns:
            0.0 (不匹配) ~ 1.0 (完美匹配)
        """
        level_weights = {
            CapabilityLevel.BASIC: 0.5,
            CapabilityLevel.STANDARD: 0.8,
            CapabilityLevel.EXPERT: 1.0,
        }

        for cap in self._capabilities:
            if cap.capability == capability:
                weight = level_weights.get(cap.level, 0.5)
                # 如果 Executor 空闲，加分
                availability_bonus = 0.2 if not self._status.is_busy else 0.0
                return min(weight + availability_bonus, 1.0)

        return 0.0

    def __repr__(self) -> str:
        caps = ", ".join(c.capability.value for c in self._capabilities)
        busy = "busy" if self._status.is_busy else "idle"
        return f"Executor(id={self.executor_id}, caps=[{caps}], status={busy})"


class AgentExecutor(BaseExecutor):
    """
    Agent 适配器 — 将现有 BaseAgent 包装为 Executor。

    这是 Phase 4 与 Phase 1-3 的桥接层。
    现有 6 个 Agent 无需修改即可作为 Executor 使用。
    """

    def __init__(
        self,
        agent: BaseAgent,
        capabilities: list[ExecutorCapability] = None,
        executor_id: str = None,
    ):
        super().__init__(executor_id=executor_id, capabilities=capabilities)
        self._agent = agent

    @property
    def agent(self) -> BaseAgent:
        return self._agent

    async def execute(
        self,
        node_description: str,
        context: dict[str, Any] = None,
    ) -> ExecutorResult:
        start_time = time.time()
        context = context or {}

        try:
            self._status.is_busy = True
            self._status.current_task = node_description

            # 构建上游结果上下文
            upstream = context.get("upstream_results", {})
            agent_context = {
                "project_path": context.get("project_path", "."),
                "previous_results": upstream,
                "node_id": context.get("node_id"),
            }

            # 调用底层 Agent
            result: AgentResult = await self._agent.run(
                input=node_description,
                context=agent_context,
            )

            execution_time = time.time() - start_time

            # 转换为 ExecutorResult
            if result.success:
                self._status.tasks_completed += 1
                return ExecutorResult(
                    node_id=context.get("node_id", ""),
                    success=True,
                    output=result.output,
                    artifacts=self._extract_artifacts(result.output),
                    execution_time=execution_time,
                    cost=result.metadata.get("cost", 0.0),
                    metadata={
                        "agent_name": self._agent.config.name,
                        "iterations": result.metadata.get("iterations", 0),
                        "steps": result.steps,
                    },
                )
            else:
                self._status.tasks_failed += 1
                self._status.last_error = result.error
                return ExecutorResult(
                    node_id=context.get("node_id", ""),
                    success=False,
                    output=None,
                    error=result.error,
                    execution_time=execution_time,
                    cost=result.metadata.get("cost", 0.0),
                    metadata={"agent_name": self._agent.config.name},
                )

        except Exception as e:
            execution_time = time.time() - start_time
            self._status.tasks_failed += 1
            self._status.last_error = str(e)
            return ExecutorResult(
                node_id=context.get("node_id", ""),
                success=False,
                output=None,
                error=str(e),
                execution_time=execution_time,
            )

        finally:
            self._status.is_busy = False
            self._status.current_task = None
            self._status.uptime_seconds = time.time() - self._created_at

    def _extract_artifacts(self, output: Any) -> dict:
        """从 Agent 输出中提取产物信息"""
        artifacts = {"files": [], "tests": [], "docs": []}
        if isinstance(output, dict):
            artifacts["files"] = output.get("files_created", [])
            artifacts["tests"] = output.get("tests_added", [])
        elif isinstance(output, str):
            # 简单文本输出，不提取结构化产物
            pass
        return artifacts
```

### 4.2 ExecutorRegistry — 注册与调度

```python
"""src/executors/registry.py — ExecutorRegistry"""

from __future__ import annotations

from typing import Optional
import logging

from src.plan.graph import ExecutorCapability
from src.executors.base import BaseExecutor

logger = logging.getLogger(__name__)


class ExecutorRegistry:
    """
    Executor 注册与调度中心。

    职责：
    - 管理 Executor 实例池（注册/注销）
    - 能力匹配：根据所需能力找到最佳 Executor
    - 负载均衡：在多个匹配 Executor 中选择最合适的
    - 状态追踪：监控 Executor 健康和负载
    """

    def __init__(self):
        self._executors: dict[str, BaseExecutor] = {}
        self._capability_index: dict[ExecutorCapability, list[str]] = {}

    def register(
        self,
        executor: BaseExecutor,
        capabilities: Optional[list[ExecutorCapability]] = None,
    ) -> None:
        """注册一个 Executor 实例
        
        Args:
            executor: Executor 实例
            capabilities: 可选的能力覆盖。如果不提供，使用 executor.capabilities。
                用于 Phase 5 ConfigurableWorkflowBuilder 通过 YAML 配置推断能力。
        """
        self._executors[executor.executor_id] = executor
        # 使用传入的 capabilities 或 executor 自带的 capabilities
        caps = capabilities if capabilities is not None else executor.capabilities
        # 更新能力索引
        for cap in caps:
            self._capability_index.setdefault(cap, []).append(
                executor.executor_id
            )
        logger.info(f"Registered executor: {executor.executor_id}")

    def unregister(self, executor_id: str) -> bool:
        """注销一个 Executor 实例"""
        if executor_id not in self._executors:
            return False

        executor = self._executors.pop(executor_id)
        # 清理能力索引（兼容 ExecutorCapability 枚举和 CapabilityLevel 对象）
        caps = executor.capabilities
        for cap in caps:
            cap_key = cap if isinstance(cap, ExecutorCapability) else cap.capability
            if cap_key in self._capability_index:
                self._capability_index[cap_key] = [
                    eid
                    for eid in self._capability_index[cap_key]
                    if eid != executor_id
                ]
        logger.info(f"Unregistered executor: {executor_id}")
        return True

    def get(self, executor_id: str) -> Optional[BaseExecutor]:
        return self._executors.get(executor_id)

    def find_best(
        self,
        required_capability: ExecutorCapability,
        exclude_ids: set[str] = None,
    ) -> Optional[BaseExecutor]:
        """
        找到处理指定能力的最佳 Executor。

        匹配策略：
        1. 过滤：只保留支持该能力且未被排除的 Executor
        2. 排序：按 match_score 降序
        3. 选择：最高分且空闲的 Executor

        Args:
            required_capability: 所需能力
            exclude_ids: 排除的 Executor ID 集合

        Returns:
            最佳 Executor，如果没有匹配则返回 None
        """
        exclude_ids = exclude_ids or set()
        candidates: list[tuple[float, BaseExecutor]] = []

        for eid in self._capability_index.get(required_capability, []):
            if eid in exclude_ids:
                continue
            executor = self._executors.get(eid)
            if executor is None:
                continue
            score = executor.match_score(required_capability)
            if score > 0:
                candidates.append((score, executor))

        if not candidates:
            # 降级：尝试 GENERIC 能力的 Executor
            for eid in self._capability_index.get(
                ExecutorCapability.GENERIC, []
            ):
                if eid in exclude_ids:
                    continue
                executor = self._executors.get(eid)
                if executor and not executor.status.is_busy:
                    return executor

            return None

        # 按分数排序，优先选择空闲的
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def list_all(self) -> list[BaseExecutor]:
        return list(self._executors.values())

    def list_by_capability(
        self, capability: ExecutorCapability
    ) -> list[BaseExecutor]:
        """列出支持指定能力的所有 Executor"""
        return [
            self._executors[eid]
            for eid in self._capability_index.get(capability, [])
            if eid in self._executors
        ]

    @property
    def total_executors(self) -> int:
        return len(self._executors)

    @property
    def busy_count(self) -> int:
        return sum(1 for e in self._executors.values() if e.status.is_busy)

    def get_status_summary(self) -> dict:
        return {
            "total": self.total_executors,
            "busy": self.busy_count,
            "idle": self.total_executors - self.busy_count,
            "executors": {
                eid: {
                    "capabilities": [c.capability.value for c in exec.capabilities],
                    "busy": exec.status.is_busy,
                    "tasks_completed": exec.status.tasks_completed,
                    "tasks_failed": exec.status.tasks_failed,
                }
                for eid, exec in self._executors.items()
            },
        }
```

### 4.3 BaseVerifier 抽象

```python
"""src/verifiers/base.py — BaseVerifier 抽象基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from src.verifiers.base import (
    VerificationResult,
    VerificationItem,
    VerificationStatus,
    VerificationDimension,
)
from src.executors.base import ExecutorResult


class BaseVerifier(ABC):
    """
    Verifier 抽象基类。

    Verifier 独立于 Executor，负责对执行结果进行验证。
    每个 Verifier 可以包含多条验证规则。
    """

    def __init__(self, verifier_id: str = "", name: str = ""):
        self.verifier_id = verifier_id or self.__class__.__name__
        self.name = name or self.verifier_id

    @abstractmethod
    async def verify(
        self,
        executor_result: ExecutorResult,
        context: dict[str, Any] = None,
    ) -> VerificationResult:
        """
        验证 Executor 的执行结果。

        Args:
            executor_result: Executor 的输出
            context: 验证上下文（项目路径、PlanNode 信息等）

        Returns:
            VerificationResult: 验证结果
        """
        pass

    def applies_to(
        self,
        executor_result: ExecutorResult,
        context: dict[str, Any] = None,
    ) -> bool:
        """
        检查此 Verifier 是否适用于当前结果。

        默认实现返回 True。子类可覆盖以实现条件验证。

        Returns:
            是否适用
        """
        return True
```

### 4.4 VerifierFramework — 验证框架

```python
"""src/verifiers/framework.py — VerifierFramework"""

from __future__ import annotations

from typing import Any, Callable, Awaitable, Optional
import logging

from src.verifiers.base import (
    BaseVerifier,
    VerificationResult,
    VerificationItem,
    VerificationStatus,
    VerificationDimension,
)
from src.executors.base import ExecutorResult

logger = logging.getLogger(__name__)

# 自定义验证函数类型
CustomVerificationFn = Callable[
    [ExecutorResult, dict[str, Any]],
    Awaitable[VerificationItem],
]


class VerifierFramework:
    """
    验证框架。

    支持：
    - 预设验证规则注册（BaseVerifier 实例）
    - 自定义验证函数注册（轻量级验证逻辑）
    - 多维度质量评分聚合
    - 验证结果聚合（overall_status / overall_score）
    """

    def __init__(
        self,
        pass_threshold: float = 0.7,
        warning_threshold: float = 0.85,
    ):
        self._verifiers: dict[str, BaseVerifier] = {}
        self._custom_rules: list[CustomVerificationFn] = []
        self._pass_threshold = pass_threshold
        self._warning_threshold = warning_threshold

    def register_verifier(self, verifier: BaseVerifier) -> None:
        """注册一个 Verifier"""
        self._verifiers[verifier.verifier_id] = verifier
        logger.info(f"Registered verifier: {verifier.name}")

    def register_custom_rule(self, rule_fn: CustomVerificationFn) -> None:
        """注册自定义验证函数"""
        self._custom_rules.append(rule_fn)

    async def verify(
        self,
        executor_result: ExecutorResult,
        context: dict[str, Any] = None,
    ) -> VerificationResult:
        """
        对执行结果执行完整验证流程。

        1. 遍历所有已注册的 Verifier
        2. 执行所有自定义验证规则
        3. 聚合结果计算 overall_status 和 overall_score
        4. 生成多维度评分

        Args:
            executor_result: 待验证的执行结果
            context: 验证上下文

        Returns:
            VerificationResult: 聚合验证结果
        """
        context = context or {}
        result = VerificationResult(
            node_id=executor_result.node_id,
            executor_result=executor_result,
        )

        # 1. 执行已注册的 Verifier
        for vid, verifier in self._verifiers.items():
            if not verifier.applies_to(executor_result, context):
                continue
            try:
                vr = await verifier.verify(executor_result, context)
                for item in vr.items:
                    result.add_item(item)
            except Exception as e:
                logger.error(f"Verifier {vid} failed: {e}")
                result.add_item(VerificationItem(
                    rule_id=vid,
                    dimension=VerificationDimension.CORRECTNESS,
                    status=VerificationStatus.FAILED,
                    score=0.0,
                    message=f"验证器异常: {e}",
                ))

        # 2. 执行自定义规则
        for idx, rule_fn in enumerate(self._custom_rules):
            try:
                item = await rule_fn(executor_result, context)
                result.add_item(item)
            except Exception as e:
                logger.error(f"Custom rule #{idx} failed: {e}")
                result.add_item(VerificationItem(
                    rule_id=f"custom-{idx}",
                    dimension=VerificationDimension.CORRECTNESS,
                    status=VerificationStatus.FAILED,
                    score=0.0,
                    message=f"自定义规则异常: {e}",
                ))

        # 3. 聚合结果
        self._aggregate(result)
        return result

    def _aggregate(self, result: VerificationResult) -> None:
        """聚合验证结果，计算 overall_status 和 overall_score"""
        if not result.items:
            result.overall_status = VerificationStatus.PASSED
            result.overall_score = 1.0
            result.summary = "无验证规则，默认通过"
            return

        # 计算各维度平均分
        dim_scores: dict[str, list[float]] = {}
        for item in result.items:
            dim = item.dimension.value
            dim_scores.setdefault(dim, []).append(item.score)

        result.dimension_scores = {
            dim: sum(scores) / len(scores)
            for dim, scores in dim_scores.items()
        }

        # 总体得分 = 所有 item 的加权平均
        total_score = sum(i.score for i in result.items) / len(result.items)
        result.overall_score = round(total_score, 3)

        # 总体状态
        has_failed = any(
            i.status == VerificationStatus.FAILED for i in result.items
        )
        has_warning = any(
            i.status == VerificationStatus.WARNING for i in result.items
        )

        if has_failed:
            result.overall_status = VerificationStatus.FAILED
        elif has_warning:
            result.overall_status = VerificationStatus.WARNING
        else:
            result.overall_status = VerificationStatus.PASSED

        # 阈值覆盖
        if result.overall_status == VerificationStatus.PASSED:
            if result.overall_score < self._pass_threshold:
                result.overall_status = VerificationStatus.FAILED
            elif result.overall_score < self._warning_threshold:
                result.overall_status = VerificationStatus.WARNING

        # 生成摘要
        passed = sum(1 for i in result.items if i.status == VerificationStatus.PASSED)
        failed = sum(1 for i in result.items if i.status == VerificationStatus.FAILED)
        warned = sum(1 for i in result.items if i.status == VerificationStatus.WARNING)
        result.summary = (
            f"验证完成: {passed} 通过, {warned} 警告, {failed} 失败 | "
            f"总分: {result.overall_score}"
        )

    @property
    def verifier_count(self) -> int:
        return len(self._verifiers)

    @property
    def custom_rule_count(self) -> int:
        return len(self._custom_rules)
```

### 4.5 PlannerAgent — 规划器

```python
"""src/agents/planner.py — PlannerAgent"""

from __future__ import annotations

from typing import Any, Optional
import json
import uuid

from src.core.agent import AgentConfig, AgentRole, AgentResult
from src.claude.wrapper import ClaudeAgentWrapper, ClaudeSDKConfig, ClaudeToolType
from src.claude.hooks import create_hooks
from src.plan.graph import PlanGraph, PlanNode, NodeType, NodeStatus


# Planner 系统提示
PLANNER_SYSTEM_PROMPT = """
你是一个任务规划专家 (Planner)。你的职责是：

1. **任务分析**: 理解用户的自然语言任务描述，判断任务类型和复杂度
2. **任务分解**: 将任务拆解为原子子任务（每个子任务应足够小，可由一个 Executor 完成）
3. **依赖构建**: 分析子任务之间的依赖关系，构建 DAG（有向无环图）
4. **资源分配**: 为每个子任务指定所需的 Executor 能力
5. **动态调整**: 根据执行反馈（失败/验证不通过）重新规划

输出格式（JSON）：
{
    "plan_type": "default | iterative | exploratory",
    "nodes": [
        {
            "id": "节点ID（语义化，如 req-analysis）",
            "name": "节点名称",
            "description": "任务详细描述，包含足够的上下文供Executor执行",
            "required_capability": "能力枚举值",
            "dependencies": ["依赖节点ID列表"],
            "parallel_group": "并行组名（可选，同组节点可并发）",
            "condition": "条件表达式（可选）",
            "max_retries": 3,
            "timeout_seconds": 300
        }
    ],
    "rationale": "规划理由说明"
}

能力枚举值：
- requirements_analysis: 需求分析
- technical_design: 技术设计
- code_development: 代码开发
- code_review: 代码审查
- testing: 测试验证
- bug_fixing: Bug修复
- documentation: 文档编写
- security_audit: 安全审计
- deployment: 部署
- generic: 通用能力（兜底）

注意事项：
- 确保 DAG 无环
- 合理设置并行组以提高执行效率
- 为每个节点提供足够详细的 description
- 依赖关系要准确，避免过度约束或遗漏依赖
"""


class PlannerAgent(ClaudeAgentWrapper):
    """
    Planner Agent — 负责任务规划。

    继承 ClaudeAgentWrapper，使用更强的模型（建议 opus/sonnet）。
    生成 PlanGraph 作为执行计划。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen3.6-plus",
        hooks: list = None,
    ):
        config = AgentConfig(
            name="planner",
            role=AgentRole.MANAGER,
            description="任务规划专家 - 分析、分解任务并构建执行计划DAG",
            model=model,
            tools=["read_file", "search"],
            max_iterations=5,
            timeout=120,
            temperature=0.3,
            system_prompt=PLANNER_SYSTEM_PROMPT,
        )

        claude_config = ClaudeSDKConfig(
            api_key=api_key,
            model=model,
            max_tokens=4096,
            temperature=0.3,
            tools=[
                ClaudeToolType.READ_FILE,
                ClaudeToolType.SEARCH,
            ],
            system_prompt=PLANNER_SYSTEM_PROMPT,
        )

        hooks = hooks or create_hooks(safety=True, logging=True, cost_control=True)
        super().__init__(config, claude_config, hooks)

    async def create_plan(
        self,
        task: str,
        context: dict[str, Any] = None,
    ) -> PlanGraph:
        """
        为任务创建执行计划。

        Args:
            task: 用户任务描述
            context: 上下文信息（项目路径、已有文件等）

        Returns:
            PlanGraph: 生成的执行计划
        """
        context = context or {}
        context_info = json.dumps(context, ensure_ascii=False, indent=2)

        prompt = f"""
请为以下任务创建执行计划：

任务: {task}

项目上下文:
{context_info}

请按 JSON 格式输出计划。
"""

        result = await self.run(input=prompt, context={"role": "planner"})

        if not result.success:
            raise RuntimeError(f"Planner 生成计划失败: {result.error}")

        return self._parse_plan_response(result.output)

    async def replan(
        self,
        original_plan: PlanGraph,
        failed_node_id: str,
        failure_reason: str,
        available_results: dict[str, Any] = None,
    ) -> PlanGraph:
        """
        根据失败信息重新规划。

        Args:
            original_plan: 原始计划
            failed_node_id: 失败的节点 ID
            failure_reason: 失败原因
            available_results: 已成功节点的结果

        Returns:
            PlanGraph: 修正后的计划
        """
        available_info = json.dumps(
            {nid: r for nid, r in (available_results or {}).items()},
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""
原始计划执行失败，需要重新规划。

原始任务: {original_plan.task}
失败节点: {failed_node_id}
失败原因: {failure_reason}

已成功节点的结果:
{available_info}

请生成修正后的计划。策略：
1. 分析失败原因
2. 如果是因为任务描述不清，细化该节点的 description
3. 如果是因为能力不匹配，调整 required_capability
4. 如果需要拆分任务，拆分为多个子节点
5. 保持已成功节点的下游依赖关系

输出 JSON 格式的修正计划。
"""

        replan_result = await self.run(
            input=prompt,
            context={"role": "planner_replan"},
        )

        if not replan_result.success:
            raise RuntimeError(f"Planner 重新规划失败: {replan_result.error}")

        return self._parse_plan_response(replan_result.output)

    def _parse_plan_response(self, output: Any) -> PlanGraph:
        """解析 LLM 的 JSON 响应为 PlanGraph"""
        if isinstance(output, str):
            # 尝试从文本中提取 JSON
            import re
            json_match = re.search(r"\{[\s\S]*\}", output)
            if json_match:
                output = json_match.group()

        if isinstance(output, str):
            data = json.loads(output)
        elif isinstance(output, dict):
            data = output
        else:
            raise ValueError(f"无法解析 Planner 输出: {type(output)}")

        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        plan_graph = PlanGraph(
            id=plan_id,
            task=data.get("task", ""),
            plan_type=data.get("plan_type", "default"),
            planner_model=self.claude_config.model,
        )

        for node_data in data.get("nodes", []):
            node = PlanNode(
                id=node_data["id"],
                name=node_data["name"],
                node_type=NodeType.TASK,
                description=node_data["description"],
                required_capability=node_data.get("required_capability", "generic"),
                dependencies=node_data.get("dependencies", []),
                parallel_group=node_data.get("parallel_group"),
                condition=node_data.get("condition"),
                max_retries=node_data.get("max_retries", 3),
                timeout_seconds=node_data.get("timeout_seconds", 300),
            )
            plan_graph.add_node(node)

        return plan_graph
```

### 4.6 DynamicWorkflowBuilder — 动态工作流构建器

```python
"""src/workflows/dynamic_builder.py — DynamicWorkflowBuilder"""

from __future__ import annotations

from typing import Any, Callable, Awaitable, Optional
import logging

try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = None

from src.plan.graph import PlanGraph, PlanNode, NodeStatus, NodeType
from src.workflows.states import DynamicWorkflowState, create_dynamic_initial_state
from src.executors.registry import ExecutorRegistry
from src.verifiers.framework import VerifierFramework

logger = logging.getLogger(__name__)

# LangGraph 节点函数类型
DynamicNodeFunc = Callable[[DynamicWorkflowState], Awaitable[dict]]


class DynamicWorkflowBuilder:
    """
    动态工作流构建器。

    替代现有的 DevelopmentPipelineBuilder。
    从 PlanGraph 动态构建 LangGraph StateGraph。

    支持：
    - 并行节点（通过 Annotated 状态字段聚合）
    - 条件分支（conditional_edges）
    - 验证失败后的 replan 回路
    """

    def __init__(
        self,
        registry: ExecutorRegistry,
        verifier_framework: Optional[VerifierFramework] = None,
        checkpointer: Any = None,
        max_iterations: int = 10,
    ):
        self._registry = registry
        self._verifier = verifier_framework
        self._checkpointer = checkpointer or MemorySaver()
        self._max_iterations = max_iterations
        self._workflow: Optional[StateGraph] = None
        self._app: Any = None

    def build(self, plan_graph: PlanGraph) -> Any:
        """
        从 PlanGraph 构建 LangGraph StateGraph。

        Args:
            plan_graph: Planner 生成的执行计划

        Returns:
            编译后的 LangGraph 应用
        """
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("langgraph 未安装")

        self._workflow = StateGraph(DynamicWorkflowState)

        # 1. 为每个 PlanNode 创建 LangGraph 节点
        self._add_executor_nodes(plan_graph)

        # 2. 添加验证节点（如果配置了 Verifier）
        if self._verifier:
            self._add_verifier_nodes(plan_graph)

        # 3. 添加 replan 节点
        self._add_replan_node()

        # 4. 构建边（依赖关系）
        self._add_edges(plan_graph)

        # 5. 添加条件路由
        self._add_conditional_edges(plan_graph)

        # 6. 设置入口点
        entry_nodes = plan_graph.get_entry_nodes()
        if entry_nodes:
            self._workflow.set_entry_point(entry_nodes[0].id)

        # 7. 编译
        self._app = self._workflow.compile(
            checkpointer=self._checkpointer,
        )

        return self._app

    def _add_executor_nodes(self, plan_graph: PlanGraph) -> None:
        """为每个 PlanNode 创建 LangGraph 节点函数"""
        for node_id, plan_node in plan_graph.nodes.items():
            executor = self._registry.find_best(plan_node.required_capability)

            if executor is None:
                logger.warning(
                    f"未找到匹配 Executor 的节点: {node_id} "
                    f"(需要能力: {plan_node.required_capability.value})"
                )
                continue

            # 创建节点函数（闭包捕获 executor 和 plan_node）
            node_func = self._create_node_func(executor, plan_node)
            self._workflow.add_node(node_id, node_func)

    def _create_node_func(
        self,
        executor: Any,
        plan_node: PlanNode,
    ) -> DynamicNodeFunc:
        """创建单个节点的 LangGraph 函数"""

        async def node_func(state: DynamicWorkflowState) -> dict:
            """LangGraph 节点执行函数"""
            node_id = plan_node.id

            # 构建上下文
            context = {
                "project_path": state.get("project_path", "."),
                "upstream_results": self._get_upstream_results(state, node_id),
                "node_id": node_id,
                "plan_graph_id": state.get("plan_graph_id", ""),
            }

            # 执行 Executor
            result = await executor.execute(
                node_description=plan_node.description,
                context=context,
            )

            # 更新状态
            updates = {
                "current_node": node_id,
                "executor_results": {
                    **state.get("executor_results", {}),
                    node_id: result.to_dict(),
                },
                "iteration_count": state.get("iteration_count", 0) + 1,
                "messages": [{
                    "role": f"executor:{executor.executor_id}",
                    "content": f"节点 {node_id} 执行{'成功' if result.success else '失败'}",
                    "success": result.success,
                }],
            }

            # 如果配置了 Verifier，立即验证
            if self._verifier and result.success:
                vr = await self._verifier.verify(result, context)
                updates["verifier_results"] = {
                    **state.get("verifier_results", {}),
                    node_id: vr.to_dict(),
                }
                updates["verification_passed"] = vr.is_passed

            # 更新总成本
            if result.cost > 0:
                current_cost = state.get("total_cost", 0.0)
                updates["total_cost"] = current_cost + result.cost

            return updates

        return node_func

    def _add_verifier_nodes(self, plan_graph: PlanGraph) -> None:
        """添加独立的验证节点（可选）"""
        # 在 _create_node_func 中已内联验证，此方法保留用于扩展
        pass

    def _add_replan_node(self) -> None:
        """添加 replan 节点"""

        async def replan_node(state: DynamicWorkflowState) -> dict:
            return {
                "current_node": "__replan__",
                "needs_replan": True,
                "messages": [{
                    "role": "system",
                    "content": "触发重新规划",
                }],
            }

        self._workflow.add_node("__replan__", replan_node)

    def _add_edges(self, plan_graph: PlanGraph) -> None:
        """根据 PlanGraph 的依赖关系添加边"""
        for src_id, tgt_id in plan_graph.edges:
            if src_id in plan_graph.nodes and tgt_id in plan_graph.nodes:
                self._workflow.add_edge(src_id, tgt_id)

        # 添加 replan 回路
        self._workflow.add_edge("__replan__", "__start__")

    def _add_conditional_edges(self, plan_graph: PlanGraph) -> None:
        """添加条件边"""

        # 验证失败路由
        if self._verifier:
            def verify_router(state: DynamicWorkflowState) -> str:
                passed = state.get("verification_passed", True)
                iterations = state.get("iteration_count", 0)
                if iterations >= self._max_iterations:
                    return "__end__"
                if not passed:
                    return "__replan__"
                return "__continue__"

            # 为每个有验证的节点添加条件边
            for node_id in plan_graph.nodes:
                self._workflow.add_conditional_edges(
                    node_id,
                    verify_router,
                    {
                        "__continue__": self._get_next_node(plan_graph, node_id),
                        "__replan__": "__replan__",
                        "__end__": END,
                    },
                )

    def _get_next_node(
        self, plan_graph: PlanGraph, node_id: str
    ) -> Optional[str]:
        """获取节点的下一个节点（用于边路由）"""
        for src, tgt in plan_graph.edges:
            if src == node_id:
                return tgt
        return END

    def _get_upstream_results(
        self, state: DynamicWorkflowState, current_node: str
    ) -> dict:
        """获取上游节点的结果"""
        all_results = state.get("executor_results", {})
        return all_results

    def get_app(self) -> Any:
        """获取编译后的应用"""
        if self._app is None:
            raise RuntimeError("工作流尚未构建，请先调用 build()")
        return self._app


def create_dynamic_pipeline(
    plan_graph: PlanGraph,
    registry: ExecutorRegistry,
    verifier: Optional[VerifierFramework] = None,
    checkpoint_path: Optional[str] = None,
    max_iterations: int = 10,
) -> Any:
    """
    便捷函数：从 PlanGraph 创建并编译动态工作流。

    Args:
        plan_graph: 执行计划
        registry: Executor 注册中心
        verifier: 验证框架（可选）
        checkpoint_path: SQLite 检查点路径
        max_iterations: 最大迭代次数

    Returns:
        编译后的 LangGraph 应用
    """
    import os

    if checkpoint_path:
        os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
        try:
            from langgraph.checkpoint.sqlite.aio import SqliteSaver
            checkpointer = SqliteSaver.from_conn_string(checkpoint_path)
        except ImportError:
            checkpointer = MemorySaver()
    else:
        checkpointer = MemorySaver()

    builder = DynamicWorkflowBuilder(
        registry=registry,
        verifier_framework=verifier,
        checkpointer=checkpointer,
        max_iterations=max_iterations,
    )

    return builder.build(plan_graph)
```

### 4.7 验证规则库

```python
"""src/verifiers/rules/code_quality.py — 代码质量验证规则"""

from __future__ import annotations

from typing import Any

from src.verifiers.base import (
    BaseVerifier,
    VerificationResult,
    VerificationItem,
    VerificationStatus,
    VerificationDimension,
)
from src.executors.base import ExecutorResult


class CodeQualityVerifier(BaseVerifier):
    """
    代码质量验证器。

    验证维度：
    - lint: 代码静态分析（如 pycodestyle、eslint）
    - complexity: 代码复杂度（圈复杂度等）
    - style: 代码风格一致性
    """

    def __init__(self):
        super().__init__(verifier_id="code_quality", name="代码质量验证")

    async def verify(
        self,
        executor_result: ExecutorResult,
        context: dict[str, Any] = None,
    ) -> VerificationResult:
        context = context or {}
        result = VerificationResult(
            node_id=executor_result.node_id,
            executor_result=executor_result,
        )

        artifacts = executor_result.artifacts or {}
        files = artifacts.get("files", [])

        if not files:
            # 无文件产出物，跳过代码质量检查
            result.add_item(VerificationItem(
                rule_id="code-quality-files",
                dimension=VerificationDimension.CODE_QUALITY,
                status=VerificationStatus.SKIPPED,
                score=1.0,
                message="无文件产出，跳过代码质量检查",
            ))
            result.overall_status = VerificationStatus.SKIPPED
            result.overall_score = 1.0
            return result

        # 1. Lint 检查（简化实现：检查文件是否存在语法错误）
        lint_item = await self._check_lint(files, context)
        result.add_item(lint_item)

        # 2. 风格检查
        style_item = await self._check_style(files, context)
        result.add_item(style_item)

        return result

    async def _check_lint(
        self, files: list, context: dict
    ) -> VerificationItem:
        """执行 lint 检查"""
        # TODO: 实际集成 pycodestyle / eslint 等工具
        # 这里做简化检查
        error_count = 0
        warnings = []

        for f in files:
            path = f.get("path", "") if isinstance(f, dict) else str(f)
            # 简化: 检查文件是否可读取
            import os
            if not os.path.exists(path):
                error_count += 1
                warnings.append(f"文件不存在: {path}")

        if error_count > 0:
            return VerificationItem(
                rule_id="lint-file-exists",
                dimension=VerificationDimension.CODE_QUALITY,
                status=VerificationStatus.FAILED,
                score=0.0,
                message=f"{error_count} 个文件不存在",
                details={"warnings": warnings},
            )

        return VerificationItem(
            rule_id="lint-file-exists",
            dimension=VerificationDimension.CODE_QUALITY,
            status=VerificationStatus.PASSED,
            score=1.0,
            message="所有文件存在",
        )

    async def _check_style(
        self, files: list, context: dict
    ) -> VerificationItem:
        """执行风格检查"""
        # TODO: 实际集成 black / prettier 等
        return VerificationItem(
            rule_id="style-consistency",
            dimension=VerificationDimension.STYLE,
            status=VerificationStatus.PASSED,
            score=0.9,
            message="风格检查通过（简化实现）",
        )


"""src/verifiers/rules/security.py — 安全验证规则"""

from __future__ import annotations

from typing import Any

from src.verifiers.base import (
    BaseVerifier,
    VerificationResult,
    VerificationItem,
    VerificationStatus,
    VerificationDimension,
)
from src.executors.base import ExecutorResult


class SecurityVerifier(BaseVerifier):
    """
    安全验证器。

    验证维度：
    - sast: 静态应用安全测试
    - dependency: 依赖漏洞扫描
    - secrets: 硬编码密钥检测
    """

    # 常见危险模式
    DANGEROUS_PATTERNS = [
        "password\s*=\s*['\"]",
        "api_key\s*=\s*['\"]",
        "secret\s*=\s*['\"]",
        "token\s*=\s*['\"]",
    ]

    def __init__(self):
        super().__init__(verifier_id="security", name="安全验证")

    async def verify(
        self,
        executor_result: ExecutorResult,
        context: dict[str, Any] = None,
    ) -> VerificationResult:
        context = context or {}
        result = VerificationResult(
            node_id=executor_result.node_id,
            executor_result=executor_result,
        )

        artifacts = executor_result.artifacts or {}
        files = artifacts.get("files", [])

        # 1. 硬编码密钥检测
        secrets_item = await self._check_secrets(files, context)
        result.add_item(secrets_item)

        # 2. 依赖安全检查
        deps_item = await self._check_dependencies(context)
        result.add_item(deps_item)

        return result

    async def _check_secrets(
        self, files: list, context: dict
    ) -> VerificationItem:
        """检测硬编码密钥"""
        import re
        import os

        findings = []
        for f in files:
            path = f.get("path", "") if isinstance(f, dict) else str(f)
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r") as fh:
                    content = fh.read()
                for pattern in self.DANGEROUS_PATTERNS:
                    if re.search(pattern, content, re.IGNORECASE):
                        findings.append(f"{path}: 疑似硬编码密钥")
            except Exception:
                pass

        if findings:
            return VerificationItem(
                rule_id="secrets-detection",
                dimension=VerificationDimension.SECURITY,
                status=VerificationStatus.FAILED,
                score=0.0,
                message=f"发现 {len(findings)} 处疑似硬编码密钥",
                details={"findings": findings},
            )

        return VerificationItem(
            rule_id="secrets-detection",
            dimension=VerificationDimension.SECURITY,
            status=VerificationStatus.PASSED,
            score=1.0,
            message="未发现硬编码密钥",
        )

    async def _check_dependencies(
        self, context: dict
    ) -> VerificationItem:
        """依赖安全扫描"""
        # TODO: 集成 pip-audit / npm audit 等
        return VerificationItem(
            rule_id="dependency-scan",
            dimension=VerificationDimension.SECURITY,
            status=VerificationStatus.PASSED,
            score=0.8,
            message="依赖安全检查通过（简化实现）",
        )
```

### 4.8 DynamicWorkflowState — 扩展状态定义

```python
"""src/workflows/states.py — 扩展 WorkflowState"""

from __future__ import annotations

from typing import TypedDict, Annotated, Sequence, Optional
import operator
from datetime import datetime


class DynamicWorkflowState(TypedDict):
    """
    动态工作流全局状态。

    扩展原有的 WorkflowState，新增 PlanGraph 和 P/E/V 相关字段。
    """

    # === 继承自 WorkflowState 的字段 ===
    task: str
    project_path: str
    messages: Annotated[Sequence[dict], operator.add]
    current_stage: str
    iteration_count: int
    total_cost: float
    start_time: str
    end_time: str

    # === PlanGraph 相关 ===
    plan_graph_id: str
    """当前执行计划的 ID"""

    plan_graph_json: str
    """PlanGraph 的 JSON 序列化（用于持久化）"""

    plan_status: str
    """计划状态: draft / executing / completed / failed / replanning"""

    # === Executor 结果 ===
    executor_results: Annotated[dict, lambda a, b: {**a, **b}]
    """所有节点的执行结果映射: {node_id: ExecutorResult.to_dict()}"""

    current_node: str
    """当前正在执行的节点 ID"""

    # === Verifier 结果 ===
    verifier_results: Annotated[dict, lambda a, b: {**a, **b}]
    """所有节点的验证结果映射: {node_id: VerificationResult.to_dict()}"""

    verification_passed: bool
    """最近一次验证是否通过"""

    # === 控制流 ===
    needs_replan: bool
    """是否需要重新规划"""

    replan_reason: str
    """重新规划的原因"""

    completed_nodes: Annotated[list, operator.add]
    """已完成节点 ID 列表"""

    failed_nodes: Annotated[list, operator.add]
    """失败节点 ID 列表"""


def create_dynamic_initial_state(
    task: str,
    plan_graph,  # PlanGraph 实例
    project_path: str = ".",
) -> DynamicWorkflowState:
    """创建动态工作流初始状态"""
    return DynamicWorkflowState(
        task=task,
        project_path=project_path,
        messages=[],
        current_stage="planning",
        iteration_count=0,
        total_cost=0.0,
        start_time=datetime.now().isoformat(),
        end_time="",
        plan_graph_id=plan_graph.id,
        plan_graph_json=plan_graph.to_json(),
        plan_status="executing",
        executor_results={},
        current_node="",
        verifier_results={},
        verification_passed=True,
        needs_replan=False,
        replan_reason="",
        completed_nodes=[],
        failed_nodes=[],
    )


def merge_dynamic_state(
    old: DynamicWorkflowState,
    new: dict,
) -> DynamicWorkflowState:
    """合并动态工作流状态更新"""
    merged = dict(old)

    for key, value in new.items():
        if key == "messages":
            old_msgs = merged.get("messages", [])
            merged["messages"] = operator.add(old_msgs, value)
        elif key == "executor_results":
            old_results = merged.get("executor_results", {})
            merged["executor_results"] = {**old_results, **value}
        elif key == "verifier_results":
            old_results = merged.get("verifier_results", {})
            merged["verifier_results"] = {**old_results, **value}
        elif key == "completed_nodes":
            old_list = merged.get("completed_nodes", [])
            merged["completed_nodes"] = operator.add(old_list, value)
        elif key == "failed_nodes":
            old_list = merged.get("failed_nodes", [])
            merged["failed_nodes"] = operator.add(old_list, value)
        else:
            merged[key] = value

    return DynamicWorkflowState(**merged)
```

### 4.9 PlannerAgent — Orchestrator 集成

```python
"""src/core/orchestrator.py — PEVOrchestrator 扩展"""

from __future__ import annotations

from typing import Any, Optional
import asyncio

from src.core.orchestrator import BaseOrchestrator, OrchestratorConfig, OrchestrationMode
from src.core.agent import AgentResult
from src.plan.graph import PlanGraph, PlanNode, NodeStatus
from src.agents.planner import PlannerAgent
from src.executors.registry import ExecutorRegistry
from src.executors.base import AgentExecutor, ExecutorResult
from src.verifiers.framework import VerifierFramework
from src.workflows.dynamic_builder import DynamicWorkflowBuilder


class PEVOrchestrator(BaseOrchestrator):
    """
    P/E/V 编排器。

    这是 Phase 4 的顶层入口，协调整个 P/E/V 流程：
    1. Planner 生成 PlanGraph
    2. ExecutorRegistry 匹配 Executor
    3. DynamicWorkflowBuilder 构建 LangGraph
    4. 执行 + Verifier 验证
    5. 失败时触发 Replan
    """

    def __init__(
        self,
        config: OrchestratorConfig = None,
        planner: PlannerAgent = None,
        registry: ExecutorRegistry = None,
        verifier: VerifierFramework = None,
    ):
        super().__init__(config or OrchestratorConfig(
            mode=OrchestrationMode.HIERARCHICAL,
        ))
        self._planner = planner
        self._registry = registry or ExecutorRegistry()
        self._verifier = verifier or VerifierFramework()
        self._current_plan: Optional[PlanGraph] = None

    async def execute(self, task: str, context: dict = None) -> AgentResult:
        """
        执行完整 P/E/V 流程。

        1. 调用 Planner 生成 PlanGraph
        2. 注册 Executors
        3. 构建动态工作流
        4. 执行并验证
        5. 失败时 replan（最多 max_replan 次）

        Args:
            task: 用户任务描述
            context: 执行上下文

        Returns:
            AgentResult: 最终结果
        """
        context = context or {}
        max_replan = context.get("max_replan", 3)
        replan_count = 0

        # Step 1: 生成计划
        self._current_plan = await self._planner.create_plan(
            task=task,
            context=context,
        )

        # Step 2-4: 执行循环
        while replan_count <= max_replan:
            try:
                # 构建工作流
                builder = DynamicWorkflowBuilder(
                    registry=self._registry,
                    verifier_framework=self._verifier,
                    max_iterations=self.config.max_workers,
                )
                app = builder.build(self._current_plan)

                # 执行
                initial_state = create_dynamic_initial_state(
                    task=task,
                    plan_graph=self._current_plan,
                    project_path=context.get("project_path", "."),
                )

                result = await app.ainvoke(initial_state, config={
                    "configurable": {"thread_id": f"pev-{self._current_plan.id}"},
                })

                return AgentResult(
                    success=True,
                    output=result,
                    metadata={
                        "plan_id": self._current_plan.id,
                        "replan_count": replan_count,
                    },
                )

            except Exception as e:
                replan_count += 1
                if replan_count > max_replan:
                    return AgentResult(
                        success=False,
                        output=None,
                        error=f"超过最大重新规划次数 ({max_replan}): {e}",
                    )

                # 触发重新规划
                self._current_plan = await self._planner.replan(
                    original_plan=self._current_plan,
                    failed_node_id=context.get("failed_node", ""),
                    failure_reason=str(e),
                    available_results=context.get("available_results", {}),
                )

        return AgentResult(success=False, output=None, error="未知错误")
```

---

## 5. 工作流程

### 5.1 正常流程

```
Task (自然语言)
  │
  ▼
┌──────────────┐
│ 1. PLANNING  │  PlannerAgent.create_plan(task)
│              │  ──► 生成 PlanGraph (DAG)
└──────┬───────┘
       │ PlanGraph
       ▼
┌──────────────┐
│ 2. DISPATCH  │  DynamicWorkflowBuilder.build(plan)
│              │  ├── ExecutorRegistry.find_best() 匹配 Executor
│              │  ├── 创建 LangGraph StateGraph
│              │  └── 编译为 LangGraph app
└──────┬───────┘
       │ Compiled App
       ▼
┌──────────────┐
│ 3. EXECUTE   │  app.ainvoke(initial_state)
│              │  ├── 按拓扑顺序执行节点
│              │  ├── 并行组并发执行
│              │  └── 每个节点: Executor.execute()
└──────┬───────┘
       │ ExecutorResult
       ▼
┌──────────────┐
│ 4. VERIFY    │  VerifierFramework.verify(result)
│              │  ├── 代码质量检查
│              │  ├── 安全检查
│              │  └── 聚合评分
└──────┬───────┘
       │ VerificationResult (passed)
       ▼
┌──────────────┐
│ 5. COMPLETE  │  所有节点验证通过
│              │  汇总结果返回
└──────────────┘
```

### 5.2 异常流程 — 失败与 Replan

```
Executor 执行失败 / Verifier 验证失败
  │
  ▼
┌───────────────────────────────────┐
│ 检测失败                           │
│  - ExecutorResult.success = False  │
│  - VerificationResult.failed       │
└───────────────┬───────────────────┘
                │
                ▼
┌───────────────────────────────────┐
│ 判断是否达到最大重试/重规划次数     │
│  if retry_count < max_retries:     │
│     ──► 直接重试同一节点            │
│  elif replan_count < max_replan:   │
│     ──► 触发 Replan                │
│  else:                             │
│     ──► 标记整体失败                │
└───────────────┬───────────────────┘
                │
         ┌──────┴──────┐
         │             │
      重试            Replan
         │             │
         ▼             ▼
    原Executor    PlannerAgent.replan()
    .execute()    ──► 修正 PlanGraph
         │              │
         │              ▼
         │         重建 LangGraph
         │         ──► 继续执行
         │              │
         ▼              ▼
    ExecutorResult   新的 Executor 执行
```

### 5.3 并行执行

```
PlanGraph 中的并行组示例:

        ┌─────────┐
        │  N1: 需求│
        └────┬────┘
             │
        ┌────┴────┐
        │  N2: 设计│
        └────┬────┘
             │
     ┌───────┴───────┐
     │               │
┌────▼────┐    ┌────▼────┐
│ N3a:前端 │    │ N3b:后端 │  ← parallel_group = "development"
│ (Executor│    │ (Executor│
│  front)   │    │  back)   │
└────┬─────┘    └────┬─────┘
     │               │
     └───────┬───────┘
             │
        ┌────▼────┐
        │ N4: 集成 │
        └─────────┘
```

**LangGraph 并行执行机制**：
- LangGraph StateGraph 天然支持 DAG 的并行执行
- 同一层级的节点（无相互依赖）会自动并行
- 通过 `Annotated[..., operator.add]` 字段实现状态累加
- `executor_results` 和 `verifier_results` 使用 dict merge reducer

### 5.4 完整执行时序图

```
用户                PEVOrchestrator        PlannerAgent        ExecutorRegistry      LangGraph         Executor          Verifier
 │                       │                     │                     │                   │                  │                 │
 │── execute(task) ─────►│                     │                     │                   │                  │                 │
 │                       │── create_plan() ───►│                     │                   │                  │                 │
 │                       │                     │── LLM call ──► PlanGraph               │                  │                 │
 │                       │◄─ PlanGraph ────────┤                     │                   │                  │                 │
 │                       │                     │                     │                   │                  │                 │
 │                       │── build() ──────────────────────────────►│                   │                  │                 │
 │                       │  │                   │                     │── register() ────►│                  │                 │
 │                       │  │◄─ StateGraph ◄────┤                     │                   │                  │                 │
 │                       │                     │                     │                   │                  │                 │
 │                       │── ainvoke() ────────────────────────────►│── node_func() ────►│                  │                 │
 │                       │                     │                     │                   │── execute() ────►│                 │
 │                       │                     │                     │                   │                  │── Agent.run()   │
 │                       │                     │                     │                   │                  │◄─ AgentResult  │
 │                       │                     │                     │                   │◄─ ExecutorResult │                 │
 │                       │                     │                     │                   │                  │                 │
 │                       │                     │                     │                   │── verify() ──────────────────────►│
 │                       │                     │                     │                   │                  │◄─ VerifyResult │
 │                       │                     │                     │                   │                  │                 │
 │                       │◄─ FinalResult ◄─────┤                     │                   │                  │                 │
 │◄─ AgentResult ◄───────┤                     │                     │                   │                  │                 │
```

---

## 八、Verifier 规则体系统一说明

Verifier 规则定义在 Phase 4/5/7 中分别处于不同抽象层次，以下是三层规则的关系和转换路径：

### 8.1 三层规则架构

| 层次 | 来源 | 规则格式 | 作用域 |
|------|------|---------|--------|
| **L1: YAML 配置层** | Phase 5/6 配置文件 | `{name, check, severity, timeout}` | 工作流级别，声明式 |
| **L2: 代码级规则** | Phase 4 VerificationRule | `{rule_id, dimension, status, score, message}` | 单次执行级别，结构化 |
| **L3: 维度阈值层** | Phase 7 生产监控 | `{dimension, threshold}` | 全局聚合级别，评分门槛 |

### 8.2 转换流程

```
YAML 规则 (Phase 5 config)
    │
    ▼ ConfigurableWorkflowBuilder 加载
    │
    ▼ 为每条 YAML 规则创建对应的 VerificationRule
    │
VerificationRule (Phase 4)
    │
    ▼ VerifierFramework 执行 check 命令
    │
    ▼ 产生 VerificationItem 结果
    │
VerificationResult (聚合后的 score)
    │
    ▼ Phase 7 CostController/MetricsCollector 聚合
    │
维度阈值检查 (Phase 7)
    │
    ▼ score >= threshold ? pass : fail
    │
最终判定
```

### 8.3 实现映射

```python
def yaml_rule_to_verification_rule(yaml_rule: VerificationRule) -> dict:
    """将 Phase 5 YAML 规则转换为 VerifierFramework 可执行的规则"""
    return {
        "rule_id": f"yaml-{yaml_rule.name}",
        "dimension": _map_severity_to_dimension(yaml_rule.severity),
        "check_command": yaml_rule.check,
        "severity": yaml_rule.severity.value,
        "timeout": yaml_rule.timeout,
    }

def _map_severity_to_dimension(severity: SeverityLevel) -> str:
    """SeverityLevel → VerificationDimension 映射"""
    mapping = {
        SeverityLevel.INFO: "quality",
        SeverityLevel.WARNING: "quality",
        SeverityLevel.ERROR: "correctness",
        SeverityLevel.CRITICAL: "security",
    }
    return mapping.get(severity, "quality")
```

### 8.4 Phase 7 可观测性与现有 Hooks 的关系

Phase 1-3 已有 hooks 机制，Phase 7 新增的可观测性组件与 hooks 的关系：

| Phase 1-3 组件 | Phase 7 组件 | 关系 |
|---------------|-------------|------|
| `hooks(logging=True)` | `StructuredLogger` | **替代** — StructuredLogger 提供更完整的日志体系 |
| `hooks(cost_control=True)` | `CostController` | **增强** — CostController 复用 hooks 的预算检查，新增实时追踪 |
| `hooks(safety=True)` | `CircuitBreaker` | **互补** — hooks 控制文件/网络权限，CircuitBreaker 控制 API 弹性 |
| 无 | `MetricsCollector` | **新增** — 无对应组件 |
| 无 | `Tracer` | **新增** — 无对应组件 |

**集成策略**：Phase 7 的可观测性组件通过 Phase 4 的 `HookManager` 接入工作流，
hooks 触发时同步写入 MetricsCollector 和 Tracer，不改变现有 hooks 的调用方式。

---

## 九、与现有代码的集成

### 6.1 现有 Agent → Executor 适配

**核心策略**: 使用 `AgentExecutor` 适配器模式，零修改复用现有 6 个 Agent。

```python
# 适配示例：将现有 Agent 注册为 Executor

from src.agents.developer import create_developer_agent
from src.agents.reviewer import create_reviewer_agent
from src.agents.tester import create_tester_agent
from src.executors.base import AgentExecutor
from src.executors.registry import ExecutorRegistry
from src.plan.graph import ExecutorCapability, CapabilityLevel

registry = ExecutorRegistry()

# 1. 创建现有 Agent 实例
dev_agent = create_developer_agent(model="qwen3.6-plus")
reviewer_agent = create_reviewer_agent(model="qwen3.6-plus")
tester_agent = create_tester_agent(model="qwen3.6-plus")

# 2. 包装为 Executor
dev_executor = AgentExecutor(
    agent=dev_agent,
    capabilities=[
        ExecutorCapability(
            capability=ExecutorCapability.CODE_DEVELOPMENT,
            level=CapabilityLevel.STANDARD,
            supported_languages=["python", "javascript"],
        ),
    ],
)

reviewer_executor = AgentExecutor(
    agent=reviewer_agent,
    capabilities=[
        ExecutorCapability(
            capability=ExecutorCapability.CODE_REVIEW,
            level=CapabilityLevel.EXPERT,
        ),
    ],
)

tester_executor = AgentExecutor(
    agent=tester_agent,
    capabilities=[
        ExecutorCapability(
            capability=ExecutorCapability.TESTING,
            level=CapabilityLevel.STANDARD,
        ),
    ],
)

# 3. 注册到 Registry
registry.register(dev_executor)
registry.register(reviewer_executor)
registry.register(tester_executor)
```

**现有 6 个 Agent 的能力映射表**：

| 现有 Agent | 类名 | 映射 ExecutorCapability | 能力等级 |
|-----------|------|------------------------|---------|
| RequirementsAgent | `requirements.py` | `REQUIREMENTS_ANALYSIS` | STANDARD |
| DesignerAgent | `designer.py` | `TECHNICAL_DESIGN` | STANDARD |
| DeveloperAgent | `developer.py` | `CODE_DEVELOPMENT` | STANDARD |
| ReviewerAgent | `reviewer.py` | `CODE_REVIEW` | EXPERT |
| TesterAgent | `tester.py` | `TESTING` | STANDARD |
| FixerAgent | `fixer.py` | `BUG_FIXING` | STANDARD |

### 6.2 向后兼容方案

```python
# src/workflows/builder.py 添加 deprecation 标记

import warnings

class DevelopmentPipelineBuilder:
    """
    开发流水线构建器。

    .. deprecated:: 0.4.0
        使用 DynamicWorkflowBuilder + PlannerAgent 替代。
        此类保留用于向后兼容，将在 Phase 5 中移除。
    """

    def __init__(self, config: PipelineConfig = None):
        warnings.warn(
            "DevelopmentPipelineBuilder 已废弃，请使用 DynamicWorkflowBuilder",
            DeprecationWarning,
            stacklevel=2,
        )
        # ... 原有实现保持不变
```

### 6.3 CLI 入口扩展

```python
# src/cli/main.py 扩展新的命令

import argparse
from src.agents.planner import create_planner_agent
from src.executors.registry import ExecutorRegistry
from src.executors.base import AgentExecutor
from src.verifiers.framework import VerifierFramework
from src.verifiers.rules.code_quality import CodeQualityVerifier
from src.verifiers.rules.security import SecurityVerifier
from src.workflows.dynamic_builder import create_dynamic_pipeline


async def cmd_run_dynamic(task: str, project_path: str = "."):
    """新的动态执行命令"""
    # 1. 创建 Planner
    planner = create_planner_agent(model="qwen3.6-plus")

    # 2. 创建 Registry 并注册 Executor
    registry = ExecutorRegistry()
    registry.register(create_dev_executor())
    registry.register(create_reviewer_executor())
    registry.register(create_tester_executor())

    # 3. 创建 Verifier
    verifier = VerifierFramework()
    verifier.register_verifier(CodeQualityVerifier())
    verifier.register_verifier(SecurityVerifier())

    # 4. 生成计划
    plan = await planner.create_plan(task, {"project_path": project_path})
    print(plan.visualize_ascii())

    # 5. 构建并执行
    app = create_dynamic_pipeline(
        plan_graph=plan,
        registry=registry,
        verifier=verifier,
        checkpoint_path="./checkpoints/dynamic.db",
    )

    result = await app.ainvoke(
        create_dynamic_initial_state(task, plan, project_path),
        config={"configurable": {"thread_id": f"pev-{plan.id}"}},
    )
    return result
```

---

## 7. 文件变更清单

### 7.1 新增文件

| 文件路径 | 描述 | 预估行数 |
|---------|------|---------|
| `src/plan/__init__.py` | Plan 模块入口 | 5 |
| `src/plan/graph.py` | PlanNode, PlanGraph 数据模型 | 250 |
| `src/agents/planner.py` | PlannerAgent 实现 | 180 |
| `src/executors/__init__.py` | Executors 模块入口 | 5 |
| `src/executors/base.py` | BaseExecutor, AgentExecutor, ExecutorResult | 200 |
| `src/executors/registry.py` | ExecutorRegistry | 120 |
| `src/verifiers/__init__.py` | Verifiers 模块入口 | 5 |
| `src/verifiers/base.py` | BaseVerifier, VerificationResult | 80 |
| `src/verifiers/framework.py` | VerifierFramework | 150 |
| `src/verifiers/rules/__init__.py` | 规则库入口 | 5 |
| `src/verifiers/rules/code_quality.py` | 代码质量验证规则 | 100 |
| `src/verifiers/rules/security.py` | 安全验证规则 | 100 |
| `src/workflows/dynamic_builder.py` | DynamicWorkflowBuilder | 250 |
| `src/core/orchestrator_pev.py` | PEVOrchestrator | 150 |
| `tests/test_plan_graph.py` | PlanGraph 单元测试 | 150 |
| `tests/test_executor_registry.py` | ExecutorRegistry 单元测试 | 120 |
| `tests/test_verifier_framework.py` | VerifierFramework 单元测试 | 120 |
| `tests/test_dynamic_builder.py` | DynamicWorkflowBuilder 集成测试 | 150 |
| `tests/test_pev_integration.py` | P/E/V 端到端集成测试 | 200 |

**总计**: 19 个新文件，约 2,245 行代码

### 7.2 修改文件

| 文件路径 | 修改内容 | 影响范围 |
|---------|---------|---------|
| `src/workflows/states.py` | 添加 DynamicWorkflowState 及辅助函数 | 向后兼容（新增类型，不修改原有） |
| `src/workflows/builder.py` | 添加 `@deprecated` 警告 | 仅添加警告，不改逻辑 |
| `src/cli/main.py` | 添加 `run-dynamic` 子命令 | 新增功能，不影响现有命令 |
| `src/core/orchestrator.py` | 添加 PEVOrchestrator 类 | 新增类，不影响 BaseOrchestrator |
| `src/agents/__init__.py` | 导出 PlannerAgent | 新增导出 |

### 7.3 目录结构变更（Phase 4 完成后）

```
src/
├── core/
│   ├── agent.py
│   ├── state.py
│   ├── workflow.py
│   ├── orchestrator.py
│   ├── orchestrator_pev.py      # [新增] PEVOrchestrator
│   └── tool.py
├── claude/
│   ├── wrapper.py
│   ├── hooks.py
│   └── tools.py
├── plan/                         # [新增] 规划模块
│   ├── __init__.py
│   └── graph.py                  # PlanNode, PlanGraph
├── agents/
│   ├── __init__.py               # [修改] 添加 PlannerAgent 导出
│   ├── requirements.py
│   ├── designer.py
│   ├── developer.py
│   ├── reviewer.py
│   ├── tester.py
│   ├── fixer.py
│   └── planner.py                # [新增] PlannerAgent
├── executors/                    # [新增] 执行模块
│   ├── __init__.py
│   ├── base.py                   # BaseExecutor, AgentExecutor
│   └── registry.py               # ExecutorRegistry
├── verifiers/                    # [新增] 验证模块
│   ├── __init__.py
│   ├── base.py                   # BaseVerifier
│   ├── framework.py              # VerifierFramework
│   └── rules/
│       ├── __init__.py
│       ├── code_quality.py       # CodeQualityVerifier
│       └── security.py           # SecurityVerifier
├── workflows/
│   ├── __init__.py
│   ├── states.py                 # [修改] 添加 DynamicWorkflowState
│   ├── builder.py                # [修改] 添加 deprecated 警告
│   ├── runner.py
│   └── dynamic_builder.py        # [新增] DynamicWorkflowBuilder
└── cli/
    ├── __init__.py
    └── main.py                   # [修改] 添加 run-dynamic 命令

tests/
├── test_plan_graph.py            # [新增]
├── test_executor_registry.py     # [新增]
├── test_verifier_framework.py    # [新增]
├── test_dynamic_builder.py       # [新增]
└── test_pev_integration.py       # [新增]
```

---

## 8. 测试策略

### 8.1 单元测试

| 测试文件 | 测试目标 | 关键测试用例 |
|---------|---------|-------------|
| `test_plan_graph.py` | PlanGraph | 节点增删、拓扑排序、并行组检测、环检测、序列化/反序列化 |
| `test_executor_registry.py` | ExecutorRegistry | 注册/注销、能力匹配、负载均衡、降级策略 |
| `test_verifier_framework.py` | VerifierFramework | 规则注册、自定义规则、评分聚合、阈值判定 |
| `test_agent_executor.py` | AgentExecutor | Agent 适配转换、错误处理、产物提取 |

**示例：PlanGraph 拓扑排序测试**

```python
import pytest
from src.plan.graph import PlanGraph, PlanNode, NodeType, NodeStatus


class TestPlanGraph:
    def test_topological_sort_linear(self):
        """线性依赖: A -> B -> C"""
        graph = PlanGraph(id="test-1", task="test")
        graph.add_node(PlanNode(id="A", name="A"))
        graph.add_node(PlanNode(id="B", name="B", dependencies=["A"]))
        graph.add_node(PlanNode(id="C", name="C", dependencies=["B"]))

        order = graph.topological_sort()
        assert order.index("A") < order.index("B") < order.index("C")

    def test_topological_sort_diamond(self):
        """菱形依赖: A -> B,C -> D"""
        graph = PlanGraph(id="test-2", task="test")
        graph.add_node(PlanNode(id="A", name="A"))
        graph.add_node(PlanNode(id="B", name="B", dependencies=["A"]))
        graph.add_node(PlanNode(id="C", name="C", dependencies=["A"]))
        graph.add_node(PlanNode(id="D", name="D", dependencies=["B", "C"]))

        order = graph.topological_sort()
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")

    def test_cycle_detection(self):
        """环检测: A -> B -> C -> A"""
        graph = PlanGraph(id="test-3", task="test")
        graph.add_node(PlanNode(id="A", name="A", dependencies=["C"]))
        graph.add_node(PlanNode(id="B", name="B", dependencies=["A"]))
        graph.add_node(PlanNode(id="C", name="C", dependencies=["B"]))

        with pytest.raises(ValueError, match="环"):
            graph.topological_sort()

    def test_get_ready_nodes(self):
        """获取可执行节点"""
        graph = PlanGraph(id="test-4", task="test")
        graph.add_node(PlanNode(id="A", name="A"))
        graph.add_node(PlanNode(id="B", name="B", dependencies=["A"]))
        graph.add_node(PlanNode(id="C", name="C", dependencies=["A"]))

        ready = graph.get_ready_nodes(set())
        assert len(ready) == 1
        assert ready[0].id == "A"

        ready = graph.get_ready_nodes({"A"})
        assert len(ready) == 2
        assert {n.id for n in ready} == {"B", "C"}

    def test_serialization_roundtrip(self):
        """序列化/反序列化一致性"""
        graph = PlanGraph(id="test-5", task="test task")
        graph.add_node(PlanNode(
            id="A", name="A", description="Test node",
            required_capability=ExecutorCapability.CODE_DEVELOPMENT,
            parallel_group="group1",
        ))

        json_str = graph.to_json()
        restored = PlanGraph.from_json(json_str)

        assert restored.id == graph.id
        assert "A" in restored.nodes
        assert restored.nodes["A"].parallel_group == "group1"
```

### 8.2 集成测试

| 测试文件 | 测试场景 |
|---------|---------|
| `test_dynamic_builder.py` | PlanGraph → LangGraph 转换正确性、节点函数执行 |
| `test_pev_integration.py` | 完整 P/E/V 流程、replan 触发、并行执行 |

**集成测试关键场景**：

```python
class TestPEVIntegration:
    """P/E/V 端到端集成测试"""

    @pytest.mark.asyncio
    async def test_simple_plan_execution(self):
        """简单计划: 单节点执行"""
        # 1. 创建简单 PlanGraph
        graph = PlanGraph(id="simple", task="创建文件")
        graph.add_node(PlanNode(
            id="create", name="创建文件",
            description="创建一个 hello.py 文件",
            required_capability=ExecutorCapability.CODE_DEVELOPMENT,
        ))

        # 2. 注册 Executor
        registry = ExecutorRegistry()
        registry.register(create_dev_executor())

        # 3. 构建工作流
        builder = DynamicWorkflowBuilder(registry=registry)
        app = builder.build(graph)

        # 4. 执行
        result = await app.ainvoke(
            create_dynamic_initial_state("创建文件", graph),
            config={"configurable": {"thread_id": "test-simple"}},
        )

        assert result["executor_results"]["create"]["success"] is True

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        """并行节点执行"""
        graph = PlanGraph(id="parallel", task="并行开发")
        graph.add_node(PlanNode(id="design", name="设计"))
        graph.add_node(PlanNode(
            id="frontend", name="前端开发",
            dependencies=["design"], parallel_group="dev",
        ))
        graph.add_node(PlanNode(
            id="backend", name="后端开发",
            dependencies=["design"], parallel_group="dev",
        ))
        graph.add_node(PlanNode(
            id="integrate", name="集成",
            dependencies=["frontend", "backend"],
        ))

        # 验证拓扑排序正确反映并行关系
        order = graph.topological_sort()
        assert order.index("design") < order.index("frontend")
        assert order.index("design") < order.index("backend")
        # frontend 和 backend 在同一层级，可并行

    @pytest.mark.asyncio
    async def test_replan_on_failure(self):
        """执行失败触发 replan"""
        # 测试 replan 逻辑
        pass
```

### 8.3 测试覆盖目标

| 模块 | 目标覆盖率 |
|------|-----------|
| `src/plan/graph.py` | 90% |
| `src/executors/base.py` | 85% |
| `src/executors/registry.py` | 90% |
| `src/verifiers/base.py` | 85% |
| `src/verifiers/framework.py` | 90% |
| `src/workflows/dynamic_builder.py` | 80% |
| `src/agents/planner.py` | 60% (LLM 调用难以 mock) |

---

## 9. 实施步骤

### Step 1: 数据模型层（PlanGraph）

**目标**: 实现 PlanNode、PlanGraph 数据结构，完成单元测试

**文件**:
- `src/plan/__init__.py`
- `src/plan/graph.py`

**验收标准**:
- PlanNode 序列化/反序列化正确
- PlanGraph 拓扑排序、环检测、并行组检测全部通过
- 至少 90% 单元测试覆盖率

**预估工作量**: 0.5 天

---

### Step 2: Executor 抽象与注册中心

**目标**: 实现 BaseExecutor、AgentExecutor 适配器、ExecutorRegistry

**文件**:
- `src/executors/__init__.py`
- `src/executors/base.py`
- `src/executors/registry.py`

**验收标准**:
- AgentExecutor 能正确包装现有 Agent 并返回 ExecutorResult
- ExecutorRegistry 能力匹配算法正确
- 至少 85% 单元测试覆盖率

**预估工作量**: 1 天

---

### Step 3: Verifier 框架与规则库

**目标**: 实现 BaseVerifier、VerifierFramework、基础验证规则

**文件**:
- `src/verifiers/__init__.py`
- `src/verifiers/base.py`
- `src/verifiers/framework.py`
- `src/verifiers/rules/code_quality.py`
- `src/verifiers/rules/security.py`

**验收标准**:
- VerifierFramework 正确聚合多规则结果
- 维度评分和阈值判定正确
- 至少 85% 单元测试覆盖率

**预估工作量**: 1 天

---

### Step 4: PlannerAgent

**目标**: 实现 PlannerAgent，能够生成合法的 PlanGraph

**文件**:
- `src/agents/planner.py`
- `src/agents/__init__.py` (修改)

**验收标准**:
- PlannerAgent 能解析 LLM 输出为 PlanGraph
- 生成的 PlanGraph 通过拓扑排序（无环）
- replan 功能正常

**预估工作量**: 1.5 天

---

### Step 5: DynamicWorkflowBuilder

**目标**: 实现从 PlanGraph 到 LangGraph StateGraph 的动态构建

**文件**:
- `src/workflows/dynamic_builder.py`
- `src/workflows/states.py` (修改，添加 DynamicWorkflowState)

**验收标准**:
- 正确将 PlanNode 转换为 LangGraph 节点函数
- 并行组正确映射为 LangGraph 并行执行
- 条件分支和 replan 回路正确构建
- 编译后的 app 可正常执行

**预估工作量**: 2 天

---

### Step 6: 集成与 CLI 扩展

**目标**: 实现 PEVOrchestrator，扩展 CLI，完成端到端测试

**文件**:
- `src/core/orchestrator_pev.py`
- `src/cli/main.py` (修改)
- `tests/test_pev_integration.py`

**验收标准**:
- 完整 P/E/V 流程端到端可运行
- CLI `run-dynamic` 命令可用
- 向后兼容：原有 `run` 命令不受影响
- 至少一个真实任务的完整执行通过

**预估工作量**: 1.5 天

---

**总预估工作量**: ~7.5 天

---

## 10. 风险与缓解

### 10.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **LLM 生成的 PlanGraph 含环** | 拓扑排序失败，工作流无法执行 | 中 | 1. 在 Planner 提示词中强调无环约束<br>2. PlanGraph.add_node 时检测环<br>3. 拓扑排序失败时自动触发 replan |
| **LLM 生成的 JSON 格式错误** | PlanGraph 解析失败 | 中 | 1. 使用 JSON schema 验证<br>2. 添加重试机制（最多 3 次）<br>3. 降级为默认线性计划 |
| **并行执行的竞态条件** | 状态不一致 | 低 | 1. 使用 LangGraph 的 Annotated reducer<br>2. executor_results 使用 dict merge<br>3. 关键状态操作加锁 |
| **Executor 匹配失败** | 节点无法执行 | 低 | 1. GENERIC 能力兜底<br>2. 明确错误提示用户注册新 Executor<br>3. 自动扩展 Executor 池 |
| **Verifier 误判** | 正常结果被判失败 | 中 | 1. 阈值可配置<br>2. WARNING 状态不阻止执行<br>3. 支持人工覆盖验证结果 |
| **LangGraph 版本不兼容** | StateGraph 构建失败 | 低 | 1. 锁定 langgraph 版本<br>2. 提供兼容层<br>3. 集成测试覆盖多版本 |
| **Planner 规划质量不稳定** | 生成的计划效率低下 | 中 | 1. 提供计划模板（针对常见任务类型）<br>2. 支持人工审核/修正计划<br>3. 基于历史执行数据优化 prompt |

### 10.2 架构风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **三层耦合度过高** | 难以独立替换某一层 | 低 | 1. 严格通过接口通信<br>2. 接口使用 Protocol/ABC<br>3. 每层独立测试 |
| **状态爆炸** | DynamicWorkflowState 字段过多 | 低 | 1. 使用 TypedDict 提供类型提示<br>2. 序列化时压缩大字段<br>3. 按需加载上游结果 |
| **Replan 死循环** | Planner 不断生成无法执行的计划 | 中 | 1. 设置 max_replan 上限<br>2. 检测计划相似度（避免重复）<br>3. 最终降级为手动模式 |

### 10.3 实施风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **向后兼容破坏** | 现有用户工作流失效 | 低 | 1. DevelopmentPipelineBuilder 保留<br>2. 添加 deprecation warning<br>3. 集成测试覆盖两种模式 |
| **LLM 成本激增** | Planner 每次执行都消耗 token | 中 | 1. 缓存相似任务的计划<br>2. 使用更快的模型做规划<br>3. 计划持久化复用 |

### 10.4 性能考虑

```
组件              延迟预估           优化方向
──────────────    ────────────────   ─────────────────────────
Planner.plan()    3-10s (LLM)       计划缓存、流式输出
Executor.execute  5-60s (LLM+工具)  并发执行、超时控制
Verifier.verify   0.1-2s (本地)     并行验证规则、增量检查
Workflow build    0.5-1s (LangGraph) 节点缓存、增量编译
```

---

## 附录

### A. PlanGraph 与 LangGraph 字段映射

| PlanGraph 概念 | LangGraph 概念 | 实现方式 |
|---------------|---------------|---------|
| PlanNode | StateGraph node | `workflow.add_node(node_id, node_func)` |
| dependency edge | StateGraph edge | `workflow.add_edge(src, tgt)` |
| parallel_group | 同层级并行节点 | 同一拓扑层级的节点自动并行 |
| condition | conditional_edges | `workflow.add_conditional_edges()` |
| entry point | set_entry_point | `workflow.set_entry_point(entry_id)` |
| terminal | END | 边的目标为 `END` |
| replan | 条件回路 | `add_edge(replan_node, entry)` |

### B. 迁移指南：从 DevelopmentPipelineBuilder 到 DynamicWorkflowBuilder

```python
# ── 旧方式 (Phase 1-3) ──
from src.workflows.builder import create_dev_pipeline

builder = create_dev_pipeline(
    api_key=...,
    enable_human_review=True,
)
app = builder.build()
result = await app.ainvoke(initial_state, config=...)

# ── 新方式 (Phase 4) ──
from src.agents.planner import create_planner_agent
from src.executors.registry import ExecutorRegistry
from src.executors.base import AgentExecutor
from src.plan.graph import ExecutorCapability
from src.verifiers.framework import VerifierFramework
from src.workflows.dynamic_builder import create_dynamic_pipeline

# 1. 创建 Planner
planner = create_planner_agent()

# 2. 生成计划
plan = await planner.create_plan("用户任务描述")

# 3. 注册 Executor
registry = ExecutorRegistry()
registry.register(AgentExecutor(
    agent=create_developer_agent(),
    capabilities=[ExecutorCapability(capability=ExecutorCapability.CODE_DEVELOPMENT)],
))
# ... 注册其他 Executor

# 4. 创建 Verifier
verifier = VerifierFramework()
verifier.register_verifier(CodeQualityVerifier())

# 5. 构建并执行
app = create_dynamic_pipeline(
    plan_graph=plan,
    registry=registry,
    verifier=verifier,
)
result = await app.ainvoke(
    create_dynamic_initial_state("用户任务", plan),
    config={"configurable": {"thread_id": f"pev-{plan.id}"}},
)
```

### C. 关键设计决策记录 (ADR)

| # | 决策 | 理由 | 替代方案 |
|---|------|------|---------|
| 1 | PlanGraph 使用纯 Python dataclass 而非 networkx | 减少依赖，足够满足 DAG 操作需求 | networkx 提供更丰富的图算法 |
| 2 | Executor 通过 Adapter 复用现有 Agent | 保护已有投资，零成本迁移 | 重写所有 Executor（工作量大） |
| 3 | Verifier 独立于 Executor | 关注点分离，可替换验证策略 | 在 Executor 内嵌验证逻辑（耦合度高） |
| 4 | 使用 LangGraph StateGraph 作为执行引擎 | 复用已有 checkpointer 和中断机制 | 自建 DAG 执行引擎（重复造轮子） |
| 5 | Planner 使用 LLM 而非规则引擎 | 灵活适应各种任务类型 | 基于模板的规则引擎（不够灵活） |
