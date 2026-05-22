# Web UI 开发路线图

> 为 multi-agent-orchestration 项目规划 Web Dashboard，从最小 MVP 开始逐步演进

## 一、架构定位

```
┌─────────────────────────────────────────────────────────────────────┐
│                          用户接口层                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐│
│  │ CLI         │  │ Web UI      │  │ API Server  │  │ Feishu/Slack││
│  │ hermes run  │  │ Dashboard   │  │ REST/WS     │  │ Bot         ││
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                              │
                        （复用后端现有层）
```

**设计原则：**
- Web UI 是**并行接口之一**，不替代 CLI，而是互补
- 后端 FastAPI 直接复用现有 Python 代码（src/），不重写业务逻辑
- 前端只负责展示和交互，所有状态来自 SQLite + WebSocket

---

## 二、Phase 1: MVP — 只读 Dashboard

**核心目标：能"看到"系统在做什么，不需要交互操作**

### 功能清单

| 功能 | 说明 |
|------|------|
| 执行列表 | 所有工作流执行记录（ID、状态、开始时间、耗时） |
| 执行详情 | 点击一条执行，查看节点执行顺序、每个 Agent 的输出摘要 |
| 实时状态 | WebSocket 推送当前运行的执行进度（节点切换、状态更新） |
| 系统概览 | 顶部卡片：运行中/成功/失败/总数 |

### 交付物

```
src/api/
├── server.py          # FastAPI 应用入口
├── routes/
│   ├── executions.py  # REST: GET /api/executions
│   └── ws.py          # WebSocket: /ws/stream/{thread_id}
└── models.py          # Pydantic 响应模型

web/
├── src/
│   ├── pages/
│   │   ├── Home.tsx       # 执行列表 + 系统概览
│   │   └── Execution.tsx  # 执行详情页
│   ├── components/
│   │   ├── ExecutionList.tsx
│   │   ├── ExecutionCard.tsx
│   │   ├── StatusBadge.tsx
│   │   └── LiveIndicator.tsx
│   └── lib/
│       └── websocket.ts   # WS 连接管理
├── package.json
└── vite.config.ts
```

### 不做的事

- ❌ 创建任务（CLI 操作）
- ❌ 修改配置（CLI 编辑 YAML）
- ❌ Agent 管理（CLI/配置文件管理）

### 技术选型

| 层 | 技术 |
|----|------|
| 后端 | FastAPI（复用现有 Python 项目） |
| 前端 | React + Vite + TypeScript |
| UI 库 | shadcn/ui（轻量、可定制） |
| 实时通信 | WebSocket |
| 数据源 | SQLite（复用现有 checkpointer） |

### 预估时间：1-2 天

---

## 三、Phase 2: 任务提交与交互

**核心目标：能在 Web 上发起和控制任务**

### 功能清单

| 功能 | 说明 |
|------|------|
| 新建任务 | 表单：任务描述、选择工作流模板、目标项目路径 |
| 任务控制 | 暂停 / 恢复 / 终止正在运行的执行 |
| 实时日志流 | 每个节点执行时实时展示 stdout/stderr |
| 文件预览 | 执行中 Agent 创建/修改的文件可在线查看 diff |

### 新增 API

```
POST   /api/executions         # 创建新执行
POST   /api/executions/{id}/pause
POST   /api/executions/{id}/resume
POST   /api/executions/{id}/cancel
GET    /api/executions/{id}/logs?node_id=xxx
GET    /api/executions/{id}/files?node_id=xxx
GET    /api/workflows           # 列出可用工作流模板
```

### 预估时间：3-4 天

---

## 四、Phase 3: 工作流可视化

**核心目标：直观看到任务执行图（类似 LangGraph Studio）**

### 功能清单

| 功能 | 说明 |
|------|------|
| DAG 可视化 | React Flow 渲染 Plan Graph 节点和依赖边 |
| 节点状态高亮 | 运行中（蓝）、成功（绿）、失败（红）、等待（灰） |
| 节点详情面板 | 点击节点：输入、输出、工具调用、耗时、Token |
| 并行执行展示 | 并行节点并排，依赖边动态高亮 |

### 依赖库

```json
{
  "reactflow": "^11.11.0"
}
```

### 预估时间：3-4 天

---

## 五、Phase 4: 配置管理

**核心目标：在 Web 上管理工作流配置**

### 功能清单

| 功能 | 说明 |
|------|------|
| 工作流列表 | 展示所有 YAML 配置的工作流模板 |
| 配置编辑器 | 在线编辑 YAML（语法高亮 + Schema 校验） |
| Agent 管理 | 已注册 Agent、能力声明、模型配置、启停 |
| 验证规则管理 | 增删改 Verifier 规则 |

### 新增 API

```
GET    /api/workflows/{name}     # 获取工作流 YAML
PUT    /api/workflows/{name}     # 更新工作流 YAML
GET    /api/agents               # 列出所有 Agent
PUT    /api/agents/{id}/enable   # 启用/禁用
GET    /api/verifiers            # 列出验证规则
POST   /api/verifiers            # 新增规则
DELETE /api/verifiers/{id}       # 删除规则
```

### 预估时间：4-5 天

---

## 六、Phase 5: 可观测性面板

**核心目标：运维级监控**

### 功能清单

| 功能 | 说明 |
|------|------|
| 成本面板 | Token 消耗、费用统计（按日/周/月、按 Agent、按工作流） |
| 成功率仪表 | 成功率趋势图、失败原因分布 |
| 性能指标 | 各节点平均耗时、P50/P95/P99 延迟 |
| 告警中心 | 阈值告警配置 + 告警历史 |

### 依赖库

```json
{
  "recharts": "^2.12.0"
}
```

### 预估时间：3-4 天

---

## 七、Phase 6: 高级功能

### 功能清单

| 功能 | 说明 |
|------|------|
| 执行历史对比 | 对比两次执行的输出差异、性能变化 |
| 知识库管理 | 项目级知识的增删查 |
| 团队协作 | 用户管理、权限控制、任务分配 |
| 导出/报表 | 导出执行报告为 PDF/Markdown |

### 预估时间：5-7 天

---

## 八、总览

| Phase | 名称 | 核心功能 | 预估时间 | 优先级 |
|-------|------|---------|---------|--------|
| 1 | 只读 Dashboard | 执行列表、详情、实时状态 | 1-2 天 | **P0** |
| 2 | 任务交互 | 新建任务、控制、日志、文件预览 | 3-4 天 | **P0** |
| 3 | 工作流可视化 | DAG 图、节点详情、并行展示 | 3-4 天 | **P1** |
| 4 | 配置管理 | YAML 编辑、Agent 管理、规则管理 | 4-5 天 | **P1** |
| 5 | 可观测性 | 成本、成功率、性能、告警 | 3-4 天 | **P2** |
| 6 | 高级功能 | 对比、知识库、协作、报表 | 5-7 天 | **P3** |

**推荐路径：** Phase 1 → 2 → 3，每个 Phase 可独立交付，不影响已有功能。

---

*创建时间: 2026-05-22*
