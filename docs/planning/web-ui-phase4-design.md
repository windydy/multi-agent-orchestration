# Phase 4 详细技术设计 — 配置管理

## 1. 目标

在 Web 上管理工作流配置：
- 查看已注册的工作流模板（YAML 配置）
- 在线编辑工作流 YAML（语法高亮 + Schema 校验）
- Agent 管理：已注册 Agent、能力声明、模型配置、启用/禁用
- Verifier 规则管理：增删改验证规则

## 2. 方案设计

### 2.1 后端 API

**新增路由**：

```
GET    /api/config/workflows           # 列出所有工作流模板
GET    /api/config/workflows/{name}    # 获取工作流 YAML 内容
PUT    /api/config/workflows/{name}    # 更新工作流 YAML
GET    /api/config/agents              # 列出所有已注册 Agent
GET    /api/config/agents/{id}         # 获取 Agent 详情
PUT    /api/config/agents/{id}         # 更新 Agent 配置（模型、启用状态）
GET    /api/config/verifiers           # 列出验证规则
POST   /api/config/verifiers           # 新增验证规则
PUT    /api/config/verifiers/{id}      # 更新验证规则
DELETE /api/config/verifiers/{id}      # 删除验证规则
```

**数据存储**：Phase 4 使用 SQLite 配置表（后续可迁移到文件/远程存储）。

**新增数据模型**：
- `WorkflowConfig` — name, description, yaml_content, created_at, updated_at
- `AgentConfig` — id, name, capabilities, model, enabled, description
- `VerifierRule` — id, name, condition, action, severity, enabled

### 2.2 前端

**新增页面/组件**：
- `ConfigPage` — 三 tab 布局 (Workflows / Agents / Verifiers)
- `YAMLEditor` — Monaco Editor 或 CodeMirror 实现 YAML 编辑 + 语法校验
- `AgentCard` — 显示 Agent 能力、模型、启用状态
- `VerifierTable` — 规则列表，支持增删改

**依赖**：
```bash
npm install @monaco-editor/react monaco-editor js-yaml
```

### 2.3 文件结构

```
src/api/
├── routes/
│   └── config.py              # 配置管理路由

web/src/
├── pages/
│   └── ConfigPage.tsx
├── components/
│   ├── YAMLEditor.tsx
│   ├── AgentCard.tsx
│   └── VerifierTable.tsx
```

### 2.4 数据库迁移

新增 SQLite 表：
- `workflow_configs` — YAML 配置存储
- `agent_configs` — Agent 注册信息
- `verifier_rules` — 验证规则

### 2.5 Schema 校验

PUT /api/config/workflows/{name} 接收 YAML 后：
1. 用 `yaml.safe_load()` 解析
2. 验证必填字段（name, nodes, edges）
3. 验证节点名与 edges 引用一致
4. 返回校验错误或 200 OK

## 3. 验收标准

1. GET /api/config/workflows 返回所有注册的工作流
2. PUT 非法 YAML 返回 422 + 校验错误信息
3. Agent 启用/禁用后立即生效
4. 前端 YAML 编辑器实时语法高亮
5. 新增 Verifier 规则后可在列表中看到

## 4. P0 预修复（基于 Phase 1-3 教训）

- **P0-1**: Config 路由必须在 `__init__.py` 注册，同时 server.py 不能重复注册
- **P0-2**: Config API 必须有完整 TDD 测试覆盖
- **P0-3**: SQLite 表创建使用 migration 模式（幂等），避免重复建表冲突

## 5. 不做的事

- ❌ 文件级 YAML 同步（直接读写 YAML 文件）— Phase 5
- ❌ 多用户权限控制 — Phase 6
- ❌ 配置版本历史 — Phase 5
