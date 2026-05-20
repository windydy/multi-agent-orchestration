# Multi-Agent Orchestration - 生产级路线图

> 从当前 Phase 1-3 基础架构，升级到生产级可用的多Agent编排系统

## 一、现状评估

### 已完成 (Phase 1-3) ✅
- LangGraph 编排层基础架构
- ClaudeAgentWrapper 执行层
- 6 个专业 Agent（requirements → design → develop → review → test → fix）
- 状态持久化（SQLite checkpointer）
- Hooks 安全控制
- CLI 接口
- 测试框架骨架

### 当前局限
1. **编排硬编码**: 工作流节点和边固定在 `builder.py`，无法动态配置
2. **缺乏 Planner 层**: 没有"总指挥"Agent负责任务分解和动态调度
3. **角色边界模糊**: 各Agent职责重叠，缺乏清晰的 Planner/Executor/Verifier 三层架构
4. **缺少生产级能力**: 监控、日志、告警、成本控制、熔断机制不足
5. **Agent角色有限**: 仅覆盖软件开发，缺少 DevOps、Data、Security 等领域

---

## 二、规划者/执行者/验证者模式 (P/E/V)

### 核心概念

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Planner 层 (总指挥)                          │
│                                                                      │
│  职责：                                                              │
│  - 任务分析：理解用户意图，判断任务类型                               │
│  - 任务分解：拆解为原子子任务，建立依赖关系图                         │
│  - 动态调度：根据执行反馈调整计划，处理异常                           │
│  - 资源分配：选择合适的 Executor，配置工具和上下文                    │
│                                                                      │
│  输入：用户任务描述 + 项目上下文                                      │
│  输出：执行计划（Plan Graph）+ 子任务队列                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Executor 层    │  │  Executor 层    │  │  Executor 层    │
│                 │  │                 │  │                 │
│  职责：         │  │  职责：         │  │  职责：         │
│  - 执行原子任务 │  │  - 执行原子任务 │  │  - 执行原子任务 │
│  - 使用工具操作 │  │  - 使用工具操作 │  │  - 使用工具操作 │
│  - 反馈执行结果 │  │  - 反馈执行结果 │  │  - 反馈执行结果 │
│  - 处理异常     │  │  - 处理异常     │  │  - 处理异常     │
│                 │  │                 │  │                 │
│  Example:       │  │  Example:       │  │  Example:       │
│  Developer      │  │  DevOps Agent   │  │  Data Agent     │
└─────────────────┘  └─────────────────┘  └─────────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Verifier 层 (独立审核)                        │
│                                                                      │
│  职责：                                                              │
│  - 结果验证：检查 Executor 输出是否满足质量标准                       │
│  - 规则检查：执行预设的验证规则（代码规范、安全检查等）               │
│  - 质量评估：生成评分和建议                                          │
│  - 反馈闭环：将问题反馈给 Planner 调整计划                           │
│                                                                      │
│  输入：Executor 输出 + 验证规则                                       │
│  输出：验证结果（通过/失败/建议）+ 质量评分                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 与传统流水线的区别

| 维度 | 传统流水线 (当前) | P/E/V 模式 |
|------|------------------|------------|
| 流程 | 固定顺序（requirements → design → ...） | 动态生成的 Plan Graph |
| 决策 | 硬编码条件边 | Planner 实时决策 |
| 异常处理 | 预设回退路径（fix → test 循环） | Planner 动态调整计划 |
| 灵活性 | 低（修改需要改代码） | 高（配置化 + 动态规划） |
| 适用场景 | 标准化开发流程 | 复杂多变的任务场景 |

---

## 三、Phase 4-8 路线图

### Phase 4: Planner/Executor/Verifier 核心架构 ⏳
**目标**: 实现 P/E/V 三层架构，替代硬编码流水线

#### 4.1 Planner Agent
```python
# src/agents/planner.py
class PlannerAgent(BaseAgent):
    """规划者Agent
    
    职责：
    - 分析任务，生成执行计划（Plan Graph）
    - 动态调度 Executor
    - 处理异常和调整计划
    """
    
    def plan(self, task: str, context: dict) -> PlanGraph:
        """生成执行计划
        
        输出：DAG结构的执行图
        {
            "nodes": [
                {"id": "req_1", "type": "requirements", "dependencies": []},
                {"id": "dev_1", "type": "developer", "dependencies": ["req_1"]},
                {"id": "dev_2", "type": "developer", "dependencies": ["req_1"]},  # 并行
                {"id": "test_1", "type": "tester", "dependencies": ["dev_1", "dev_2"]},
            ],
            "entry": "req_1",
            "terminal": "test_1"
        }
        """
        pass
    
    def replan(self, current_state: dict, failure_info: dict) -> PlanGraph:
        """根据失败信息调整计划
        
        如：dev_1失败，添加fix节点，调整依赖
        """
        pass
    
    def dispatch(self, plan: PlanGraph, available_executors: list) -> dict:
        """将子任务分配给Executor
        
        考虑：
        - Executor 能力匹配
        - 当前负载
        - 优先级
        """
        pass
```

