# Phase 5: 配置化编排 - 详细技术设计

> 版本: 1.0
> 日期: 2026-05-20
> 状态: 设计稿

## 一、概述

### 1.1 目标

通过 YAML 配置文件定义工作流，无需修改代码即可调整流程。用户只需编写配置文件，系统自动构建 LangGraph 工作流并执行。

### 1.2 与 Phase 4 的关系

| 层次 | Phase 4 | Phase 5 |
|------|---------|---------|
| 编排 | DynamicWorkflowBuilder 从 PlanGraph 动态构建 | ConfigurableWorkflowBuilder 从 YAML 配置构建 |
| 灵活性 | 运行时生成 PlanGraph | 预定义配置 + 运行时覆盖 |
| 使用方式 | 编程 API | 配置文件 + CLI |
| 关系 | 提供底层构建能力 | 在 Phase 4 之上提供配置层 |

### 1.3 核心价值

- **零代码修改**: 添加新流程只需写 YAML
- **版本控制**: 配置文件纳入 Git 管理
- **可复用**: 模板继承和组合
- **可验证**: Schema 校验防止配置错误

---

## 二、配置 Schema 设计

### 2.1 完整 YAML 结构

```yaml
# config/workflows/software-development.yaml
$schema: "https://example.com/workflow-schema-v1.json"  # 可选
version: "1.0"

# 工作流元信息
name: software-development
display_name: "标准软件开发流水线"
description: "需求分析 → 技术设计 → 开发 → 审查 → 测试"

# Planner 配置
planner:
  enabled: true
  model: qwen3.6-plus
  max_plan_depth: 5
  allow_parallel: true
  auto_replan: true  # 失败时自动重新规划

# Executor 配置
executors:
  # 全局默认
  defaults:
    model: qwen3.6-plus
    max_iterations: 10
    timeout: 300
    retry: 2
  
  # 单个 Executor 配置（覆盖默认）
  requirements:
    model: qwen3.6-plus
    max_iterations: 15
    timeout: 600
    tools: [read_file, search]
    system_prompt: |
      你是需求分析师...
    
  developer:
    model: qwen3.6-plus
    max_iterations: 20
    timeout: 900
    tools: [read_file, write_file, edit_file, bash, search]
    parallel_instances: 3
  
  reviewer:
    model: qwen3.6-plus
    max_iterations: 10
    timeout: 600
    tools: [read_file, search]

# Verifier 配置
verifiers:
  code_quality:
    enabled: true
    rules:
      - name: lint
        check: "ruff check ."
        severity: error
        timeout: 60
      - name: test_coverage
        check: "pytest --cov --cov-fail-under=80"
        severity: warning
        timeout: 120
      - name: type_check
        check: "mypy src/"
        severity: warning
        timeout: 90
  
  security:
    enabled: true
    rules:
      - name: dependency_audit
        check: "pip-audit"
        severity: critical
        timeout: 120

# 流程模板
flow_template:
  entry_point: requirements
  
  nodes:
    - id: requirements
      type: requirements
      label: "需求分析"
      timeout: 600
      retry: 2
      
    - id: design
      type: designer
      label: "技术设计"
      timeout: 600
      depends_on: [requirements]
      
    - id: develop
      type: developer
      label: "开发实现"
      timeout: 900
      depends_on: [design]
      parallel: true  # 支持并行子任务
      
    - id: review
      type: reviewer
      label: "代码审查"
      timeout: 600
      depends_on: [develop]
      
    - id: verify
      type: verifier_group
      label: "质量验证"
      depends_on: [develop]
      verifiers: [code_quality, security]
      
    - id: test
      type: tester
      label: "测试验证"
      timeout: 600
      depends_on: [review, verify]
  
  edges:
    # 简单边
    - from: requirements
      to: design
      
    - from: design
      to: develop
      
    - from: develop
      to: review
      
    - from: review
      to: test
      condition: "approved"
    
    - from: review
      to: develop
      condition: "needs_revision"
    
    - from: review
      to: human_review
      condition: "human"
    
    # Verifier 结果边
    - from: verify
      to: test
      condition: "passed"
    
    - from: verify
      to: develop
      condition: "failed"

# 人工审批配置
human_review:
  enabled: true
  nodes: [review, test]  # 在哪些节点后暂停
  auto_approve_after: 300  # 5分钟无响应自动通过

# 成本配置
cost_control:
  warning_threshold: 5.0    # $5 警告
  limit_threshold: 10.0     # $10 限制
  stop_threshold: 20.0      # $20 强制停止

# 检查点配置
checkpoint:
  enabled: true
  path: "./checkpoints/${WORKFLOW_NAME}.db"
  interval: 60  # 每60秒保存

# 日志配置
logging:
  level: INFO
  format: structured  # structured | text
  output:
    - type: file
      path: "./logs/${WORKFLOW_NAME}.json"
    - type: console

# 自定义变量（可在配置中引用）
vars:
  project_root: "./project"
  test_framework: pytest
```

