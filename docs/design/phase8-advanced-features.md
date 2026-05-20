# Phase 8: 高级特性 - 详细技术设计

> 版本: 1.0
> 日期: 2026-05-20
> 状态: 设计稿

## 一、概述

### 1.1 目标

添加多项目支持、知识库与记忆、团队协作、Web UI 和第三方集成等高级特性，提升系统在生产环境中的实用性和用户体验。

### 1.2 特性清单

| 特性 | 优先级 | 说明 |
|------|--------|------|
| 多项目管理 | P1 | WorkspaceManager，项目隔离与共享 |
| 知识库与记忆 | P1 | AgentMemory，语义检索 |
| 团队协作 | P2 | RBAC 权限、任务分配 |
| Web UI | P2 | React 前端，实时可视化 |
| 第三方集成 | P2 | GitHub、Jira、通知机器人 |

---

## 二、多项目管理

### 2.1 src/workspace/manager.py

```python
import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class ProjectConfig:
    """项目配置"""
    name: str
    root_path: str
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    default_workflow: str = "software-development"
    vars: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class WorkspaceConfig:
    """工作空间配置"""
    name: str
    projects: dict[str, ProjectConfig] = field(default_factory=dict)
    default_project: Optional[str] = None
    shared_tools: list[str] = field(default_factory=list)
    shared_env: dict = field(default_factory=dict)


class WorkspaceManager:
    """工作空间管理器
    
    功能:
    - 多项目切换和管理
    - 项目间依赖声明
    - 共享配置和工具链
    - 项目模板
    """
    
    WORKSPACE_FILE = ".workspace.yaml"
    
    def __init__(self, root_path: str = "."):
        self.root = Path(root_path).resolve()
        self.config = self._load_workspace()
    
    def _load_workspace(self) -> WorkspaceConfig:
        ws_file = self.root / self.WORKSPACE_FILE
        if ws_file.exists():
            with open(ws_file) as f:
                data = yaml.safe_load(f) or {}
            # 解析为 WorkspaceConfig
            return WorkspaceConfig(
                name=data.get("name", "default"),
                default_project=data.get("default_project"),
            )
        return WorkspaceConfig(name="default")
    
    def create_project(self, name: str, path: str, 
                       description: str = "",
                       template: str = None) -> ProjectConfig:
        """创建项目"""
        project = ProjectConfig(
            name=name,
            root_path=path,
            description=description,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        
        self.config.projects[name] = project
        
        # 如果使用模板，复制模板文件
        if template:
            self._apply_template(name, path, template)
        
        self._save_workspace()
        return project
    
    def switch_project(self, name: str) -> ProjectConfig:
        """切换到项目"""
        if name not in self.config.projects:
            raise ValueError(f"项目 '{name}' 不存在")
        self.config.default_project = name
        self._save_workspace()
        return self.config.projects[name]
    
    def get_current_project(self) -> Optional[ProjectConfig]:
        """获取当前项目"""
        if self.config.default_project:
            return self.config.projects.get(self.config.default_project)
        return None
    
    def list_projects(self) -> list[ProjectConfig]:
        """列出所有项目"""
        return list(self.config.projects.values())
    
    def delete_project(self, name: str):
        """删除项目"""
        if name in self.config.projects:
            del self.config.projects[name]
            self._save_workspace()
    
    def _apply_template(self, name: str, path: str, template: str):
        """应用项目模板"""
        template_dir = Path(__file__).parent.parent.parent / "templates" / template
        if not template_dir.exists():
            return
        
        import shutil
        dest = Path(path)
        dest.mkdir(parents=True, exist_ok=True)
        
        for item in template_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, dest / item.name)
            elif item.is_dir():
                shutil.copytree(item, dest / item.name)
    
    def _save_workspace(self):
        ws_file = self.root / self.WORKSPACE_FILE
        data = {
            "name": self.config.name,
            "default_project": self.config.default_project,
            "projects": {
                name: {
                    "root_path": p.root_path,
                    "description": p.description,
                    "created_at": p.created_at,
                    "tags": p.tags,
                }
                for name, p in self.config.projects.items()
            }
        }
        with open(ws_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
```

---

## 三、知识库与记忆系统

