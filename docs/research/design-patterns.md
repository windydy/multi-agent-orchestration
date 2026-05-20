# 设计模式总结

## 一、编排模式

### 1. 对话模式 (Conversational Pattern)
```
Agent A ←→ Agent B ←→ Agent C
     ↓          ↓          ↓
  [消息传递，无中心控制]
```
**代表:** AutoGen
**特点:** 
- 自然协作，类似人类团队讨论
- 无预设流程，动态决策
- 适合开放性问题

**代码示例 (AutoGen):**
```python
from autogen import ConversableAgent, AssistantAgent

assistant = AssistantAgent("assistant", llm_config={...})
user_proxy = ConversableAgent("user", human_input_mode="ALWAYS")

user_proxy.initiate_chat(assistant, message="请帮我分析这个需求")
```

### 2. 工作流模式 (Workflow Pattern)
```
[Start] → [Node A] → [Node B] → [Node C] → [End]
              ↓           ↓
          [条件分支]  [并行节点]
```
**代表:** LangGraph, Haystack
**特点:**
- 预定义流程图
- 确定性执行
- 易于调试和监控

**代码示例 (LangGraph):**
```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(State)
workflow.add_node("research", research_node)
workflow.add_node("analyze", analyze_node)
workflow.add_edge("research", "analyze")
workflow.add_edge("analyze", END)
app = workflow.compile()
```

### 3. 角色扮演模式 (Role-Playing Pattern)
```
┌─────────────────────────────────────┐
│           Crew/Team                 │
│  ┌─────────┐ ┌─────────┐ ┌───────┐ │
│  │ Agent A │ │ Agent B │ │ AgentC│ │
│  │ (PM)    │ │ (Dev)   │ │ (QA)  │ │
│  └─────────┘ └─────────┘ └───────┘ │
│        ↓           ↓         ↓     │
│     [Sequential / Hierarchical]    │
└─────────────────────────────────────┘
```
**代表:** CrewAI, MetaGPT
**特点:**
- 明确角色分工
- SOP驱动
- 适合模拟场景

**代码示例 (CrewAI):**
```python
from crewai import Agent, Task, Crew

pm = Agent(role="Product Manager", goal="定义需求", ...)
dev = Agent(role="Developer", goal="实现功能", ...)
qa = Agent(role="QA Engineer", goal="测试验证", ...)

crew = Crew(agents=[pm, dev, qa], tasks=[...], process="sequential")
crew.kickoff()
```

### 4. 层级模式 (Hierarchical Pattern)
```
              ┌──────────┐
              │ Manager  │
              └────┬─────┘
          ┌─────────┼─────────┐
          ↓         ↓         ↓
     ┌────────┐ ┌────────┐ ┌────────┐
     │Worker 1│ │Worker 2│ │Worker 3│
     └────────┘ └────────┘ └────────┘
```
**所有框架都支持**
**特点:**
- 任务分解和委派
- 结果聚合
- 适合复杂任务

### 5. 黑板模式 (Blackboard Pattern)
```
┌────────────────────────────────┐
│         Shared Memory          │
│  ┌──────────────────────────┐  │
│  │  State / Message Pool    │  │
│  └──────────────────────────┘  │
└────────────────────────────────┘
         ↑      ↑      ↑
         │      │      │
    ┌────┴─┐ ┌──┴───┐ ┌┴─────┐
    │Agent1│ │Agent2│ │Agent3│
    └──────┘ └──────┘ └──────┘
```
**代表:** MetaGPT
**特点:**
- 共享状态
- 解耦Agent
- 信息聚合

---

## 二、状态管理模式

### 中心化状态 (LangGraph)
```python
from typing import TypedDict

class State(TypedDict):
    messages: list
    current_task: str
    results: dict
    next_agent: str

# 所有节点共享同一状态
def node_a(state: State) -> State:
    state["messages"].append("Node A processed")
    return state
```

### 消息传递 (AutoGen)
```python
# 每条消息独立传递
agent_a.send(message, agent_b)
# agent_b在reply中处理
```

### 共享黑板 (MetaGPT)
```python
class MessagePool:
    def __init__(self):
        self.pool = []
    
    def publish(self, message):
        self.pool.append(message)
    
    def subscribe(self, agent):
        return [m for m in self.pool if m.target == agent]
```

---

## 三、人机协作模式

### 中断点模式 (LangGraph)
```python
workflow.add_node("human_review", human_review_node)
workflow.add_edge("analyze", "human_review")
# 在此处中断等待人类输入
app = workflow.compile(interrupt_before=["human_review"])

# 恢复执行
app.invoke(state)
```

### 代理模式 (AutoGen)
```python
user_proxy = UserProxyAgent(
    "user",
    human_input_mode="ALWAYS",  # 每轮都需要人类确认
    code_execution_config={"use_docker": False}
)
```

### 审批流程 (CrewAI)
```python
task = Task(
    description="执行关键操作",
    agent=agent,
    human_input=True  # 需要人类审批
)
```

---

## 四、并行执行模式

### 并行节点 (LangGraph)
```python
from langgraph.graph import StateGraph

workflow = StateGraph(State)
workflow.add_node("a", node_a)
workflow.add_node("b", node_b)
workflow.add_node("c", node_c)

# a完成后同时启动b和c
workflow.add_edge("a", "b")
workflow.add_edge("a", "c")
```

### 异步执行 (通用)
```python
import asyncio

async def run_parallel(agents, task):
    results = await asyncio.gather(*[
        agent.run(task) for agent in agents
    ])
    return results
```

---

## 五、错误处理模式

### 重试机制
```python
from tenacity import retry, stop_after_attempt

@retry(stop=stop_after_attempt(3))
def run_agent(agent, input):
    return agent.invoke(input)
```

### 回退策略
```python
def run_with_fallback(primary_agent, fallback_agent, input):
    try:
        return primary_agent.invoke(input)
    except Exception as e:
        logger.warning(f"Primary failed: {e}, using fallback")
        return fallback_agent.invoke(input)
```

### 优雅降级
```python
def run_with_degradation(agent, input, complexity_threshold=0.8):
    if input.complexity > complexity_threshold:
        # 复杂任务使用简化流程
        return agent.simplified_run(input)
    return agent.full_run(input)
```

---

## 六、最佳实践

### 1. Agent设计原则
- **单一职责:** 每个Agent只做一件事
- **明确边界:** 定义清晰的输入输出
- **可测试性:** 每个Agent可独立测试
- **幂等性:** 相同输入产生相同输出

### 2. 状态管理原则
- **最小状态:** 只存必要信息
- **不可变性:** 避免直接修改状态
- **可追溯:** 记录状态变化历史
- **可恢复:** 支持checkpoint和恢复

### 3. 工作流设计原则
- **简单优先:** 从简单开始逐步增加复杂度
- **可视化:** 提供流程可视化
- **可观测:** 记录每个节点的输入输出
- **可中断:** 关键节点支持人工介入

### 4. 生产部署原则
- **超时控制:** 每个节点设置超时
- **资源限制:** 控制并发和内存
- **监控告警:** 实时监控执行状态
- **日志追踪:** 完整的执行日志