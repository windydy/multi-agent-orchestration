# Phase 9 需求文档：需求澄清机制 (ClarifierAgent)

> **版本**: v1.0
> **日期**: 2026-05-24
> **状态**: 设计评审中
> **目标**: 在 PlannerAgent 之前引入 ClarifierAgent，解决用户输入模糊、系统盲目执行的问题

---

## 1. 问题陈述

### 1.1 现状

当前系统执行链路：
```
用户任务 → PlannerAgent → PlanGraph → Executor → ...
```

RequirementsAgent 的 prompt 中包含"澄清模糊需求"，但：
- 没有独立环节，澄清指令被淹没在分析指令中
- 没有 Human-in-the-Loop 机制，Agent 不会主动暂停提问
- 没有澄清状态机，系统不会等待用户回复

### 1.2 问题示例

用户输入："帮我做一个电商网站"
系统行为：直接拆解任务 → 分配 executor → 执行
缺失环节：没有人问用户"面向什么用户群体？需要哪些核心功能？技术栈偏好？预算和时间限制？"

### 1.3 目标

1. **引入 ClarifierAgent**（需求澄清 Agent），在 PlannerAgent 之前对用户输入进行澄清评分，必要时进入交互澄清环节
2. **修复用户入口**：Web UI 首页增加 "创建任务" 表单，用户无需调 API 即可发起任务
3. **完整用户流程**：用户提交任务 → 系统自动评分 → 必要时弹出澄清问题 → 用户回答 → 执行 → 查看结果

完整链路：
```
用户打开 Web UI → 填写任务描述 → ClarifierAgent 评分 → [必要时澄清] → PlannerAgent → PlanGraph → Executor → ...
```

---

## 2. 架构设计

### 2.1 整体流程图

```
┌─────────────┐
│ 用户提交任务  │
└──────┬──────┘
       ▼
┌─────────────────────────────────────────────┐
│ ClarifierAgent                              │
│  1. 分析输入完整性（9 个维度）                │
│  2. 计算澄清分数（0-100）                    │
│  3. 判断是否需要澄清                           │
│     - 分数 >= 80：直接通过                    │
│     - 分数 < 80：  生成澄清问题               │
└──────┬──────────────────────────────────────┘
       ▼
  ┌────────────┐
  │ 需要澄清？   │
  └──────┬─────┘
    yes  │  no
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────────┐ ┌──────────────┐
│ 澄清模式 │ │ 直接通过      │
│         │ │ (跳过澄清)    │
│ 模式A: 保守│ └──────┬───────┘
│ 模式B: 交互│        ▼
└────┬────┘ ┌──────────────┐
     │      │ PlannerAgent │
     ▼      └──────────────┘
┌─────────────────────┐
│ 保守模式:             │
│ 使用合理假设，标注    │
│ "基于以下假设"       │
│ 直接进入 Planner     │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 交互模式:             │
│ 1. 执行状态 → clarifying│
│ 2. WebSocket 推送问题  │
│ 3. 等待用户回复       │
│ 4. 用户回复 → 重新评估 │
│ 5. 分数足够 → 放行     │
└──────────┬──────────┘
           ▼
┌──────────────┐
│ PlannerAgent │
└──────────────┘
```

### 2.2 澄清维度评分模型

ClarifierAgent 对用户输入进行 9 个维度评估，每个维度 1-5 分：

| 维度 | 说明 | 示例问题 |
|------|------|---------|
| functional_scope | 功能范围是否明确 | "需要哪些核心功能？" |
| target_users | 目标用户是否明确 | "面向什么用户群体？" |
| tech_constraints | 技术约束是否明确 | "有技术栈偏好或限制吗？" |
| timeline | 时间要求是否明确 | "期望的交付时间是？" |
| budget | 预算范围是否明确 | "预算或成本限制是？" |
| quality_reqs | 质量要求是否明确 | "对性能、安全、可用性有什么要求？" |
| integration | 集成需求是否明确 | "需要对接现有系统吗？" |
| success_criteria | 成功标准是否明确 | "怎么判断这个项目成功了？" |
| context | 项目背景是否充分 | "这个项目的背景和业务场景是？" |

**总分计算**：加权平均 × 20 = 0-100 分
- 默认权重：所有维度等权
- 可按任务类型调整权重（如"开发类"更关注 tech_constraints）

**阈值**：
- >= 80：直接通过，无需澄清
- 50-79：需要澄清，可保守模式或交互模式
- < 50：强烈建议交互澄清，保守模式会标注高风险

