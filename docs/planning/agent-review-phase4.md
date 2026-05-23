# Phase 4 配置管理 — 独立评审报告

> **评审对象**: Phase 4 设计文档 + 实现代码
> **评审时间**: 2026-05-23
> **评审范围**: 设计文档 (`web-ui-phase4-design.md`), API 设计 (`routes/config.py`), 数据模型 (`services/config_store.py`), 前端实现 (`ConfigPage.tsx`, `YAMLEditor.tsx`, `AgentCard.tsx`, `VerifierTable.tsx`), 测试 (`tests/api/test_config.py`)
> **前置文档**: 已阅读 `review-phase4-design.md` 和 `review-phase4-code.md`，以下为独立发现

---

## 评审结论：⚠️ 有条件通过 — 需修复 4 个 P0 问题

---

## P0 问题

### P0-1: config_router 注册方式不一致，可能导致路由前缀重复

**文件**: `src/api/routes/config.py` (line 9), `src/api/server.py` (line 89)

`config.py` 中定义了 `router = APIRouter(tags=["api"])` — **没有 prefix**。
`server.py` 中直接 `app.include_router(config_router)` — **也没有加 prefix**。

但其他通过 `__init__.py` 注册的路由（如 health, overview）使用 `router = APIRouter(prefix="/api")` 再 include 到带 `/api` 前缀的父 router 中。

对比发现：
- `dag_router` (line 7 of dag.py): `APIRouter(tags=["api"])` — 无前缀 → `server.py` line 88: `app.include_router(dag_router)` — 正确
- `config_router` (line 9 of config.py): `APIRouter(tags=["api"])` — 无前缀 → `server.py` line 89: `app.include_router(config_router)` — 一致

**但** `config.py` 里的路由定义已经包含了完整路径如 `/api/config/workflows`（line 97）。这意味着路由路径中硬编码了 `/api` 前缀。

**问题**: 如果未来 `config_router` 被移入 `__init__.py` 的父 router（它带 `prefix="/api"`），路由会变成 `/api/api/config/workflows` — 双重前缀。

**修复**: 在 `config.py` 中将路由路径从 `/api/config/workflows` 改为 `/config/workflows`，保持与其他路由模块一致的约定。

---

### P0-2: Workflow 缺少 DELETE 端点

**文件**: 设计文档 line 18-21, `routes/config.py` line 97-124

设计文档和实现都只有 `GET` + `PUT`（upsert），没有 `DELETE`。对于配置管理系统，用户应该能够删除不再需要的工作流配置。

**影响**: 一旦创建了错误的工作流，只能通过手动修改数据库清除。

**修复**: 增加 `DELETE /api/config/workflows/{name}` 端点。

---

### P0-3: Workflow YAML 校验不够充分

**文件**: `services/config_store.py` line 189-201

当前校验只检查：
1. YAML 语法合法性
2. 顶层是 dict
3. 有 `nodes` 且为 list
4. 有 `edges` 字段

**缺失的校验**:
- **nodes 与 edges 一致性**: 设计文档 line 78 明确说"验证节点名与 edges 引用一致"，但 `config_store.py` 完全没实现此逻辑。
- **node 结构校验**: nodes 列表中的元素是否包含必需的 `name` 字段？
- **edges 结构校验**: edges 是否有 `from` 和 `to` 字段？
- **节点名唯一性**: nodes 列表中是否有重复名称？
- **edges 自环检测**: 是否有 `from == to`？

**修复**: 补充 edge-node 一致性校验和结构校验。

```python
# 校验节点名集合
node_names = {n["name"] for n in parsed["nodes"] if isinstance(n, dict) and "name" in n}
# 校验 edges 引用
for edge in parsed.get("edges", []):
    if not isinstance(edge, dict):
        raise ValueError("Each edge must be a mapping")
    if "from" not in edge or "to" not in edge:
        raise ValueError("Each edge must have 'from' and 'to' fields")
    if edge["from"] not in node_names:
        raise ValueError(f"Edge references unknown node: {edge['from']}")
    if edge["to"] not in node_names:
        raise ValueError(f"Edge references unknown node: {edge['to']}")
```

---

### P0-4: Agent 启用/禁用后不会通知运行中的 Execution

**文件**: `services/config_store.py` line 242-265, `src/api/services/execution_manager.py`

`update_agent` 修改了 SQLite 中的 `enabled` 字段，但 `ExecutionManager` 在执行任务时如何感知到 agent 被禁用？

当前没有机制：
- ExecutionManager 没有订阅 ConfigStore 的变更
- 没有 agent 状态变更事件广播
- 如果正在执行的任务使用了一个被禁用的 agent，它会继续运行直到完成

**影响**: "Agent 启用/禁用后立即生效"（验收标准 #3）无法实现。

**修复（Phase 4 可接受的方案）**:
- 方案 A: ExecutionManager 在调度每个 node 前检查 ConfigStore 中 agent 的 enabled 状态
- 方案 B: 在验收标准中注明"对新建 execution 生效"，不影响运行中的任务（推荐，改动最小）

---

## P1 问题

### P1-1: AgentCard model 输入框每次 onChange 立即发送 API 请求

**文件**: `web/src/components/AgentCard.tsx` line 30-34

```tsx
onChange={(e) => onModelChange(agent.id, e.target.value)}
```

`ConfigPage.handleAgentModelChange` 每次 onChange 触发 `fetch PUT`。用户输入 "gpt-4o" 会触发 6 次 API 调用（每个字符一次）。

**修复**: 使用 `onBlur` 替代 `onChange`，或添加 debounce（300ms）。

