"""
EmbeddingProvider 抽象基类和占位实现

提供文本嵌入向量生成的统一接口，支持多种 embedding 模型。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional
import hashlib
import struct
import math


@dataclass
class EmbeddingConfig:
    """Embedding 配置"""
    model_name: str = "text-embedding-3-small"
    dimensions: int = 1536
    batch_size: int = 32
    max_retries: int = 3
    timeout: int = 60
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    extra_params: dict = field(default_factory=dict)


@dataclass
class EmbeddingResult:
    """Embedding 结果"""
    embeddings: List[List[float]]
    model: str
    dimensions: int
    usage: dict = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """是否成功"""
        return self.error is None


class EmbeddingProvider(ABC):
    """Embedding 提供者抽象基类
    
    所有 embedding 提供者必须实现以下方法:
    - embed_texts: 批量文本嵌入
    - embed_query: 查询文本嵌入
    - get_dimensions: 获取向量维度
    """

    def __init__(self, config: EmbeddingConfig):
        """初始化 EmbeddingProvider
        
        Args:
            config: Embedding 配置
        """
        self.config = config

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> EmbeddingResult:
        """批量文本嵌入
        
        Args:
            texts: 待嵌入的文本列表
            
        Returns:
            EmbeddingResult: 嵌入结果
        """
        pass

    @abstractmethod
    def embed_query(self, query: str) -> EmbeddingResult:
        """查询文本嵌入
        
        Args:
            query: 查询文本
            
        Returns:
            EmbeddingResult: 嵌入结果
        """
        pass

    @abstractmethod
    def get_dimensions(self) -> int:
        """获取向量维度
        
        Returns:
            int: 向量维度
        """
        pass

    def _batch_texts(self, texts: List[str]) -> List[List[str]]:
        """将文本列表分批
        
        Args:
            texts: 文本列表
            
        Returns:
            List[List[str]]: 分批后的文本列表
        """
        batch_size = self.config.batch_size
        return [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]

    def __repr__(self) -> str:
        return f"EmbeddingProvider(model={self.config.model_name}, dims={self.config.dimensions})"


# ==================== 占位实现 ====================

class MockEmbeddingProvider(EmbeddingProvider):
    """Mock Embedding 提供者（用于测试和开发）
    
    使用确定性哈希生成伪随机向量，相同输入始终产生相同输出。
    """

    def embed_texts(self, texts: List[str]) -> EmbeddingResult:
        """批量文本嵌入（Mock 实现）
        
        Args:
            texts: 待嵌入的文本列表
            
        Returns:
            EmbeddingResult: 包含伪随机向量的结果
        """
        if not texts:
            return EmbeddingResult(
                embeddings=[],
                model=self.config.model_name,
                dimensions=self.config.dimensions,
                usage={"prompt_tokens": 0, "total_tokens": 0},
            )

        all_embeddings = []
        total_tokens = 0

        # 按批处理
        for batch in self._batch_texts(texts):
            for text in batch:
                embedding = self._generate_embedding(text)
                all_embeddings.append(embedding)
                # 估算 token 数（简单按字符数/4）
                total_tokens += max(1, len(text) // 4)

        return EmbeddingResult(
            embeddings=all_embeddings,
            model=self.config.model_name,
            dimensions=self.config.dimensions,
            usage={
                "prompt_tokens": total_tokens,
                "total_tokens": total_tokens,
            },
        )

    def embed_query(self, query: str) -> EmbeddingResult:
        """查询文本嵌入（Mock 实现）
        
        Args:
            query: 查询文本
            
        Returns:
            EmbeddingResult: 包含伪随机向量的结果
        """
        return self.embed_texts([query])

    def get_dimensions(self) -> int:
        """获取向量维度
        
        Returns:
            int: 配置的向量维度
        """
        return self.config.dimensions

    def _generate_embedding(self, text: str) -> List[float]:
        """基于文本生成确定性伪随机向量
        
        使用 SHA-256 哈希确保相同输入产生相同输出。
        
        Args:
            text: 输入文本
            
        Returns:
            List[float]: 归一化的伪随机向量
        """
        dimensions = self.config.dimensions
        
        # 使用 SHA-256 生成确定性哈希
        hash_bytes = hashlib.sha256(text.encode('utf-8')).digest()
        
        # 扩展哈希以覆盖所有维度
        embedding = []
        seed = int.from_bytes(hash_bytes[:8], byteorder='big')
        
        for i in range(dimensions):
            # 使用线性同余生成器产生伪随机数
            seed = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
            # 转换为 [-1, 1] 范围的浮点数
            value = (seed / 0xFFFFFFFFFFFFFFFF) * 2 - 1
            embedding.append(value)
        
        # L2 归一化
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding
