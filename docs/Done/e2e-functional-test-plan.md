# E2E 功能性验证测试方案

> 目标：设计一张完整的"一图一测试"方案，覆盖 multi-agent-orchestration 系统的核心功能链路，确保系统能真实执行任务而非 Mock。

---

## 一、现状诊断

| 维度 | 现状 | 风险等级 |
|------|------|---------|
| 总测试数 | ~664 个 | - |
| 真实 LLM 调用测试 | 0 个 | 🔴 致命 |
| E2E 执行链路 | 仅有 `test_e2e_real_execution.py`（结构验证，非真实执行） | 🔴 致命 |
| API → 工作流执行 | `create_execution` 路由只写数据库，不触发工作流 | 🔴 致命 |
| Bug Fix 全链路 | 路由逻辑有单元测试，但未走完"发现→修复→验证" | 🟠 高 |
| Phase 8 功能 | 多项目管理/知识库/Web UI 无 E2E 验证 | 🟠 高 |
| 并发执行 | 无测试验证隔离性 | 🟡 中 |
| 错误恢复 | 无测试覆盖超时/重试/降级 | 🟡 中 |

### 核心问题

**系统从未真正调用过一次 LLM API 来完成任务。** 所有测试要么用 `AsyncMock` 替代 `app.ainvoke`，要么只验证组件创建成功。这导致：
- 无法确认 `ClaudeAgentWrapper` 与 DashScope API 的真实兼容性
- 无法确认 LangGraph StateGraph 编译后能实际执行
- 无法确认工具调用（write_file/bash/search）在真实环境中工作
- 无法确认多 Agent 间的上下文传递和状态流转

---

## 二、测试架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    E2E 测试金字塔                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  L3 ┌─────────────────────────────────────────────────────┐    │
│     │  系统级 E2E（真实 API + 完整工作流 + 多 Agent）       │    │
│     │  test_real_api_to_execution                         │    │
│     │  test_real_multi_workflow                           │    │
│     │  test_real_concurrent_executions                    │    │
│     └─────────────────────────────────────────────────────┘    │
│                              ▲                                  │
│  L2 ┌────────────────────────┼─────────────────────────────┐    │
│     │  业务级 E2E（真实 LLM + 关键场景）                     │    │
│     │  test_real_single_node ──────────────────────────────┤    │
│     │  test_real_developer_reviewer_tester ────────────────┤    │
│     │  test_real_fix_cycle ────────────────────────────────┤    │
│     │  test_real_knowledge_memory ─────────────────────────┤    │
│     │  test_real_dynamic_workflow ─────────────────────────┤    │
│     └─────────────────────────────────────────────────────┘    │
│                              ▲                                  │
│  L1 ┌────────────────────────┼─────────────────────────────┐    │
│     │  组件级验证（结构验证 + 无 Mock）                      │    │
│     │  test_config_loading_real                             │    │
│     │  test_executor_real_creation                          │    │
│     │  test_plangraph_real_build                            │    │
│     │  test_verifier_real_rules                             │    │
│     │  test_no_mock_components                              │    │
│     └─────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

执行流程（单条 E2E 链路）:

User/API ──POST /api/executions──▶ ExecutionManager.create_execution()
                                        │
                                        ▼
                                   写入 execution_state.db
                                   写入 events.db (execution_started)
                                        │
                                        ▼ (需要修复：触发真实工作流)
                                   WorkflowRunner.run()
                                        │
                                        ▼
                                   LangGraph StateGraph.ainvoke()
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
              develop node        reviewer node       tester node
              (qwen3.6-plus)     (kimi-k2.5)        (qwen3.6-plus)
                    │                   │                   │
                    ▼                   ▼                   ▼
              ClaudeAgentWrapper  ClaudeAgentWrapper  ClaudeAgentWrapper
              → DashScope API     → DashScope API     → DashScope API
              → write_file        → read_file         → bash(pytest)
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        ▼
                                  输出文件 / 测试结果
                                        │
                                        ▼
                                   EventLog 记录所有事件
                                   execution_state.db 更新状态
                                        │
                                        ▼
                                  GET /api/executions/{id}
                                  返回完整 DAG + 所有事件