### 2.2 字段说明

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `$schema` | string | 否 | - | JSON Schema URL |
| `version` | string | 否 | "1.0" | 配置版本 |
| `name` | string | **是** | - | 工作流唯一标识 |
| `display_name` | string | 否 | name | 显示名称 |
| `planner` | object | 否 | 见下 | Planner 配置 |
| `executors` | object | **是** | - | Executor 配置 |
| `verifiers` | object | 否 | {} | Verifier 配置 |
| `flow_template` | object | **是** | - | 流程模板 |
| `human_review` | object | 否 | {enabled:false} | 人工审批 |
| `cost_control` | object | 否 | {warning_threshold:5, limit_threshold:10, stop_threshold:20} | 成本控制 |
| `checkpoint` | object | 否 | {enabled:true} | 检查点 |
| `logging` | object | 否 | {level:"INFO"} | 日志配置 |
| `vars` | object | 否 | {} | 自定义变量 |

### 2.3 极简配置示例

```yaml
# 最简开发流程
name: simple-dev
executors:
  developer:
    model: qwen3.6-plus
    tools: [read_file, write_file, bash]
flow_template:
  entry_point: develop
  nodes:
    - id: develop
      type: developer
      label: "开发"
  edges: []
```

---

## 三、数据模型（Pydantic v2）

### 3.1 src/config/schema.py

```python
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, Literal, Any
from enum import Enum


class SeverityLevel(str, Enum):
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
        """合并默认值"""
        return ExecutorConfig(
            model=self.model or defaults.model,
            max_iterations=self.max_iterations or defaults.max_iterations,
            timeout=self.timeout or defaults.timeout,
            retry=self.retry or defaults.retry,
            tools=self.tools or defaults.tools,
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
    warning_threshold: float = 5.0    # 统一命名为 warning_threshold
    limit_threshold: float = 10.0     # 统一命名为 limit_threshold
    stop_threshold: float = 20.0      # 统一命名为 stop_threshold


class CheckpointConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    path: str = "./checkpoints/${WORKFLOW_NAME}.db"
    interval: int = 60


class LoggingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["file", "console", "webhook"]
    path: Optional[str] = None
    url: Optional[str] = None


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: str = "INFO"
    format: Literal["structured", "text"] = "structured"
    output: list[LoggingOutput] = Field(default_factory=lambda: [
        LoggingOutput(type="console")
    ])
```

### 3.2 WorkflowConfig 根配置

