"""
Phase 5: ConfigurableWorkflowBuilder — 从 YAML 配置构建工作流

src/workflows/config_builder.py
"""

from typing import Any, Optional
import logging

from src.config.schema import WorkflowConfig, FlowNode, FlowEdge
from src.plan.graph import PlanGraph, PlanNode, NodeType, ExecutorCapability
from src.executors.registry import ExecutorRegistry
from src.workflows.dynamic_builder import DynamicWorkflowBuilder

logger = logging.getLogger(__name__)

# FlowNode.type → ExecutorCapability 映射
TYPE_TO_CAPABILITY = {
    "requirements": ExecutorCapability.REQUIREMENTS_ANALYSIS,
    "designer": ExecutorCapability.TECHNICAL_DESIGN,
    "developer": ExecutorCapability.CODE_DEVELOPMENT,
    "reviewer": ExecutorCapability.CODE_REVIEW,
    "tester": ExecutorCapability.TESTING,
    "fixer": ExecutorCapability.BUG_FIXING,
    "documentation": ExecutorCapability.DOCUMENTATION,
    "architect": ExecutorCapability.ARCHITECTURE_DESIGN,
    "devops": ExecutorCapability.DEVOPS_CI_CD,
    "security": ExecutorCapability.SECURITY_AUDIT,
    "data": ExecutorCapability.DATA_ENGINEERING,
    "product": ExecutorCapability.PRODUCT_MANAGEMENT,
}


class ConfigurableWorkflowBuilder:
    """从配置构建工作流
    
    工作流程:
    1. 加载 WorkflowConfig
    2. 解析 executors → 创建/注册 Executor 实例
    3. 解析 flow_template → 构建 PlanGraph
    4. 使用 DynamicWorkflowBuilder 编译
    """
    
    def __init__(self, config: WorkflowConfig):
        # 合并 defaults 到 executors
        self.config = config.merge_executor_defaults()
        self._executor_registry = ExecutorRegistry()
        self._dynamic_builder = DynamicWorkflowBuilder()
        self._app: Any = None
    
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
        
        这里创建 AgentExecutor 适配器，将 Phase 1-3 的 Agent 包装为 Executor。
        由于我们没有实际的 API key，这里创建一个 mock executor。
        """
        from src.executors.base import BaseExecutor, ExecutorStatus
        from src.plan.graph import PlanNode as PN
        
        class MockExecutor(BaseExecutor):
            async def execute(self, node: PN, context: dict) -> dict:
                return {
                    "output": f"Executed by {name}",
                    "success": True,
                    "metadata": {"model": cfg.model or "qwen3.6-plus"},
                }
        
        caps = self._infer_capabilities(name, cfg)
        return MockExecutor(
            executor_id=f"{name}-executor",
            name=name,
            capabilities=caps,
        )
    
    def _infer_capabilities(self, name: str, cfg) -> list[ExecutorCapability]:
        """推断 Executor 能力声明
        
        返回 ExecutorCapability 枚举列表。
        """
        # type → capability 映射
        cap = TYPE_TO_CAPABILITY.get(name, ExecutorCapability.GENERIC)
        
        caps = [cap]
        
        # 如果配置了特殊工具，添加对应能力
        if cfg.tools:
            if "bash" in cfg.tools:
                caps.append(ExecutorCapability.DEPLOYMENT)
            if "search" in cfg.tools:
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
        import uuid
        from datetime import datetime
        
        # FlowNode.type → ExecutorCapability 映射
        
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
                required_capability=TYPE_TO_CAPABILITY.get(
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
