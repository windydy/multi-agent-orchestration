# 端到端测试补充规划

> 基于对现有 664 个测试的审计，识别缺失的真实 E2E 测试场景，按优先级排列。

## 现状审计

| 维度 | 现状 |
|------|------|
| 总测试数 | 664 |
| E2E 覆盖 | 仅有 `test_e2e_real_execution.py`（结构验证，非真实执行） |
| 真实 LLM 调用 | 几乎为零，全是 Mock |
| API 集成 | FastAPI TestClient 级别的集成测试已覆盖 |
| 路由逻辑 | Fix cycle、review routing 等逻辑测试已覆盖 |
| 领域工具 | CICDTool/SecurityScanTool/DataAnalysisTool 等单元测试已覆盖 |

### 核心缺失

1. **没有任何测试真正调用 LLM API 执行任务** — 所有 agent 节点都是 Mock
2. **WorkflowRunner 全是 Mock** — `test_pipeline.py` 用 `AsyncMock` 替代 `app.ainvoke`
3. **API 到真实执行链路断裂** — REST API 的 `create_execution` 只写数据库，不触发真实工作流
4. **Bug Fix 全链路未真实验证** — 路由逻辑测试覆盖，但从未从"发现 bug → 修复 → 重新测试"走完一轮
5. **多项目管理、知识库、记忆等 Phase 8 功能没有 E2E 验证**

---

## 优先级 P0：最小真实执行链路

> **目标：证明系统能不调 Mock 地完成一次最小工作流。**

### 1. 真实 LLM 调用 — 单节点执行

**文件**: `tests/e2e/test_real_single_node.py`

**场景**:
- 配置一个只有 `develop` 节点的极简 workflow
- `ClaudeAgentWrapper` 使用真实 API key（从 `~/.hermes/config.yaml` 读取）
- 给 Agent 一个极小任务（如"写一个返回 'hello' 的 Python 函数"）
- 验证：
  - API 调用成功返回（非 Mock）
  - 输出文件确实被写入磁盘
  - Token 使用量 > 0
  - 费用计算 > 0

**验收标准**: 测试运行后，磁盘上出现 Agent 创建的 `.py` 文件，且内容正确。

**风险**: 耗时 ~10-30s，需要 API key 可用。用 `@pytest.mark.e2e` 标记，默认跳过。

### 2. 真实 Pipeline — 三节点串行

**文件**: `tests/e2e/test_real_pipeline.py`

**场景**:
- 任务: "实现一个计算器类，支持加减乘除"
- 节点: `developer → reviewer → tester`
- 三个 Agent 使用不同模型（与生产配置一致）
- 验证：
  - 每个节点都真实调用了 LLM
  - Reviewer 的输入包含 Developer 的输出
  - Tester 在 Developer 写的文件上运行 `pytest`
  - 最终状态为 success（或 fix cycle 后 success）

**验收标准**: EventLog 中有三个 `node_completed` 事件，且每个的 `token_usage` > 0。

---

## 优先级 P1：关键业务场景端到端

> **目标：覆盖用户最常使用的业务流程。**

### 3. Bug Fix 全链路 — 从发现到修复到通过

**文件**: `tests/e2e/test_real_fix_cycle.py`

**场景**:
- 预先准备一个有 bug 的项目（如除零未处理的 calculator）
- 启动 `tester` → 发现测试失败
- `fixer` 收到失败信息，修复代码
- `tester` 重新运行，验证通过
- 验证：
  - 修复前的代码和修复后的代码 diff 可追踪
  - 修复后所有测试通过
  - 迭代次数 = 1（一次修复成功）
- 额外场景: 测试多次失败的边界（达到 max_iterations）

### 4. REST API 创建执行 → 后台真实运行

**文件**: `tests/e2e/test_api_to_execution.py`

**场景**:
- `POST /api/executions` 创建一个执行
- 验证执行状态从 `running` → 各节点 `node_started/node_completed` → `execution_completed`
- WebSocket 推送实时事件
- 最终查询 `/api/executions/{id}` 获取完整 DAG

**当前问题**: `create_execution` 路由只写数据库，不启动真实工作流。这个测试会暴露这个 gap。

**验收标准**: 执行完成后，EventLog 和 execution_state.db 都有完整记录，且 DAG 端点返回正确结构。

