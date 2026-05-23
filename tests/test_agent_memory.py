"""AgentMemory 类的测试用例 — 适配新 API"""
import pytest
import os
import json
from datetime import datetime
from src.knowledge.memory import MemoryEntry, AgentMemory


@pytest.fixture
def db_path(tmp_path):
    """提供临时数据库路径"""
    return str(tmp_path / "test_memory.db")


@pytest.fixture
def memory(db_path):
    """提供 AgentMemory 实例"""
    return AgentMemory(db_path=db_path)


class TestAgentMemoryInit:
    """AgentMemory 初始化测试"""

    def test_init_creates_database(self, db_path):
        """测试初始化时创建数据库"""
        mem = AgentMemory(db_path=db_path)
        assert os.path.exists(db_path)

    def test_init_creates_table(self, db_path):
        """测试初始化时创建表"""
        import sqlite3
        mem = AgentMemory(db_path=db_path)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memory'")
        result = cursor.fetchone()
        conn.close()
        assert result is not None
        assert result[0] == "memory"

    def test_init_empty_workspace(self, db_path):
        """测试空工作空间初始化"""
        mem = AgentMemory(db_path=db_path)
        stats = mem.get_stats("nonexistent")
        assert stats["total"] == 0


class TestAddAndRecall:
    """添加和回忆测试"""

    def test_add_and_recall_basic(self, memory, db_path):
        """测试基本的添加和回忆"""
        entry = MemoryEntry(
            key="test_key",
            value="test_value",
            category="test",
            project_id="proj1",
        )
        memory.remember(entry)
        
        recalled = memory.recall("test_key")
        assert recalled is not None
        assert recalled.key == "test_key"
        assert recalled.value == "test_value"
        assert recalled.category == "test"
        assert recalled.project_id == "proj1"

    def test_add_complex_value(self, memory):
        """测试添加复杂类型的值"""
        complex_value = {"nested": {"key": "value"}, "list": [1, 2, 3]}
        entry = MemoryEntry(
            key="complex",
            value=complex_value,
            category="data",
            project_id="proj1",
        )
        memory.remember(entry)
        recalled = memory.recall("complex")
        assert recalled.value == complex_value

    def test_add_empty_value(self, memory):
        """测试添加空值"""
        entry = MemoryEntry(
            key="empty",
            value="",
            category="test",
            project_id="proj1",
        )
        memory.remember(entry)
        recalled = memory.recall("empty")
        assert recalled is not None
        assert recalled.value == ""

    def test_add_special_characters(self, memory):
        """测试添加特殊字符"""
        special_value = "Hello! @#$%^&*()_+-=[]{}|;':\",./<>?"
        entry = MemoryEntry(
            key="special",
            value=special_value,
            category="test",
            project_id="proj1",
        )
        memory.remember(entry)
        recalled = memory.recall("special")
        assert recalled.value == special_value

    def test_add_unicode(self, memory):
        """测试添加 Unicode 字符"""
        unicode_value = "こんにちは世界 🌍"
        entry = MemoryEntry(
            key="unicode",
            value=unicode_value,
            category="test",
            project_id="proj1",
        )
        memory.remember(entry)
        recalled = memory.recall("unicode")
        assert recalled.value == unicode_value


