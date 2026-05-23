# Phase 3 代码评审报告

> **评审对象**: Phase 3 DAG 可视化相关代码
> **评审时间**: 2026-05-22

---

## P0 问题

### P0-1: DAGView 缺少空节点容错

`src/components/DAGView.tsx` 中 `dag.nodes.map()` 没有处理 `dag.nodes` 为空的情况。当执行没有任何节点事件时，React Flow 会渲染空白画布，没有任何提示。

**修复**：当 `dag.nodes.length === 0` 时显示 "No nodes recorded yet" 占位提示。

### P0-2: DAG 路由双重注册风险

`src/api/routes/__init__.py` 注册了 `dag_router`，同时 `src/api/server.py` 也直接 `app.include_router(dag_router)`。这会导致路由注册两次，可能产生 405 或重复路由问题。

**检查**: 需要确认 server.py 是否也 include 了 dag_router。

### P0-3: NodeDetailPanel 使用隐式 any 类型

`DAGView.tsx` 中 `selectedNode` 类型是 `any`，`NodeDetailPanel` 的 `data` 参数也是 `any`。在 strict TypeScript 下应该定义明确类型。

**修复**：定义 `DAGNodeData` 类型接口。

---

## P1 问题

### P1-1: dagre layout 可能重复计算

每次渲染都调用 `getLayoutedElements()`，即使节点数据没有变化。React Flow 的 fitView 已经能自动调整视口。

**修复**：用 useMemo 缓存 layout 计算结果。

### P1-2: 边的样式没有区分状态

所有边都是 `#374151` 灰色。但实际应该：如果目标节点是 failed，边应该显示红色；如果源节点和目标节点都 success，边显示绿色。

**修复**：根据节点状态动态设置边的颜色。

### P1-3: React Flow 没有 nodeTypes 类型安全

`const nodeTypes = { dagCustom: DAGCustomNode }` 没有类型约束。

**修复**：使用 `@xyflow/react` 的 NodeTypes 类型。

### P1-4: 缺少 DAG API 的响应类型标注

`fetchDAG()` 返回类型是 `any`，应该标注为 `Promise<DAGResponse>`。

---

## P2 问题

### P2-1: 暗色模式下 Controls 按钮不明显

React Flow 的 Controls 组件默认浅色图标，在暗色主题下对比度低。

### P2-2: DAG 组件没有响应式高度

`h-[500px]` 固定高度，在小屏设备上可能过大。