```python
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
    
    @validator("name")
    def validate_name(cls, v):
        if not v or not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("name 只能包含字母、数字、横线和下划线")
        return v
    
    @validator("flow_template")
    def validate_flow(cls, v, values):
        """验证流程图无环且 entry_point 存在"""
        node_ids = {n.id for n in v.nodes}
        
        # 检查 entry_point 存在
        if v.entry_point not in node_ids:
            raise ValueError(f"entry_point '{v.entry_point}' 不在节点列表中")
        
        # 检查依赖存在
        for node in v.nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    raise ValueError(
                        f"节点 '{node.id}' 依赖 '{dep}' 不存在"
                    )
        
        # 检查是否有环
        if cls._has_cycle(v):
            raise ValueError("流程图中检测到循环依赖")
        
        return v
    
    @staticmethod
    def _has_cycle(template: "FlowTemplate") -> bool:
        """使用 DFS 检测有向图中的环"""
        adj = {n.id: [] for n in template.nodes}
        for node in template.nodes:
            for dep in node.depends_on:
                adj[dep].append(node.id)
        
        visited = set()
        rec_stack = set()
        
        def dfs(node_id):
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
        import re
        import os
        
        def resolve_value(value):
            if isinstance(value, str):
                # 匹配 ${VAR} 或 ${VAR:-default}
                pattern = r"\$\{([^}]+)\}"
                def replace(match):
                    var_expr = match.group(1)
                    if ":-" in var_expr:
                        var_name, default = var_expr.split(":-", 1)
                        return os.environ.get(var_name, default)
                    return os.environ.get(var_expr, match.group(0))
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
```

---

## 四、ConfigLoader 设计

### 4.1 src/config/loader.py

```python
import os
import yaml
from pathlib import Path
from typing import Optional
from .schema import WorkflowConfig


class ConfigLoader:
    """配置加载器
    
    功能:
    - 加载单个或多个 YAML 配置
    - 配置合并（基础 + 覆盖）
    - 环境变量解析
    - Schema 校验
    """
    
    # 内置工作流目录
    BUILTIN_DIR = Path(__file__).parent.parent.parent / "config" / "workflows"
    
    def __init__(self):
        self._configs: dict[str, WorkflowConfig] = {}
    
    def load(self, path: str, resolve_vars: bool = True) -> WorkflowConfig:
        """加载单个配置文件
        
        Args:
            path: 配置文件路径（绝对路径或相对于项目根）
            resolve_vars: 是否解析环境变量
        
        Returns:
            验证后的 WorkflowConfig
        """
        file_path = self._resolve_path(path)
        
        with open(file_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        
        config = WorkflowConfig(**raw)
        
        if resolve_vars:
            config = config.resolve_vars()
        
        config = config.merge_executor_defaults()
        
        self._configs[config.name] = config
        return config
    
    def load_merged(self, paths: list[str]) -> WorkflowConfig:
        """加载并合并多个配置
        
        第一个为基础配置，后续为覆盖配置。
        """
        if not paths:
            raise ValueError("至少需要一个配置文件路径")
        
        base = self.load(paths[0])
        
        for override_path in paths[1:]:
            override = self.load(override_path)
            base = self._merge_configs(base, override)
        
        return base
    
    def load_builtin(self, name: str) -> WorkflowConfig:
        """加载内置工作流配置"""
        path = self.BUILTIN_DIR / f"{name}.yaml"
        if not path.exists():
            available = [f.stem for f in self.BUILTIN_DIR.glob("*.yaml")]
            raise FileNotFoundError(
                f"内置工作流 '{name}' 不存在。可用的: {available}"
            )
        return self.load(str(path))
    
    def validate_file(self, path: str) -> tuple[bool, list[str]]:
        """验证配置文件，不加载
        
        Returns:
            (是否有效, 错误列表)
        """
        try:
            self.load(path)
            return True, []
        except Exception as e:
            return False, [str(e)]
    
    def _resolve_path(self, path: str) -> Path:
        """解析文件路径"""
        p = Path(path)
        if p.is_absolute():
            return p
        
        # 相对路径从当前目录查找
        if p.exists():
            return p.resolve()
        
        # 从内置目录查找
        builtin = self.BUILTIN_DIR / p
        if builtin.exists():
            return builtin
        
        raise FileNotFoundError(f"配置文件未找到: {path}")
    
    def _merge_configs(self, base: WorkflowConfig, override: WorkflowConfig) -> WorkflowConfig:
        """合并两个配置，override 优先"""
        base_data = base.model_dump(by_alias=True)
        override_data = override.model_dump(by_alias=True)
        
        merged = self._deep_merge(base_data, override_data)
        return WorkflowConfig(**merged)
    
    def _deep_merge(self, base: dict, override: dict) -> dict:
        """深度合并字典"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def list_builtins(self) -> list[dict]:
        """列出所有内置工作流"""
        workflows = []
        for f in sorted(self.BUILTIN_DIR.glob("*.yaml")):
            with open(f) as fh:
                data = yaml.safe_load(fh)
            workflows.append({
                "name": data.get("name", f.stem),
                "display_name": data.get("display_name", ""),
                "description": data.get("description", ""),
                "path": str(f),
            })
        return workflows
```

