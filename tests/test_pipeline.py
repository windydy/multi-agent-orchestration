"""
完整流水线测试
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import os

pytest.importorskip("langgraph")
pytest.importorskip("anthropic")


from src.workflows.runner import WorkflowRunner, run_pipeline, print_state_summary
from src.workflows.states import create_initial_state, WorkflowStateManager


@pytest.mark.asyncio
class TestWorkflowRunner:
    """测试WorkflowRunner"""
    
    @patch("src.workflows.runner.LANGGRAPH_AVAILABLE", True)
    @patch("src.workflows.builder.LANGGRAPH_AVAILABLE", True)
    async def test_runner_init(self):
        """测试Runner初始化"""
        runner = WorkflowRunner(api_key="test-key")
        
        assert runner.pipeline is not None
    
    @patch("src.workflows.runner.LANGGRAPH_AVAILABLE", True)
    @patch("src.workflows.builder.LANGGRAPH_AVAILABLE", True)
    async def test_run_without_interrupt(self):
        """测试无中断运行"""
        runner = WorkflowRunner(api_key="test-key")
        
        # Mock app
        runner.app = Mock()
        runner.app.ainvoke = AsyncMock(return_value={
            "task": "test",
            "current_stage": "completed",
            "iteration_count": 1,
            "total_cost": 0.1,
        })
        
        result = await runner.run("test task", "./project/")
        
        assert result["success"] is True
        assert "thread_id" in result
    
    @patch("src.workflows.runner.LANGGRAPH_AVAILABLE", True)
    @patch("src.workflows.builder.LANGGRAPH_AVAILABLE", True)
    async def test_run_until_interrupt(self):
        """测试运行直到中断"""
        runner = WorkflowRunner(api_key="test-key")
        
        runner.app = Mock()
        runner.app.ainvoke = AsyncMock(return_value={
            "task": "test",
            "current_stage": "review",
            "messages": [{"role": "develop", "content": "done"}],
        })
        runner.app.get_state = Mock(return_value=Mock(
            values={"current_stage": "review"},
            next=["human_review"]
        ))
        
        result = await runner.run_until_interrupt("test task")
        
        assert "thread_id" in result
        assert "next_steps" in result
    
    @patch("src.workflows.runner.LANGGRAPH_AVAILABLE", True)
    @patch("src.workflows.builder.LANGGRAPH_AVAILABLE", True)
    async def test_resume(self):
        """测试恢复执行"""
        runner = WorkflowRunner(api_key="test-key")
        
        runner.app = Mock()
        runner.app.update_state = Mock()
        runner.app.ainvoke = AsyncMock(return_value={
            "task": "test",
            "current_stage": "completed",
        })
        
        runner._executions["test_thread"] = {
            "task": "test",
            "start_time": "2024-01-01",
        }
        
        result = await runner.resume("test_thread", approval=True, comment="通过")
        
        assert result["success"] is True
        assert result["approval_result"]["approved"] is True
    
    @patch("src.workflows.runner.LANGGRAPH_AVAILABLE", True)
    @patch("src.workflows.builder.LANGGRAPH_AVAILABLE", True)
    def test_get_state(self):
        """测试获取状态"""
        runner = WorkflowRunner(api_key="test-key")
        
        runner.app = Mock()
        runner.app.get_state = Mock(return_value=Mock(
            values={"task": "test", "current_stage": "develop"},
            next=["review"],
            created_at="2024-01-01",
            parent_config=None
        ))
        
        state = runner.get_state("test_thread")
        
        assert state["values"]["task"] == "test"
        assert state["next"] == ["review"]
    
    @patch("src.workflows.runner.LANGGRAPH_AVAILABLE", True)
    @patch("src.workflows.builder.LANGGRAPH_AVAILABLE", True)
    def test_list_executions(self):
        """测试列出执行"""
        runner = WorkflowRunner(api_key="test-key")
        
        runner._executions = {
            "thread_1": {"task": "task1", "status": "completed"},
            "thread_2": {"task": "task2", "status": "running"},
        }
        
        executions = runner.list_executions()
        
        assert len(executions) == 2


@pytest.mark.asyncio
class TestRunPipeline:
    """测试便捷函数"""
    
    @patch("src.workflows.runner.LANGGRAPH_AVAILABLE", True)
    @patch("src.workflows.builder.LANGGRAPH_AVAILABLE", True)
    async def test_run_pipeline_no_review(self):
        """测试无人工审批运行"""
        with patch("src.workflows.runner.WorkflowRunner") as mock_runner_class:
            mock_runner = Mock()
            mock_runner.run = AsyncMock(return_value={
                "success": True,
                "thread_id": "test",
                "final_state": {"current_stage": "completed"}
            })
            mock_runner_class.return_value = mock_runner
            
            result = await run_pipeline(
                task="test",
                enable_human_review=False
            )
            
            assert result["success"] is True


class TestPrintStateSummary:
    """测试状态打印"""
    
    def test_print_summary(self, capsys):
        """测试打印摘要"""
        state = {
            "task": "实现功能",
            "current_stage": "test",
            "iteration_count": 3,
            "total_cost": 0.5,
            "messages": [{"role": "develop", "content": "代码完成"}],
        }
        
        print_state_summary(state)
        
        captured = capsys.readouterr()
        assert "实现功能" in captured.out
        assert "test" in captured.out
        assert "0.50" in captured.out


class TestWorkflowStateManager:
    """测试WorkflowStateManager"""
    
    def test_get_summary(self):
        """测试获取摘要"""
        state = create_initial_state("test task")
        manager = WorkflowStateManager(state)
        
        manager.update_stage_result("requirements", {"done": True})
        manager.update_stage_result("design", {"done": True})
        manager.add_cost(0.1)
        
        summary = manager.get_summary()
        
        assert summary["task"] == "test task"
        assert summary["iteration_count"] == 2
        assert summary["total_cost"] == 0.1
        assert "requirements" in summary["stages_completed"]
        assert "design" in summary["stages_completed"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])