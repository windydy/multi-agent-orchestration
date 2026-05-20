"""
Tool工具抽象

定义Agent可使用的工具接口
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class ToolConfig:
    """工具配置"""
    name: str
    description: str
    parameters: dict = field(default_factory=dict)  # JSON Schema格式
    timeout: int = 60
    requires_confirmation: bool = False  # 是否需要人工确认
    dangerous: bool = False  # 是否为危险操作


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    execution_time: float = 0.0


class BaseTool(ABC):
    """工具基类
    
    所有工具必须实现run方法
    """
    
    def __init__(self, config: ToolConfig):
        self.config = config
    
    @abstractmethod
    async def run(self, **kwargs) -> ToolResult:
        """执行工具
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            ToolResult: 执行结果
        """
        pass
    
    def validate_params(self, params: dict) -> bool:
        """验证参数
        
        根据config.parameters中的schema验证
        """
        # 简单验证: 检查required参数
        required = self.config.parameters.get("required", [])
        for r in required:
            if r not in params:
                return False
        return True
    
    def to_function_schema(self) -> dict:
        """转换为LLM Function Calling Schema"""
        return {
            "name": self.config.name,
            "description": self.config.description,
            "parameters": self.config.parameters
        }
    
    def __repr__(self) -> str:
        return f"Tool(name={self.config.name})"


# ==================== 内置工具示例 ====================

class SearchTool(BaseTool):
    """搜索工具示例"""
    
    async def run(self, query: str, **kwargs) -> ToolResult:
        # 实际实现会调用搜索API
        return ToolResult(
            success=True,
            output=f"Search results for: {query}",
            metadata={"query": query}
        )


class CodeExecutionTool(BaseTool):
    """代码执行工具示例"""
    
    async def run(self, code: str, language: str = "python", **kwargs) -> ToolResult:
        # 实际实现会安全执行代码
        return ToolResult(
            success=True,
            output=f"Executed {language} code",
            metadata={"language": language, "code_length": len(code)}
        )


class FileReadTool(BaseTool):
    """文件读取工具"""
    
    async def run(self, path: str, **kwargs) -> ToolResult:
        try:
            with open(path, 'r') as f:
                content = f.read()
            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class FileWriteTool(BaseTool):
    """文件写入工具"""
    
    async def run(self, path: str, content: str, **kwargs) -> ToolResult:
        try:
            with open(path, 'w') as f:
                f.write(content)
            return ToolResult(success=True, output=f"Written to {path}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class APICallTool(BaseTool):
    """API调用工具"""
    
    async def run(self, url: str, method: str = "GET", data: dict = None, **kwargs) -> ToolResult:
        # 实际实现会调用HTTP API
        return ToolResult(
            success=True,
            output=f"Called {method} {url}",
            metadata={"url": url, "method": method}
        )


class ToolRegistry:
    """工具注册中心"""
    
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        self._tools[tool.config.name] = tool
    
    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)
    
    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
    
    def get_all_schemas(self) -> list[dict]:
        return [tool.to_function_schema() for tool in self._tools.values()]
    
    async def execute(self, name: str, params: dict) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, output=None, error=f"Tool {name} not found")
        
        if not tool.validate_params(params):
            return ToolResult(success=False, output=None, error="Invalid parameters")
        
        return await tool.run(**params)