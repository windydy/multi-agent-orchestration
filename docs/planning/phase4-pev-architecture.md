# Phase 4 详细技术设计: Planner/Executor/Verifier 核心架构

> 版本: 1.0
> 日期: 2026-05-20
> 状态: 待实现

---

## 一、目标

将当前硬编码的固定流水线升级为 **Planner/Executor/Verifier (P/E/V) 三层动态架构**，实现：

1. **动态规划**: PlannerAgent 根据任务自动生成执行计划（DAG 图）
2. **注册式执行**: ExecutorRegistry 统一管理所有 Executor 的能力声明和实例池
3. **独立验证**: VerifierFramework 提供独立于执行者的质量验证
4. **向后兼容**: 现有 6 个 Agent 保持不变，作为 Executor 适配接入新架构

---

## 二、现状分析

### 当前架构（硬编码流水线）
```
requirements → design → develop → review → test → fix
                    ↖_______________________↙
```
- 节点固定写在 `builder.py`
- 条件边（conditional edges）硬编码
- 无法扩展新角色而不修改核心代码
- 缺乏任务分解能力（整个任务作为一个整体处理）

### 目标架构（P/E/V）
```
                    Planner
                  /    |    \
            Executor  Executor  Executor
                  \    |    /
                 Verifier (独立审核)
```
- Planner 动态生成 DAG
- Executor 注册制，按需调用
- Verifier 独立于执行者
- 异常时 Planner 可 replan

---

## 三、核心数据结构

### 3.1 PlanGraph（执行计划图）

```python
@dataclass
class PlanNode:
    """执行计划中的一个节点"""
    id: str                          # 唯一标识，如 "req_1", "dev_1"
    executor_type: str               # 类型，如 "developer", "reviewer"
    task: str                        # 具体任务描述
    input_keys: list[str] = None     # 依赖的状态字段
    output_key: str                  # 输出存入状态的哪个字段
    dependencies: list[str] = None   # 依赖的节点 ID（用于 DAG 排序）
    timeout: int = 300               # 超时时间
    retry_count: int = 0             # 重试次数
    metadata: dict = None            # 额外元数据

@dataclass
class PlanGraph:
    """完整的执行计划（DAG）"""
    nodes: list[PlanNode]
    edges: list[tuple[str, str]]      # (source, target) 边
    entry_point: str                  # 入口节点
    terminal_nodes: list[str]         # 终止节点
    metadata: dict = None             # 计划元数据（版本、创建时间等）
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "nodes": [dataclasses.asdict(n) for n in self.nodes],
            "edges": self.edges,
            "entry_point": self.entry_point,
            "terminal_nodes": self.terminal_nodes,
        }

@dataclass
class ExecutionTrace:
    """执行追踪（用于 replan）"""
    plan_id: str
    current_node: str
    completed_nodes: list[str]
    failed_nodes: list[str]
    node_results: dict[str, dict]     # node_id -> result
    state_snapshot: dict              # 执行到当前的状态快照
    error_info: dict = None           # 失败信息（如果有）
```

### 3.2 ExecutorDescriptor（执行者描述）

```python
@dataclass
class ExecutorDescriptor:
    """Executor 的能力描述"""
    executor_id: str                  # 唯一标识
    executor_type: str                # 类型标签
    capabilities: list[str]           # 能力声明，如 ["code:python", "test:pytest"]
    tools: list[str]                  # 支持的工具体系
    model: str                        # 使用的模型
    max_concurrency: int = 1          # 最大并发实例数
    timeout: int = 300                # 默认超时
    description: str = ""             # 描述
    status: str = "idle"              # idle/busy/error
    last_used: Optional[str] = None   # 最后使用时间
```

### 3.3 VerificationRule（验证规则）

```python
@dataclass
class VerificationRule:
    name: str                         # 规则名称
    executor_type: str                # 针对哪种 Executor
    check_type: str                   # "command" / "function" / "llm"
    command: Optional[str] = None     # 如果是 command 类型
    function: Optional[Callable] = None  # 如果是 function 类型
    prompt: Optional[str] = None      # 如果是 llm 类型
    severity: str = "warning"         # "info" / "warning" / "error" / "critical"
    enabled: bool = True
    description: str = ""

@dataclass
class VerificationResult:
    rule: str
    passed: bool
    severity: str
    message: str
    details: dict = None
    timestamp: str = ""
```

---