### 2.3 保守模式 vs 交互模式

| 特性 | 保守模式 | 交互模式 |
|------|---------|---------|
| 适用场景 | 用户不在场、异步任务、紧急任务 | 用户在线、重要项目 |
| 行为 | 用合理假设填充缺失信息 | 通过 WebSocket 向用户提问，等待回复 |
| 风险控制 | 标注"基于以下假设"，风险提示 | 用户确认后继续 |
| 执行速度 | 快 | 慢（需等待用户回复） |

默认使用保守模式。交互模式需要用户主动开启（Web UI 中提供开关）。

---

## 3. 数据模型

### 3.1 ClarifierResult

```python
@dataclass
class ClarifierResult:
    """ClarifierAgent 的澄清结果"""
    score: float                          # 0-100 澄清分数
    dimensions: dict[str, DimensionScore]  # 各维度评分
    questions: list[ClarificationQuestion]  # 待澄清问题
    assumptions: list[Assumption]           # 保守模式的假设
    recommendation: str                     # "skip" / "conservative" / "interactive"
    enriched_task: str                      # 增强后的任务描述（含假设）
```

### 3.2 ClarificationQuestion

```python
@dataclass
class ClarificationQuestion:
    """单个澄清问题"""
    dimension: str     # 维度名
    question: str      # 问题文本
    importance: str    # "high" / "medium" / "low"
    user_answer: Optional[str] = None  # 用户回复（交互模式）
```

### 3.3 执行状态扩展

现有 ExecutionHandle 新增 `clarification` 字段：

```python
@dataclass
class ClarificationState:
    """澄清状态"""
    status: Literal["skipped", "clarifying", "clarified", "conservative"]
    score: float = 0.0
    result: Optional[ClarifierResult] = None
    user_answers: dict[str, str] = field(default_factory=dict)  # {question_id: answer}
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
```

ExecutionHandle 新增：
```python
clarification: Optional[ClarificationState] = None
```

新增执行状态：`"clarifying"`（澄清中，等待用户回复）

---

## 4. 对现有系统的影响分析

### 4.1 后端改造

#### 4.1.1 `src/clarifier/agent.py` — 新增文件

新建 ClarifierAgent：
- 分析输入完整性和维度评分
- 生成澄清问题
- 根据用户回复重新评估
- 保守模式填充假设

```
src/clarifier/
├── __init__.py
├── agent.py          # ClarifierAgent 主类
├── dimensions.py      # 维度定义和评分模型
├── prompts.py         # 系统提示和模板
└── assumptions.py     # 保守模式默认假设库
```

#### 4.1.2 `src/workflows/runner.py` — 修改

`WorkflowRunner.run()` 方法中，在调用 PlannerAgent 之前加入 ClarifierAgent：

```python
async def run(self, task, project_path, thread_id=None, 
              clarification_mode="auto"):  # "auto" / "conservative" / "interactive"
    # 1. ClarifierAgent 评分
    clarifier_result = await self.clarifier.analyze(task)
    
    if clarifier_result.score >= 80:
        # 直接通过
        return await self._run_with_planner(task, ...)
    
    if clarification_mode == "interactive" and clarifier_result.score < 80:
        # 进入交互澄清
        return await self._run_interactive_clarification(task, clarifier_result, ...)
    
    # 保守模式
    enriched_task = clarifier_result.enriched_task
    return await self._run_with_planner(enriched_task, ...)
```

#### 4.1.3 `src/api/routes/executions.py` — 修改

新增澄清相关路由：

```python
# 提交澄清问题回复
@router.post("/executions/{thread_id}/clarify", response_model=ClarifyResponse)
async def submit_clarification(thread_id: str, req: ClarifyRequest):
    """用户在 Web UI 回答澄清问题后调用"""
    em = _get_em()
    await em.submit_clarification(thread_id, req.answers)
    # 唤醒被暂停的执行
    await em.resume_after_clarification(thread_id)
    return ClarifyResponse(status="clarification_submitted")

# 查询澄清状态
@router.get("/executions/{thread_id}/clarification", response_model=ClarificationStatus)
async def get_clarification_status(thread_id: str):
    """前端轮询或首次加载时查询澄清问题"""
    em = _get_em()
    handle = await em.get_execution(thread_id)
    if handle.clarification and handle.clarification.status == "clarifying":
        return ClarificationStatus(
            status="clarifying",
            questions=handle.clarification.result.questions,
            score=handle.clarification.score,
        )
    return ClarificationStatus(status="not_clarifying")
```

#### 4.1.4 `src/api/services/execution_manager.py` — 修改

