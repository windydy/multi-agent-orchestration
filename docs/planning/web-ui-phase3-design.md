# Phase 3 详细技术设计 — DAG 工作流可视化

## 1. 目标

为每条执行记录提供直观的 DAG 图展示，让用户一眼看清：
- 节点依赖关系
- 实时执行状态（运行中/成功/失败/等待）
- 节点耗时与 Token 消耗
- 并行执行路径

## 2. 方案设计

### 2.1 后端：新增 DAG API

**新增路由** `GET /api/executions/{thread_id}/dag`

返回 Plan Graph 的结构 + 当前执行状态：

```json
{
  "thread_id": "thread_abc123",
  "nodes": [
    {
      "id": "requirements",
      "label": "Requirements Agent",
      "status": "success",
      "started_at": "2026-05-22T14:00:00Z",
      "ended_at": "2026-05-22T14:00:15Z",
      "duration_ms": 15000,
      "token_usage": {"input": 300, "output": 800},
      "cost": 0.12,
      "output_summary": "Requirements doc generated"
    }
  ],
  "edges": [
    {"from": "requirements", "to": "design"},
    {"from": "design", "to": "develop"},
    {"from": "develop", "to": "review"},
    {"from": "develop", "to": "test"},
    {"from": "review", "to": "fix"},
    {"from": "test", "to": "fix"}
  ]
}
```

**数据源**：复用 `EventLog.get_execution()` 获取事件，`execution_read._build_nodes()` 聚合节点状态。

**新增数据结构**：
- `DAGResponse` (Pydantic) — nodes + edges
- `DAGNode` — 继承 NodeEvent + position info
- `DAGEdge` — from/to

**DAG 结构定义**：硬编码默认 workflow template 的图结构（`development` workflow），后续 Phase 4 从 YAML 配置读取。

### 2.2 前端：React Flow DAG 视图

**技术栈**：`@xyflow/react`（React Flow v12 新版包名）

**新增组件**：
- `DAGView` — 主 DAG 渲染容器
- `DAGNode` — 自定义节点（状态颜色、耗时、token 图标）
- `DAGEdge` — 自定义边（成功=绿色，失败=红色虚线）
- `NodeDetailPanel` — 右侧滑出面板，点击节点显示详情

**交互**：
- 自动布局：使用 `dagre` 计算节点位置
- 节点点击 → 右侧弹出详情面板
- 运行中的节点有脉冲动画
- 支持缩放/拖拽

**页面路由**：`/executions/{thread_id}` 页面增加 "Graph" tab

### 2.3 文件结构

```
src/api/
├── routes/
│   └── dag.py                  # GET /api/executions/{id}/dag

web/src/
├── pages/
│   └── ExecutionPage.tsx       # 新增 "Graph" tab
├── components/
│   ├── DAGView.tsx             # React Flow 容器
│   ├── DAGCustomNode.tsx       # 自定义节点渲染
│   ├── DAGCustomEdge.tsx       # 自定义边
│   └── NodeDetailPanel.tsx     # 右侧详情面板
├── lib/
│   └── dagLayout.ts            # dagre 自动布局逻辑
```

### 2.4 依赖

```bash
cd web && npm install @xyflow/react dagre
```

## 3. 验收标准

1. 打开执行详情页，切换到 Graph tab，显示完整的 DAG 图
2. 成功节点显示绿色，失败显示红色，运行中显示蓝色脉冲
3. 点击节点，右侧显示详情（输出摘要、耗时、Token、成本）
4. 空执行（无事件）显示灰色占位节点
5. 响应式布局，支持缩放/拖拽

## 4. P0 修复（来自评审）

- **P0-1**: DAG 路由需在 `routes/__init__.py` 中注册（import + include_router）
- **P0-2**: TDD 先写 `tests/api/test_dag.py`，覆盖空 DAG、完整图、失败节点、并行节点

## 5. 不做的事

- ❌ WebSocket 实时推送（后续 Phase 升级）
- ❌ 从 YAML 动态加载图结构（Phase 4 配置管理）
- ❌ 节点级文件 diff（Phase 2 已规划但未实现，继续往后推）
