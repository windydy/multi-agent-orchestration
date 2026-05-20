"""
Claude工具注册表

管理可用工具和自定义工具
"""

from typing import Callable, Optional, Any, Awaitable
from dataclasses import dataclass, field
from .wrapper import ClaudeToolType, ToolCallResult


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    input_schema: dict
    executor: Callable
    timeout: int = 60


class ClaudeToolRegistry:
    """Claude工具注册表
    
    管理内置工具和自定义工具
    """
    
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        """注册内置工具"""
        # read_file
        self.register(ToolDefinition(
            name="read_file",
            description="读取文件内容",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"}
                },
                "required": ["path"]
            },
            executor=self._read_file_executor
        ))
        
        # write_file
        self.register(ToolDefinition(
            name="write_file",
            description="写入文件内容",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "文件内容"}
                },
                "required": ["path", "content"]
            },
            executor=self._write_file_executor
        ))
        
        # edit_file
        self.register(ToolDefinition(
            name="edit_file",
            description="编辑文件，替换指定内容",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "old_string": {"type": "string", "description": "要替换的内容"},
                    "new_string": {"type": "string", "description": "新内容"}
                },
                "required": ["path", "old_string", "new_string"]
            },
            executor=self._edit_file_executor
        ))
        
        # bash
        self.register(ToolDefinition(
            name="bash",
            description="执行shell命令",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"},
                    "timeout": {"type": "integer", "description": "超时秒数", "default": 60}
                },
                "required": ["command"]
            },
            executor=self._bash_executor,
            timeout=300
        ))
        
        # search
        self.register(ToolDefinition(
            name="search",
            description="搜索文件内容或文件名",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "搜索模式"},
                    "path": {"type": "string", "description": "搜索目录", "default": "."}
                },
                "required": ["pattern"]
            },
            executor=self._search_executor
        ))
    
    def register(self, tool: ToolDefinition):
        """注册工具"""
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[ToolDefinition]:
        """获取工具定义"""
        return self._tools.get(name)
    
    def list_tools(self) -> list[str]:
        """列出所有工具"""
        return list(self._tools.keys())
    
    def get_tool_definitions_for_claude(self, tool_names: list[str] = None) -> list[dict]:
        """获取Claude API格式的工具定义"""
        tools = []
        tool_names = tool_names or self.list_tools()
        
        for name in tool_names:
            if name in self._tools:
                tool = self._tools[name]
                tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema
                })
        
        return tools
    
    async def execute(self, name: str, input_data: dict) -> ToolCallResult:
        """执行工具"""
        tool = self.get(name)
        if not tool:
            return ToolCallResult(name, input_data, f"工具不存在: {name}", False)
        
        try:
            import asyncio
            if asyncio.iscoroutinefunction(tool.executor):
                result = await tool.executor(input_data)
            else:
                result = tool.executor(input_data)
            
            if isinstance(result, ToolCallResult):
                return result
            elif isinstance(result, str):
                return ToolCallResult(name, input_data, result, True)
            else:
                return ToolCallResult(name, input_data, str(result), True)
                
        except Exception as e:
            return ToolCallResult(name, input_data, f"执行错误: {str(e)}", False)
    
    # 内置工具执行器
    async def _read_file_executor(self, input_data: dict) -> str:
        import os
        path = input_data.get("path")
        if os.path.exists(path):
            with open(path, "r") as f:
                return f.read()
        return f"文件不存在: {path}"
    
    async def _write_file_executor(self, input_data: dict) -> str:
        import os
        path = input_data.get("path")
        content = input_data.get("content")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"文件已写入: {path}"
    
    async def _edit_file_executor(self, input_data: dict) -> str:
        path = input_data.get("path")
        old = input_data.get("old_string")
        new = input_data.get("new_string")
        
        import os
        if not os.path.exists(path):
            return f"文件不存在: {path}"
        
        with open(path, "r") as f:
            content = f.read()
        
        if old not in content:
            return f"未找到目标内容: {old}"
        
        content = content.replace(old, new)
        with open(path, "w") as f:
            f.write(content)
        
        return f"文件已编辑: {path}"
    
    async def _bash_executor(self, input_data: dict) -> str:
        import asyncio
        command = input_data.get("command")
        timeout = input_data.get("timeout", 60)
        
        result = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(
            result.communicate(),
            timeout=timeout
        )
        
        if stdout:
            return stdout.decode()
        return stderr.decode()
    
    async def _search_executor(self, input_data: dict) -> str:
        import subprocess
        pattern = input_data.get("pattern")
        path = input_data.get("path", ".")
        
        result = subprocess.run(
            ["grep", "-rn", pattern, path],
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            return result.stdout
        return "未找到匹配"


# 全局工具注册表
_global_registry = None

def get_registry() -> ClaudeToolRegistry:
    """获取全局工具注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ClaudeToolRegistry()
    return _global_registry