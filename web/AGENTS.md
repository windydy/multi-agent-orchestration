# web LLM 索引

## 适用范围

`web/` 是 Vite + React + TypeScript Dashboard，用于操作和观察多 Agent 工作流。

## 子功能索引

- `src/App.tsx`：应用路由和全局布局。
- `src/pages/HomePage.tsx`：执行概览和启动入口。
- `src/pages/ExecutionPage.tsx`：单次执行详情、DAG、日志和时间线。
- `src/pages/ConfigPage.tsx`：workflow、Agent、verifier 配置管理。
- `src/pages/ObservabilityPage.tsx`：成本、成功率、性能、失败原因和告警。
- `src/components/`：DAG、表格、状态、统计卡片、YAML 编辑器等 UI 组件。
- `src/lib/api.ts`：后端 API client。
- `src/types/index.ts`：共享前端类型。
- `src/index.css`：Tailwind 和设计 token。

## 设计规范

- 页面组件负责数据编排，展示组件保持纯渲染和明确 props。
- API response 类型必须与 `src/api` Pydantic 模型同步。
- UI 状态至少区分 loading、empty、success、error。
- 交互控件必须有 hover、focus、disabled 状态，并保持键盘可访问。
- 布局要避免模板化 dashboard 堆卡片，优先通过层级、节奏和状态语义表达系统运行状况。

## 约束

- 不要在前端硬编码 API Key 或敏感配置。
- 不要使用 `dangerouslySetInnerHTML`，除非先通过可信 sanitizer。
- 不要直接依赖 `node_modules` 下的文件或 AGENTS.md。
- 修改 API path、字段名或枚举时同步 `api.ts`、types、页面和测试。
- 图表和 DAG 渲染必须处理空数据和部分失败数据。

## 最佳实践

- 新 API 调用统一放在 `src/lib/api.ts`，不要散落 fetch。
- 复杂可视化组件接收规范化数据，不在组件内拼接后端原始响应。
- 使用 TypeScript 明确 props 和 API 返回类型，避免 `any`。
- 前端变更后运行 `npm run build`；涉及 UI 行为时启动 dev server 手动验证。
- 保持语义 HTML：导航用 `nav`，主内容用 `main`，表格数据用 `table` 或可访问替代结构。
