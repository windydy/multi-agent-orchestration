"""MemoryEntry 数据类和 AgentMemory 记忆系统

提供知识库记忆条目的数据结构和 Agent 记忆管理系统，
支持 SQLite 存储、精确查询和语义检索。
"""
import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional


@dataclass(frozen=True)
class MemoryEntry:
    """记忆条目数据类

    用于存储和管理知识库中的记忆条目，包含键值对、分类信息、
    项目关联、标签和时间戳。

    Attributes:
        key: 记忆条目的唯一标识键
        value: 记忆条目的值，可以是任意类型
        category: 记忆条目的分类
        project_id: 关联的项目 ID
        tags: 标签列表，用于分类和检索
        timestamps: 时间戳字典，记录创建、更新等时间信息
    """

    key: str
    value: Any
    category: str
    project_id: str
    tags: list[str] = field(default_factory=list)
    timestamps: dict[str, datetime] = field(default_factory=dict)


class AgentMemory:
    """Agent 记忆系统

    双层存储:
    - SQLite: 结构化数据，精确查询
    - 向量数据库: 语义检索（可选）

    功能:
    - remember(entry): 存储记忆
    - recall(key): 按 key 检索
    - search(project_id, category, query): 搜索记忆
    - semantic_search(query, project_id, limit): 语义检索
    - forget(key): 遗忘
    - get_stats(project_id): 获取统计信息
    """

    def __init__(self, db_path: str = "./memory/agent_memory.db",
                 embedding_provider=None):
        """初始化 AgentMemory

        Args:
            db_path: SQLite 数据库路径
            embedding_provider: EmbeddingProvider 实例，用于语义检索
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedding_provider = embedding_provider
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
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

    def remember(self, entry: MemoryEntry) -> bool:
        """存储记忆

        Args:
            entry: MemoryEntry 实例

        Returns:
            bool: 是否成功存储
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            now = datetime.now().isoformat()

            # 检查是否已存在
            cursor = conn.execute("SELECT access_count FROM memory WHERE key = ?", (entry.key,))
            row = cursor.fetchone()

            if row:
                # 更新现有记录
                access_count = row[0] + 1
                conn.execute("""
                    UPDATE memory
                    SET value = ?, category = ?, project_id = ?, tags = ?,
                        updated_at = ?, access_count = ?
                    WHERE key = ?
                """, (
                    json.dumps(entry.value, default=str),
                    entry.category,
                    entry.project_id,
                    json.dumps(entry.tags),
                    now,
                    access_count,
                    entry.key,
                ))
            else:
                # 插入新记录
                conn.execute("""
                    INSERT INTO memory
                    (key, value, category, project_id, tags, created_at, updated_at, access_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.key,
                    json.dumps(entry.value, default=str),
                    entry.category,
                    entry.project_id,
                    json.dumps(entry.tags),
                    now,
                    now,
                    0,
                ))

            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def recall(self, key: str) -> Optional[MemoryEntry]:
        """按 key 检索记忆

        Args:
            key: 记忆条目的键

        Returns:
            Optional[MemoryEntry]: 记忆条目，如果不存在则返回 None
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute("SELECT * FROM memory WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()

        if row:
            # 更新访问计数
            self._increment_access_count(key)

            return MemoryEntry(
                key=row[0],
                value=json.loads(row[1]),
                category=row[2],
                project_id=row[3],
                tags=json.loads(row[4] or "[]"),
                timestamps={
                    "created_at": datetime.fromisoformat(row[5]) if row[5] else None,
                    "updated_at": datetime.fromisoformat(row[6]) if row[6] else None,
                },
            )
        return None

    def search(self, project_id: str, category: str = None,
               query: str = None, limit: int = 10) -> List[MemoryEntry]:
        """搜索记忆

        Args:
            project_id: 项目 ID
            category: 分类（可选）
            query: 搜索关键词（可选）
            limit: 返回结果数量限制

        Returns:
            List[MemoryEntry]: 匹配的记忆条目列表
        """
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
                key=r[0],
                value=json.loads(r[1]),
                category=r[2],
                project_id=r[3],
                tags=json.loads(r[4] or "[]"),
                timestamps={
                    "created_at": datetime.fromisoformat(r[5]) if r[5] else None,
                    "updated_at": datetime.fromisoformat(r[6]) if r[6] else None,
                },
            )
            for r in rows
        ]

    def semantic_search(self, query: str, project_id: str = None,
                        limit: int = 5) -> List[MemoryEntry]:
        """语义检索（向量搜索）

        Args:
            query: 搜索查询
            project_id: 项目 ID（可选）
            limit: 返回结果数量限制

        Returns:
            List[MemoryEntry]: 语义匹配的记忆条目列表
        """
        if not self.embedding_provider:
            return []

        # 获取查询向量
        result = self.embedding_provider.embed_query(query)
        if not result.success or not result.embeddings:
            return []

        query_vec = result.embeddings[0]

        # 获取所有记忆条目
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute("SELECT * FROM memory")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return []

        # 计算相似度（余弦相似度）
        import math

        def cosine_similarity(vec1, vec2):
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm1 = math.sqrt(sum(a * a for a in vec1))
            norm2 = math.sqrt(sum(b * b for b in vec2))
            if norm1 == 0 or norm2 == 0:
                return 0
            return dot_product / (norm1 * norm2)

        # 为每个条目计算相似度
        scored_entries = []
        for row in rows:
            # 过滤项目
            if project_id and row[3] != project_id:
                continue

            # 获取条目的向量（使用 value 的 embedding）
            entry_result = self.embedding_provider.embed_texts([row[1]])
            if entry_result.success and entry_result.embeddings:
                entry_vec = entry_result.embeddings[0]
                similarity = cosine_similarity(query_vec, entry_vec)
                scored_entries.append((similarity, row))

        # 按相似度排序
        scored_entries.sort(key=lambda x: x[0], reverse=True)

        # 返回前 limit 个结果
        results = []
        for _, row in scored_entries[:limit]:
            entry = MemoryEntry(
                key=row[0],
                value=json.loads(row[1]),
                category=row[2],
                project_id=row[3],
                tags=json.loads(row[4] or "[]"),
                timestamps={
                    "created_at": datetime.fromisoformat(row[5]) if row[5] else None,
                    "updated_at": datetime.fromisoformat(row[6]) if row[6] else None,
                },
            )
            results.append(entry)

        return results

    def forget(self, key: str) -> bool:
        """遗忘（删除记忆）

        Args:
            key: 记忆条目的键

        Returns:
            bool: 是否成功删除
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("DELETE FROM memory WHERE key = ?", (key,))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def get_stats(self, project_id: str = None) -> dict:
        """获取统计信息

        Args:
            project_id: 项目 ID（可选）

        Returns:
            dict: 统计信息，包含 total 和 by_category
        """
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

    def _increment_access_count(self, key: str):
        """增加访问计数

        Args:
            key: 记忆条目的键
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "UPDATE memory SET access_count = access_count + 1 WHERE key = ?",
            (key,)
        )
        conn.commit()
        conn.close()

    def clear(self, project_id: str = None) -> int:
        """清空记忆

        Args:
            project_id: 项目 ID（可选），如果为 None 则清空所有

        Returns:
            int: 删除的记录数
        """
        conn = sqlite3.connect(str(self.db_path))
        if project_id:
            cursor = conn.execute("SELECT COUNT(*) FROM memory WHERE project_id = ?", (project_id,))
            count = cursor.fetchone()[0]
            conn.execute("DELETE FROM memory WHERE project_id = ?", (project_id,))
        else:
            cursor = conn.execute("SELECT COUNT(*) FROM memory")
            count = cursor.fetchone()[0]
            conn.execute("DELETE FROM memory")
        conn.commit()
        conn.close()
        return count

    def get_all_keys(self, project_id: str = None) -> List[str]:
        """获取所有记忆的键

        Args:
            project_id: 项目 ID（可选）

        Returns:
            List[str]: 键列表
        """
        conn = sqlite3.connect(str(self.db_path))
        if project_id:
            cursor = conn.execute("SELECT key FROM memory WHERE project_id = ?", (project_id,))
        else:
            cursor = conn.execute("SELECT key FROM memory")
        keys = [row[0] for row in cursor.fetchall()]
        conn.close()
        return keys