---

## 五、ConfigurableWorkflowBuilder 设计

### 5.1 src/workflows/config_builder.py

```python
from typing import Optional, Any
from ..config.schema import WorkflowConfig, FlowNode, FlowEdge
from ..executors.registry import ExecutorRegistry
from ..plan.graph import PlanGraph
from .dynamic_builder import DynamicWorkflowBuilder


class ConfigurableWorkflowBuilder:
    """从配置构建工作流
    
    工作流程:
    1. 加载 WorkflowConfig
    2. 解析 executors → 创建/注册 Executor 实例
    3. 解析 flow_template → 构建 PlanGraph
    4. 使用 DynamicWorkflowBuilder 编译
    """
    
    def __init__(self, config: WorkflowConfig):
        self.config = config
        self._executor_registry = ExecutorRegistry()
        self._dynamic_builder = DynamicWorkflowBuilder()
        self._app = None
    
    def build(self) -> Any:
        """构建并编译工作流
        
        Returns:
            编译后的 LangGraph 应用
        """
        # 1. 注册 Executors
        self._register_executors()
        
        # 2. 从 flow_template 构建 PlanGraph
        plan = self._template_to_plangraph()
        
        # 3. 使用 DynamicWorkflowBuilder 编译
        self._app = self._dynamic_builder.from_plan(plan).build()
        
        return self._app
    
    def _register_executors(self):
        """注册配置中的 Executors"""
        for name, cfg in self.config.executors.items():
            executor = self._create_executor(name, cfg)
            capabilities = self._infer_capabilities(name, cfg)
            # 传入 capabilities 覆盖 executor 自带的能力声明
            self._executor_registry.register(executor, capabilities)
    
    def _create_executor(self, name: str, cfg) -> Any:
        """创建 Executor 实例
        
        根据 type 查找对应的 Agent/Executor 类并实例化。
        """
        # 从 Agent 工厂创建
        from ..agents import (
            create_requirements_agent,
            create_designer_agent,
            create_developer_agent,
            create_reviewer_agent,
            create_tester_agent,
            create_fixer_agent,
        )
        
        factory_map = {
            "requirements": create_requirements_agent,
            "designer": create_designer_agent,
            "developer": create_developer_agent,
            "reviewer": create_reviewer_agent,
            "tester": create_tester_agent,
            "fixer": create_fixer_agent,
        }
        
        factory = factory_map.get(name)
        if factory is None:
            raise ValueError(f"未知的 Executor 类型: {name}")
        
        return factory(
            model=cfg.model,
        )
    
    def _infer_capabilities(self, name: str, cfg) -> list[ExecutorCapability]:
        """推断 Executor 能力声明
        
        返回 ExecutorCapability 枚举列表，与 ExecutorRegistry.register()
        的 capabilities 参数类型对齐。
        """
        from ..plan.graph import ExecutorCapability
        
        # type → capability 映射
        type_to_cap = {
            "requirements": ExecutorCapability.REQUIREMENTS_ANALYSIS,
            "designer": ExecutorCapability.TECHNICAL_DESIGN,
            "developer": ExecutorCapability.CODE_DEVELOPMENT,
            "reviewer": ExecutorCapability.CODE_REVIEW,
            "tester": ExecutorCapability.TESTING,
            "fixer": ExecutorCapability.BUG_FIXING,
            "documentation": ExecutorCapability.DOCUMENTATION,
        }
        
        caps = [type_to_cap.get(name, ExecutorCapability.GENERIC)]
        
        # 如果配置了特殊工具，添加对应能力
        if "bash" in (cfg.tools or []):
            caps.append(ExecutorCapability.DEPLOYMENT)
        if "search" in (cfg.tools or []):
            caps.append(ExecutorCapability.GENERIC)
        
        return caps
    
    def _template_to_plangraph(self) -> PlanGraph:
        """将 FlowTemplate 转换为 PlanGraph
        
        字段映射说明:
        FlowNode (Phase 5 YAML)  →  PlanNode (Phase 4)
        ──────────────────────────────────────────────
        id          → id
        type        → required_capability (需映射为 ExecutorCapability 枚举)
        label       → description
        depends_on  → dependencies
        timeout     → timeout_seconds
        retry       → max_retries
        parallel    → parallel_group (布尔值 → 自动生成组名)
        condition   → condition
        """
        from ..plan.graph import PlanNode, PlanGraph, NodeType, ExecutorCapability
        from datetime import datetime
        import uuid
        
        # FlowNode.type → ExecutorCapability 映射
        type_to_capability = {
            "requirements": ExecutorCapability.REQUIREMENTS_ANALYSIS,
            "designer": ExecutorCapability.TECHNICAL_DESIGN,
            "developer": ExecutorCapability.CODE_DEVELOPMENT,
            "reviewer": ExecutorCapability.CODE_REVIEW,
            "tester": ExecutorCapability.TESTING,
            "fixer": ExecutorCapability.BUG_FIXING,
        }
        
        nodes = []
        parallel_groups: dict[str, list[str]] = {}  # 收集并行节点组
        
        for node in self.config.flow_template.nodes:
            # 生成并行组名：同批次并行节点共享一个 group
            group_name = None
            if node.parallel:
                group_name = f"parallel-{uuid.uuid4().hex[:8]}"
                parallel_groups[node.id] = group_name
            
            plan_node = PlanNode(
                id=node.id,
                name=node.label,                          # label → name
                node_type=NodeType.TASK,
                description=node.label,                   # label → description
                required_capability=type_to_capability.get(
                    node.type, ExecutorCapability.GENERIC
                ),
                dependencies=node.depends_on,             # depends_on → dependencies
                parallel_group=group_name,                # parallel → parallel_group
                condition=node.condition,
                max_retries=node.retry,                   # retry → max_retries
                timeout_seconds=node.timeout,             # timeout → timeout_seconds
            )
            nodes.append(plan_node)
        
        # 为同批次的并行节点分配相同的 group
        # 通过拓扑排序找出同一层级的并行节点
        node_ids = {n.id for n in self.config.flow_template.nodes}
        for nid, group in parallel_groups.items():
            for other in nodes:
                if other.id != nid and other.parallel_group is None:
                    # 检查是否有相同的依赖集（同层级）
                    src_node = next((n for n in self.config.flow_template.nodes if n.id == nid), None)
                    if src_node and set(src_node.depends_on) == set(other.dependencies):
                        other.parallel_group = group
        
        # 构建 PlanGraph（对齐 Phase 4 的 PlanGraph 构造函数签名）
        # Phase 4 PlanGraph 参数: id, task, nodes(dict), edges(list of tuples)
        nodes_dict = {n.id: n for n in nodes}
        edges_list = []
        for edge in self.config.flow_template.edges:
            edges_list.append((edge.from_node, edge.to_node))
        
        return PlanGraph(
            id=f"plan-{self.config.name}",
            task=self.config.display_name or self.config.name,
            nodes=nodes_dict,
            edges=edges_list,
            plan_type="configurable",
            status="draft",
        )
    
    def get_app(self) -> Any:
        """获取已编译的应用"""
        if self._app is None:
            self.build()
        return self._app
```