## 四、文件结构

```
src/
├── plan/                              # NEW: 计划层
│   ├── __init__.py
│   ├── graph.py                       # PlanNode, PlanGraph, ExecutionTrace
│   ├── planner.py                     # PlannerAgent 实现
│   ├── scheduler.py                   # DAG 调度器（拓扑排序 + 并行）
│   └── executor_runner.py             # 计划执行器
│
├── executors/                         # NEW: 执行者层
│   ├── __init__.py
│   ├── base.py                        # BaseExecutor 抽象类
│   ├── registry.py                    # ExecutorRegistry 注册中心
│   └── adapter.py                     # 将旧 Agent 适配为 Executor
│
├── verifiers/                         # NEW: 验证者层
│   ├── __init__.py
│   ├── base.py                        # BaseVerifier 抽象类
│   ├── framework.py                   # VerifierFramework
│   └── rules/
│       ├── __init__.py
│       ├── code_quality.py            # lint, coverage
│       ├── security.py                # 安全检查
│       └── custom.py                  # 自定义规则
│
├── agents/                            # 现有 Agent（不变）
│   ├── planner.py                     # NEW: Planner Agent
│   └── ...
│
├── workflows/                         # 现有 + 新增
│   ├── dynamic_builder.py             # NEW: 从 PlanGraph 构建 LangGraph
│   ├── states.py                      # 扩展 WorkflowState
│   └── ...
```

---

## 五、核心实现

### 5.1 PlannerAgent

```python
# src/agents/planner.py
class PlannerAgent(BaseAgent):
    """规划者Agent - P/E/V 架构的核心
    
    职责:
    1. 分析任务，判断任务类型
    2. 拆解为原子子任务
    3. 建立依赖关系
    4. 生成 PlanGraph (DAG)
    5. 执行失败时 replan
    """
    
    # 任务类型模板库
    TASK_TEMPLATES = {
        "feature_development": {
            "description": "开发新功能",
            "pattern": [
                ("requirements", "分析需求，输出需求文档"),
                ("design", "根据需求文档设计技术方案"),
                ("develop", "根据设计文档实现代码"),
                ("review", "审查代码质量"),
                ("test", "运行测试验证"),
            ],
            "model": ["requirements", "design", "develop", "review", "test"],
        },
        "bug_fix": {
            "description": "修复已知Bug",
            "pattern": [
                ("diagnose", "分析Bug原因，定位问题代码"),
                ("develop", "修复Bug并编写回归测试"),
                ("test", "验证修复结果"),
            ],
        },
        "code_refactor": {
            "description": "代码重构",
            "pattern": [
                ("design", "设计重构方案"),
                ("develop", "执行重构"),
                ("review", "审查重构结果"),
                ("test", "确保测试通过"),
            ],
        },
    }
    
    def __init__(self, api_key=None, model="qwen3.6-plus", hooks=None):
        config = AgentConfig(
            name="planner",
            role=AgentRole.MANAGER,
            description="规划者 - 负责任务分解和执行计划生成",
            model=model,
            tools=["read", "write", "search"],
            max_iterations=5,
            timeout=120,
            temperature=0.3,
            system_prompt=self._build_system_prompt()
        )
        # ... 初始化 ClaudeSDKConfig ...
        super().__init__(config)
    
    async def plan(self, task: str, context: dict = None) -> PlanGraph:
        """生成执行计划
        
        流程:
        1. 分析任务类型（使用 LLM 或规则匹配）
        2. 查找匹配的模板
        3. 用 LLM 细化模板中的每个任务
        4. 建立依赖关系
        5. 生成 PlanGraph
        """
        context = context or {}
        
        # Step 1: 识别任务类型
        task_type = await self._identify_task_type(task, context)
        
        # Step 2: 匹配模板
        template = self.TASK_TEMPLATES.get(task_type)
        if not template:
            # 未知任务类型，用 LLM 生成全新计划
            return await self._generate_plan_from_scratch(task, context)
        
        # Step 3: 细化模板（LLM 填充具体任务描述）
        detailed_nodes = await self._refine_template(template, task, context)
        
        # Step 4: 构建 PlanGraph
        return self._build_plan_graph(detailed_nodes)
    
    async def replan(self, trace: ExecutionTrace) -> PlanGraph:
        """根据失败信息调整计划
        
        流程:
        1. 分析失败原因
        2. 保留已完成节点
        3. 调整后续计划（可能需要添加新节点）
        4. 返回新 PlanGraph
        """
        error_info = trace.error_info or {}
        failed_node = trace.failed_nodes[-1] if trace.failed_nodes else None
        
        if not failed_node:
            # 没有具体失败节点，从头重新规划
            return await self.plan(trace.state_snapshot.get("task", ""))
        
        # 构建新计划
        new_plan = await self._generate_replan(
            original_task=trace.state_snapshot.get("task", ""),
            completed_nodes=trace.completed_nodes,
            failed_node=failed_node,
            error_info=error_info,
        )
        
        return new_plan
    
    async def _identify_task_type(self, task: str, context: dict) -> str:
        """识别任务类型"""
        # 先尝试关键词匹配
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["bug", "fix", "修复", "错误"]):
            return "bug_fix"
        if any(kw in task_lower for kw in ["refactor", "重构", "重构代码"]):
            return "code_refactor"
        
        # 再用 LLM 判断
        prompt = f"""
        请判断以下任务属于哪种类型:
        任务: {task}
        
        可选类型: feature_development, bug_fix, code_refactor
        如果都不匹配，回答: unknown
        只回答类型名称，不要其他内容。
        """
        result = await self._call_llm(prompt)
        return result.strip().lower()
    
    def _build_plan_graph(self, nodes: list[dict]) -> PlanGraph:
        """从细化后的节点构建 PlanGraph"""
        plan_nodes = []
        edges = []
        
        for i, node_info in enumerate(nodes):
            node_id = f"{node_info['type']}_{i}"
            plan_node = PlanNode(
                id=node_id,
                executor_type=node_info["type"],
                task=node_info["description"],
                input_keys=node_info.get("input_keys", []),
                output_key=f"{node_info['type']}_result",
                dependencies=[f"{nodes[j]['type']}_{j}" for j in node_info.get("deps_indices", [])],
                timeout=node_info.get("timeout", 300),
            )
            plan_nodes.append(plan_node)
            
            # 添加边
            for j in node_info.get("deps_indices", []):
                parent_id = f"{nodes[j]['type']}_{j}"
                edges.append((parent_id, node_id))
        
        # 找入口和终点
        all_ids = {n.id for n in plan_nodes}
        deps_ids = set()
        for e in edges:
            deps_ids.add(e[1])
        entry = (all_ids - deps_ids).pop() if all_ids - deps_ids else plan_nodes[0].id
        terminal = [n.id for n in plan_nodes if n.id not in {e[0] for e in edges}]
        
        return PlanGraph(
            nodes=plan_nodes,
            edges=edges,
            entry_point=entry,
            terminal_nodes=terminal,
            metadata={"created_at": datetime.now().isoformat(), "plan_version": "1.0"},
        )
```