```

---

## 三、测试用例详细设计

### L1：组件级验证（已有 `test_e2e_real_execution.py`，需补充）

#### 1.1 配置加载真实验证
- **文件**: `tests/e2e/test_e2e_components.py`
- **验证**: 从 `config/workflows/phase8-bootstrap.yaml` 加载，检查所有字段非空
- **验收**: 4 个 executor 配置都正确，模型名称、工具列表、system prompt 都有值

#### 1.2 Executor 真实创建
- **验证**: `AgentExecutor` 包装的是 `ClaudeAgentWrapper` 而非 Mock
- **验证**: `ClaudeAgentWrapper._client` 和 `_async_client` 都成功初始化
- **验证**: API Key 从 Hermes config.yaml 正确读取
- **验收**: `isinstance(exec._agent, ClaudeAgentWrapper)` 为 True

#### 1.3 LangGraph 编译验证
- **验证**: `ConfigurableWorkflowBuilder.build()` 返回非 None 的 CompiledStateGraph
- **验证**: 图的节点数与配置中的 executor 数一致
- **验收**: `app.get_graph()` 返回的图结构正确

#### 1.4 Verifier 真实 Shell 执行
- **验证**: `VerifierFramework` 执行 `python --version` 返回成功
- **验收**: 测试结果包含真实的 Python 版本信息

#### 1.5 无 Mock 组件扫描
- **验证**: `src/` 目录中没有 `MockExecutor`、`FakeAgent` 等类
- **验收**: grep 返回空结果

---

### L2：业务级 E2E（核心新增）

#### 2.1 真实单节点执行
- **文件**: `tests/e2e/test_real_single_node.py`
- **标记**: `@pytest.mark.e2e @pytest.mark.slow`
- **场景**:
  - 极简 workflow：只有 `developer` 节点
  - 任务：`"写一个 Python 函数 def hello(): return 'hello world'"`
  - 使用真实 API Key（从 `~/.hermes/config.yaml` 读取）
- **验证**:
  1. `ClaudeAgentWrapper.run()` 成功调用 DashScope API
  2. 输出中包含 `hello` 函数定义
  3. 生成的 `.py` 文件写入磁盘，内容正确
  4. `token_usage.input > 0`, `token_usage.output > 0`
  5. `cost > 0`
  6. `metadata.model == "qwen3.6-plus"`
- **验收标准**: 测试运行后，临时目录中存在 Agent 创建的 `.py` 文件，且 `python -c "from file import hello; assert hello() == 'hello world'"` 通过

#### 2.2 真实三节点串行 Pipeline
- **文件**: `tests/e2e/test_real_pipeline.py`
- **标记**: `@pytest.mark.e2e @pytest.mark.slow`
- **场景**:
  - 任务：`"实现一个 Calculator 类，支持加减乘除，包含边界处理"`
  - 节点：`developer → reviewer → tester`
  - 三个 Agent 使用不同模型（与生产一致）
- **验证**:
  1. 每个节点都真实调用 LLM（token_usage > 0）
  2. Reviewer 的输入包含 Developer 的完整输出
  3. Tester 在 Developer 写的文件上运行 `pytest`
  4. EventLog 中有 3 个 `node_completed` 事件
  5. 最终状态为 `success` 或经过 fix cycle 后 `success`
  6. 生成的文件在 workspace 中可访问
- **验收标准**: EventLog 和 execution_state.db 都有完整记录，且最终测试通过率 ≥ 80%

#### 2.3 真实 Bug Fix 全链路
- **文件**: `tests/e2e/test_real_fix_cycle.py`
- **标记**: `@pytest.mark.e2e @pytest.mark.slow`
- **场景**:
  - 预设一个有 bug 的项目（除零未处理的 Calculator）
  - 启动 `tester` → 发现测试失败
  - `fixer` 收到失败信息，修复代码
  - `tester` 重新运行，验证通过
- **验证**:
  1. 修复前后的代码 diff 可追踪
  2. 修复后所有测试通过
  3. 迭代次数 = 1（一次修复成功）
  4. EventLog 记录完整的 fix cycle 事件序列
- **额外场景**: 测试多次失败的边界（达到 max_iterations 后标记为 failed）

#### 2.4 知识库与记忆 E2E
- **文件**: `tests/e2e/test_knowledge_e2e.py`
- **标记**: `@pytest.mark.e2e`
- **场景**:
  1. 执行任务 A：`"实现一个 Python 快速排序算法"`
  2. Agent 将经验写入 AgentMemory（如"快速排序需要注意边界条件"）
  3. 执行任务 B：`"实现一个归并排序算法"`（相似但不相同）
  4. 验证 AgentMemory 被检索并注入 prompt
- **验证**:
  1. 第二次执行的 prompt 中包含第一次的经验
  2. 可通过 prompt 日志或 embedding 相似度验证
  3. AgentMemory 数据库中有两条相关记录

#### 2.5 动态 Workflow 编译 E2E
- **文件**: `tests/e2e/test_dynamic_workflow_e2e.py`
- **标记**: `@pytest.mark.e2e`
- **场景**:
  1. `PlannerAgent` 接收任务描述（真实 LLM 调用）
  2. 生成 PlanGraph（节点、依赖关系、执行顺序）
  3. `DynamicWorkflowBuilder` 从 PlanGraph 编译 LangGraph StateGraph
  4. 编译后的 app 可执行
- **验证**:
  1. PlanGraph 的节点数 ≥ 2
  2. 编译后的图结构与 PlanGraph 一致
  3. 条件路由（如 review → pass/fail）正确配置
  4. 生成的图可被 `app.ainvoke()` 执行

---

### L3：系统级 E2E

#### 3.1 REST API 创建执行 → 后台真实运行
- **文件**: `tests/e2e/test_real_api_to_execution.py`
- **标记**: `@pytest.mark.e2e @pytest.mark.integration`
- **场景**:
  1. `POST /api/executions` 创建一个执行
  2. 验证执行状态从 `running` → 各节点完成 → `execution_completed`
  3. WebSocket 推送实时事件
  4. 最终查询 `/api/executions/{id}` 获取完整 DAG
- **当前问题**: `create_execution` 路由只写数据库，**不启动真实工作流**
- **需要修复**:
  - 在 `executions.py` 的 `create_execution` 路由中，创建 ExecutionHandle 后需要启动后台任务：
  ```python
  # 伪代码
  task = asyncio.create_task(run_workflow(handle.thread_id, req.task, req.workflow))
  await em.bind_task(handle.thread_id, task)
  ```
- **验收标准**: 执行完成后，EventLog 和 execution_state.db 都有完整记录，DAG 端点返回正确结构

#### 3.2 多工作流切换 E2E
- **文件**: `tests/e2e/test_real_multi_workflow.py`
- **标记**: `@pytest.mark.e2e`
- **场景**:
  1. 同一个项目中连续执行两个不同 workflow（development → bugfix）
  2. 验证执行隔离（thread_id 不同，数据库记录不串）
  3. 验证项目文件在两次执行间正确传递

#### 3.3 并发执行隔离
- **文件**: `tests/e2e/test_real_concurrent_executions.py`
- **标记**: `@pytest.mark.e2e @pytest.mark.slow`
- **场景**:
  1. 同时创建 3 个执行（不同 thread_id）
  2. 验证每个执行有独立的工作目录
  3. 验证数据库记录不冲突
  4. 验证 WebSocket 推送给正确的订阅者

---

## 四、实施计划

### 阶段 1：基础设施准备（1-2 小时）

1. **新增 `conftest.py` fixtures**:
   - `real_api_config` — 从 `~/.hermes/config.yaml` 读取 custom provider
   - `tmp_project` — 创建临时项目目录，测试后清理
   - `buggy_project` — 预设有 bug 的项目
   - `api_server` — 启动真实 FastAPI 服务器（用 httpx 而非 TestClient）

2. **创建 `tests/e2e/` 目录结构**:
   ```
   tests/e2e/
   ├── __init__.py
   ├── conftest.py          # E2E 专用 fixtures
   ├── test_e2e_components.py    # L1: 组件级验证
   ├── test_real_single_node.py  # L2: 单节点
   ├── test_real_pipeline.py     # L2: 三节点
   ├── test_real_fix_cycle.py    # L2: Bug Fix
   ├── test_knowledge_e2e.py     # L2: 知识库
   ├── test_dynamic_workflow_e2e.py  # L2: 动态编译
   ├── test_real_api_to_execution.py # L3: API 集成
   ├── test_real_multi_workflow.py   # L3: 多工作流
   └── test_real_concurrent_executions.py  # L3: 并发
   ```

3. **标记约定**:
   ```python
   @pytest.mark.e2e              # 需要真实 LLM 调用，默认跳过
   @pytest.mark.slow             # 耗时 > 30s
   @pytest.mark.integration      # 需要数据库/网络
   ```

### 阶段 2：核心修复（2-3 小时）

**问题**: `create_execution` 路由只写数据库，不触发真实工作流

**修复方案**:
```python
# src/api/routes/executions.py
@router.post("/executions", response_model=CreateExecutionResponse, status_code=201)
async def create_execution(req: CreateExecutionRequest):
    em = _get_em()
    log = _get_log()
    handle = await em.create_execution(...)
    log.log(handle.thread_id, "execution_started", ...)
    
    # 新增：启动后台工作流任务
    async def run_workflow_task():
        try:
            from src.workflows.runner import WorkflowRunner
            from src.workflows.config_builder import ConfigurableWorkflowBuilder
            # 加载配置，构建工作流，执行
            runner = WorkflowRunner(...)
            result = await runner.run(req.task, project_path, thread_id=handle.thread_id)
            await em.complete_execution(handle.thread_id, 
                status="completed" if result["success"] else "failed")
        except Exception as e:
            await em.complete_execution(handle.thread_id, status="failed")
    
    task = asyncio.create_task(run_workflow_task())
    await em.bind_task(handle.thread_id, task)
    
    return CreateExecutionResponse(...)
```

### 阶段 3：测试实现（4-6 小时）

按优先级实现：
1. P0: `test_real_single_node.py` + `test_real_pipeline.py`
2. P1: `test_real_fix_cycle.py` + `test_real_api_to_execution.py`
3. P2: `test_knowledge_e2e.py` + `test_dynamic_workflow_e2e.py`
4. P3: `test_real_multi_workflow.py` + `test_real_concurrent_executions.py`

### 阶段 4：验证与运行

```bash
# 运行组件级验证（快速）
pytest tests/e2e/test_e2e_components.py -v

# 运行单个 E2E 测试
pytest tests/e2e/test_real_single_node.py -v -m e2e

# 运行所有 E2E 测试
pytest tests/e2e/ -v -m e2e

# 运行全部测试（包括 E2E）
pytest tests/ -v
```

---

## 五、验收标准

### 必须达成（P0）

1. ✅ **系统能真实调用一次 LLM API 并完成任务**
   - `test_real_single_node.py` 通过
   - 生成的文件在磁盘上可验证
   - Token 使用量和费用 > 0

2. ✅ **三节点 Pipeline 能完整执行**
   - `test_real_pipeline.py` 通过
   - EventLog 有 3 个 node_completed 事件
   - 每个事件 token_usage > 0

3. ✅ **create_execution API 能触发真实工作流**
   - `test_real_api_to_execution.py` 通过
   - 执行完成后状态正确
   - DAG 端点返回完整结构

### 建议达成（P1）

4. ✅ Bug Fix 全链路走完一轮
5. ✅ 知识库与记忆能跨执行检索
6. ✅ 动态 Workflow 编译后可执行

### 可选（P2）

7. ✅ 多工作流切换隔离正确
8. ✅ 并发执行不冲突
9. ✅ 错误恢复机制工作

---

## 六、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| API 调用超时 | 测试失败 | 设置 120s 超时，用 `@pytest.mark.timeout` |
| API Key 不可用 | 全部 E2E 失败 | 从 Hermes config.yaml 读取，测试前检查 |
| 模型返回无效 JSON | 解析失败 | Verifier 捕获并触发 replan |
| LLM 输出不符合预期 | 验证失败 | 使用宽松断言（如"包含 hello 函数"而非精确匹配） |
| 测试耗时过长 | CI 超时 | 用 `@pytest.mark.slow` 标记，默认跳过 |
| 磁盘空间不足 | 文件写入失败 | 用 `tmp_path` fixture，测试后自动清理 |

---

## 七、执行时间预估

| 阶段 | 任务 | 预估时间 |
|------|------|---------|
| 阶段 1 | 基础设施（fixtures、目录、标记） | 1-2h |
| 阶段 2 | 核心修复（create_execution 路由） | 2-3h |
| 阶段 3 | 测试实现（10 个测试文件） | 4-6h |
| 阶段 4 | 验证运行 + 调试 | 2-3h |
| **总计** | | **9-14h** |

### 测试运行时间

| 类别 | 测试数 | 单次运行耗时 |
|------|--------|-------------|
| L1 组件级 | 5 | ~30s |
| L2 业务级 | 5 | ~3-5min |
| L3 系统级 | 3 | ~5-10min |
| **总计** | **13** | **~10-15min** |

---

## 八、后续演进

1. **CI/CD 集成**: E2E 测试默认跳过，需要手动触发（`pytest -m e2e`）
2. **性能基准**: 记录每次 E2E 运行的耗时、费用、token 用量
3. **模型对比**: 同一任务用不同模型运行，比较输出质量
4. **自动化回归**: 每次代码提交后运行 L1 组件级验证
5. **可观测性**: E2E 测试运行后生成报告（成功率、平均耗时、平均费用）
