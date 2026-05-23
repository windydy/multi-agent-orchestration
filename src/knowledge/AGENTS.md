# knowledge LLM 索引

## 适用范围

`src/knowledge/` 负责 Agent 记忆与检索，包括 SQLite 结构化存储和可选 embedding 语义检索。

## 子功能索引

- `memory.py`：`MemoryEntry` 和 `AgentMemory`，提供 remember、recall、search、semantic_search、forget、stats。
- `embeddings.py`：embedding provider 抽象或实现。

## 设计规范

- 记忆条目应包含 key、category、project_id、tags 和时间戳，便于按项目隔离。
- SQLite 查询必须参数化，避免 SQL 注入。
- 语义检索是可选增强，结构化检索必须独立可用。
- 记忆内容应可 JSON 序列化。

## 约束

- 不要把密钥、凭据、用户隐私或完整敏感日志写入 memory。
- 不要在检索失败时伪造结果；返回空集合或明确错误。
- 数据库路径应由调用方或配置控制，测试使用临时路径。
- embedding provider 不应改变 `MemoryEntry` 的基本存储语义。

## 最佳实践

- 写入前明确 category 和 project_id，避免全局污染。
- 更新已有 key 时保留访问计数和更新时间。
- 为新增查询增加索引或说明性能影响。
- 对 remember/recall/search/forget 和异常路径写测试。