### 5.2 ExecutorRegistry

```python
# src/executors/registry.py
class ExecutorRegistry:
    """Executor 注册中心
    
    管理:
    - Executor 注册和能力声明
    - 按能力匹配 Executor
    - 实例池和负载管理
    - Executor 健康检查
    """
    
    _instance = None  # 单例
    
    def __init__(self):
        self._descriptors: dict[str, ExecutorDescriptor] = {}
        self._factories: dict[str, Callable] = {}
        self._instances: dict[str, BaseExecutor] = {}
        self._active_count: dict[str, int] = defaultdict(int)
    
    @classmethod
    def get(cls) -> "ExecutorRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register(self, executor_id: str, factory: Callable, descriptor: ExecutorDescriptor):
        """注册 Executor
        
        Args:
            executor_id: 唯一标识
            factory: 创建 Executor 的工厂函数
            descriptor: 能力描述
        """
        self._descriptors[executor_id] = descriptor
        self._factories[executor_id] = factory
    
    def match(self, executor_type: str) -> list[ExecutorDescriptor]:
        """根据类型匹配可用的 Executor"""
        return [
            d for d in self._descriptors.values()
            if d.executor_type == executor_type and d.status != "error"
        ]
    
    def match_by_capability(self, capability: str) -> list[ExecutorDescriptor]:
        """根据能力匹配 Executor"""
        return [
            d for d in self._descriptors.values()
            if capability in d.capabilities and d.status != "error"
        ]
    
    def get_executor(self, executor_id: str) -> BaseExecutor:
        """获取或创建 Executor 实例"""
        if executor_id not in self._instances:
            factory = self._factories.get(executor_id)
            if factory:
                self._instances[executor_id] = factory()
            else:
                raise ValueError(f"Executor not found: {executor_id}")
        
        self._active_count[executor_id] += 1
        self._descriptors[executor_id].status = "busy"
        return self._instances[executor_id]
    
    def release(self, executor_id: str):
        """释放 Executor"""
        self._active_count[executor_id] = max(0, self._active_count[executor_id] - 1)
        if self._active_count[executor_id] == 0:
            self._descriptors[executor_id].status = "idle"
            self._descriptors[executor_id].last_used = datetime.now().isoformat()
    
    def list_all(self) -> list[dict]:
        """列出所有 Executor"""
        return [
            {
                "executor_id": eid,
                "type": d.executor_type,
                "capabilities": d.capabilities,
                "status": d.status,
                "active_count": self._active_count.get(eid, 0),
            }
            for eid, d in self._descriptors.items()
        ]
    
    def health_check(self) -> dict:
        """健康检查"""
        return {
            eid: {
                "status": d.status,
                "active": self._active_count.get(eid, 0),
                "last_used": d.last_used,
            }
            for eid, d in self._descriptors.items()
        }


def register_builtin_executors():
    """注册内置的 Executor（适配现有 Agent）"""
    registry = ExecutorRegistry.get()
    
    # 从旧 Agent 创建 Executor 适配器
    registry.register(
        executor_id="requirements",
        factory=lambda: AgentAsExecutor(
            agent=create_requirements_agent(),
            executor_type="requirements",
        ),
        descriptor=ExecutorDescriptor(
            executor_id="requirements",
            executor_type="requirements",
            capabilities=["requirements:analysis", "requirements:spec"],
            tools=["read", "search"],
            model="qwen3.6-plus",
            max_concurrency=2,
            description="需求分析 Executor",
        ),
    )
    
    registry.register(
        executor_id="design",
        factory=lambda: AgentAsExecutor(
            agent=create_designer_agent(),
            executor_type="design",
        ),
        descriptor=ExecutorDescriptor(
            executor_id="design",
            executor_type="design",
            capabilities=["design:technical", "design:architecture"],
            tools=["read", "write", "search"],
            model="qwen3.6-plus",
            max_concurrency=2,
            description="技术设计 Executor",
        ),
    )
    
    registry.register(
        executor_id="develop",
        factory=lambda: AgentAsExecutor(
            agent=create_developer_agent(),
            executor_type="develop",
        ),
        descriptor=ExecutorDescriptor(
            executor_id="develop",
            executor_type="develop",
            capabilities=["code:python", "code:typescript", "code:generic"],
            tools=["read", "write", "edit", "bash", "search"],
            model="qwen3.6-plus",
            max_concurrency=3,
            description="代码开发 Executor",
        ),
    )
    
    registry.register(
        executor_id="review",
        factory=lambda: AgentAsExecutor(
            agent=create_reviewer_agent(),
            executor_type="review",
        ),
        descriptor=ExecutorDescriptor(
            executor_id="review",
            executor_type="review",
            capabilities=["review:code", "review:design"],
            tools=["read", "search"],
            model="qwen3.6-plus",
            max_concurrency=2,
            description="代码审查 Executor",
        ),
    )
    
    registry.register(
        executor_id="test",
        factory=lambda: AgentAsExecutor(
            agent=create_tester_agent(),
            executor_type="test",
        ),
        descriptor=ExecutorDescriptor(
            executor_id="test",
            executor_type="test",
            capabilities=["test:unit", "test:integration", "test:e2e"],
            tools=["bash", "read", "search"],
            model="qwen3.6-plus",
            max_concurrency=2,
            description="测试验证 Executor",
        ),
    )
    
    registry.register(
        executor_id="fix",
        factory=lambda: AgentAsExecutor(
            agent=create_fixer_agent(),
            executor_type="fix",
        ),
        descriptor=ExecutorDescriptor(
            executor_id="fix",
            executor_type="fix",
            capabilities=["fix:bug", "fix:test"],
            tools=["read", "edit", "bash", "search"],
            model="qwen3.6-plus",
            max_concurrency=2,
            description="Bug 修复 Executor",
        ),
    )
```