#### 4.2 Executor Registry
```python
# src/executors/registry.py
class ExecutorRegistry:
    """Executor 注册中心
    
    管理：
    - Executor 能力声明
    - Executor 实例池
    - 负载和状态
    """
    
    def register(self, executor: BaseExecutor, capabilities: list[str]):
        """注册Executor及其能力
        
        capabilities 示例：
        ["code:python", "code:typescript", "test:pytest", "deploy:k8s"]
        """
        pass
    
    def match(self, task_type: str) -> list[BaseExecutor]:
        """根据任务类型匹配合适的Executor"""
        pass
    
    def get_status(self, executor_id: str) -> ExecutorStatus:
        """获取Executor状态：idle/busy/error"""
        pass
```

#### 4.3 Verifier Framework
```python
# src/verifiers/framework.py
class VerifierFramework:
    """验证框架
    
    支持：
    - 预设验证规则
    - 自定义验证函数
    - 多维度质量评分
    """
    
    def register_rule(self, rule: VerificationRule):
        """注册验证规则
        
        rule 示例：
        {
            "name": "code_style",
            "executor": "developer",
            "check": "ruff check .",
            "severity": "warning"
        }
        """
        pass
    
    def verify(self, executor_output: dict, rules: list[str]) -> VerificationResult:
        """执行验证"""
        pass
```

#### 交付物
- `src/agents/planner.py` - Planner Agent 实现
- `src/executors/registry.py` - Executor 注册中心
- `src/verifiers/framework.py` - 验证框架
- `src/workflows/dynamic_builder.py` - 动态工作流构建器
- 更新测试覆盖

---

### Phase 5: 配置化编排 ⏳
**目标**: 通过配置文件定义工作流，无需修改代码

#### 5.1 配置 Schema
```yaml
# config/workflows/software-development.yaml
name: software-development
description: 标准软件开发流水线

# Planner 配置
planner:
  model: opus  # 使用更强的模型做规划
  max_plan_depth: 5
  allow_parallel: true

# Executor 配置
executors:
  requirements:
    model: opus
    tools: [read, search]
    timeout: 300
    
  developer:
    model: sonnet
    tools: [read, write, edit, bash, search]
    timeout: 900
    parallel_instances: 3  # 允许3个并行实例
    
  reviewer:
    model: opus
    tools: [read, search]
    timeout: 300

# Verifier 配置
verifiers:
  code_quality:
    rules:
      - name: lint
        check: "ruff check ."
        severity: error
      - name: test_coverage
        check: "pytest --cov --cov-fail-under=80"
        severity: warning
      - name: security
        check: "bandit -r ."
        severity: critical
        
# 流程模板（可选，Planner可动态生成）
flow_template:
  nodes: [requirements, design, develop, test]
  edges:
    - {from: requirements, to: design}
    - {from: design, to: develop}
    - {from: develop, to: test}
  conditional_edges:
    - {from: test, condition: "passed", to: END}
    - {from: test, condition: "failed", to: fix}
```

#### 5.2 Workflow Loader
```python
# src/workflows/loader.py
class WorkflowLoader:
    """从配置加载工作流"""
    
    def load(self, config_path: str) -> DynamicWorkflow:
        """加载YAML配置，构建工作流"""
        pass
    
    def validate(self, config: dict) -> ValidationResult:
        """验证配置完整性"""
        pass
```

#### 交付物
- `config/workflows/*.yaml` - 预设工作流配置
- `src/workflows/loader.py` - 配置加载器
- `src/workflows/schema.py` - 配置 Schema 定义
- CLI 支持：`hermes run --workflow config/my-workflow.yaml`

---

### Phase 6: 领域专业Agent扩展 ⏳
**目标**: 扩展Agent覆盖研发全生命周期

#### 6.1 DevOps Agent
```python
# src/agents/devops.py
class DevOpsAgent(BaseExecutor):
    """DevOps Agent
    
    能力：
    - CI/CD 配置和执行
    - 容器化（Docker/K8s）
    - 部署和发布
    - 监控配置
    """
    
    capabilities = [
        "deploy:docker",
        "deploy:k8s",
        "ci:github_actions",
        "ci:gitlab_ci",
        "infra:terraform",
    ]
```

