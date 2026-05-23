# workspace LLM 索引

## 适用范围

`src/workspace/` 管理多项目工作区配置，当前核心文件是 `manager.py`。

## 核心模型

- `ProjectConfig`：单个项目的 root path、描述、默认 workflow、变量和标签。
- `WorkspaceConfig`：工作区名、项目集合、默认项目、共享工具和共享环境。
- `WorkspaceManager`：加载/保存 `.workspace.yaml`，执行 create、switch、list、delete 等操作。

## 设计规范

- `.workspace.yaml` 是用户可编辑状态文件，读写必须保持清晰和可恢复。
- 项目路径应规范化并在使用前校验存在性或创建意图。
- 模板应用和项目注册应分离，避免部分成功导致配置不一致。

## 约束

- 删除项目配置不等于删除项目目录；涉及文件删除必须由调用方显式确认。
- 不要把密钥写入 `shared_env` 示例或默认值。
- YAML 读取失败时要保守处理，避免覆盖用户已有配置。
- 工作区状态不应依赖当前进程 cwd 的隐式变化。

## 最佳实践

- 新增字段时兼容旧 `.workspace.yaml`。
- 保存 YAML 时保留 Unicode 可读性，避免写入 Python 对象标签。
- 对 create/switch/list/delete 和损坏 YAML 路径写测试。
- 多项目执行时使用 project_id/project_path 隔离 checkpoints、memory 和日志。
