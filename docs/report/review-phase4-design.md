# Phase 4 设计评审报告

> **评审对象**: `docs/planning/web-ui-phase4-design.md`
> **评审时间**: 2026-05-22

## 评审结论：✅ 通过，修复 3 个问题后开始实现

---

## P0 问题

### P0-1: 配置存储方案不一致

设计方案说"Phase 4 使用 SQLite 配置表"，但 2.5 Schema 校验部分说"接收 YAML 后 yaml.safe_load() 解析"。这两者有冲突：

- 如果存在 SQLite 表里，那 YAML 是序列化后的文本，每次 PUT 需要重新解析存储
- 如果读文件系统里的 YAML 文件，就不需要 SQLite 配置表

**修复**：明确 Phase 4 使用 SQLite 作为唯一存储，PUT 时解析 YAML 校验后存储 yaml_content 字符串。GET 时返回 yaml_content 字符串。

### P0-2: 缺少 Agent 持久化方案

现有的 `src/agents/` 目录下有硬编码的 Agent 类（DevOps、Security、Data 等）。Phase 4 的 Agent 管理是：
1. 只读展示已有的硬编码 Agent？
2. 还是可以动态注册新 Agent？

**修复**：Phase 4 先做 **只读展示 + 模型配置修改 + 启用/禁用**。动态注册新 Agent 类需要代码部署，不在 Phase 4 范围。

### P0-3: Verifier 规则没有数据模型

设计中提到 VerifierRule 有 condition 和 action 字段，但没有定义具体结构。前端怎么渲染？

**修复**：定义明确的 Pydantic 模型：
```python
class VerifierRule(BaseModel):
    id: str
    name: str
    condition: str  # "token_limit", "cost_threshold", "node_timeout"
    threshold: float
    action: str  # "warn", "fail", "retry"
    severity: str  # "low", "medium", "high"
    enabled: bool
```

---

## P1 问题

### P1-1: Monaco Editor 包体积大

Monaco Editor 完整版 ~20MB。对于 YAML 编辑来说可能过度。

**修复**：先评估 CodeMirror 6（更轻量），或者用 Monaco 的 CDN 异步加载方案。

### P1-2: Workflow 模板名称唯一性

PUT /api/config/workflows/{name} 如果 name 不存在是创建还是报错？需要明确语义。

**修复**：GET 不存在的 workflow 返回 404。PUT 不存在的 workflow 创建新的（upsert 语义）。

### P1-3: 缺少配置导入/导出

没有 API 支持批量导入/导出配置。

**修复**：Phase 5 再加，Phase 4 只做单个 CRUD。
