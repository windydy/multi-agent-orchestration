"""
完整流水线测试 - Updated to match current WorkflowRunner API
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import os

pytest.importorskip("langgraph")
pytest.importorskip("anthropic")


from src.workflows.runner import WorkflowRunner, run_pipeline, print_state_summary
from src.workflows.states import create_initial_state, WorkflowStateManager


class TestWorkflowRunner:
    """测试WorkflowRunner"""
    
    @pytest.fixture
    def mock_planner(self):
        """创建模拟的 PlannerAgent"""
        planner = Mock()
        planner.generate_plan = AsyncMock(return_value=Mock(
            id="plan_123",
            nodes={"node1": Mock()},
            edges=[],
            plan_type="development",
        ))
        planner.validate_plan = Mock(return_value=(True, []))
        planner._default_plan = Mock(return_value=Mock(
            id="plan_default",
            nodes={"node1": Mock()},
            edges=[],
            plan_type="development",
        ))
        return planner
    
    @pytest.mark.asyncio
    async def test_runner_init(self, mock_planner):
        """测试Runner初始化"""
        runner = WorkflowRunner(planner=mock_planner)
        
        assert runner.planner is mock_planner
        assert runner.clarifier is None
    
    @pytest.mark.asyncio
    async def test_run_with_mock_builder(self, mock_planner):
        """测试使用模拟 builder 运行"""
        runner = WorkflowRunner(planner=mock_planner)
        
        # Mock dynamic_builder
        mock_app = Mock()
        mock_app.ainvoke = AsyncMock(return_value={
            "task": "test",
            "verification_passed": True,
        })
        
        mock_builder = Mock()
        mock_builder.from_plan = Mock(return_value=Mock(build=Mock(return_value=mock_app)))
        
        runner.dynamic_builder = mock_builder
        
        result = await runner.run("test task", "./project/")
        
        assert result["success"] is True
        assert "thread_id" in result
    
    def test_get_state(self, mock_planner):
        """测试获取状态"""
        runner = WorkflowRunner(planner=mock_planner)
        
        # Run creates an entry in _executions
        state = runner.get_state("nonexistent_thread")
        
        assert state["thread_id"] == "nonexistent_thread"
        assert "error" in state
    
    def test_list_executions(self, mock_planner):
        """测试列出执行"""
        runner = WorkflowRunner(planner=mock_planner)
        
        runner._executions = {
            "thread_1": {"task": "task1", "status": "completed"},
            "thread_2": {"task": "task2", "status": "running"},
        }
        
        executions = runner.list_executions()
        
        assert len(executions) == 2
    
    def test_with_clarifier(self, mock_planner):
        """测试传入 clarifier"""
        clarifier = Mock()
        clarifier.analyze = AsyncMock()
        
        runner = WorkflowRunner(planner=mock_planner, clarifier=clarifier)
        
        assert runner.clarifier is clarifier


@pytest.fixture
def shared_mock_planner():
    """Shared mock planner fixture"""
    planner = Mock()
    planner.generate_plan = AsyncMock(return_value=Mock(
        id="plan_123",
        nodes={"node1": Mock()},
        edges=[],
        plan_type="development",
    ))
    planner.validate_plan = Mock(return_value=(True, []))
    return planner


class TestRunPipeline:
    """测试便捷函数"""
    
    @pytest.mark.asyncio
    async def test_run_pipeline(self, shared_mock_planner):
        """测试运行流水线"""
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
                planner=shared_mock_planner,
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
