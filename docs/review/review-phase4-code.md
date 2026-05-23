# Phase 4 代码评审报告

> **评审对象**: Phase 4 配置管理相关代码
> **评审时间**: 2026-05-22

---

## P0 问题

### P0-1: Config 路由在 server.py 重复注册

`server.py` 第 88 行 `app.include_router(config_router)` 直接注册了 config_router，而 `__init__.py` 也注册了 `dag_router` 等。需要确认 config_router 是否也在 `__init__.py` 中注册（导致双重注册）。

**检查结果**：`config_router` 只在 `server.py` 中注册，没有在 `__init__.py` 中。✅ 不是问题。

### P0-2: YAMLEditor Monaco Editor 异步加载

Monaco Editor 默认从 CDN 加载，离线环境会失败。

**修复**：在 ConfigPage 中使用 React.lazy 异步加载 Monaco，避免阻塞首次渲染。

### P0-3: ConfigPage 未处理 API 错误

`loadAll()` 的 catch 块空操作，网络错误时用户看不到任何提示。

**修复**：添加错误状态展示。

---

## P1 问题

### P1-1: AgentCard model 修改缺少 debounce

每次 onChange 都触发 fetch PUT 请求。用户快速输入时会产生大量 API 调用。

**修复**：添加 onBlur 或 debounce（300ms）再发送请求。

### P1-2: ConfigStore 的 _create_tables 不是完全幂等

虽然用了 `CREATE TABLE IF NOT EXISTS`，但 agent 种子的逻辑在每次新连接时检查。多线程环境下可能竞态。

**修复**：将种子逻辑移到 `_ensure_db()` 中只执行一次。

### P1-3: VerifierTable 表单硬编码了 condition 选项

前端下拉菜单写死了 `token_limit`、`cost_threshold`、`node_timeout`，没有从后端获取可用条件列表。

**修复**：Phase 5 加，当前可接受。

---

## P2 问题

### P2-1: ConfigPage 没有 Loading 状态区分首次加载和刷新

### P2-2: YAMLEditor 没有"从模板创建"功能
