# 自动招募智能体 & 动态工作流编排方案

> multi-agent-orchestration 项目 — 从"静态注册"到"按需招募"的演进规划
>
> 创建日期: 2026-05-23 | 状态: 待执行

---

## 背景

项目已实现 Phase 1-8 的基础编排能力：Mock 已清除，Planner/Developer/Reviewer 均可调用真实 LLM，Phase 8.1 WorkspaceManager 已自举成功（363 测试全通过）。

**当前瓶颈**：所有 Agent 均在启动时静态注册到 `ExecutorRegistry`，工作流模板硬编码在 `dag.py`，无法根据任务需求**动态发现、招募、配置**合适的 Agent。用户提出核心需求：系统应能自主决定"需要哪些 Agent"、"去哪里找"、"怎么组合工作流"。

---

## 架构目标

1. **按需招募**：任务到达时，自动发现/匹配可用 Agent，无需预先注册
2. **语义匹配**：用 LLM 理解任务意图，而非硬编码的 Enum 路由
3. **动态组合**：根据任务复杂度与可用 Agent 资源，自动调整工作流拓扑
4. **后台调度**：支持定时/事件触发的后台任务，非同步阻塞执行

---

## 四阶段路线图

### Phase A: Agent Discovery Service（P0）

**目标**：实现 Agent 的动态注册与发现，替代启动时一次性静态注册。

**核心设计**：
- `AgentRegistry` — 维护可用 Agent 池，支持运行时 register/unregister
- Agent 元数据清单：`{name, capabilities[], model, tools[], status, last_seen}`
- 多源发现：
  - 本地：扫描 `src/agents/` 目录，自动加载并注册
  - MCP：通过 MCP 协议发现外部 Agent 的能力描述
  - 插件：从配置目录加载 YAML 格式的 Agent 定义
- 心跳/健康检查：Agent 定期上报状态，超时标记为 unavailable

**关键文件**：
- 新建 `src/discovery/registry.py` — AgentRegistry 核心
- 新建 `src/discovery/sources/local.py` — 本地扫描
- 新建 `src/discovery/sources/mcp.py` — MCP 发现
- 修改 `src/executors/registry.py` — 从静态注册切换为动态查询

**验收标准**：
- 新增 10 个 Agent 后无需重启服务即可被发现
- Agent 下线后 30 秒内从可用池中移除
- `pytest` 新增测试覆盖 registry CRUD + health check

---

### Phase B: Semantic Capability Matching（P1）

**目标**：用 LLM 替代硬编码的 `ExecutorCapability` Enum 路由。

**核心设计**：
- `CapabilityMatcher` — 输入自然语言任务描述，输出候选 Agent 列表及匹配分数
- 匹配策略三层：
  1. **向量相似度**：任务 embedding vs Agent capability embeddings（轻量筛选）
  2. **LLM 评分**：将任务描述 + Agent 元数据发给 LLM，返回结构化评分 `{agent_name, score, reason}`
  3. **规则兜底**：当无高匹配 Agent 时，选择 GENERIC 类型 + 给出警告
- 支持复合任务拆分：一个任务需要多个能力时，自动分解为子任务分别匹配

**关键文件**：
- 新建 `src/discovery/matcher.py` — CapabilityMatcher
- 新建 `src/discovery/embedding.py` — 向量索引维护
- 修改 `src/executors/registry.py` — `find_best()` 改用 matcher

**验收标准**：
- "帮我写一个 Redis 缓存模块" → 匹配 DevOpsAgent + DeveloperAgent
- "画一个系统架构图" → 匹配 ArchitectAgent
- 复合任务自动拆分 + 多 Agent 组合匹配
- 匹配延迟 < 3 秒（含 LLM 调用）

---

### Phase C: Agent Config Builder（P2）

**目标**：为招募到的 Agent 自动生成任务级配置（prompt、工具集、模型路由）。

**核心设计**：
- `ConfigBuilder` — 输入：任务描述 + 匹配的 Agent 元数据 → 输出：完整 Agent 配置
- 自动生成内容：
  - **System Prompt**：根据任务上下文注入角色定义、约束、输出格式
  - **工具集**：按任务类型选择性注入（写代码 → terminal/file/patch，调研 → web/search）
  - **模型路由**：按复杂度选择模型（简单任务 → 小模型，复杂推理 → 大模型）
  - **Skills 加载**：从 `skills_list` 中自动匹配并加载相关 skill
