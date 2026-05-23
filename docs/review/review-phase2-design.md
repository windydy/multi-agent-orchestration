# Phase 2 Web UI 架构评审报告

> **评审日期**: 2026-05-22
> **评审人**: 资深架构师
> **评审对象**: `/docs/planning/web-ui-phase2-design.md`
> **结论**: 🟡 有条件批准 — 需修复关键问题后方可进入实施

---

## 一、总体评价

Phase 2 方案整体方向正确，功能分层清晰，P0/P1 优先级划分合理。短轮询策略作为 MVP 是务实选择，ExecutionManager 的基本思路可行。但方案在 **LangGraph 集成机制、API 完整性和并发安全** 三个维度存在必须修复的问题，建议修复后再进入实施。

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构合理性 | ⚠️ 6/10 | ExecutionManager 与 LangGraph 集成存在竞态和状态不一致风险 |
| 与现有代码兼容性 | ✅ 8/10 | API 路由和 EventLog 复用设计合理，扩展点清晰 |
| API 完整性 | ⚠️ 5/10 | 缺少请求模型定义、错误响应规范、文件路径处理 |
| 前端完整性 | ⚠️ 6/10 | 遗漏加载态、轮询控制、路由注册、表单验证 |
| 风险缓解充分度 | ⚠️ 5/10 | 缺少服务重启恢复、并发安全机制 |
| 实施优先级 | ✅ 8/10 | 步骤和时间估算基本合理 |

---

## 二、关键问题（必须修复）

### 🔴 P0-1: ExecutionManager 与 LangGraph 的集成存在竞态和状态不一致

**问题描述**:

方案第 5.2 节中，节点函数通过 `execution_manager.get(config["thread_id"])` 获取 ExecutionHandle，但：

1. **`config` 来源不明**：当前 `_create_node_functions` 中的 `node_func(state, agent_name, field_name)` 没有 `thread_id` 上下文。thread_id 是 LangGraph 执行时传入的 `config` 参数，方案未说明如何将 thread_id 注入到节点函数。

2. **`await handle.pause_event.wait()` 阻塞位置不当**：这段代码放在节点函数开头，但 LangGraph 的节点函数执行期间，真正的阻塞发生在 `await agent.run()` 内部的 LLM 调用。pause_event 只能阻止**下一个节点启动**，无法暂停正在运行的 LLM 请求。

3. **取消机制不完整**：`handle.cancel_event.set()` 仅设置标志位，但没有调用 `asyncio.Task.cancel()` 终止实际的 LangGraph 执行任务。正在运行的 `agent.run()` 会继续执行到完成。

4. **`process` 字段未使用**：`ExecutionHandle` 定义了 `process: Optional[asyncio.Task]` 但从未赋值。没有任务引用就无法实现真正的取消。

**修复建议**:

```python
class ExecutionManager:
    def start(self, task: str, workflow: str, config: dict) -> tuple[str, ExecutionHandle]:
        thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        handle = ExecutionHandle(...)
        self._executions[thread_id] = handle
        return thread_id, handle
    
    def bind_task(self, thread_id: str, task: asyncio.Task):
        """绑定 LangGraph 执行的 asyncio.Task"""
        handle = self._executions.get(thread_id)
        if handle:
            handle.process = task
    
    def cancel(self, thread_id: str) -> bool:
        handle = self._executions.get(thread_id)
        if not handle or handle.status not in ("running", "paused"):
            return False
        handle.status = "cancelled"
        handle.cancel_event.set()
        if handle.process:
            handle.process.cancel()  # 真正取消任务
        return True
```

同时在 `_create_node_functions` 中，通过 LangGraph 的 `config` 参数传递 thread_id：

```python
async def node_func(state: WorkflowState, config: RunnableConfig, agent_name=name) -> dict:
    thread_id = config.get("configurable", {}).get("thread_id")
    handle = execution_manager.get(thread_id)
    if handle and handle.cancel_event.is_set():
        return {"current_stage": "cancelled"}
    # ... 其余逻辑
```