---

## 六、Flow Templates 机制

### 6.1 模板继承

```yaml
# config/workflows/base-dev.yaml
$schema: "..."
name: base-dev
executors:
  defaults:
    model: qwen3.6-plus
    timeout: 300
  developer:
    tools: [read_file, write_file, bash]

flow_template:
  entry_point: develop
  nodes:
    - id: develop
      type: developer
  edges: []

---

# config/workflows/custom-with-lint.yaml
# 继承 base-dev，添加 lint 步骤
extends: base-dev

executors:
  linter:
    model: qwen3.6-plus
    tools: [bash]

flow_template:
  nodes:
    - id: lint
      type: linter
      label: "代码检查"
      depends_on: [develop]
  
  edges:
    - from: develop
      to: lint
    - from: lint
      to: END
```

### 6.2 运行时覆盖

```python
from src.config.loader import ConfigLoader

loader = ConfigLoader()

# 加载基础配置
config = loader.load_builtin("software-development")

# 运行时覆盖
config.executors["developer"].timeout = 1800  # 30分钟
config.cost_control.stop = 50.0  # 提高预算上限
config.vars["project_root"] = "/tmp/my-project"

# 构建工作流
builder = ConfigurableWorkflowBuilder(config)
app = builder.build()
```

---

## 六、WorkflowRunner 接口设计

