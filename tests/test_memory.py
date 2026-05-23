"""MemoryEntry 数据类的测试用例"""
import pytest
from datetime import datetime
from src.knowledge.memory import MemoryEntry


class TestMemoryEntry:
    """MemoryEntry 数据类测试"""

    def test_create_basic_entry(self):
        """测试创建基本 MemoryEntry"""
        entry = MemoryEntry(
            key="test_key",
            value="test_value",
            category="test_category",
            project_id="proj_001",
        )
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.category == "test_category"
        assert entry.project_id == "proj_001"
        assert entry.tags == []
        assert entry.timestamps == {}

    def test_create_entry_with_tags(self):
        """测试创建带标签的 MemoryEntry"""
        entry = MemoryEntry(
            key="test_key",
            value="test_value",
            category="test_category",
            project_id="proj_001",
            tags=["tag1", "tag2", "tag3"],
        )
        assert entry.tags == ["tag1", "tag2", "tag3"]

    def test_create_entry_with_timestamps(self):
        """测试创建带时间戳的 MemoryEntry"""
        now = datetime.now()
        entry = MemoryEntry(
            key="test_key",
            value="test_value",
            category="test_category",
            project_id="proj_001",
            timestamps={"created_at": now, "updated_at": now},
        )
        assert entry.timestamps["created_at"] == now
        assert entry.timestamps["updated_at"] == now

    def test_entry_with_complex_value(self):
        """测试包含复杂值的 MemoryEntry"""
        complex_value = {"nested": {"key": "value"}, "list": [1, 2, 3]}
        entry = MemoryEntry(
            key="complex_key",
            value=complex_value,
            category="complex_category",
            project_id="proj_002",
        )
        assert entry.value == complex_value

    def test_entry_immutability(self):
        """测试 MemoryEntry 的不可变性（frozen=True）"""
        entry = MemoryEntry(
            key="test_key",
            value="test_value",
            category="test_category",
            project_id="proj_001",
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            entry.key = "new_key"

    def test_entry_equality(self):
        """测试 MemoryEntry 的相等性比较"""
        entry1 = MemoryEntry(
            key="test_key",
            value="test_value",
            category="test_category",
            project_id="proj_001",
            tags=["tag1"],
            timestamps={"created_at": datetime.now()},
        )
        entry2 = MemoryEntry(
            key="test_key",
            value="test_value",
            category="test_category",
            project_id="proj_001",
            tags=["tag1"],
            timestamps={"created_at": entry1.timestamps["created_at"]},
        )
        assert entry1 == entry2

    def test_entry_inequality(self):
        """测试 MemoryEntry 的不相等性比较"""
        entry1 = MemoryEntry(
            key="test_key",
            value="test_value",
            category="test_category",
            project_id="proj_001",
        )
        entry2 = MemoryEntry(
            key="different_key",
            value="test_value",
            category="test_category",
            project_id="proj_001",
        )
        assert entry1 != entry2

    def test_entry_repr(self):
        """测试 MemoryEntry 的字符串表示"""
        entry = MemoryEntry(
            key="test_key",
            value="test_value",
            category="test_category",
            project_id="proj_001",
        )
        repr_str = repr(entry)
        assert "MemoryEntry" in repr_str
        assert "test_key" in repr_str

    def test_entry_with_empty_tags(self):
        """测试空标签列表"""
        entry = MemoryEntry(
            key="test_key",
            value="test_value",
            category="test_category",
            project_id="proj_001",
            tags=[],
        )
        assert entry.tags == []

    def test_entry_with_empty_timestamps(self):
        """测试空时间戳字典"""
        entry = MemoryEntry(
            key="test_key",
            value="test_value",
            category="test_category",
            project_id="proj_001",
            timestamps={},
        )
        assert entry.timestamps == {}

    def test_entry_asdict(self):
        """测试将 MemoryEntry 转换为字典"""
        from dataclasses import asdict

        entry = MemoryEntry(
            key="test_key",
            value="test_value",
            category="test_category",
            project_id="proj_001",
            tags=["tag1"],
            timestamps={},
        )
        entry_dict = asdict(entry)
        assert entry_dict["key"] == "test_key"
        assert entry_dict["value"] == "test_value"
        assert entry_dict["category"] == "test_category"
        assert entry_dict["project_id"] == "proj_001"
        assert entry_dict["tags"] == ["tag1"]
        assert entry_dict["timestamps"] == {}
