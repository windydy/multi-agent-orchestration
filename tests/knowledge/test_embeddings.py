"""
EmbeddingProvider 测试

严格遵循 TDD: 先写测试，再写实现
"""

import pytest
from typing import List
from src.knowledge.embeddings import (
    EmbeddingConfig,
    EmbeddingResult,
    EmbeddingProvider,
    MockEmbeddingProvider,
)


class TestEmbeddingConfig:
    """EmbeddingConfig 配置类测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = EmbeddingConfig()
        assert config.model_name == "text-embedding-3-small"
        assert config.dimensions == 1536
        assert config.batch_size == 32
        assert config.max_retries == 3

    def test_custom_config(self):
        """测试自定义配置"""
        config = EmbeddingConfig(
            model_name="custom-model",
            dimensions=768,
            batch_size=16,
            max_retries=5,
        )
        assert config.model_name == "custom-model"
        assert config.dimensions == 768
        assert config.batch_size == 16
        assert config.max_retries == 5


class TestEmbeddingResult:
    """EmbeddingResult 结果类测试"""

    def test_result_creation(self):
        """测试结果创建"""
        embeddings = [[0.1, 0.2], [0.3, 0.4]]
        result = EmbeddingResult(
            embeddings=embeddings,
            model="test-model",
            dimensions=2,
            usage={"prompt_tokens": 10, "total_tokens": 10},
        )
        assert result.embeddings == embeddings
        assert result.model == "test-model"
        assert result.dimensions == 2
        assert result.usage["prompt_tokens"] == 10

    def test_result_with_error(self):
        """测试结果包含错误"""
        result = EmbeddingResult(
            embeddings=[],
            model="test-model",
            dimensions=0,
            error="API timeout",
        )
        assert result.error == "API timeout"
        assert result.success is False

    def test_result_success_property(self):
        """测试 success 属性"""
        # 无错误时 success 为 True
        result_ok = EmbeddingResult(
            embeddings=[[0.1]],
            model="test",
            dimensions=1,
        )
        assert result_ok.success is True

        # 有错误时 success 为 False
        result_err = EmbeddingResult(
            embeddings=[],
            model="test",
            dimensions=0,
            error="fail",
        )
        assert result_err.success is False


class TestEmbeddingProviderABC:
    """EmbeddingProvider 抽象基类测试"""

    def test_cannot_instantiate_abstract(self):
        """测试不能直接实例化抽象基类"""
        with pytest.raises(TypeError):
            EmbeddingProvider(EmbeddingConfig())

    def test_abstract_methods_exist(self):
        """测试抽象方法定义"""
        # 验证抽象方法存在
        assert hasattr(EmbeddingProvider, 'embed_texts')
        assert hasattr(EmbeddingProvider, 'embed_query')
        assert hasattr(EmbeddingProvider, 'get_dimensions')


class TestMockEmbeddingProvider:
    """MockEmbeddingProvider 占位实现测试"""

    @pytest.fixture
    def provider(self):
        """创建 MockEmbeddingProvider 实例"""
        config = EmbeddingConfig(model_name="mock-model", dimensions=128)
        return MockEmbeddingProvider(config)

    def test_provider_creation(self):
        """测试提供者创建"""
        config = EmbeddingConfig()
        provider = MockEmbeddingProvider(config)
        assert provider.config.model_name == "text-embedding-3-small"

    def test_embed_single_text(self, provider):
        """测试单个文本嵌入"""
        result = provider.embed_texts(["hello world"])
        assert result.success is True
        assert len(result.embeddings) == 1
        assert len(result.embeddings[0]) == 128  # dimensions from config
        assert result.model == "mock-model"
        assert result.dimensions == 128

    def test_embed_multiple_texts(self, provider):
        """测试多个文本嵌入"""
        texts = ["hello", "world", "test"]
        result = provider.embed_texts(texts)
        assert result.success is True
        assert len(result.embeddings) == 3
        for embedding in result.embeddings:
            assert len(embedding) == 128

    def test_embed_empty_list(self, provider):
        """测试空列表嵌入"""
        result = provider.embed_texts([])
        assert result.success is True
        assert len(result.embeddings) == 0

    def test_embed_query(self, provider):
        """测试查询嵌入"""
        result = provider.embed_query("search query")
        assert result.success is True
        assert len(result.embeddings) == 1
        assert len(result.embeddings[0]) == 128

    def test_get_dimensions(self, provider):
        """测试获取维度"""
        assert provider.get_dimensions() == 128

    def test_deterministic_embeddings(self):
        """测试相同输入产生相同输出（确定性）"""
        config = EmbeddingConfig(dimensions=64)
        provider = MockEmbeddingProvider(config)
        
        result1 = provider.embed_texts(["test text"])
        result2 = provider.embed_texts(["test text"])
        
        assert result1.embeddings == result2.embeddings

    def test_different_texts_different_embeddings(self, provider):
        """测试不同文本产生不同嵌入"""
        result1 = provider.embed_texts(["hello"])
        result2 = provider.embed_texts(["world"])
        
        assert result1.embeddings != result2.embeddings

    def test_batch_processing(self, provider):
        """测试批处理"""
        texts = [f"text_{i}" for i in range(50)]  # 超过 batch_size=32
        result = provider.embed_texts(texts)
        assert result.success is True
        assert len(result.embeddings) == 50

    def test_usage_metadata(self, provider):
        """测试使用量元数据"""
        result = provider.embed_texts(["hello", "world"])
        assert result.usage is not None
        assert "prompt_tokens" in result.usage
        assert result.usage["prompt_tokens"] > 0
