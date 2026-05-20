"""
Claude Agent Wrapper

将Claude API封装为BaseAgent兼容的接口
"""

import os
import json
import asyncio
from typing import Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# 导入Anthropic API
try:
    from anthropic import Anthropic, AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# 导入已有抽象
from src.core.agent import BaseAgent, AgentConfig, AgentResult, AgentRole


class ClaudeToolType(Enum):
    """Claude内置工具类型"""
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    EDIT_FILE = "edit_file"
    BASH = "bash"
    SEARCH = "search"
    TASK = "task"


@dataclass
class ClaudeSDKConfig:
    """Claude SDK配置"""
    api_key: Optional[str] = None  # None时从环境变量获取
    model: str = "glm-5"  # 默认使用 glm-5
    max_tokens: int = 4096
    temperature: float = 0.7
    tools: list[ClaudeToolType] = field(default_factory=lambda: [
        ClaudeToolType.READ_FILE,
        ClaudeToolType.WRITE_FILE,
        ClaudeToolType.BASH,
        ClaudeToolType.SEARCH,
    ])
    system_prompt: str = ""
    base_url: Optional[str] = None  # 自定义API endpoint
    provider: str = "anthropic"  # anthropic / dashscope
    
    # DashScope 配置（glm-5 默认）
    DASHSCOPE_BASE_URL: str = "https://coding.dashscope.aliyuncs.com/apps/anthropic"
    DASHSCOPE_ENV_KEY: str = "DASHSCOPE_API_KEY"


@dataclass
class ToolCallResult:
    """工具调用结果"""
    tool_name: str
    tool_input: dict
    output: str
    success: bool = True
    error: Optional[str] = None


class ClaudeAgentWrapper(BaseAgent):
    """Claude Agent适配器 - 继承BaseAgent
    
    使用Anthropic Messages API实现Agent功能，
    支持工具调用、流式响应、Hooks拦截。
    """
    
    def __init__(
        self,
        config: AgentConfig,
        claude_config: ClaudeSDKConfig = None,
        hooks: list[Callable] = None,
        tool_executor: Callable[[str, dict], Awaitable[ToolCallResult]] = None
    ):
        super().__init__(config)
        
        self.claude_config = claude_config or ClaudeSDKConfig(
            model=config.model,
            temperature=config.temperature,
            system_prompt=config.system_prompt
        )
        
        # API客户端
        self._client = None
        self._async_client = None
        self._init_client()
        
        # Hooks
        self._hooks = hooks or []
        
        # 工具执行器
        self._tool_executor = tool_executor or self._default_tool_executor
        
        # 会话记忆
        self._conversation_history: list[dict] = []
        
        # 成本追踪
        self._total_cost: float = 0.0
        self._total_tokens: dict = {"input": 0, "output": 0}
    
    def _init_client(self):
        """初始化Anthropic客户端
        
        从 Hermes config.yaml 读取配置，支持：
        1. Hermes 配置 (config.yaml 的 model.base_url + model.api_key)
        2. 环境变量 (DASHSCOPE_API_KEY / ANTHROPIC_API_KEY)
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic包未安装，请运行: pip install anthropic")
        
        # 优先从 Hermes config.yaml 读取
        hermes_config = self._load_hermes_config()
        
        # 确定 API Key
        api_key = self.claude_config.api_key
        if not api_key:
            api_key = hermes_config.get("api_key")
        if not api_key:
            api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not api_key:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        
        if not api_key:
            raise ValueError("需要配置 API Key (Hermes config.yaml 或 DASHSCOPE_API_KEY/ANTHROPIC_API_KEY)")
        
        # 确定 base_url
        base_url = self.claude_config.base_url
        if not base_url:
            base_url = hermes_config.get("base_url")
        if not base_url and os.environ.get("DASHSCOPE_API_KEY"):
            base_url = "https://coding.dashscope.aliyuncs.com/apps/anthropic"
        
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self._client = Anthropic(**client_kwargs)
        self._async_client = AsyncAnthropic(**client_kwargs)
    
    def _load_hermes_config(self) -> dict:
        """从 Hermes config.yaml 读取模型配置"""
        import yaml
        from pathlib import Path
        
        config_path = Path.home() / ".hermes" / "config.yaml"
        if not config_path.exists():
            return {}
        
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
            
            model_config = config.get("model", {})
            return {
                "api_key": model_config.get("api_key"),
                "base_url": model_config.get("base_url"),
            }
        except Exception:
            return {}
    
    async def run(self, input: Any, context: dict = None) -> AgentResult:
        """执行Agent任务
        
        Args:
            input: 任务输入 (字符串或结构化数据)
            context: 执行上下文
            
        Returns:
            AgentResult: 执行结果
        """
        context = context or {}
        
        # 构建输入消息
        input_message = self._build_input_message(input, context)
        
        # 开始对话循环
        steps = []
        messages = [{"role": "user", "content": input_message}]
        final_output = None
        
        iteration = 0
        max_iterations = self.config.max_iterations
        
        try:
            while iteration < max_iterations:
                iteration += 1
                step_info = f"Iteration {iteration}"
                steps.append(step_info)
                
                # 调用Claude API
                response = await self._call_claude(messages)
                
                # 更新成本追踪
                self._update_cost_tracking(response)
                
                # 检查响应类型
                content_blocks = response.content
                
                # 检查是否需要工具调用
                tool_calls = [b for b in content_blocks if b.type == "tool_use"]
                text_blocks = [b for b in content_blocks if b.type == "text"]
                
                if tool_calls:
                    # 处理工具调用
                    assistant_message = {"role": "assistant", "content": content_blocks}
                    messages.append(assistant_message)
                    
                    tool_results = []
                    for tool_call in tool_calls:
                        # 执行Hooks
                        hook_result = await self._execute_hooks("pre_tool_call", {
                            "tool": tool_call.name,
                            "input": tool_call.input
                        })
                        
                        if hook_result and hook_result.get("block"):
                            # Hook阻止了工具调用
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_call.id,
                                "content": f"Blocked: {hook_result.get('reason', 'Safety check')}",
                                "is_error": True
                            })
                            continue
                        
                        # 执行工具
                        result = await self._tool_executor(tool_call.name, tool_call.input)
                        
                        # 后执行Hook
                        await self._execute_hooks("post_tool_call", {
                            "tool": tool_call.name,
                            "input": tool_call.input,
                            "output": result.output,
                            "success": result.success
                        })
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": result.output if result.success else f"Error: {result.error}",
                            "is_error": not result.success
                        })
                    
                    messages.append({"role": "user", "content": tool_results})
                    
                else:
                    # 无工具调用，获取最终输出
                    final_output = "\n".join([b.text for b in text_blocks])
                    break
            
            # 记录历史
            self._conversation_history.extend(messages)
            
            return AgentResult(
                success=True,
                output=final_output or "任务执行完成",
                metadata={
                    "iterations": iteration,
                    "tokens": self._total_tokens,
                    "cost": self._total_cost,
                    "model": self.claude_config.model,
                },
                steps=steps
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                output=None,
                error=str(e),
                metadata={"iterations": iteration},
                steps=steps
            )
    
    async def plan(self, task: str) -> list[str]:
        """规划任务步骤
        
        使用Claude生成执行计划
        """
        plan_prompt = f"""
        请为以下任务生成执行步骤列表:
        
        任务: {task}
        
        输出格式: 每行一个步骤，格式为 "Step N: 步骤描述"
        只输出步骤，不要其他说明。
        """
        
        response = await self._call_claude([
            {"role": "user", "content": plan_prompt}
        ], max_tokens_override=1024)
        
        # 解析步骤
        steps = []
        for block in response.content:
            if block.type == "text":
                for line in block.text.strip().split("\n"):
                    if line.strip().startswith("Step"):
                        steps.append(line.strip())
        
        return steps
    
    def _build_input_message(self, input: Any, context: dict) -> str:
        """构建输入消息"""
        parts = []
        
        # 任务描述
        if isinstance(input, str):
            parts.append(f"任务: {input}")
        else:
            parts.append(f"任务: {json.dumps(input, ensure_ascii=False)}")
        
        # 角色
        parts.append(f"你的角色: {self.config.description}")
        
        # 上下文
        if context:
            parts.append(f"执行上下文:\n{json.dumps(context, ensure_ascii=False, indent=2)}")
        
        # 前置节点结果
        if "previous_results" in context:
            prev = context["previous_results"]
            parts.append(f"前置节点结果:\n{json.dumps(prev, ensure_ascii=False, indent=2)}")
        
        return "\n\n".join(parts)
    
    async def _call_claude(self, messages: list[dict], max_tokens_override: int = None) -> Any:
        """调用Claude API"""
        max_tokens = max_tokens_override or self.claude_config.max_tokens
        
        # 构建工具定义
        tools = self._build_tool_definitions()
        
        response = await self._async_client.messages.create(
            model=self.claude_config.model,
            max_tokens=max_tokens,
            temperature=self.claude_config.temperature,
            system=self.claude_config.system_prompt,
            messages=messages,
            tools=tools if tools else None,
        )
        
        return response
    
    def _build_tool_definitions(self) -> list[dict]:
        """构建Claude工具定义"""
        tools = []
        
        for tool_type in self.claude_config.tools:
            if tool_type == ClaudeToolType.READ_FILE:
                tools.append({
                    "name": "read_file",
                    "description": "读取文件内容",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "文件路径"}
                        },
                        "required": ["path"]
                    }
                })
            elif tool_type == ClaudeToolType.WRITE_FILE:
                tools.append({
                    "name": "write_file",
                    "description": "写入文件内容",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "文件路径"},
                            "content": {"type": "string", "description": "文件内容"}
                        },
                        "required": ["path", "content"]
                    }
                })
            elif tool_type == ClaudeToolType.EDIT_FILE:
                tools.append({
                    "name": "edit_file",
                    "description": "编辑文件，替换指定内容",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "文件路径"},
                            "old_string": {"type": "string", "description": "要替换的内容"},
                            "new_string": {"type": "string", "description": "新内容"}
                        },
                        "required": ["path", "old_string", "new_string"]
                    }
                })
            elif tool_type == ClaudeToolType.BASH:
                tools.append({
                    "name": "bash",
                    "description": "执行shell命令",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "要执行的命令"},
                            "timeout": {"type": "integer", "description": "超时秒数", "default": 60}
                        },
                        "required": ["command"]
                    }
                })
            elif tool_type == ClaudeToolType.SEARCH:
                tools.append({
                    "name": "search",
                    "description": "搜索文件",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string", "description": "搜索模式"},
                            "path": {"type": "string", "description": "搜索目录", "default": "."}
                        },
                        "required": ["pattern"]
                    }
                })
        
        return tools
    
    async def _default_tool_executor(self, tool_name: str, tool_input: dict) -> ToolCallResult:
        """默认工具执行器"""
        try:
            if tool_name == "read_file":
                path = tool_input.get("path")
                if os.path.exists(path):
                    with open(path, "r") as f:
                        content = f.read()
                    return ToolCallResult(tool_name, tool_input, content, True)
                else:
                    return ToolCallResult(tool_name, tool_input, f"文件不存在: {path}", False)
            
            elif tool_name == "write_file":
                path = tool_input.get("path")
                content = tool_input.get("content")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write(content)
                return ToolCallResult(tool_name, tool_input, f"文件已写入: {path}", True)
            
            elif tool_name == "edit_file":
                path = tool_input.get("path")
                old = tool_input.get("old_string")
                new = tool_input.get("new_string")
                with open(path, "r") as f:
                    content = f.read()
                if old in content:
                    content = content.replace(old, new)
                    with open(path, "w") as f:
                        f.write(content)
                    return ToolCallResult(tool_name, tool_input, f"文件已编辑: {path}", True)
                else:
                    return ToolCallResult(tool_name, tool_input, f"未找到目标内容: {old}", False)
            
            elif tool_name == "bash":
                command = tool_input.get("command")
                timeout = tool_input.get("timeout", 60)
                result = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(
                    result.communicate(),
                    timeout=timeout
                )
                output = stdout.decode() if stdout else stderr.decode()
                return ToolCallResult(tool_name, tool_input, output, result.returncode == 0)
            
            elif tool_name == "search":
                pattern = tool_input.get("pattern")
                path = tool_input.get("path", ".")
                # 简化实现
                import subprocess
                result = subprocess.run(
                    ["grep", "-r", pattern, path],
                    capture_output=True,
                    text=True
                )
                return ToolCallResult(tool_name, tool_input, result.stdout or "未找到匹配", result.returncode == 0)
            
            else:
                return ToolCallResult(tool_name, tool_input, f"未知工具: {tool_name}", False)
                
        except Exception as e:
            return ToolCallResult(tool_name, tool_input, f"执行错误: {str(e)}", False)
    
    async def _execute_hooks(self, hook_type: str, context: dict) -> Optional[dict]:
        """执行Hooks"""
        for hook in self._hooks:
            try:
                result = await hook(hook_type, context) if asyncio.iscoroutinefunction(hook) else hook(hook_type, context)
                if result:
                    return result
            except Exception:
                # Hook执行失败不阻止主流程
                pass
        return None
    
    def _update_cost_tracking(self, response: Any):
        """更新成本追踪"""
        if hasattr(response, "usage"):
            self._total_tokens["input"] += response.usage.input_tokens
            self._total_tokens["output"] += response.usage.output_tokens
            
            # 计算成本 (Claude定价)
            # Sonnet: $3/M input, $15/M output
            # Opus: $15/M input, $75/M output
            model = self.claude_config.model
            if "opus" in model.lower():
                input_cost = response.usage.input_tokens * 15 / 1_000_000
                output_cost = response.usage.output_tokens * 75 / 1_000_000
            else:  # sonnet
                input_cost = response.usage.input_tokens * 3 / 1_000_000
                output_cost = response.usage.output_tokens * 15 / 1_000_000
            
            self._total_cost += input_cost + output_cost
    
    def get_cost(self) -> float:
        """获取累计成本"""
        return self._total_cost
    
    def clear_conversation(self):
        """清空会话记忆"""
        self._conversation_history.clear()
        self._state.clear()
        self._history.clear()