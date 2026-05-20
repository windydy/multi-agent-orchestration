"""
Workflow Builder测试
"""

import pytest
from unittest.mock import Mock, patch
import os

pytest.importorskip("langgraph")

from src.workflows.states import (
    WorkflowState,
    create_initial_state,
    WorkflowStateManager,
    validate_state,
    merge_state,
)
from src.workflows.builder import (
    PipelineConfig,
    DevelopmentPipelineBuilder,
    create_dev_pipeline,
)


class TestWorkflowState:
    """测试WorkflowState"""
    
    def test_create_initial_state(self):
        """测试创建初始状态"""
        state = create_initial_state(
            task="实现登录功能",
            project_path="./project/"
        )
        
        assert state["task"] == "实现登录功能"
        assert state["project_path"] == "./project/"
        assert state["current_stage"] == "start"
        assert state["iteration_count"] == 0
        assert state["messages"] == []
        assert state["total_cost"] == 0.0
    
    def test_state_structure(self):
        """测试状态结构"""
        state = create_initial_state("test")
        
        # 检查所有必需字段
        required_fields = [
            "task", "project_path", "messages",
            "requirements", "design", "code_changes",
            "review_result", "test_result", "fix_result",
            "current_stage", "next_stage", "iteration_count",
            "needs_revision", "human_approval", "approval_comment",
            "start_time", "end_time", "total_cost"
        ]
        
        for field in required_fields:
            assert field in state


class TestWorkflowStateManager:
    """测试WorkflowStateManager"""
    
    def test_manager_init(self):
        """测试管理器初始化"""
        state = create_initial_state("test task")
        manager = WorkflowStateManager(state)
        
        assert manager.get("task") == "test task"
    
    def test_update_stage_result(self):
        """测试更新阶段结果"""
        manager = WorkflowStateManager(create_initial_state("test"))
        
        manager.update_stage_result("requirements", {"features": ["A", "B"]})
        
        assert manager.get("requirements") == {"features": ["A", "B"]}
        assert manager.get("current_stage") == "requirements"
        assert manager.get("iteration_count") == 1
    
    def test_add_message(self):
        """测试添加消息"""
        manager = WorkflowStateManager(create_initial_state("test"))
        
        manager.add_message("requirements", "分析完成")
        
        messages = manager.get("messages")
        assert len(messages) == 1
        assert messages[0]["role"] == "requirements"
        assert messages[0]["content"] == "分析完成"
    
    def test_cost_tracking(self):
        """测试成本追踪"""
        manager = WorkflowStateManager(create_initial_state("test"))
        
        manager.add_cost(0.05)
        manager.add_cost(0.03)
        
        assert manager.get("total_cost") == 0.08
    
    def test_iteration_limit(self):
        """测试迭代限制"""
        manager = WorkflowStateManager(create_initial_state("test"))
        
        for i in range(15):
            manager.update_stage_result("requirements", {})
        
        assert manager.is_max_iterations(10) is True
        assert manager.is_max_iterations(20) is False
    
    def test_complete(self):
        """测试完成标记"""
        manager = WorkflowStateManager(create_initial_state("test"))
        
        manager.complete()
        
        assert manager.get("current_stage") == "completed"
        assert manager.get("end_time") != ""


class TestStateFunctions:
    """测试状态辅助函数"""
    
    def test_validate_state(self):
        """测试状态验证"""
        valid_state = create_initial_state("test")
        assert validate_state(valid_state) is True
        
        invalid_state = {"task": "test"}  # 缺少必需字段
        assert validate_state(invalid_state) is False
    
    def test_merge_state(self):
        """测试状态合并"""
        old_state = create_initial_state("test")
        new_updates = {
            "current_stage": "requirements",
            "total_cost": 0.1,
            "messages": [{"role": "test", "content": "msg"}]
        }
        
        merged = merge_state(old_state, new_updates)
        
        assert merged["current_stage"] == "requirements"
        assert merged["total_cost"] == 0.1
        # messages应该累加
        assert len(merged["messages"]) == 1


class TestPipelineConfig:
    """测试流水线配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = PipelineConfig()
        
        assert config.api_key is None
        assert config.max_iterations == 10
        assert config.enable_human_review is True
        assert config.checkpoint_enabled is True
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = PipelineConfig(
            api_key="test-key",
            max_iterations=5,
            enable_human_review=False,
            checkpoint_path="./custom.db"
        )
        
        assert config.api_key == "test-key"
        assert config.max_iterations == 5
        assert config.enable_human_review is False


class TestDevelopmentPipelineBuilder:
    """测试流水线构建器"""
    
    @patch("src.workflows.builder.LANGGRAPH_AVAILABLE", False)
    def test_langgraph_not_available(self):
        """测试langgraph未安装"""
        with pytest.raises(ImportError, match="langgraph"):
            DevelopmentPipelineBuilder()
    
    @patch("src.workflows.builder.LANGGRAPH_AVAILABLE", True)
    @patch("src.workflows.builder.StateGraph")
    def test_build_workflow(self, mock_state_graph):
        """测试构建工作流"""
        config = PipelineConfig(enable_human_review=False)
        builder = DevelopmentPipelineBuilder(config)
        
        # Mock StateGraph
        mock_graph = Mock()
        mock_state_graph.return_value = mock_graph
        
        # Mock SqliteSaver
        with patch("src.workflows.builder.SqliteSaver") as mock_saver:
            mock_saver.from_conn_string.return_value = Mock()
            
            app = builder.build()
            
            # 验证节点添加
            assert mock_graph.add_node.called


class TestCreateDevPipeline:
    """测试创建流水线"""
    
    @patch("src.workflows.builder.LANGGRAPH_AVAILABLE", True)
    def test_create_pipeline(self):
        """测试创建流水线工厂函数"""
        pipeline = create_dev_pipeline(
            api_key="test-key",
            enable_human_review=False,
            max_iterations=5
        )
        
        assert isinstance(pipeline, DevelopmentPipelineBuilder)
        assert pipeline.config.api_key == "test-key"
        assert pipeline.config.enable_human_review is False
        assert pipeline.config.max_iterations == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])