### 6.1 src/workflows/runner.py

```python
import asyncio
from typing import Any, Optional
from ..config.schema import WorkflowConfig

class WorkflowRunner:
    """工作流运行器
    
    统一的工作流执行入口，支持同步和异步调用。
    负责：
    - 初始化状态
    - 编译/执行 LangGraph 应用
    - 超时控制
    - 异常传播
    - 结果聚合
    """
    
    def __init__(self, app: Any, config: WorkflowConfig):
        self.app = app          # 编译后的 LangGraph StateGraph
        self.config = config
        self._timeout = config.executors.get("defaults", None)
        if self._timeout:
            self._timeout = self._timeout.timeout if hasattr(self._timeout, 'timeout') else 300
        else:
            self._timeout = 300
    
    async def run(
        self,
        task: str,
        project_path: str = ".",
        auto_approve: bool = False,
    ) -> dict:
        """异步运行工作流
        
        Args:
            task: 任务描述（自然语言）
            project_path: 项目路径
            auto_approve: 是否自动审批所有人工节点
        
        Returns:
            最终状态字典，包含 executor_results, verifier_results 等
        """
        from src.workflows.states import create_dynamic_initial_state
        from src.plan.graph import PlanGraph
        
        # 初始化状态
        initial_state = create_dynamic_initial_state(
            task=task,
            plan_graph=PlanGraph(id="adhoc", task=task),
            project_path=project_path,
        )
        initial_state["auto_approve"] = auto_approve
        
        # 带超时执行
        try:
            result = await asyncio.wait_for(
                self.app.ainvoke(initial_state),
                timeout=self._timeout,
            )
            return result
        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": f"工作流执行超时 ({self._timeout}s)",
                "executor_results": initial_state.get("executor_results", {}),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "executor_results": initial_state.get("executor_results", {}),
            }
    
    def run_sync(
        self,
        task: str,
        project_path: str = ".",
        auto_approve: bool = False,
    ) -> dict:
        """同步运行工作流（阻塞调用）"""
        return asyncio.get_event_loop().run_until_complete(
            self.run(task, project_path, auto_approve)
        )
    
    def run_stream(
        self,
        task: str,
        project_path: str = ".",
        auto_approve: bool = False,
    ):
        """流式运行工作流（逐节点返回结果）"""
        from src.workflows.states import create_dynamic_initial_state
        from src.plan.graph import PlanGraph
        
        initial_state = create_dynamic_initial_state(
            task=task,
            plan_graph=PlanGraph(id="adhoc", task=task),
            project_path=project_path,
        )
        initial_state["auto_approve"] = auto_approve
        
        for chunk in self.app.stream(initial_state):
            yield chunk
```

### 6.2 与 Phase 4 的关系

| Phase 4 组件 | WorkflowRunner 如何使用 |
|-------------|------------------------|
| DynamicWorkflowBuilder | 从 PlanGraph 编译为 LangGraph app |
| ExecutorRegistry | 提供 Executor 实例池 |
| VerifierFramework | 注册验证规则到 app 的条件边 |
| DynamicWorkflowState | 作为 LangGraph StateGraph 的状态类型 |

---

## 七、配置模板继承机制

### 7.1 YAML extends 语法支持

ConfigLoader 新增 `extends` 解析逻辑：

```python
def load(self, path: str, resolve_vars: bool = True) -> WorkflowConfig:
    """加载单个配置文件，自动处理 extends 继承"""
    file_path = self._resolve_path(path)
    
    with open(file_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    
    # 检查 extends 字段
    if "extends" in raw:
        parent_name = raw.pop("extends")
        # 先加载父模板（递归支持多层继承）
        parent_config = self.load_builtin(parent_name) if "/" not in parent_name else self.load(parent_name)
        # 深度合并：当前配置覆盖父配置
        parent_data = parent_config.model_dump(by_alias=True)
        merged = self._deep_merge(parent_data, raw)
        config = WorkflowConfig(**merged)
    else:
        config = WorkflowConfig(**raw)
    
    if resolve_vars:
        config = config.resolve_vars()
    
    config = config.merge_executor_defaults()
    
    self._configs[config.name] = config
    return config
```

### 7.2 继承示例

```yaml
# config/workflows/with-lint.yaml
extends: software-development    # 继承内置模板

# 只需定义差异部分
executors:
  linter:
    model: qwen3.6-plus
    tools: [bash]

flow_template:
  nodes:
    - id: lint
      type: linter
      label: "代码检查"
      depends_on: [review]
  
  edges:
    - from: review
      to: lint
    - from: lint
      to: test
```

---

## 八、CLI 接口设计

### 7.1 新命令

```bash
# 运行工作流（通过配置文件）
hermes run --workflow config/workflows/software-development.yaml "实现用户登录功能"

# 运行内置工作流
hermes run --builtin software-development "实现用户登录功能"

# 验证配置
hermes config validate config/my-workflow.yaml

# 列出所有内置工作流
hermes config list

# 从模板创建新配置
hermes config init my-workflow --template software-development

# 合并多个配置
hermes config merge base.yaml override.yaml -o final.yaml

# 可视化工作流
hermes config visualize config/my-workflow.yaml --format mermaid
```

### 7.2 CLI 实现

```python
# src/cli/main.py 新增命令

import click
from ..config.loader import ConfigLoader
from ..workflows.config_builder import ConfigurableWorkflowBuilder
from ..workflows.runner import WorkflowRunner


@click.command()
@click.option("--workflow", "-w", type=str, help="工作流配置文件路径")
@click.option("--builtin", "-b", type=str, help="内置工作流名称")
@click.option("--path", "-p", type=str, default=".", help="项目路径")
@click.option("--approve", is_flag=True, help="自动审批所有人工节点")
@click.option("--dry-run", is_flag=True, help="只验证配置，不执行")
@click.argument("task")
def run(workflow, builtin, path, approve, dry_run, task):
    """运行工作流"""
    loader = ConfigLoader()
    
    if builtin:
        config = loader.load_builtin(builtin)
    elif workflow:
        config = loader.load(workflow)
    else:
        click.echo("错误: 请指定 --workflow 或 --builtin")
        return
    
    if dry_run:
        click.echo(f"✓ 配置验证通过: {config.name}")
        click.echo(f"  Executor: {list(config.executors.keys())}")
        click.echo(f"  节点: {[n.id for n in config.flow_template.nodes]}")
        return
    
    builder = ConfigurableWorkflowBuilder(config)
    app = builder.build()
    
    runner = WorkflowRunner(app, config)
    result = runner.run_sync(task, project_path=path, auto_approve=approve)
    click.echo(result)


@click.command()
@click.argument("config_file")
def validate(config_file):
    """验证配置文件"""
    loader = ConfigLoader()
    valid, errors = loader.validate_file(config_file)
    if valid:
        click.echo(f"✓ 配置有效: {config_file}")
    else:
        for err in errors:
            click.echo(f"✗ {err}")
        raise SystemExit(1)


@click.command()
def list_workflows():
    """列出所有内置工作流"""
    loader = ConfigLoader()
    workflows = loader.list_builtins()
    click.echo("内置工作流:")
    for wf in workflows:
        click.echo(f"  {wf['name']:20s} {wf['display_name']} - {wf['description']}")
```