### 3.1 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                      AgentMemory                         │
│                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────┐  │
│  │  Semantic Store │  │  Structured     │  │  Cache  │  │
│  │  (Vector DB)    │  │  Store          │  │  (LRU)  │  │
│  │                 │  │  (JSON/SQLite)  │  │         │  │
│  │  - 代码风格     │  │  - 项目知识     │  │  - 热   │  │
│  │  - 常见问题     │  │  - 决策历史     │  │    数据 │  │
│  │  - 经验教训     │  │  - Agent 配置   │  │  - 快速 │  │
│  └────────┬────────┘  └────────┬────────┘  │    查询 │  │
│           │                    │           └─────────┘  │
│           └────────┬───────────┘                        │
│                    ▼                                    │
│           ┌─────────────────┐                          │
│           │  Embedding      │                          │
│           │  Provider       │                          │
│           │  (向量计算)     │                          │
│           └─────────────────┘                          │
└─────────────────────────────────────────────────────────┘
```

### 3.2 src/knowledge/memory.py

```python
import json
import os
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class MemoryEntry:
    """记忆条目"""
    key: str
    value: str
    category: str  # code_style, faq, decision, lesson
    project_id: str
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    access_count: int = 0
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class AgentMemory:
    """Agent 记忆系统
    
    双层存储:
    - SQLite: 结构化数据，精确查询
    - 向量数据库: 语义检索
    """
    
    def __init__(self, db_path: str = "./memory/agent_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._vector_store = None
    
    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT NOT NULL,
                project_id TEXT NOT NULL,
                tags TEXT,
                created_at TEXT,
                updated_at TEXT,
                access_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_project 
            ON memory(project_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_category 
            ON memory(category)
        """)
        conn.commit()
        conn.close()
    
    def remember(self, entry: MemoryEntry):
        """存储记忆"""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            INSERT OR REPLACE INTO memory 
            (key, value, category, project_id, tags, created_at, updated_at, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.key, entry.value, entry.category, entry.project_id,
            json.dumps(entry.tags), entry.created_at, entry.updated_at,
            entry.access_count
        ))
        conn.commit()
        conn.close()
    
    def recall(self, key: str) -> Optional[MemoryEntry]:
        """按 key 检索"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute("SELECT * FROM memory WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return MemoryEntry(
                key=row[0], value=row[1], category=row[2],
                project_id=row[3], tags=json.loads(row[4] or "[]"),
                created_at=row[5], updated_at=row[6],
                access_count=row[7],
            )
        return None
    
    def search(self, project_id: str, category: str = None, 
               query: str = None, limit: int = 10) -> list[MemoryEntry]:
        """搜索记忆"""
        conn = sqlite3.connect(str(self.db_path))
        
        sql = "SELECT * FROM memory WHERE project_id = ?"
        params = [project_id]
        
        if category:
            sql += " AND category = ?"
            params.append(category)
        
        if query:
            sql += " AND (key LIKE ? OR value LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])
        
        sql += " ORDER BY access_count DESC LIMIT ?"
        params.append(limit)
        
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            MemoryEntry(
                key=r[0], value=r[1], category=r[2], project_id=r[3],
                tags=json.loads(r[4] or "[]"), created_at=r[5],
                updated_at=r[6], access_count=r[7],
            )
            for r in rows
        ]
    
    def semantic_search(self, query: str, project_id: str = None, 
                        limit: int = 5) -> list[MemoryEntry]:
        """语义检索（向量搜索）"""
        if not self._vector_store:
            return []
        
        # 获取查询向量
        query_vec = self._get_embedding(query)
        
        # 搜索
        results = self._vector_store.search(query_vec, limit=limit * 2)
        
        # 过滤项目
        if project_id:
            results = [r for r in results if r.get("project_id") == project_id]
        
        # 去重
        seen = set()
        entries = []
        for r in results[:limit]:
            if r["key"] not in seen:
                seen.add(r["key"])
                entry = self.recall(r["key"])
                if entry:
                    entries.append(entry)
        
        return entries
    
    def forget(self, key: str):
        """遗忘"""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("DELETE FROM memory WHERE key = ?", (key,))
        conn.commit()
        conn.close()
    
    def get_stats(self, project_id: str = None) -> dict:
        """获取统计信息"""
        conn = sqlite3.connect(str(self.db_path))
        
        if project_id:
            cursor = conn.execute(
                "SELECT category, COUNT(*) FROM memory WHERE project_id = ? GROUP BY category",
                (project_id,)
            )
        else:
            cursor = conn.execute(
                "SELECT category, COUNT(*) FROM memory GROUP BY category"
            )
        
        stats = dict(cursor.fetchall())
        total = sum(stats.values())
        conn.close()
        
        return {"total": total, "by_category": stats}
    
    def _get_embedding(self, text: str) -> list[float]:
        """获取文本向量"""
        # TODO: 调用 EmbeddingProvider
        return []
```

### 3.3 src/knowledge/embeddings.py

```python
from abc import ABC, abstractmethod
from typing import Optional


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        pass
    
    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self._client = None
    
    def embed(self, text: str) -> list[float]:
        from openai import OpenAI
        client = OpenAI()
        response = client.embeddings.create(input=text, model=self.model)
        return response.data[0].embedding


class LocalEmbeddingProvider(EmbeddingProvider):
    """使用本地模型（如 sentence-transformers）"""
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
    
    def embed(self, text: str) -> list[float]:
        from sentence_transformers import SentenceTransformer
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model.encode(text).tolist()


# 向量存储
class VectorStore:
    def __init__(self, provider: EmbeddingProvider, store_path: str = "./memory/vectors"):
        self.provider = provider
        self.store_path = store_path
    
    def add(self, key: str, text: str, metadata: dict = None):
        """添加向量"""
        vec = self.provider.embed(text)
        # 存储到 FAISS 或 Chroma
        pass
    
    def search(self, query_vec: list[float], limit: int = 5) -> list[dict]:
        """搜索相似向量"""
        # FAISS / Chroma 搜索
        return []
```

---

## 四、团队协作

### 4.1 src/team/auth.py - RBAC 权限

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class Role(str, Enum):
    ADMIN = "admin"       # 完全控制
    MANAGER = "manager"   # 管理工作流
    DEVELOPER = "developer"  # 执行任务
    REVIEWER = "reviewer"  # 审查和审批
    VIEWER = "viewer"     # 只读


@dataclass
class User:
    id: str
    name: str
    role: Role
    email: Optional[str] = None
    active: bool = True


class Permission(str, Enum):
    RUN_WORKFLOW = "workflow:run"
    PAUSE_WORKFLOW = "workflow:pause"
    RESUME_WORKFLOW = "workflow:resume"
    APPROVE = "workflow:approve"
    VIEW_HISTORY = "workflow:view"
    MANAGE_CONFIG = "config:manage"
    MANAGE_USERS = "user:manage"


# 角色权限映射
ROLE_PERMISSIONS = {
    Role.ADMIN: {p for p in Permission},
    Role.MANAGER: {
        Permission.RUN_WORKFLOW, Permission.PAUSE_WORKFLOW,
        Permission.RESUME_WORKFLOW, Permission.VIEW_HISTORY,
        Permission.MANAGE_CONFIG,
    },
    Role.DEVELOPER: {
        Permission.RUN_WORKFLOW, Permission.VIEW_HISTORY,
    },
    Role.REVIEWER: {
        Permission.RUN_WORKFLOW, Permission.APPROVE,
        Permission.VIEW_HISTORY,
    },
    Role.VIEWER: {Permission.VIEW_HISTORY},
}


class AuthManager:
    """认证和授权管理器"""
    
    def __init__(self):
        self._users: dict[str, User] = {}
        self._api_keys: dict[str, str] = {}  # api_key → user_id
    
    def add_user(self, user: User):
        self._users[user.id] = user
    
    def check_permission(self, user_id: str, permission: Permission) -> bool:
        user = self._users.get(user_id)
        if not user or not user.active:
            return False
        return permission in ROLE_PERMISSIONS.get(user.role, set())
    
    def authenticate_api_key(self, api_key: str) -> Optional[User]:
        user_id = self._api_keys.get(api_key)
        if user_id:
            return self._users.get(user_id)
        return None
```

---

## 五、Web UI 设计

### 5.1 前端架构

```
src/ui/
├── frontend/                 # React 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.tsx         # 仪表盘
│   │   │   ├── WorkflowViewer.tsx    # 工作流可视化
│   │   │   ├── TaskList.tsx          # 任务列表
│   │   │   ├── AgentStatus.tsx       # Agent 状态
│   │   │   ├── LogViewer.tsx         # 日志查看器
│   │   │   └── CostChart.tsx         # 成本图表
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts       # WebSocket 连接
│   │   │   ├── useTasks.ts           # 任务数据
│   │   │   └── useMetrics.ts         # 指标数据
│   │   ├── pages/
│   │   │   ├── Home.tsx              # 首页
│   │   │   ├── Workflows.tsx         # 工作流列表
│   │   │   ├── Tasks.tsx             # 任务详情
│   │   │   └── Settings.tsx          # 设置
│   │   ├── services/
│   │   │   └── api.ts                # API 调用
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
└── static/                  # 构建产物（由后端 serve）
```

### 5.2 WebSocket 实时通信

```python
# src/api/ws.py
from fastapi import WebSocket
import json


class WebSocketManager:
    """WebSocket 管理器"""
    
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
    
    async def connect(self, task_id: str, websocket: WebSocket):
        await websocket.accept()
        if task_id not in self._connections:
            self._connections[task_id] = []
        self._connections[task_id].append(websocket)
    
    async def disconnect(self, task_id: str, websocket: WebSocket):
        if task_id in self._connections:
            self._connections[task_id].remove(websocket)
    
    async def broadcast(self, task_id: str, message: dict):
        if task_id in self._connections:
            data = json.dumps(message)
            dead = []
            for ws in self._connections[task_id]:
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections[task_id].remove(ws)
```

---

## 六、第三方集成

### 6.1 src/integrations/github.py

```python
class GitHubIntegration:
    """GitHub 集成"""
    
    def __init__(self, token: str, owner: str, repo: str):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"
    
    async def create_pr(self, title: str, body: str, 
                        head: str, base: str = "main") -> dict:
        """创建 Pull Request"""
        import aiohttp
        url = f"{self.base_url}/pulls"
        payload = {"title": title, "body": body, "head": head, "base": base}
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                return await resp.json()
    
    async def create_issue(self, title: str, body: str, labels: list = None) -> dict:
        """创建 Issue"""
        import aiohttp
        url = f"{self.base_url}/issues"
        payload = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        headers = {"Authorization": f"Bearer {self.token}"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                return await resp.json()
```

---

## 七、与 Phase 4-7 集成

| Phase 8 组件 | 集成方式 |
|-------------|---------|
| AgentMemory | Planner/Executor 在任务前后读取/存储记忆 |
| WorkspaceManager | CLI 和 API 层使用，切换项目上下文 |
| AuthManager | API Server 中间件 |
| Web UI | 通过 API Server 获取实时数据 |
| GitHubIntegration | DevOpsAgent 调用 |

---

## 八、安全考虑

### 8.1 API Key 管理
- API Key 存储在环境变量或加密配置中
- 支持 Key 轮换和过期

### 8.2 权限隔离
- 不同项目的 Agent 实例隔离
- 文件系统沙箱

### 8.3 数据安全
- 记忆数据加密存储（可选）
- 敏感信息脱敏（API Key、密码）

---

## 九、文件变更清单

### 新增文件
```
src/workspace/
├── __init__.py
└── manager.py            # WorkspaceManager

src/knowledge/
├── __init__.py
├── memory.py             # AgentMemory
└── embeddings.py         # EmbeddingProvider

src/team/
├── __init__.py
├── auth.py               # AuthManager, RBAC
└── collaboration.py      # TeamCollaboration

src/ui/frontend/          # React 前端
├── src/components/
├── src/pages/
├── src/hooks/
└── package.json

src/integrations/
├── __init__.py
├── github.py
├── jira.py
└── slack.py

templates/
├── python-project/       # Python 项目模板
└── web-project/          # Web 项目模板
```

### 修改文件
- `src/api/server.py` - 新增 Workspace 和 Memory endpoints
- `src/cli/main.py` - 新增 workspace 命令
- `src/agents/planner.py` - 集成 AgentMemory

---

## 十、测试策略

### 10.1 单元测试
- WorkspaceManager: CRUD 操作、模板应用
- AgentMemory: SQLite 存取、搜索、语义检索
- AuthManager: 权限检查、角色映射
- GitHubIntegration: Mock API 测试

### 10.2 集成测试
- 端到端：创建项目 → 运行工作流 → 查看结果
- WebSocket 实时推送测试

### 10.3 前端测试
- React 组件测试 (Jest + RTL)
- E2E 测试 (Playwright)

---

## 十一、实施步骤

| 步骤 | 内容 | 预估时间 |
|------|------|---------|
| 1 | WorkspaceManager | 1 天 |
| 2 | AgentMemory (SQLite) | 1.5 天 |
| 3 | EmbeddingProvider + VectorStore | 1 天 |
| 4 | AuthManager (RBAC) | 1 天 |
| 5 | FastAPI 扩展 (workspace, memory endpoints) | 1 天 |
| 6 | Web UI 基础框架 | 3 天 |
| 7 | WebSocket 实时通信 | 1 天 |
| 8 | GitHub 集成 | 1 天 |
| 9 | 项目模板 | 0.5 天 |
| 10 | 测试和文档 | 1.5 天 |
| **总计** | | **12.5 天** |

---

## 十二、未来扩展

### 可扩展角色
- **TechnicalWriterAgent**: 自动生成文档
- **ReleaseManagerAgent**: 版本发布和 changelog
- **PerformanceAgent**: 性能分析和优化建议
- **ComplianceAgent**: 合规性检查

### 工具扩展方向
- 云原生：AWS/GCP/Azure SDK 集成
- 数据库：PostgreSQL、MongoDB 操作
- 消息队列：Kafka、RabbitMQ 管理

### 架构演进
- 分布式部署：多节点 Agent 执行
- Agent 编排即服务：提供 REST API 供外部系统调用
- 插件市场：社区贡献的 Agent 和工具