#### 6.2 Security Agent
```python
# src/agents/security.py
class SecurityAgent(BaseVerifier):
    """安全Agent
    
    能力：
    - 代码安全扫描
    - 依赖安全检查
    - 配置安全审计
    - 渗透测试辅助
    """
    
    capabilities = [
        "scan:sast",
        "scan:dependency",
        "audit:config",
        "test:penetration",
    ]
```

#### 6.3 Data Agent
```python
# src/agents/data.py
class DataAgent(BaseExecutor):
    """数据处理Agent
    
    能力：
    - 数据清洗和转换
    - 数据分析
    - SQL/ETL
    - 数据可视化
    """
    
    capabilities = [
        "data:clean",
        "data:analyze",
        "data:etl",
        "data:visualize",
    ]
```

#### 6.4 Architect Agent
```python
# src/agents/architect.py
class ArchitectAgent(BaseExecutor):
    """架构师Agent
    
    能力：
    - 系统架构设计
    - 技术选型建议
    - 性能优化方案
    - 架构评审
    """
    
    capabilities = [
        "arch:design",
        "arch:review",
        "arch:optimize",
        "tech:selection",
    ]
```

#### 交付物
- `src/agents/devops.py`
- `src/agents/security.py`
- `src/agents/data.py`
- `src/agents/architect.py`
- 更新 `src/executors/registry.py` 注册

---

### Phase 7: 生产级能力 ⏳
**目标**: 添加监控、日志、告警、成本控制、熔断等生产级能力

#### 7.1 监控和可观测性
```python
# src/observability/metrics.py
class MetricsCollector:
    """指标收集
    
    收集：
    - 执行时间
    - Token 消耗
    - 成本
    - 成功/失败率
    - Agent 负载
    """
    
    def collect(self, execution_trace: ExecutionTrace) -> dict:
        pass
    
    def export_prometheus(self) -> str:
        """导出 Prometheus 格式"""
        pass

# src/observability/tracing.py
class DistributedTracer:
    """分布式追踪
    
    类似 OpenTelemetry：
    - Span 级别追踪
    - Agent 间调用链
    - 工具调用详情
    """
    pass
```

#### 7.2 成本控制和熔断
```python
# src/cost/controller.py
class CostController:
    """成本控制器
    
    功能：
    - 实时成本追踪
    - 预算限制
    - 超限熔断
    - 成本预警
    """
    
    def check_budget(self, current_cost: float, budget: float) -> bool:
        """检查是否超预算"""
        pass
    
    def throttle(self, agent_id: str) -> bool:
        """限流控制"""
        pass

# src/resilience/circuit_breaker.py
class CircuitBreaker:
    """熔断器
    
    规则：
    - 连续失败3次 → 开路
    - 30秒后尝试半开
    - 成功 → 关路
    """
    pass
```

#### 7.3 日志和告警
```python
# src/logging/structured.py
class StructuredLogger:
    """结构化日志
    
    格式：
    {
        "timestamp": "2026-05-20T08:00:00Z",
        "level": "INFO",
        "agent": "developer",
        "action": "write_file",
        "file": "src/main.py",
        "execution_id": "exec_123",
        "thread_id": "thread_456"
    }
    """
    pass

# src/alerting/notifier.py
class AlertNotifier:
    """告警通知
    
    通道：
    - Slack
    - Email
    - Webhook
    - Feishu（已有）
    """
    pass
```

#### 交付物
- `src/observability/metrics.py`
- `src/observability/tracing.py`
- `src/cost/controller.py`
- `src/resilience/circuit_breaker.py`
- `src/logging/structured.py`
- `src/alerting/notifier.py`
- Prometheus metrics endpoint
- Grafana dashboard template

---

### Phase 8: 高级特性 ⏳
**目标**: 添加多项目支持、团队协作、知识库等高级特性

#### 8.1 多项目和工作空间
```python
# src/workspace/manager.py
class WorkspaceManager:
    """工作空间管理
    
    支持：
    - 多项目切换
    - 项目间依赖
    - 共享配置
    """
    pass
```

#### 8.2 知识库和记忆
```python
# src/knowledge/memory.py
class AgentMemory:
    """Agent记忆系统
    
    支持：
    - 项目级知识存储
    - 代码风格学习
    - 常见问题记忆
    - 决策历史
    """
    
    def remember(self, project_id: str, key: str, value: dict):
        """存储项目知识"""
        pass
    
    def recall(self, project_id: str, query: str) -> dict:
        """检索相关知识"""
        pass
```

#### 8.3 团队协作
```python
# src/team/collaboration.py
class TeamCollaboration:
    """团队协作
    
    支持：
    - 多用户任务分配
    - 权限控制
    - 任务移交
    - 审批流程
    """
    pass
```

#### 8.4 Web UI（可选）
```
- React + Vite 前端
- FastAPI 后端
- 实时状态 WebSocket
- 工作流可视化
- 执行历史查看
```