### 5.3 AgentAsExecutor（适配器）

```python
# src/executors/adapter.py
class AgentAsExecutor(BaseExecutor):
    """将现有 Agent 适配为 Executor 接口"""
    
    def __init__(self, agent: BaseAgent, executor_type: str, capabilities: list[str] = None):
        self._agent = agent
        self._executor_type = executor_type
        self._capabilities = capabilities or []
    
    @property
    def executor_type(self) -> str:
        return self._executor_type
    
    @property
    def capabilities(self) -> list[str]:
        return self._capabilities
    
    async def execute(self, task: str, context: dict) -> AgentResult:
        """委托给内部 Agent 执行"""
        return await self._agent.run(task, context)
    
    def get_status(self) -> dict:
        return {
            "executor_type": self._executor_type,
            "capabilities": self._capabilities,
            "agent": str(self._agent),
        }
```

### 5.4 VerifierFramework

```python
# src/verifiers/framework.py
class VerifierFramework:
    """验证框架
    
    支持三种验证模式:
    1. command: 执行 shell 命令检查
    2. function: 调用 Python 函数检查
    3. llm: 使用 LLM 评估质量
    """
    
    def __init__(self):
        self._rules: dict[str, VerificationRule] = {}
        self._rule_groups: dict[str, list[str]] = defaultdict(list)  # executor_type -> [rule_names]
    
    def register(self, rule: VerificationRule):
        """注册验证规则"""
        self._rules[rule.name] = rule
        self._rule_groups[rule.executor_type].append(rule.name)
    
    def unregister(self, rule_name: str):
        """注销规则"""
        if rule_name in self._rules:
            rule = self._rules[rule_name]
            if rule_name in self._rule_groups.get(rule.executor_type, []):
                self._rule_groups[rule.executor_type].remove(rule_name)
            del self._rules[rule_name]
    
    async def verify(self, executor_type: str, executor_output: dict, 
                     context: dict = None) -> list[VerificationResult]:
        """执行所有针对该 Executor 的验证规则"""
        rules = self._rule_groups.get(executor_type, [])
        results = []
        
        for rule_name in rules:
            rule = self._rules.get(rule_name)
            if not rule or not rule.enabled:
                continue
            
            result = await self._execute_rule(rule, executor_output, context or {})
            results.append(result)
        
        return results
    
    async def _execute_rule(self, rule: VerificationRule, output: dict, context: dict) -> VerificationResult:
        """执行单个验证规则"""
        if rule.check_type == "command":
            return await self._check_command(rule, output, context)
        elif rule.check_type == "function":
            return await self._check_function(rule, output, context)
        elif rule.check_type == "llm":
            return await self._check_llm(rule, output, context)
        else:
            return VerificationResult(
                rule=rule.name,
                passed=False,
                severity="error",
                message=f"未知检查类型: {rule.check_type}",
            )
    
    async def _check_command(self, rule: VerificationRule, output: dict, context: dict) -> VerificationResult:
        """执行命令验证"""
        try:
            process = await asyncio.create_subprocess_shell(
                rule.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=60
            )
            
            passed = process.returncode == 0
            return VerificationResult(
                rule=rule.name,
                passed=passed,
                severity=rule.severity,
                message=stdout.decode() if passed else stderr.decode(),
                details={"exit_code": process.returncode},
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            return VerificationResult(
                rule=rule.name,
                passed=False,
                severity="error",
                message=f"命令执行失败: {str(e)}",
                timestamp=datetime.now().isoformat(),
            )
    
    async def _check_function(self, rule: VerificationRule, output: dict, context: dict) -> VerificationResult:
        """执行函数验证"""
        try:
            if asyncio.iscoroutinefunction(rule.function):
                result = await rule.function(output, context)
            else:
                result = rule.function(output, context)
            
            return VerificationResult(
                rule=rule.name,
                passed=bool(result),
                severity=rule.severity,
                message=str(result) if isinstance(result, str) else "",
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            return VerificationResult(
                rule=rule.name,
                passed=False,
                severity="error",
                message=f"函数执行失败: {str(e)}",
                timestamp=datetime.now().isoformat(),
            )
    
    async def _check_llm(self, rule: VerificationRule, output: dict, context: dict) -> VerificationResult:
        """使用 LLM 验证（质量评估）"""
        # 使用 Claude/LLM 评估输出质量
        # 这里复用现有的 ClaudeAgentWrapper
        ...
```

