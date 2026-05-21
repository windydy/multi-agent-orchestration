"""
Phase 5: 配置 Schema — Pydantic v2 数据模型

src/config/schema.py
"""

from enum import Enum
from typing import Any, Optional
import os
import re

from pydantic import BaseModel, Field, model_validator, ConfigDict


class SeverityLevel(str, Enum):
    """验证规则严重级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PlannerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    model: str = "qwen3.6-plus"
    max_plan_depth: int = 5
    allow_parallel: bool = True
    auto_replan: bool = True


class ExecutorDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = "qwen3.6-plus"
    max_iterations: int = 10
    timeout: int = 300
    retry: int = 2
    tools: list[str] = Field(default_factory=list)


class ExecutorConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: Optional[str] = None
    max_iterations: Optional[int] = None
    timeout: Optional[int] = None
    retry: Optional[int] = None
    tools: Optional[list[str]] = None
    parallel_instances: int = 1
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None

    def merge_with_defaults(self, defaults: ExecutorDefaults) -> "ExecutorConfig":
        return ExecutorConfig(
            model=self.model or defaults.model,
            max_iterations=self.max_iterations or defaults.max_iterations,
            timeout=self.timeout or defaults.timeout,
            retry=self.retry or defaults.retry,
            tools=self.tools if self.tools is not None else defaults.tools,
            parallel_instances=self.parallel_instances,
            system_prompt=self.system_prompt,
            temperature=self.temperature,
        )


class VerificationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    check: str
    severity: SeverityLevel = SeverityLevel.WARNING
    timeout: int = 60


class VerifierConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    rules: list[VerificationRule] = Field(default_factory=list)


class FlowNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: str
    label: str
    timeout: int = 300
    retry: int = 2
    depends_on: list[str] = Field(default_factory=list)
    parallel: bool = False
    verifiers: list[str] = Field(default_factory=list)
    condition: Optional[str] = None


class FlowEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    condition: Optional[str] = None


class FlowTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry_point: str
    nodes: list[FlowNode]
    edges: list[FlowEdge]


class HumanReviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    nodes: list[str] = Field(default_factory=list)
    auto_approve_after: int = 300


class CostControlConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    warning_threshold: float = 5.0
    limit_threshold: float = 10.0
    stop_threshold: float = 20.0


class CheckpointConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    path: str = "./checkpoints/${WORKFLOW_NAME}.db"
    interval: int = 60


class LoggingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str  # "file" | "console" | "webhook"
    path: Optional[str] = None
    url: Optional[str] = None


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: str = "INFO"
    format: str = "structured"  # "structured" | "text"
    output: list[LoggingOutput] = Field(
        default_factory=lambda: [LoggingOutput(type="console")]
    )


class WorkflowConfig(BaseModel):
    """工作流配置根对象"""
    model_config = ConfigDict(extra="forbid")

    schema_: Optional[str] = Field(None, alias="$schema")
    version: str = "1.0"
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None

    planner: PlannerConfig = Field(default_factory=PlannerConfig)
    executors: dict[str, ExecutorConfig]
    defaults: Optional[ExecutorDefaults] = Field(default_factory=ExecutorDefaults)
    verifiers: dict[str, VerifierConfig] = Field(default_factory=dict)
    flow_template: FlowTemplate
    human_review: HumanReviewConfig = Field(default_factory=HumanReviewConfig)
    cost_control: CostControlConfig = Field(default_factory=CostControlConfig)
    checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    vars: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_flow(self) -> "WorkflowConfig":
        """验证流程图无环且 entry_point 存在"""
        v = self.flow_template
        node_ids = {n.id for n in v.nodes}

        # 检查 entry_point 存在
        if v.entry_point not in node_ids:
            raise ValueError(
                f"entry_point '{v.entry_point}' 不在节点列表中"
            )

        # 检查依赖存在
        for node in v.nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    raise ValueError(
                        f"节点 '{node.id}' 依赖不存在的节点 '{dep}'"
                    )

        # 检查是否有环
        if self._has_cycle(v):
            raise ValueError("流程图中检测到循环依赖")

        # 验证名称
        if not self.name or not self.name.replace("-", "").replace("_", "").isalnum():
            raise ValueError("name 只能包含字母、数字、横线和下划线")

        return self

    @staticmethod
    def _has_cycle(template: FlowTemplate) -> bool:
        """使用 DFS 检测有向图中的环"""
        adj: dict[str, list[str]] = {n.id: [] for n in template.nodes}
        for node in template.nodes:
            for dep in node.depends_on:
                if dep in adj:
                    adj[dep].append(node.id)

        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            for neighbor in adj.get(node_id, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node_id)
            return False

        for node_id in adj:
            if node_id not in visited:
                if dfs(node_id):
                    return True
        return False

    def resolve_vars(self) -> "WorkflowConfig":
        """解析配置中的 ${VAR} 引用"""
        def resolve_value(value: Any) -> Any:
            if isinstance(value, str):
                pattern = r"\$\{([^}]+)\}"
                def replace(match: re.Match) -> str:
                    var_expr = match.group(1)
                    if ":-" in var_expr:
                        var_name, default = var_expr.split(":-", 1)
                        return os.environ.get(var_name, default)
                    var_name = var_expr
                    return os.environ.get(var_name, match.group(0))
                return re.sub(pattern, replace, value)
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(v) for v in value]
            return value

        data = self.model_dump(by_alias=True)
        resolved = resolve_value(data)
        return WorkflowConfig(**resolved)

    def merge_executor_defaults(self) -> "WorkflowConfig":
        """将 defaults 合并到每个 executor"""
        defaults = self.defaults or ExecutorDefaults()
        executors = {}
        for name, cfg in self.executors.items():
            executors[name] = cfg.merge_with_defaults(defaults)

        data = self.model_dump(by_alias=True)
        data["executors"] = {name: cfg.model_dump() for name, cfg in executors.items()}
        return WorkflowConfig(**data)