- 配置缓存：相似任务复用已有配置，减少 LLM 调用

**关键文件**：
- 新建 `src/discovery/config_builder.py` — AgentConfigBuilder
- 新建 `src/discovery/prompt_templates.py` — 可组合的 prompt 模板库
- 修改 `src/workflows/config_builder.py` — 集成动态配置生成

**验收标准**：
- 同一 Agent 在不同任务下获得差异化 prompt/tools 配置
- 模型路由策略正确（简单/中等/复杂 三级分类）
- Skills 自动加载命中率达到 80%+

---

### Phase D: Dynamic Workflow Composer（P3）

**目标**：运行时动态构建工作流拓扑，替代硬编码的 `_WORKFLOW_TEMPLATES`。

**核心设计**：
- `WorkflowComposer` — 输入：任务描述 → 输出：`PlanGraph`（DAG）
- 工作流程：
  1. PlannerAgent 分析任务，生成候选节点列表
  2. CapabilityMatcher 为每个节点匹配最佳 Agent
  3. WorkflowComposer 根据依赖关系组装 DAG
  4. 根据可用 Agent 动态裁剪/扩展（如某类 Agent 不可用时自动降级）
- 复杂度自适应：
  - 简单任务：跳过 review 节点，直接 develop → verify
  - 复杂任务：完整五步流程 plan → review → TDD → code review → verify
  - 无可用 Agent：给出降级方案或拒绝执行
- 后台任务调度：
  - 集成 Hermes `cronjob` 工具，支持定时触发工作流
  - 支持 webhook 事件驱动（GitHub push → 自动触发 code review 工作流）

**关键文件**：
- 新建 `src/workflows/composer.py` — DynamicWorkflowComposer
- 新建 `src/workflows/scheduler.py` — 后台任务调度
- 修改 `src/api/routes/dag.py` — 移除硬编码 `_WORKFLOW_TEMPLATES`
- 修改 `src/workflows/dynamic_builder.py` — 支持动态 DAG 输入

**验收标准**：
- 接收自然语言任务描述，自动构建并执行完整工作流
- 简单任务自动跳过不必要节点（节省时间/成本）
- Agent 不可用时自动降级并通知
- 支持 cronjob 定时触发 + webhook 事件触发

---

## 优先级排序

| 优先级 | Phase | 核心产出 | 预估工时 |
|--------|-------|----------|----------|
| P0 | A — Agent Discovery Service | 动态注册/发现 + 健康检查 | 2-3 天 |
| P1 | B — Semantic Capability Matching | LLM 驱动的语义匹配 | 2-3 天 |
| P2 | C — Agent Config Builder | 自动配置生成 | 1-2 天 |
| P3 | D — Dynamic Workflow Composer | 动态 DAG + 后台调度 | 3-4 天 |

**前置依赖**：Phase A → Phase B → Phase C → Phase D（顺序执行，不可并行）

---

## 技术约束

1. **保持 LangGraph 兼容性**：所有动态构建最终输出 `StateGraph`，不破坏现有 `DynamicWorkflowBuilder`
2. **363 测试回归**：每阶段完成后全量测试必须通过
3. **模型路由不变**：Planner=MiniMax-M2.5, Developer/Tester=qwen3.6-plus, Reviewer=kimi-k2.5
4. **无 Mock**：所有组件必须调用真实 LLM/API，不再使用 Mock 方案
5. **API 配置**：统一从 `~/.hermes/config.yaml` custom provider 读取

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| MCP 发现协议不稳定 | Phase A 延期 | 先实现本地扫描，MCP 作为后续增强 |
| LLM 匹配评分不稳定 | Phase B 准确率下降 | 加入 few-shot 示例 + 输出格式校验 |
| 动态 DAG 产生循环依赖 | Phase D 执行失败 | 复用现有 `topological_sort` 循环检测 |
| Agent 资源不足时降级不当 | 任务执行失败 | 建立降级策略矩阵（明确每类任务的降级路径） |

---

## 下一步

1. 确认方案无遗漏后，开始 Phase A 的 TDD 循环
2. 先写 `AgentRegistry` 测试用例（register/unregister/health-check/find）
3. 按 写方案 → 方案 review → TDD → 代码 review → 自动化验证 五步流程推进