### 5. 多工作流切换 E2E

**文件**: `tests/e2e/test_multi_workflow.py`

**场景**:
- 同一个项目中连续执行两个不同 workflow（development → bugfix）
- 验证执行隔离（thread_id 不同，数据库记录不串）
- 验证项目文件在两次执行间正确传递

---

## 优先级 P2：系统级集成

> **目标：验证组件间的集成点和边界条件。**

### 6. 知识库与记忆的 E2E

**文件**: `tests/e2e/test_knowledge_e2e.py`

**场景**:
- 执行一个任务，Agent 将经验写入 AgentMemory
- 执行第二个相似任务，验证 AgentMemory 被检索并注入 prompt
- 验证：第二次执行用了第一次的经验（可通过 prompt 日志验证）

### 7. 并发执行隔离

**文件**: `tests/e2e/test_concurrent_executions.py`

**场景**:
- 同时创建 3 个执行（不同 thread_id）
- 验证每个执行有独立的工作目录
- 验证数据库记录不冲突
- 验证 WebSocket 推送给正确的订阅者

### 8. 错误恢复与中断

**文件**: `tests/e2e/test_error_recovery.py`

**场景**:
- LLM 调用超时（mock network error）→ 验证系统重试
- LLM 返回无效 JSON → 验证 Verifier 捕获并触发 replan
- 执行中途 cancel → 验证状态正确回滚
- 数据库损坏 → 验证优雅降级

### 9. 动态 Workflow 编译 E2E

**文件**: `tests/e2e/test_dynamic_workflow_e2e.py`

**场景**:
- 给 PlannerAgent 一个任务描述
- Planner 生成 PlanGraph（真实 LLM 调用）
- DynamicWorkflowBuilder 从 PlanGraph 编译 LangGraph StateGraph
- 编译后的 app 可执行
- 验证生成的图结构与预期一致（节点、边、条件路由）

---

## 优先级 P3：基础设施与运维

> **目标：保证部署后系统的可观测性和稳定性。**

### 10. 可观测性端到端

**文件**: `tests/e2e/test_observability_e2e.py`

**场景**:
- 执行一次工作流
- 验证 metrics 被正确记录（token 用量、费用、延迟）
- 验证 tracing 信息完整（每个节点的输入/输出摘要）
- 查询 `/api/overview` 聚合统计与原始数据一致

### 11. 配置文件热加载

**文件**: `tests/e2e/test_config_reload.py`

**场景**:
- 修改 workflow YAML 配置（改模型或添加节点）
- 验证新执行使用新配置
- 验证旧执行不受影响

### 12. Agent 能力匹配与路由

**文件**: `tests/e2e/test_agent_routing_e2e.py`

**场景**:
- 注册 5 个不同类型的 Agent（DevOps, Security, Data, Architect, PM）
- 给一个复合任务（包含多个领域）
- 验证每个子任务路由到正确的 Agent
- 验证能力评分 match_score 正确

---

## 实施策略

### 标记约定

```python
@pytest.mark.e2e              # 需要真实 LLM 调用，默认跳过
@pytest.mark.slow             # 耗时 > 30s
@pytest.mark.integration      # 需要数据库/网络
```

运行方式:
```bash
# 快速测试（默认）
pytest tests/ -m "not e2e and not slow"

# 包含 E2E
pytest tests/ -m "e2e" --e2e-api-key=$DASHSCOPE_API_KEY

# 全部
pytest tests/
```

### conftest 补充

需要新增的 fixtures:
- `real_api_config` — 从 `~/.hermes/config.yaml` 读取 custom provider 配置
- `tmp_project` — 创建临时项目目录，测试后清理
- `buggy_project` — 预设有 bug 的项目（用于 fix cycle 测试）
- `api_server` — 启动真实 FastAPI 服务器（用 httpx 而非 TestClient）

### 执行顺序建议

| 阶段 | 测试数 | 预估耗时 |
|------|--------|----------|
| P0 (最小链路) | 2 | ~1 min |
| P1 (业务场景) | 3 | ~5 min |
| P2 (系统集成) | 4 | ~10 min |
| P3 (运维基建) | 3 | ~5 min |

### 预期总测试数增量

从 664 → ~676（新增 12 个 E2E 测试模块，每个模块 3-8 个测试用例，约 50-80 个新测试）