### 5.5 预设验证规则

```python
# src/verifiers/rules/code_quality.py
def register_default_rules(framework: VerifierFramework):
    """注册默认验证规则"""
    
    # 针对 developer 的规则
    framework.register(VerificationRule(
        name="developer_lint",
        executor_type="develop",
        check_type="command",
        command="ruff check . || true",  # 不阻止流程
        severity="warning",
        description="代码规范检查",
    ))
    
    framework.register(VerificationRule(
        name="developer_test_pass",
        executor_type="develop",
        check_type="command",
        command="pytest tests/ -q || true",
        severity="warning",
        description="测试通过检查",
    ))
    
    # 针对 reviewer 的规则
    framework.register(VerificationRule(
        name="reviewer_no_blocking_issues",
        executor_type="review",
        check_type="function",
        function=lambda output, ctx: not output.get("blocking_issues", []),
        severity="error",
        description="审查结果无阻塞级问题",
    ))
    
    # 针对 test 的规则
    framework.register(VerificationRule(
        name="test_all_passed",
        executor_type="test",
        check_type="function",
        function=lambda output, ctx: output.get("all_passed", False),
        severity="error",
        description="所有测试通过",
    ))
```

### 5.6 DynamicWorkflowBuilder

```python
# src/workflows/dynamic_builder.py
class DynamicWorkflowBuilder:
    """从 PlanGraph 动态构建 LangGraph StateGraph"""
    
    def __init__(self, registry: ExecutorRegistry = None, verifier: VerifierFramework = None):
        self._registry = registry or ExecutorRegistry.get()
        self._verifier = verifier or VerifierFramework()
    
    def build(self, plan: PlanGraph, state_class: type = WorkflowState) -> Any:
        """从 PlanGraph 构建 LangGraph
        
        流程:
        1. 创建 StateGraph
        2. 为每个 PlanNode 创建 LangGraph 节点函数
        3. 根据 PlanGraph.edges 添加边
        4. 添加 Verifier 节点（在每个 Executor 之后）
        5. 设置入口和终点
        6. 编译
        """
        workflow = StateGraph(state_class)
        
        # 为每个节点创建函数
        for plan_node in plan.nodes:
            workflow.add_node(
                plan_node.id,
                self._make_node_function(plan_node)
            )
        
        # 添加边
        for source, target in plan.edges:
            workflow.add_edge(source, target)
        
        # 添加验证节点（可选）
        for plan_node in plan.nodes:
            verifier_results = await self._verifier.verify(
                plan_node.executor_type,
                {},  # 执行时从 state 获取
                {},
            )
            if verifier_results:
                workflow.add_node(
                    f"{plan_node.id}_verify",
                    self._make_verify_node_function(plan_node, verifier_results)
                )
                workflow.add_edge(plan_node.id, f"{plan_node.id}_verify")
                # 修改原有 target 边指向验证节点
                # ...
        
        # 设置入口
        workflow.set_entry_point(plan.entry_point)
        
        # 设置终点
        for terminal in plan.terminal_nodes:
            workflow.add_edge(terminal, END)
        
        # 编译
        checkpointer = SqliteSaver.from_conn_string("./checkpoints/pipeline.db")
        return workflow.compile(checkpointer=checkpointer)
    
    def _make_node_function(self, plan_node: PlanNode) -> Callable:
        """为 PlanNode 创建 LangGraph 节点函数"""
        async def node_func(state: WorkflowState) -> dict:
            executor = self._registry.get_executor(plan_node.executor_type)
            try:
                # 构建上下文
                context = self._build_context(state, plan_node)
                
                # 执行
                result = await executor.execute(plan_node.task, context)
                
                # 返回状态更新
                return {
                    plan_node.output_key: result.output if result.success else {"error": result.error},
                    "current_stage": plan_node.id,
                    "iteration_count": state.get("iteration_count", 0) + 1,
                }
            finally:
                self._registry.release(plan_node.executor_type)
        
        return node_func
```

