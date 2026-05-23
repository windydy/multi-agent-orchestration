# api LLM 索引

## 适用范围

`src/api/` 提供 Dashboard 后端：FastAPI app、REST routes、services、WebSocket 和 API 数据模型。

## 子功能索引

- `server.py`：FastAPI app 工厂、依赖注入、CORS、静态资源挂载。
- `models.py`：API 响应模型。
- `routes/`：health、overview、executions、events、files、workflows、dag、config、observability、ws。
- `services/`：事件日志、执行管理、配置存储、可观测性存储等状态服务。
- `ws.py`：WebSocket connection manager。

## 设计规范

- 路由层只处理 HTTP/WebSocket 协议、请求校验和响应映射。
- 持久化、执行状态和聚合查询放在 services 层。
- 长任务必须后台执行，并通过 execution manager 维护暂停、恢复、取消和完成状态。
- 所有请求体和响应体使用 Pydantic 模型定义。

## 约束

- 不要在路由中硬编码密钥、外部 URL 或生产 CORS 策略。
- 文件访问必须通过 project root 校验，防止路径穿越。
- 后台 task 的异常必须记录并转为失败状态，不能悬挂。
- WebSocket 连接必须在断开和异常时清理。
- 修改 REST response shape 时同步 `web/src/lib/api.ts` 和 `web/src/types`。

## 最佳实践

- 新路由放在独立 `routes/<feature>.py`，通过 `routes/__init__.py` 聚合。
- 共享状态用 setter 注入，测试中传入临时数据库或 fake service。
- SQLite service 要显式关闭连接或使用短连接。
- API 测试覆盖 2xx、4xx、5xx 和并发/取消路径。
