"""
Phase 8: AgentMemory 知识库与记忆测试
"""

import pytest
import os
import tempfile
from pathlib import Path

from src.knowledge.memory import MemoryEntry, AgentMemory
from src.knowledge.embeddings import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
    MockEmbeddingProvider,
)


class TestMemoryEntry:
    def test_create_entry(self):
        entry = MemoryEntry(key='test', value='value', category='test', project_id='p1')
        assert entry.key == 'test'
        assert entry.value == 'value'
        assert entry.tags == []

    def test_auto_timestamps(self):
        entry = MemoryEntry(key='k', value='v', category='c', project_id='p')
        assert hasattr(entry, 'timestamps')
        assert entry.timestamps is not None


class TestAgentMemory:
    @pytest.fixture
    def mem(self):
        with tempfile.TemporaryDirectory() as td:
            yield AgentMemory(db_path=os.path.join(td, 'test.db'))

    def test_remember_and_recall(self, mem):
        entry = MemoryEntry(key='hello', value='world', category='greeting', project_id='p1')
        mem.remember(entry)
        recalled = mem.recall('hello')
        assert recalled is not None
        assert recalled.value == 'world'

    def test_recall_nonexistent(self, mem):
        assert mem.recall('nonexistent') is None

    def test_overwrite(self, mem):
        mem.remember(MemoryEntry(key='k', value='v1', category='c', project_id='p'))
        mem.remember(MemoryEntry(key='k', value='v2', category='c', project_id='p'))
        assert mem.recall('k').value == 'v2'

    def test_search_by_project(self, mem):
        mem.remember(MemoryEntry(key='k1', value='v1', category='c1', project_id='p1'))
        mem.remember(MemoryEntry(key='k2', value='v2', category='c2', project_id='p2'))
        results = mem.search('p1')
        assert len(results) == 1
        assert results[0].key == 'k1'

    def test_search_by_category(self, mem):
        mem.remember(MemoryEntry(key='k1', value='v1', category='code', project_id='p1'))
        mem.remember(MemoryEntry(key='k2', value='v2', category='design', project_id='p1'))
        results = mem.search('p1', category='code')
        assert len(results) == 1

    def test_search_by_query(self, mem):
        mem.remember(MemoryEntry(key='my_key', value='some_value', category='c', project_id='p1'))
        results = mem.search('p1', query='my_key')
        assert len(results) == 1

    def test_search_limit(self, mem):
        for i in range(10):
            mem.remember(MemoryEntry(key=f'k{i}', value=f'v{i}', category='c', project_id='p1'))
        results = mem.search('p1', limit=3)
        assert len(results) <= 3

    def test_forget(self, mem):
        mem.remember(MemoryEntry(key='del', value='val', category='c', project_id='p'))
        assert mem.recall('del') is not None
        mem.forget('del')
        assert mem.recall('del') is None

    def test_get_stats(self, mem):
        mem.remember(MemoryEntry(key='k1', value='v1', category='code', project_id='p1'))
        mem.remember(MemoryEntry(key='k2', value='v2', category='design', project_id='p1'))
        mem.remember(MemoryEntry(key='k3', value='v3', category='code', project_id='p1'))
        stats = mem.get_stats('p1')
        assert stats['total'] == 3
        assert stats['by_category']['code'] == 2
        assert stats['by_category']['design'] == 1

    def test_persistence(self, mem):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, 'persist.db')
            m1 = AgentMemory(db_path=db)
            m1.remember(MemoryEntry(key='persisted', value='yes', category='c', project_id='p'))
            m2 = AgentMemory(db_path=db)
            recalled = m2.recall('persisted')
            assert recalled is not None
            assert recalled.value == 'yes'


class TestMockEmbeddingProvider:
    def test_embed_query(self):
        config = EmbeddingConfig(model_name='mock', dimensions=128)
        provider = MockEmbeddingProvider(config)
        result = provider.embed_query('hello world')
        assert result.success
        assert len(result.embeddings) == 1
        assert len(result.embeddings[0]) == 128

    def test_embed_texts(self):
        config = EmbeddingConfig(dimensions=64)
        provider = MockEmbeddingProvider(config)
        result = provider.embed_texts(['text1', 'text2'])
        assert result.success
        assert len(result.embeddings) == 2
        assert len(result.embeddings[0]) == 64

    def test_deterministic(self):
        config = EmbeddingConfig(dimensions=128)
        provider = MockEmbeddingProvider(config)
        r1 = provider.embed_query('same text')
        r2 = provider.embed_query('same text')
        assert r1.embeddings[0] == r2.embeddings[0]

    def test_get_dimensions(self):
        config = EmbeddingConfig(dimensions=256)
        provider = MockEmbeddingProvider(config)
        assert provider.get_dimensions() == 256

    def test_empty_texts(self):
        config = EmbeddingConfig(dimensions=128)
        provider = MockEmbeddingProvider(config)
        result = provider.embed_texts([])
        assert result.success
        assert result.embeddings == []
