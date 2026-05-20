"""
Claude Agent Wrapper测试
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import os

# 跳过如果anthropic未安装
pytest.importorskip("anthropic")

from src.claude.wrapper import (
    ClaudeAgentWrapper,
    ClaudeSDKConfig,
    ClaudeToolType,
    ToolCallResult,
)
from src.core.agent import AgentConfig, AgentRole


@pytest.fixture
def mock_api_key():
    """模拟API Key"""
    return "mock-api-key-12345"


@pytest.fixture
def agent_config():
    """Agent配置"""
    return AgentConfig(
        name="test_agent",
        role=AgentRole.WORKER,
        description="测试Agent",
        model="claude-sonnet-4-20250514",
        max_iterations=5,
    )


@pytest.fixture
def claude_config(mock_api_key):
    """Claude SDK配置"""
    return ClaudeSDKConfig(
        api_key=mock_api_key,
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        temperature=0.5,
        tools=[ClaudeToolType.READ_FILE, ClaudeToolType.BASH],
    )


class TestClaudeSDKConfig:
    """测试ClaudeSDKConfig"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = ClaudeSDKConfig()
        
        assert config.model == "glm-5"  # 默认使用 glm-5
        assert config.max_tokens == 4096
        assert config.temperature == 0.7
        assert config.api_key is None
        assert ClaudeToolType.READ_FILE in config.tools
    
    def test_custom_config(self, mock_api_key):
        """测试自定义配置"""
        config = ClaudeSDKConfig(
            api_key=mock_api_key,
            model="claude-opus-4-20250514",
            temperature=0.1
        )
        
        assert config.api_key == mock_api_key
        assert config.model == "claude-opus-4-20250514"
        assert config.temperature == 0.1


class TestToolCallResult:
    """测试ToolCallResult"""
    
    def test_success_result(self):
        """测试成功结果"""
        result = ToolCallResult(
            tool_name="read_file",
            tool_input={"path": "/test.py"},
            output="file content",
            success=True
        )
        
        assert result.success is True
        assert result.error is None
        assert result.output == "file content"
    
    def test_failure_result(self):
        """测试失败结果"""
        result = ToolCallResult(
            tool_name="bash",
            tool_input={"command": "invalid"},
            output="",
            success=False,
            error="Command failed"
        )
        
        assert result.success is False
        assert result.error == "Command failed"


class TestClaudeAgentWrapper:
    """测试ClaudeAgentWrapper"""
    
    @patch("src.claude.wrapper.ANTHROPIC_AVAILABLE", False)
    def test_import_error_without_anthropic(self, agent_config, claude_config):
        """测试无anthropic包时的错误"""
        with pytest.raises(ImportError):
            ClaudeAgentWrapper(agent_config, claude_config)
    
    def test_missing_api_key(self, agent_config):
        """测试缺少API Key时的错误"""
        # 移除环境变量
        if "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]
        if "DASHSCOPE_API_KEY" in os.environ:
            del os.environ["DASHSCOPE_API_KEY"]
        
        with patch("src.claude.wrapper.ANTHROPIC_AVAILABLE", True):
            # Mock Hermes config 返回空配置
            with patch.object(ClaudeAgentWrapper, "_load_hermes_config", return_value={}):
                with pytest.raises(ValueError, match="API Key"):
                    ClaudeAgentWrapper(agent_config)
    
    @patch("src.claude.wrapper.AsyncAnthropic")
    @patch("src.claude.wrapper.ANTHROPIC_AVAILABLE", True)
    def test_init_with_api_key(self, mock_async_client, agent_config, mock_api_key):
        """测试使用API Key初始化"""
        os.environ["ANTHROPIC_API_KEY"] = mock_api_key
        
        wrapper = ClaudeAgentWrapper(agent_config)
        
        assert wrapper.config.name == "test_agent"
        assert wrapper._hooks == []
    
    def test_build_input_message(self, agent_config, mock_api_key):
        """测试构建输入消息"""
        with patch("src.claude.wrapper.AsyncAnthropic"):
            with patch("src.claude.wrapper.ANTHROPIC_AVAILABLE", True):
                os.environ["ANTHROPIC_API_KEY"] = mock_api_key
                wrapper = ClaudeAgentWrapper(agent_config)
                
                message = wrapper._build_input_message(
                    "测试任务",
                    {"previous_results": {"design": "设计方案"}}
                )
                
                assert "测试任务" in message
                assert "测试Agent" in message
    
    def test_build_tool_definitions(self, agent_config, mock_api_key):
        """测试构建工具定义"""
        with patch("src.claude.wrapper.AsyncAnthropic"):
            with patch("src.claude.wrapper.ANTHROPIC_AVAILABLE", True):
                os.environ["ANTHROPIC_API_KEY"] = mock_api_key
                
                config = ClaudeSDKConfig(
                    api_key=mock_api_key,
                    tools=[ClaudeToolType.READ_FILE, ClaudeToolType.BASH]
                )
                wrapper = ClaudeAgentWrapper(agent_config, config)
                
                tools = wrapper._build_tool_definitions()
                
                assert len(tools) == 2
                assert tools[0]["name"] == "read_file"
                assert tools[1]["name"] == "bash"


@pytest.mark.asyncio
class TestToolExecutor:
    """测试工具执行器"""
    
    async def test_read_file_executor(self, agent_config, mock_api_key):
        """测试文件读取"""
        with patch("src.claude.wrapper.AsyncAnthropic"):
            with patch("src.claude.wrapper.ANTHROPIC_AVAILABLE", True):
                os.environ["ANTHROPIC_API_KEY"] = mock_api_key
                wrapper = ClaudeAgentWrapper(agent_config)
                
                # 创建临时文件
                import tempfile
                with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                    f.write("test content")
                    temp_path = f.name
                
                result = await wrapper._default_tool_executor(
                    "read_file",
                    {"path": temp_path}
                )
                
                assert result.success is True
                assert "test content" in result.output
                
                os.unlink(temp_path)
    
    async def test_write_file_executor(self, agent_config, mock_api_key):
        """测试文件写入"""
        with patch("src.claude.wrapper.AsyncAnthropic"):
            with patch("src.claude.wrapper.ANTHROPIC_AVAILABLE", True):
                os.environ["ANTHROPIC_API_KEY"] = mock_api_key
                wrapper = ClaudeAgentWrapper(agent_config)
                
                import tempfile
                temp_dir = tempfile.mkdtemp()
                temp_path = os.path.join(temp_dir, "test.txt")
                
                result = await wrapper._default_tool_executor(
                    "write_file",
                    {"path": temp_path, "content": "new content"}
                )
                
                assert result.success is True
                
                # 验证文件内容
                with open(temp_path) as f:
                    assert f.read() == "new content"
                
                os.unlink(temp_path)
                os.rmdir(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])