---

## 六、WorkflowState 扩展

```python
# src/workflows/states.py (扩展)

class WorkflowState(TypedDict, total=False):
    """扩展后的全局状态"""
    
    # === 原有字段 ===
    task: str
    project_path: str
    messages: Annotated[Sequence[dict], operator.add]
    requirements: dict
    design: dict
    code_changes: dict
    review_result: dict
    test_result: dict
    fix_result: dict
    current_stage: str
    next_stage: str
    iteration_count: int
    needs_revision: bool
    human_approval: bool
    approval_comment: str
    start_time: str
    end_time: str
    total_cost: float
    
    # === NEW: P/E/V 架构新增 ===
    plan_graph: dict                    # 当前执行计划
    plan_id: str                        # 计划唯一标识
    plan_version: int                   # 计划版本号（replan 时递增）
    
    execution_trace: dict               # 执行追踪信息
    executor_registry_status: dict      # Executor 注册中心状态快照
    
    verification_results: Annotated[list[dict], operator.add]  # 验证结果累加
    
    replan_count: int                   # 重新规划次数
    max_replans: int                    # 最大 replan 次数
    
    # === NEW: 通用执行器结果 ===
    executor_results: dict              # executor_id -> result (通用存储)
```

---

## 七、执行流程

### 7.1 正常执行流程