---

## 四、架构总览（最终形态）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户接口层                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ CLI         │  │ Web UI      │  │ API Server  │  │ Feishu/Slack│        │
│  │ hermes run  │  │ Dashboard   │  │ REST/WS     │  │ Bot         │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              配置层                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Workflow Config (YAML)                                               │   │
│  │ - Planner config                                                     │   │
│  │ - Executor registry                                                  │   │
│  │ - Verifier rules                                                     │   │
│  │ - Flow templates                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Planner 层 (总指挥)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PlannerAgent                                                         │   │
│  │ - task_analyze() → 任务类型判断                                       │   │
│  │ - plan() → Plan Graph (DAG)                                          │   │
│  │ - dispatch() → Executor 分配                                         │   │
│  │ - replan() → 异常调整                                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Executor 层 (执行者)                               │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐    │
│  │Developer  │ │DevOps     │ │Security   │ │Data       │ │Architect  │    │
│  │(代码实现) │ │(部署运维) │ │(安全扫描) │ │(数据处理) │ │(架构设计) │    │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘    │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐                                 │
│  │Reviewer   │ │Tester     │ │Fixer      │                                 │
│  │(代码审查) │ │(测试验证) │ │(Bug修复)  │                                 │
│  └───────────┘ └───────────┘ └───────────┘                                 │
│                                                                              │
│  ExecutorRegistry: 能力声明 + 实例池 + 负载管理                              │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Verifier 层 (验证者)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ VerifierFramework                                                    │   │
│  │ - code_quality: lint, coverage, style                                │   │
│  │ - security: sast, dependency, config                                 │   │
│  │ - performance: benchmark, profiling                                  │   │
│  │ - custom: 用户自定义规则                                              │   │
│  └─────────────────────────────────────────────────────────────────────┐   │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           编排引擎 (LangGraph)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ DynamicWorkflowBuilder                                               │   │
│  │ - 从 Plan Graph 构建 StateGraph                                      │   │
│  │ - 动态添加节点和边                                                    │   │
│  │ - 支持 parallel/concurrent 执行                                      │   │
│  │ - Checkpointer 持久化                                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           基础设施层                                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │
│  │ Observability│ │ Cost Control│ │ Resilience │ │ Knowledge   │        │
│  │ Metrics/Trace│ │ Budget/Throt│ │ CircuitBreak│ │ Memory/RAG │        │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                        │
│  │ State Store │ │ Tool Registry│ │ Hook System│                        │
│  │ SQLite/Redis│ │ File/Bash/API│ │ Safety/Log │                        │
│  └─────────────┘ └─────────────┘ └─────────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 五、实施优先级

| Phase | 优先级 | 预估时间 | 核心价值 |
|-------|--------|----------|----------|
| Phase 4: P/E/V架构 | **P0** | 2-3周 | 核心架构升级，解决硬编码问题 |
| Phase 5: 配置化编排 | **P0** | 1-2周 | 灵活性，无需改代码调整流程 |
| Phase 7: 生产级能力 | **P1** | 1-2周 | 生产部署必需的监控和熔断 |
| Phase 6: 领域Agent扩展 | **P2** | 2-3周 | 覆盖更多场景，按需添加 |
| Phase 8: 高级特性 | **P3** | 2-4周 | 团队协作、知识库等增强 |

---

## 六、第一步行动建议

**立即开始 Phase 4 的核心部分：**

1. 设计并实现 `PlannerAgent` - 这是 P/E/V 模式的核心
2. 实现 `ExecutorRegistry` - 管理现有Agent的能力声明
3. 实现 `VerifierFramework` - 独立的验证层
4. 创建 `DynamicWorkflowBuilder` - 从 Plan Graph 动态构建 LangGraph

**建议的代码结构：**
```
src/
├── agents/
│   ├── planner.py          # NEW: Planner Agent
│   └── ...
├── executors/
│   ├── base.py             # NEW: BaseExecutor
│   └ registry.py           # NEW: ExecutorRegistry
│   └── ...
├── verifiers/
│   ├── base.py             # NEW: BaseVerifier
│   ├── framework.py        # NEW: VerifierFramework
│   └── rules/              # NEW: 验证规则库
│       ├── code_quality.py
│       ├── security.py
│       └── ...
├── workflows/
│   ├── dynamic_builder.py  # NEW: 动态工作流构建器
│   └── ...
└── plan/                   # NEW: 计划相关
    ├── graph.py            # PlanGraph (DAG)
    ├── scheduler.py        # 计划调度器
    └── executor.py         # 计划执行器
```

---

*文档版本: v1.0*
*创建时间: 2026-05-20*
*状态: 待评审*