ExecutionManager 新增：
- `set_clarifying_state(thread_id, clarifier_result)` — 设置澄清中状态
- `submit_clarification(thread_id, answers)` — 接收用户回复
- `resume_after_clarification(thread_id)` — 澄清完成后恢复执行

ExecutionHandle 新增 `clarification` 字段，数据库新增 `clarification` 列。

#### 4.1.5 `src/api/ws.py` — 修改

WebSocket 新增澄清消息类型：
```json
// 服务端推送澄清问题
{ "type": "clarification_request", "data": { "questions": [...] } }

// 客户端回复
{ "type": "clarification_answer", "data": { "answers": {...} } }
```

#### 4.1.6 `src/api/server.py` — 修改

`create_app()` 中初始化 ClarifierAgent 并注入 WorkflowRunner。

### 4.2 前端改造

#### 4.2.1 新建组件 `ClarificationPage.tsx`

当执行状态为 `clarifying` 时显示：

```
┌─────────────────────────────────────────────┐
│  🤔 需求澄清                                │
│                                             │
│  系统需要更多信息来制定更好的执行计划。       │
│  请回答以下问题：                             │
│                                             │
│  [HIGH] 功能范围：需要哪些核心功能？          │
│  ┌───────────────────────────────────────┐  │
│  │ 用户输入...                            │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  [MEDIUM] 目标用户：面向什么用户群体？        │
│  ┌───────────────────────────────────────┐  │
│  │ 用户输入...                            │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  [LOW] 预算：预算或成本限制是？              │
│  ┌───────────────────────────────────────┐  │
│  │ 用户输入...                            │
│  └───────────────────────────────────────┘  │
│                                             │
│  或者：[使用保守模式继续 ▶]                 │
│  （使用合理假设，可能不准确）                │
│                                             │
│  [提交回答]                                 │
└─────────────────────────────────────────────┘
```

#### 4.2.2 修改 `ExecutionPage.tsx`

- 执行详情页面新增 "clarifying" 状态展示
- 状态为 `clarifying` 时显示 ClarificationPage 组件
- 通过 WebSocket 或轮询接收澄清问题
- 用户提交回答后，调用 `/api/executions/{id}/clarify` API

#### 4.2.3 修改 `ExecutionTable.tsx`

- 表格新增 "clarification" 列
- 显示澄清状态图标：✓ (已澄清) / ⏳ (澄清中) / — (跳过)

#### 4.2.4 修改 `HomePage.tsx` — 创建任务入口（核心改造）

**问题**：首页当前是只读仪表盘，用户无法通过 UI 发起任务。

**改造**：在首页增加 "创建任务" 按钮和表单弹窗：