class TestSearch:
    """搜索测试"""

    def test_search_by_project(self, memory):
        """按项目搜索"""
        memory.remember(MemoryEntry(key="k1", value="v1", category="c", project_id="proj1"))
        memory.remember(MemoryEntry(key="k2", value="v2", category="c", project_id="proj2"))
        
        results = memory.search("proj1")
        assert len(results) == 1
        assert results[0].key == "k1"

    def test_search_by_category(self, memory):
        """按类别搜索"""
        memory.remember(MemoryEntry(key="k1", value="v1", category="code", project_id="proj1"))
        memory.remember(MemoryEntry(key="k2", value="v2", category="design", project_id="proj1"))
        
        results = memory.search("proj1", category="code")
        assert len(results) == 1
        assert results[0].category == "code"

    def test_search_by_query(self, memory):
        """按查询字符串搜索"""
        memory.remember(MemoryEntry(key="my_key", value="some_value", category="c", project_id="proj1"))
        results = memory.search("proj1", query="my_key")
        assert len(results) >= 1

    def test_search_limit(self, memory):
        """搜索结果限制"""
        for i in range(10):
            memory.remember(MemoryEntry(key=f"k{i}", value=f"v{i}", category="c", project_id="proj1"))
        results = memory.search("proj1", limit=3)
        assert len(results) <= 3

    def test_search_no_results(self, memory):
        """搜索无结果"""
        results = memory.search("nonexistent")
        assert len(results) == 0


class TestUpdate:
    """更新测试"""

    def test_update_existing_key(self, memory):
        """测试更新已存在的键"""
        memory.remember(MemoryEntry(key="k", value="v1", category="c", project_id="proj1"))
        memory.remember(MemoryEntry(key="k", value="v2", category="c", project_id="proj1"))
        recalled = memory.recall("k")
        assert recalled.value == "v2"

    def test_update_category(self, memory):
        """测试更新类别"""
        memory.remember(MemoryEntry(key="k", value="v", category="old", project_id="proj1"))
        memory.remember(MemoryEntry(key="k", value="v", category="new", project_id="proj1"))
        recalled = memory.recall("k")
        assert recalled.category == "new"


class TestForget:
    """删除测试"""

    def test_forget_existing_key(self, memory):
        """测试删除已存在的键"""
        memory.remember(MemoryEntry(key="del", value="val", category="c", project_id="proj1"))
        memory.forget("del")
        assert memory.recall("del") is None

    def test_forget_nonexistent_key(self, memory):
        """测试删除不存在的键"""
        memory.forget("nonexistent")  # 不应抛异常


class TestGetStats:
    """统计测试"""

    def test_get_stats_basic(self, memory):
        """基本统计"""
        memory.remember(MemoryEntry(key="k1", value="v1", category="code", project_id="proj1"))
        memory.remember(MemoryEntry(key="k2", value="v2", category="design", project_id="proj1"))
        stats = memory.get_stats("proj1")
        assert stats["total"] == 2

    def test_get_stats_with_categories(self, memory):
        """按类别统计"""
        memory.remember(MemoryEntry(key="k1", value="v1", category="code", project_id="proj1"))
        memory.remember(MemoryEntry(key="k2", value="v2", category="code", project_id="proj1"))
        memory.remember(MemoryEntry(key="k3", value="v3", category="design", project_id="proj1"))
        stats = memory.get_stats("proj1")
        assert stats["by_category"]["code"] == 2
        assert stats["by_category"]["design"] == 1

    def test_get_stats_empty_project(self, memory):
        """空项目统计"""
        stats = memory.get_stats("nonexistent")
        assert stats["total"] == 0


class TestPersistence:
    """持久化测试"""

    def test_save_and_reload(self, db_path):
        """测试保存和重新加载"""
        m1 = AgentMemory(db_path=db_path)
        m1.remember(MemoryEntry(key="persisted", value="yes", category="c", project_id="proj1"))
        
        m2 = AgentMemory(db_path=db_path)
        recalled = m2.recall("persisted")
        assert recalled is not None
        assert recalled.value == "yes"


class TestSemanticSearch:
    """语义搜索测试"""

    def test_semantic_search_no_embeddings(self, memory):
        """无 embedding provider 时的语义搜索"""
        memory.remember(MemoryEntry(key="k", value="v", category="c", project_id="proj1"))
        # 没有 embedding provider 时应返回空或降级
        results = memory.semantic_search("query", project_id="proj1")
        # 可能返回空列表（无向量存储）
        assert isinstance(results, list)
