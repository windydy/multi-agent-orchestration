# Phase 3 设计评审报告

> **评审对象**: `docs/planning/web-ui-phase3-design.md`
> **评审时间**: 2026-05-22

## 评审结论：✅ 通过，修复 2 个问题后开始实现

---

## P0 问题

### P0-1: DAG 路由未注册到 `__init__.py`

设计文档提到新增 `src/api/routes/dag.py`，但没提到需要修改 `src/api/routes/__init__.py` 来注册这个路由。Phase 1-2 犯过同样的错误。

**修复**：在 `__init__.py` 中 import 并 include_router。

### P0-2: 缺少 DAG 单元测试

设计文档提到新增 API 端点，但没有对应的测试计划。Phase 2 的教训是：没有测试的代码在重构时会退化。

**修复**：TDD 先写 `tests/api/test_dag.py`，覆盖：
- 空执行返回空 DAG
- 有节点的执行返回完整图
- 失败节点的边和状态
- 并行节点的边

---

## P1 问题

### P1-1: DAG 图结构应该支持多种 workflow

当前硬编码 `development` workflow。虽然 Phase 4 才做 YAML 配置，但后端应该至少能根据 `workflow` 字段返回不同的图结构。

**修复**：增加一个 `_WORKFLOW_TEMPLATES` 字典，默认包含 `development`，后续可扩展。

### P1-2: NodeDetailPanel 需要与执行详情的节点信息对齐

Phase 1-2 的 `execution_read.py` 已经有 `_build_nodes()` 聚合节点数据。DAG 的 NodeDetailPanel 应该复用同一个数据结构，不要创建新的 Pydantic model。

**修复**：DAGResponse 中的 nodes 复用 NodeEvent 结构，增加 `position` 字段给前端。

### P1-3: @xyflow/react 需要确认兼容性

React Flow v12 改名为 `@xyflow/react`，API 有较大变化。需要确认与项目现有的 React 18 + TypeScript 兼容。

**修复**：安装后验证 `npm run build` 通过。