---

### P1-2: Verifier 创建/更新时后端未校验 condition 和 action 的枚举值

**文件**: `routes/config.py` line 80-92

`VerifierCreateRequest` 的 `condition` 和 `action` 字段是自由字符串，没有限制为合法枚举值。用户可以创建 `condition: "foobar"` 这种无效规则。

**修复**: 使用 `Literal` 类型限制：
```python
from typing import Literal
ConditionType = Literal["token_limit", "cost_threshold", "node_timeout"]
ActionType = Literal["warn", "fail", "retry"]
SeverityType = Literal["low", "medium", "high"]
```

---

### P1-3: ConfigStore `_create_tables` 在多线程下的竞态条件

**文件**: `services/config_store.py` line 111-117, 124-173

`_get_conn` 在首次连接时调用 `_create_tables`，但 `_create_tables` 不在 `_write_lock` 保护下。虽然 `CREATE TABLE IF NOT EXISTS` 是幂等的，但 seed 逻辑（line 159-173）在多个线程首次连接时可能执行多次 INSERT。

**实际风险**: 因为 seed 前有 `COUNT(*)` 检查，且 SQLite 在同一连接内序列化执行，实际冲突概率极低。但 `__init__` 和 `_ensure_db` 都调用 `_create_tables`，存在重复逻辑。

**修复**: 将 `_create_tables` 的调用限制在 `__init__` 中单次执行，`_get_conn` 中不再调用。

---

### P1-4: Workflow 名称缺少输入校验

**文件**: `routes/config.py` line 115-124

`upsert_workflow(name: str, ...)` 的 `name` 参数没有长度限制、字符限制。用户可以传入空字符串、包含 SQL 特殊字符的名称。

**修复**: 
- 路径参数 name 应有 `min_length=1` 约束
- 建议限制为 `[a-zA-Z0-9_-]+` 格式（正则校验）

---

### P1-5: 删除 Verifier 规则时没有关联检查

**文件**: `services/config_store.py` line 340-345

如果某个 Verifier 规则正在被运行中的 execution 使用，删除后可能导致运行时异常。

**修复**: Phase 4 可接受不做，但应在文档中标注为已知限制。

---

## P2 问题

### P2-1: YAMLEditor 前端验证与后端验证不一致

**文件**: `web/src/components/YAMLEditor.tsx` line 19-24

前端只做 `jsyaml.load()` 语法校验，不校验 `nodes`/`edges` 结构。用户可能看到前端验证通过（绿色），但后端返回 422。

**修复**: 前端也补充 nodes/edges 校验逻辑，或者在后端返回 422 时显示更友好的错误信息。

---

### P2-2: Monaco Editor 离线环境无法加载

**文件**: `web/src/components/YAMLEditor.tsx`

`@monaco-editor/react` 默认从 CDN (jsdelivr) 加载 Monaco worker 文件。离线或内网环境会失败。

**修复**: 配置 `monaco` 的 `paths.vs` 选项指向本地 node_modules。

---

### P2-3: ConfigPage 中 fetch 没有检查 HTTP 响应的 ok 状态

**文件**: `web/src/pages/ConfigPage.tsx` line 22-25

```tsx
fetch('/api/config/agents').then(r => r.json()),
```

如果 API 返回 500 或 404，`r.json()` 仍会尝试解析，可能抛出 Unexpected token 错误而不是有意义的错误信息。

**修复**: 在 `.then(r => r.json())` 前加 `if (!r.ok) throw new Error(...)` 检查。

---

### P2-4: VerifierTable 删除操作没有确认对话框

**文件**: `web/src/components/VerifierTable.tsx` line 143-148

点击 ✕ 按钮直接删除，没有确认提示。

**修复**: 添加 `window.confirm("确认删除此规则？")` 确认。

---

### P2-5: `workflows.py` 与 `config.py` 存在概念重叠

**文件**: `src/api/routes/workflows.py` line 32-47, `src/api/routes/config.py` line 97-103

`workflows.py` 提供 `GET /api/workflows` 返回硬编码的 workflow 模板列表。
`config.py` 提供 `GET /api/config/workflows` 返回 SQLite 中存储的 workflow 配置。

两个端点都叫 "workflows"，语义不同但路径相似，容易混淆。Phase 5 如果需要统一，需要设计迁移方案。

---

## 正面评价

1. **测试覆盖良好**: `tests/api/test_config.py` 覆盖了 CRUD 的主要场景、错误路径和边界情况
2. **SQLite 选型合理**: 对于 Phase 4 的配置管理规模，SQLite 比文件系统更可靠，支持并发读写
3. **dataclass + sqlite3.Row 模式清晰**: `config_store.py` 的数据层设计简洁，JSON 序列化 capabilities 字段处理得当
4. **前端类型同步**: TypeScript 接口定义与 Pydantic models 一一对应
5. **线程安全考虑**: 使用 `threading.local()` 管理 SQLite 连接 + `_write_lock` 保护写操作
6. **upsert 语义合理**: `ON CONFLICT DO UPDATE` 实现了 PUT 的幂等性

---

## 总结统计

| 优先级 | 数量 | 状态 |
|--------|------|------|
| P0 | 4 | 需修复 |
| P1 | 5 | 建议修复 |
| P2 | 5 | 可选优化 |

**总体结论**: Phase 4 设计方向正确，核心架构合理。P0-1（路由前缀一致性）和 P0-3（YAML 校验缺失）应在实现前修复。P0-4 可以通过调整验收标准解决。其余问题可在后续迭代中逐步优化。