```
用户提交任务
    │
    ▼
┌─────────────────┐
│ Planner.plan()  │ 生成初始 PlanGraph
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│ DynamicWorkflowBuilder.build│ 将 PlanGraph 转为 LangGraph
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ LangGraph 执行                               │
│                                             │
│   Node_1 → Node_2 → Node_3                  │
│     │          │          │                 │
│     ▼          ▼          ▼                 │
│  Executor   Executor   Executor             │
│     │          │          │                 │
│     ▼          ▼          ▼                 │
│  Verifier   Verifier   Verifier             │
│     │          │          │                 │
└──────────────┼──────────┼───────────────────┘
               │          │
               ▼          ▼
           全部通过    有失败
               │          │
               ▼          ▼
             END      Planner.replan()
                         │
                         ▼
                    生成新 PlanGraph
                         │
                         ▼
                    继续执行（跳过已完成节点）
```

### 7.2 Replan 流程

```
Node_X 执行失败
    │
    ▼
ExecutionTrace 记录失败信息
    │
    ▼
Planner.replan(trace)
    │
    ├── 分析失败原因
    │   ├── 工具不可用 → 换工具
    │   ├── 超时 → 简化任务
    │   ├── 依赖问题 → 调整依赖
    │   └── 任务太难 → 拆分子任务
    │
    ├── 保留已完成节点
    │
    └── 生成新 PlanGraph
        │
        ▼
    从最后一个成功节点继续
```

---

## 八、配置示例

```yaml
# config/pev.yaml
planner:
  model: "qwen3.6-plus"
  task_templates:
    feature_development:
      pattern: [requirements, design, develop, review, test]
    bug_fix:
      pattern: [diagnose, develop, test]
    code_refactor:
      pattern: [design, develop, review, test]
  max_replans: 3

executors:
  requirements:
    model: "qwen3.6-plus"
    max_concurrency: 2
    timeout: 300
  develop:
    model: "qwen3.6-plus"
    max_concurrency: 3
    timeout: 900
  review:
    model: "qwen3.6-plus"
    max_concurrency: 2
    timeout: 300

verifiers:
  rules:
    - name: lint
      executor_type: develop
      check_type: command
      command: "ruff check . || true"
      severity: warning
    - name: test_pass
      executor_type: develop
      check_type: command
      command: "pytest tests/ -q || true"
      severity: warning
    - name: no_blocking_issues
      executor_type: review
      check_type: function
      severity: error
```

---

## 九、测试策略

### 9.1 单元测试

```python
# tests/plan/test_planner.py
async def test_planner_identifies_feature_development():
    planner = PlannerAgent()
    task_type = await planner._identify_task_type("实现用户登录功能")
    assert task_type == "feature_development"

async def test_planner_generates_plan():
    planner = PlannerAgent()
    plan = await planner.plan("实现用户登录功能")
    assert len(plan.nodes) > 0
    assert plan.entry_point is not None
    assert len(plan.terminal_nodes) > 0

async def test_planner_replans_on_failure():
    planner = PlannerAgent()
    trace = ExecutionTrace(
        plan_id="plan_1",
        current_node="develop_0",
        completed_nodes=["requirements_0", "design_0"],
        failed_nodes=["develop_0"],
        node_results={"requirements_0": {...}, "design_0": {...}},
        state_snapshot={"task": "实现用户登录功能"},
        error_info={"error": "依赖包不兼容"},
    )
    new_plan = await planner.replan(trace)
    assert len(new_plan.nodes) > 0
    # 验证已完成节点不在新计划中（或标记为跳过）

# tests/executors/test_registry.py
def test_executor_registry_match():
    registry = ExecutorRegistry()
    register_builtin_executors()
    
    matches = registry.match("develop")
    assert len(matches) == 1
    assert matches[0].executor_type == "develop"

def test_executor_registry_by_capability():
    registry = ExecutorRegistry()
    register_builtin_executors()
    
    matches = registry.match_by_capability("code:python")
    assert len(matches) >= 1

# tests/verifiers/test_framework.py
async def test_verifier_command_rule():
    framework = VerifierFramework()
    framework.register(VerificationRule(
        name="echo_test",
        executor_type="develop",
        check_type="command",
        command="echo 'hello'",
        severity="info",
    ))
    
    results = await framework.verify("develop", {}, {})
    assert len(results) == 1
    assert results[0].passed == True
```