### 🔴 P0-2: 服务重启后执行状态完全丢失

**问题描述**:

`ExecutionManager._executions` 是纯内存 dict，FastAPI 进程重启后：
- 所有 ExecutionHandle 丢失
- LangGraph checkpoint（SQLite 持久化）中仍保存了执行状态
- 前端看到的 "running" 任务实际已无后端管理，无法暂停/取消/查看日志

**修复建议**:

启动时从 LangGraph checkpoint 恢复活跃执行状态：
```python
async def lifespan(app: FastAPI):
    # 启动时恢复活跃执行
    await execution_manager.restore_from_checkpoints()
    yield
    # 关闭时等待或清理
    await execution_manager.cleanup()
```

`restore_from_checkpoints` 方法应读取 LangGraph 的 SQLite checkpoint，找出所有未完成的 thread_id，重建 ExecutionHandle（状态设为 "unknown"，允许前端手动终止）。

### 🔴 P0-3: 文件 API 的路径参数设计有安全隐患

**问题描述**:

`GET /api/executions/{id}/files/{path}` 中，`{path}` 是文件路径如 `src/api/models.py`。问题：
1. URL 路径中的斜杠会被 FastAPI 路由器截断（需要特殊处理）
2. 存在目录遍历风险（`../../../etc/passwd`）
3. 特殊字符需要 URL 编码

**修复建议**:

改用查询参数：
```
GET /api/executions/{id}/files?path=src/api/models.py
```

并添加路径白名单验证：
```python
def _validate_file_path(path: str, project_root: str) -> str:
    full_path = os.path.normpath(os.path.join(project_root, path))
    if not full_path.startswith(os.path.normpath(project_root)):
        raise HTTPException(403, "Access denied")
    return full_path
```

### 🔴 P0-4: ExecutionManager 缺少并发安全保护

**问题描述**:

FastAPI 是异步框架，多个请求可能并发访问 `_executions` dict。当前实现：
- `cancel()`、`pause()`、`resume()` 中的 `get` + `set` 非原子操作
- 两个并发请求可能同时读到同一 handle 并修改状态

**修复建议**:

使用 `asyncio.Lock` 保护状态变更：
```python
class ExecutionManager:
    def __init__(self):
        self._executions: dict[str, ExecutionHandle] = {}
        self._lock = asyncio.Lock()
    
    async def cancel(self, thread_id: str) -> bool:
        async with self._lock:
            handle = self._executions.get(thread_id)
            if not handle or handle.status != "running":
                return False
            handle.status = "cancelled"
            handle.cancel_event.set()
            if handle.process:
                handle.process.cancel()
        return True
```

---

## 三、建议改进（可选优化）

### 🟡 S1: 日志 API 缺少增量查询语义

当前 `GET /api/executions/{id}/logs?offset={offset}` 使用偏移量，但：
- 响应中应包含 `has_more: bool` 告知前端是否还有更多日志
- 对于正在运行的执行，offset 可能因并发写入导致跳过或重复
- 建议增加 `?since=<timestamp>` 作为替代方案，更适合时间序列日志

```json
// 改进后的响应
{
  "logs": [...],
  "has_more": true,
  "next_offset": 15
}
```

### 🟡 S2: 前端轮询控制策略需细化

- **ExecutionPage 已有 2s 轮询**：当前代码已在执行详情页轮询 detail 数据，新增的 LogViewer 1s 轮询会与之竞争
- **建议**：合并为单一轮询入口，detail API 返回时附带最新日志，减少请求数量
- **自动停止**：执行完成后应停止轮询，当前设计未说明停止条件
- **用户滚动锁定**：日志自动滚动时如果用户向上滚动查看旧日志，不应自动跳到底部

### 🟡 S3: API 请求模型缺失