---

## 八、与 Phase 4 集成

| Phase 4 组件 | Phase 5 如何使用 |
|-------------|-----------------|
| DynamicWorkflowBuilder | 被 ConfigurableWorkflowBuilder 调用 |
| ExecutorRegistry | 由配置驱动的 Executor 注册 |
| PlannerAgent | 当 planner.enabled=true 时启用 |
| VerifierFramework | 从 config.verifiers 加载规则 |
| PlanGraph | 从 flow_template 转换生成 |

---

## 九、向后兼容

Phase 1-3 的硬编码方式仍然可用：

```python
# 旧方式（仍然有效，标记为 deprecated）
from src.workflows.builder import create_dev_pipeline

builder = create_dev_pipeline(api_key="...")
app = builder.build()

# 新方式（推荐）
from src.config.loader import ConfigLoader
from src.workflows.config_builder import ConfigurableWorkflowBuilder

loader = ConfigLoader()
config = loader.load_builtin("software-development")
builder = ConfigurableWorkflowBuilder(config)
app = builder.build()
```

---

## 十、文件变更清单

### 新增文件
```
src/config/
├── __init__.py
├── loader.py           # ConfigLoader
├── schema.py           # Pydantic models
└── workflow_config.py  # WorkflowConfig 辅助类

config/workflows/
├── software-development.yaml
├── code-review.yaml
├── bug-fix.yaml
└── data-pipeline.yaml

src/workflows/
└── config_builder.py   # ConfigurableWorkflowBuilder
```

### 修改文件
- `src/cli/main.py` - 新增命令
- `src/workflows/runner.py` - 支持配置驱动
- `src/agents/__init__.py` - 导出所有工厂函数

---

## 十一、测试策略

### 11.1 单元测试
- Schema 验证（必填字段、类型、枚举）
- 环境变量解析（${VAR}、${VAR:-default}、不存在时保留）
- 配置合并（基础+覆盖深度合并）
- 流程图验证（环检测、entry_point 存在性、依赖存在性）

### 11.2 集成测试
- ConfigLoader 加载完整 YAML
- ConfigurableWorkflowBuilder 构建可运行的 LangGraph
- 端到端：YAML 配置 → 构建 → 执行

### 11.3 测试用例
```python
def test_schema_validation_required_fields():
    """测试必填字段验证"""
    with pytest.raises(ValidationError):
        WorkflowConfig(name="", executors={}, flow_template={})

def test_cycle_detection():
    """测试环检测"""
    data = {
        "name": "cycle-test",
        "executors": {"a": {}, "b": {}},
        "flow_template": {
            "entry_point": "a",
            "nodes": [
                {"id": "a", "type": "x", "label": "A", "depends_on": ["b"]},
                {"id": "b", "type": "y", "label": "B", "depends_on": ["a"]},
            ],
            "edges": []
        }
    }
    with pytest.raises(ValidationError, match="循环依赖"):
        WorkflowConfig(**data)

def test_var_resolution():
    """测试环境变量解析"""
    os.environ["MY_PATH"] = "/tmp/test"
    config = WorkflowConfig(...)
    resolved = config.resolve_vars()
    assert resolved.checkpoint.path == "./checkpoints/${WORKFLOW_NAME}.db"
```

---

## 十二、实施步骤

| 步骤 | 内容 | 预估时间 |
|------|------|---------|
| 1 | 定义 Pydantic Schema | 0.5 天 |
| 2 | 实现 ConfigLoader | 1 天 |
| 3 | 创建示例 YAML 配置 | 0.5 天 |
| 4 | 实现 ConfigurableWorkflowBuilder | 1.5 天 |
| 5 | CLI 命令扩展 | 0.5 天 |
| 6 | 测试和文档 | 1 天 |
| **总计** | | **5 天** |

