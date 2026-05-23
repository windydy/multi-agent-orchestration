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
from src.agents.loader import AgentLoader

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
    "planner": ExecutorCapability.GENERIC,
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
        self._agent_loader = AgentLoader()
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
        
        优先从 agents/{name}.md 加载 Agent 定义，
        如果找不到则使用内置的 system_prompts 映射。
        """
        from src.executors.agent_adapter import AgentExecutor
        from src.core.agent import AgentConfig, AgentRole
        from src.claude.wrapper import ClaudeAgentWrapper, ClaudeSDKConfig, ClaudeToolType
        from src.claude.hooks import create_hooks
        
        # 工具名称映射
        TOOL_MAP = {
            "read": ClaudeToolType.READ_FILE,
            "read_file": ClaudeToolType.READ_FILE,
            "write": ClaudeToolType.WRITE_FILE,
            "write_file": ClaudeToolType.WRITE_FILE,
            "edit": ClaudeToolType.EDIT_FILE,
            "edit_file": ClaudeToolType.EDIT_FILE,
            "bash": ClaudeToolType.BASH,
            "search": ClaudeToolType.SEARCH,
        }
        
        # 尝试从 agents/{name}.md 加载
        agent_def = None
        loader = self._agent_loader
        available = loader.list_agents()
        
        # 名称映射: yaml name → agent file name
        name_mapping = {
            "planner": "planner",
            "requirements": "requirements-analyst",
            "designer": "designer",
            "developer": "developer",
            "reviewer": "reviewer",
            "tester": "tester",
            "fixer": "fixer",
            "documentation": "documentation",
            "architect": "architect",
            "devops": "devops",
            "security": "security",
            "data": "data",
            "product": "product-manager",
        }
        
        agent_file_name = name_mapping.get(name, name)
        if agent_file_name in available:
            agent_def = loader.load(agent_file_name)
        
        if agent_def:
            sys_prompt = agent_def.system_prompt
            model = cfg.model if cfg.model is not None else agent_def.model
            tools_list = cfg.tools if cfg.tools is not None else agent_def.tools
            max_iterations = cfg.max_iterations if cfg.max_iterations is not None else agent_def.max_iterations
            timeout = cfg.timeout if cfg.timeout is not None else agent_def.timeout
            temperature = cfg.temperature if cfg.temperature is not None else agent_def.temperature
        else:
            # 降级到内置映射
            sys_prompt = self._get_builtin_prompt(name)
            model = cfg.model or "qwen3.6-plus"
            tools_list = cfg.tools or ["read_file", "bash"]
            max_iterations = cfg.max_iterations or 15
            timeout = cfg.timeout or 300
            temperature = cfg.temperature if cfg.temperature is not None else 0.3
        
        tools = [TOOL_MAP.get(t, ClaudeToolType.READ_FILE) for t in tools_list if t in TOOL_MAP or t in ["read", "read_file", "write", "write_file", "edit", "edit_file", "bash", "search"]]
        if not tools:
            tools = [ClaudeToolType.READ_FILE, ClaudeToolType.BASH]
        
        # 创建 AgentConfig
        agent_config = AgentConfig(
            name=name,
            role=AgentRole.WORKER,
            description=agent_def.description if agent_def else f"{name} executor",
            model=model,
            tools=[t.value for t in tools],
            max_iterations=max_iterations,
            timeout=timeout,
            temperature=temperature,
            system_prompt=sys_prompt,
        )
        
        # 创建 ClaudeSDKConfig
        claude_config = ClaudeSDKConfig(
            model=model,
            max_tokens=8192,
            temperature=temperature,
            tools=tools,
            system_prompt=sys_prompt,
        )
        
        # 创建真实 Agent
        hooks = create_hooks(safety=True, logging=True, cost_control=True)
        agent = ClaudeAgentWrapper(agent_config, claude_config, hooks)
        
        # 包装为 AgentExecutor
        caps = self._infer_capabilities(name, cfg)
        return AgentExecutor(
            executor_id=f"{name}-executor",
            name=name,
            agent=agent,
            capabilities=caps,
        )
    
    @staticmethod
    def _get_builtin_prompt(name: str) -> str:
        """内置 system prompt 映射（降级路径）"""
        prompts = {
            "planner": "你是任务规划专家，负责将复杂任务分解为可执行的 DAG 计划。",
            "requirements": "你是需求分析师，负责理解用户需求并提取功能点。",
            "designer": "你是系统架构师，负责技术设计和架构规划。",
            "developer": "你是开发工程师，负责实现代码和编写测试。",
            "reviewer": "你是代码审查专家，负责审查代码质量和安全性。",
            "tester": "你是测试工程师，负责编写和执行自动化测试。",
            "fixer": "你是 Bug 修复专家，负责定位和修复缺陷。",
            "documentation": "你是技术文档工程师，负责编写文档。",
            "architect": "你是架构师，负责技术选型和架构设计。",
            "devops": "你是 DevOps 工程师，负责 CI/CD 和部署。",
            "security": "你是安全专家，负责安全审计和漏洞扫描。",
            "data": "你是数据工程师，负责数据分析和处理。",
            "product": "你是产品经理，负责需求分析和优先级排序。",
        }
        return prompts.get(name, f"你是 {name} 角色，负责执行任务。")
    
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