```
┌─────────────────────────────────────────────────┐
│ Multi-Agent Dashboard          [＋ 创建任务]     │
│                                                 │
│ [统计卡片: TOTAL 1 | RUNNING 1 | SUCCESS 0]     │
│                                                 │
│ EXECUTIONS                                      │
│ ┌─────────────────────────────────────────────┐ │
│ │ THREAD            | STATUS  | PROGRESS      │ │
│ │ thread_9e9d6d9c   | Running | 2/5           │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

点击 "＋ 创建任务" 弹出表单：

```
┌─────────────────────────────────────────────┐
│  创建新任务                          [×]    │
│                                             │
│  任务描述 *                                 │
│  ┌───────────────────────────────────────┐  │
│  │ 帮我做一个...                          │  │
│  │                                       │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  工作流                                     │
│  [● development] [○ custom] [○ dag]        │
│                                             │
│  澄清模式                                   │
│  [● auto]    (系统自动判断)                 │
│  [○ interactive] (总是提问)                 │
│  [○ conservative] (总是使用假设)            │
│                                             │
│  [取消]          [提交 ▶]                   │
└─────────────────────────────────────────────┘
```

提交流程：
1. 调用 `POST /api/executions` 创建执行
2. 如果 ClarifierAgent 评分 < 80 且模式为 interactive：
   - 执行进入 `clarifying` 状态
   - 自动跳转到 `/executions/{id}` 页面显示澄清问题表单
3. 如果直接通过或保守模式：
   - 自动进入执行
   - Dashboard 实时更新进度

#### 4.2.5 路由注册

在 `App.tsx` 中，执行详情页的路由支持澄清状态：
```
/executions/{id} — 如果状态是 clarifying，自动显示澄清面板
```

### 4.3 数据库变更

#### 4.3.1 ExecutionHandle 表

```sql
ALTER TABLE execution_handles ADD COLUMN clarification TEXT;
-- JSON 序列化的 ClarificationState
```

#### 4.3.2 可选：独立的 clarification_sessions 表

```sql
CREATE TABLE clarification_sessions (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    score REAL NOT NULL,
    questions TEXT NOT NULL,        -- JSON
    assumptions TEXT,               -- JSON
    user_answers TEXT,              -- JSON
    status TEXT NOT NULL,           -- clarifying / clarified / skipped / conservative
    created_at REAL NOT NULL,
    completed_at REAL,
    FOREIGN KEY (thread_id) REFERENCES execution_handles(thread_id)
);
```

---

## 5. 实施计划

### 5.1 阶段划分

| 阶段 | 内容 | 预估工作量 |
|------|------|-----------|
| Phase 9.1 | ClarifierAgent 核心实现 | 2-3 天 |
| Phase 9.2 | 后端集成（ExecutionManager + API 路由） | 2 天 |
| Phase 9.3 | Web UI 改造（ClarificationPage + 状态展示） | 2-3 天 |
| Phase 9.4 | WebSocket 交互澄清 | 1-2 天 |
| Phase 9.5 | 测试（单元 + E2E） | 2 天 |

### 5.2 关键里程碑

1. **MVP**：ClarifierAgent 能评分并输出澄清问题（无需交互，只输出结果）
2. **交互**：Web UI 显示澄清问题，用户可提交回复
3. **自动化**：执行链路完整集成，从澄清到规划到执行

---

## 6. 风险和缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| ClarifierAgent LLM 调用失败 | 澄清无法进行 | 降级为保守模式，直接通过 |
| 用户不回复澄清问题 | 执行永久暂停 | 设置超时（如 30 分钟），超时后自动保守模式 |
| 澄清问题太多 | 用户疲劳 | 限制最多 5 个问题，按重要性排序 |
| 保守模式假设不准确 | 执行结果偏离预期 | 在最终交付物中标注所有假设，要求用户确认 |
| 现有执行流程不兼容 | 历史执行报错 | 新增字段使用 Optional，保持向后兼容 |

---

## 7. 验收标准

1. ClarifierAgent 对 "帮我做一个电商网站" 能生成至少 3 个澄清问题
2. ClarifierAgent 对 "用 React + FastAPI 做一个用户管理系统，支持 CRUD，3 天交付" 能直接通过（分数 >= 80）
3. Web UI 在 clarifying 状态下显示澄清问题表单
4. 用户提交回复后，执行自动恢复并进入 PlannerAgent 阶段
5. 保守模式下，执行结果中包含假设列表
6. 所有现有测试通过

---

## 8. 附录

### 8.1 保守模式默认假设库

```python
DEFAULT_ASSUMPTIONS = {
    "functional_scope": "实现核心 CRUD 功能",
    "target_users": "一般 Web 用户",
    "tech_constraints": "使用项目现有技术栈",
    "timeline": "标准开发周期",
    "budget": "无特殊限制",
    "quality_reqs": "基本质量要求",
    "integration": "无外部集成需求",
    "success_criteria": "功能可用、无严重 bug",
    "context": "通用项目",
}
```

### 8.2 现有系统改造清单

| 文件 | 修改类型 | 改动内容 |
|------|---------|---------|
| `src/clarifier/` | **新增** | ClarifierAgent 及相关模块 |
| `src/workflows/runner.py` | 修改 | run() 方法加入 ClarifierAgent |
| `src/workflows/states.py` | 修改 | 新增 clarification 状态字段 |
| `src/api/routes/executions.py` | 修改 | 新增 /clarify 和 /clarification 路由 |
| `src/api/services/execution_manager.py` | 修改 | 新增澄清状态管理方法 |
| `src/api/server.py` | 修改 | 初始化 ClarifierAgent |
| `src/api/ws.py` | 修改 | 支持澄清消息类型 |
| `web/src/pages/ClarificationPage.tsx` | **新增** | 澄清问题表单 |
| `web/src/pages/ExecutionPage.tsx` | 修改 | 支持 clarifying 状态 |
| `web/src/pages/HomePage.tsx` | 修改 | 新增澄清模式选择器 |
| `web/src/components/ExecutionTable.tsx` | 修改 | 新增澄清状态列 |
| `web/src/lib/api.ts` | 修改 | 新增澄清相关 API 调用 |
| `web/src/types.ts` | 修改 | 新增澄清相关类型 |
| `tests/` | **新增** | ClarifierAgent 单元测试 + E2E |