### 9.2 集成测试

```python
# tests/integration/test_pev_pipeline.py
async def test_full_pev_pipeline():
    """测试完整的 P/E/V 流程"""
    planner = PlannerAgent()
    registry = ExecutorRegistry()
    register_builtin_executors()
    verifier = VerifierFramework()
    register_default_rules(verifier)
    
    # 1. Planner 生成计划
    plan = await planner.plan("实现一个简单的计算器模块")
    assert len(plan.nodes) >= 3
    
    # 2. 构建工作流
    builder = DynamicWorkflowBuilder(registry, verifier)
    app = builder.build(plan)
    
    # 3. 执行
    config = {"configurable": {"thread_id": "test_thread"}}
    result = await app.ainvoke(create_initial_state("实现计算器"), config=config)
    
    # 4. 验证
    assert result["current_stage"] == "completed"
    assert result["iteration_count"] > 0
```

---

## 十、迁移路径

### 从现有架构迁移到 P/E/V

```
现有代码（Phase 1-3）
    │
    ├── 保持不变
    │   ├── src/core/agent.py
    │   ├── src/core/state.py
    │   ├── src/core/workflow.py
    │   ├── src/core/orchestrator.py
    │   ├── src/core/tool.py
    │   ├── src/claude/wrapper.py
    │   ├── src/claude/hooks.py
    │   ├── src/agents/*.py (6个Agent)
    │
    ├── 新增
    │   ├── src/plan/
    │   ├── src/executors/
    │   ├── src/verifiers/
    │   ├── src/agents/planner.py
    │   ├── src/workflows/dynamic_builder.py
    │
    └── 可选保留（向后兼容）
        ├── src/workflows/builder.py (旧版硬编码流水线)
        ├── src/workflows/runner.py (旧版 runner)
```

### 兼容层

```python
# src/workflows/compat.py
class CompatibilityWrapper:
    """兼容旧版 API 的包装器"""
    
    @staticmethod
    async def run_pipeline(task, project_path, config=None):
        """旧版 API 兼容"""
        planner = PlannerAgent()
        plan = await planner.plan(task)
        
        registry = ExecutorRegistry()
        register_builtin_executors()
        
        builder = DynamicWorkflowBuilder(registry)
        app = builder.build(plan)
        
        return await app.ainvoke(create_initial_state(task, project_path))
```

---

## 十一、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Planner 生成无效 DAG | 执行失败 | 增加 DAG 校验，检查循环和孤立节点 |
| Executor 匹配失败 | 任务无法执行 | 提供默认 fallback executor |
| Verifier 误报 | 阻塞正常流程 | severity=warning 的规则不阻塞，只记录 |
| Replan 循环 | 无限重新规划 | 设置 max_replans 限制 |
| 性能下降 | 动态规划增加延迟 | 模板缓存，避免每次都调用 LLM |

---

## 十二、验收标准

- [ ] PlannerAgent 能正确识别 3 种任务类型
- [ ] PlannerAgent 能为每种类型生成有效的 PlanGraph (DAG)
- [ ] ExecutorRegistry 能注册、匹配、获取 Executor
- [ ] VerifierFramework 支持 command/function/llm 三种验证模式
- [ ] DynamicWorkflowBuilder 能从 PlanGraph 构建 LangGraph
- [ ] 现有 6 个 Agent 通过适配器接入 ExecutorRegistry
- [ ] 完整端到端测试通过（规划 → 执行 → 验证）
- [ ] Replan 机制测试通过
- [ ] 单元测试覆盖率 > 80%

---

*文档版本: v1.0*
*创建时间: 2026-05-20*
*作者: Hermes Agent*