`POST /api/executions` 缺少 Pydantic 请求模型定义。建议：
```python
class CreateExecutionRequest(BaseModel):
    task: str = Field(min_length=1, max_length=10000)
    workflow: str = Field(default="development", pattern="^[a-zA-Z_]+$")
    project_path: Optional[str] = None
    models: Optional[dict[str, str]] = None
    max_iterations: int = Field(default=10, ge=1, le=50)
```

### 🟡 S4: 缺少工作流/模型枚举查询 API

新建任务表单需要：
- 可用的工作流模板列表（当前硬编码 "development"）
- 可用的模型选项（sonnet/opus 等）

建议新增：
```
GET /api/workflows          # 返回可用工作流列表
GET /api/models             # 返回可用模型配置
```

### 🟡 S5: 文件变更检测方案需明确

方案提到"snapshot diff 方式"但未详细说明。建议：
1. 执行前：记录项目目录的文件快照（路径 + mtime + size）
2. 执行后：对比快照，标记 created/modified/deleted
3. 存储：将变更列表写入 EventLog 的 `execution_completed` 事件的 data 字段
4. 避免在内存中维护快照（防止重启丢失）

### 🟡 S6: 前端新增组件需要错误边界

- `LogViewer` 需要处理 API 500/超时错误
- `ControlButtons` 需要在 API 请求期间显示 loading 并禁用按钮
- `TaskForm` 需要表单验证（task 必填、project_path 合法性检查）

### 🟢 S7: 日志存储可考虑写入优化

当前 EventLog 每次 `log()` 都执行 `commit()`，高频日志场景下会成为瓶颈。建议：
- 批量写入：收集 10 条或 1 秒后批量 commit
- 或使用 WAL 模式（Write-Ahead Logging）提升写入性能

---

## 四、方案优点（值得保留）

1. ✅ **EventLog 复用设计**：通过新增 `node_log` event_type 扩展现有 EventLog，避免引入新存储
2. ✅ **短轮询 MVP 策略**：Phase 2 用短轮询快速验证功能，Phase 3 升级 WebSocket，节奏合理
3. ✅ **P0/P1 优先级划分**：任务提交和控制为 P0，日志和文件预览为 P1，聚焦核心功能
4. ✅ **TDD 开发流程**：实施步骤中每步都标注 TDD，保证质量
5. ✅ **前端组件化设计**：TaskForm、LogViewer、FileList、ControlButtons 职责清晰

---

## 五、实施步骤调整建议

| 原步骤 | 调整建议 |
|--------|----------|
| Step 1: ExecutionManager + 测试 | **增加并发安全测试**、**增加重启恢复测试** |
| Step 2: POST /api/executions + 控制 API | **增加请求模型验证**、**增加幂等性支持** |
| Step 3: 日志 API + 文件 API | **修复文件路径安全问题**、**增加增量查询语义** |
| Step 4: PipelineBuilder 集成 | **明确 thread_id 注入机制**、**确保 cancel 能中断 LangGraph 执行** |
| Step 5: NewTaskPage + 控制按钮 | **增加表单验证**、**增加错误处理和加载态** |
| Step 6: LogViewer + FileList | **增加轮询停止逻辑**、**增加用户滚动锁定** |
| — | **新增 Step 7**: 服务重启恢复集成测试 |

---

## 六、评审结论

### 🟡 有条件批准进入实施阶段

**必须修复项**（进入实施前）：
1. [P0-1] 明确 ExecutionManager 与 LangGraph 的 thread_id 传递机制
2. [P0-1] 完善 cancel/pause 机制，确保能中断正在运行的 LangGraph 执行
3. [P0-2] 设计服务重启后的状态恢复方案
4. [P0-3] 修改文件 API 路径参数设计，改用查询参数 + 路径白名单
5. [P0-4] ExecutionManager 增加并发安全保护（asyncio.Lock）

**建议修复项**（可在实施阶段并行处理）：
- [S1-S7] 按优先级在对应步骤中纳入

**整体时间估算**：修复上述问题后，预计 **4.5-5 天**（原估算 4 天，增加 0.5 天用于并发安全测试和重启恢复）。

---

*报告生成时间: 2026-05-22 20:00*
