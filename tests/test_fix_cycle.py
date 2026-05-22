"""
Fix Cycle Tests

验证 fix 循环的完整流程：
1. 测试失败 → fix 节点 → 重新测试通过 → END
2. 测试多次失败 → 达到 max_iterations → 强制结束
3. 测试失败且不可修复 → human_review
4. 完整的端到端模拟（mock agent 输出）
"""

import pytest
from src.workflows.builder import (
    DevelopmentPipelineBuilder,
    PipelineConfig,
)
from src.workflows.states import create_initial_state


class TestFixCycleRouting:
    """测试 fix 循环的路由逻辑"""

    def test_test_failed_fixable_routes_to_fix(self):
        """测试失败且可修复 → 路由到 fix"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=False)
        )
        state = create_initial_state("test task")
        state["test_result"] = {
            "passed": False,
            "fixable": True,
            "failures": [{"test": "test_divide", "error": "ZeroDivisionError"}],
        }

        next_node = builder._test_router(state)
        assert next_node == "fix"

    def test_test_passed_routes_to_end(self):
        """测试通过 → 路由到 END"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=False)
        )
        state = create_initial_state("test task")
        state["test_result"] = {
            "passed": True,
            "total_tests": 18,
            "passed_tests": 18,
        }

        next_node = builder._test_router(state)
        assert next_node == "end"

    def test_test_failed_not_fixable_routes_to_human_review(self):
        """测试失败且不可修复 → 路由到 human_review"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=True)
        )
        state = create_initial_state("test task")
        state["test_result"] = {
            "passed": False,
            "fixable": False,
            "summary": "无法自动修复",
        }

        next_node = builder._test_router(state)
        assert next_node == "human_review"

    def test_test_failed_not_fixable_no_human_routes_to_end(self):
        """测试失败且不可修复，无人工审批 → 路由到 END"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=False)
        )
        state = create_initial_state("test task")
        state["test_result"] = {
            "passed": False,
            "fixable": False,
            "summary": "无法自动修复",
        }

        next_node = builder._test_router(state)
        assert next_node == "end"


class TestMaxIterations:
    """测试迭代限制强制结束"""

    def test_max_iterations_forces_test_end(self):
        """达到最大迭代次数时，test 强制结束"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=True, max_iterations=3)
        )
        state = create_initial_state("test task")
        state["iteration_count"] = 3
        state["test_result"] = {
            "passed": False,
            "fixable": True,
            "failures": [{"test": "test_fail", "error": "AssertionError"}],
        }

        next_node = builder._test_router(state)
        assert next_node == "end"

    def test_max_iterations_forces_review_to_test(self):
        """达到最大迭代次数时，review 强制进入 test"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=True, max_iterations=3)
        )
        state = create_initial_state("test task")
        state["iteration_count"] = 3
        state["review_result"] = {
            "needs_revision": True,
            "issues": ["style issue"],
        }

        next_node = builder._review_router(state)
        assert next_node == "test"


class TestReviewRouting:
    """测试 review 路由逻辑"""

    def test_review_approved_routes_to_test(self):
        """审查通过 → 路由到 test"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=False)
        )
        state = create_initial_state("test task")
        state["review_result"] = {"approved": True}

        next_node = builder._review_router(state)
        assert next_node == "test"

    def test_review_needs_revision_routes_to_develop(self):
        """审查不通过 → 路由回 develop"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=False)
        )
        state = create_initial_state("test task")
        state["review_result"] = {"needs_revision": True}

        next_node = builder._review_router(state)
        assert next_node == "develop"

    def test_review_ambiguous_routes_to_human_review(self):
        """审查结果不明确 → 路由到 human_review"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=True)
        )
        state = create_initial_state("test task")
        state["review_result"] = {"issues": ["minor style issue"]}

        next_node = builder._review_router(state)
        assert next_node == "human_review"

    def test_review_ambiguous_no_human_routes_to_test(self):
        """审查结果不明确，无人工审批 → 路由到 test"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=False)
        )
        state = create_initial_state("test task")
        state["review_result"] = {"issues": ["minor style issue"]}

        next_node = builder._review_router(state)
        assert next_node == "test"


class TestFixCycleSimulation:
    """模拟完整的 fix 循环流程"""

    def test_full_fix_cycle(self):
        """模拟完整流程: develop → review → test(fail) → fix → test(pass) → END"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=False, max_iterations=10)
        )

        state = create_initial_state("修复 divide bug")

        # Step 1: Develop — 代码变更
        state["code_changes"] = {
            "files_changed": ["calculator.py"],
            "changes": ["Added divide by zero check"],
        }
        state["current_stage"] = "develop"

        # Step 2: Review — 审查通过
        state["review_result"] = {"approved": True}
        next_node = builder._review_router(state)
        assert next_node == "test", f"Expected test, got {next_node}"

        # Step 3: Test — 发现失败，可修复
        state["test_result"] = {
            "passed": False,
            "fixable": True,
            "failures": [
                {
                    "test": "test_divide_by_zero",
                    "error": "ZeroDivisionError",
                    "likely_cause": "divide 方法未处理除零",
                }
            ],
        }
        next_node = builder._test_router(state)
        assert next_node == "fix", f"Expected fix, got {next_node}"

        # Step 4: Fix — 修复代码
        state["fix_result"] = {
            "fixes_applied": [
                {
                    "file": "calculator.py",
                    "change": "Added ValueError check in divide()",
                }
            ],
        }

        # Step 5: Re-test — 测试通过
        state["test_result"] = {
            "passed": True,
            "total_tests": 18,
            "passed_tests": 18,
        }
        next_node = builder._test_router(state)
        assert next_node == "end", f"Expected end, got {next_node}"

    def test_fix_cycle_with_multiple_iterations(self):
        """模拟多次 fix 循环: test(fail) → fix → test(fail) → fix → test(pass)"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=False, max_iterations=10)
        )
        state = create_initial_state("修复多个 bug")

        # 第一轮：测试发现 bug，修复
        state["test_result"] = {
            "passed": False,
            "fixable": True,
            "failures": [{"test": "test_divide", "error": "ZeroDivisionError"}],
        }
        assert builder._test_router(state) == "fix"

        state["fix_result"] = {"fixes_applied": [{"file": "calculator.py"}]}
        state["iteration_count"] = 1

        # 第二轮：修复不完整，仍有 bug
        state["test_result"] = {
            "passed": False,
            "fixable": True,
            "failures": [
                {
                    "test": "test_factorial_negative",
                    "error": "ValueError not raised",
                }
            ],
        }
        assert builder._test_router(state) == "fix"

        state["fix_result"] = {
            "fixes_applied": [
                {"file": "calculator.py"},
                {"file": "calculator.py"},
            ]
        }
        state["iteration_count"] = 2

        # 第三轮：测试通过
        state["test_result"] = {"passed": True, "total_tests": 18}
        assert builder._test_router(state) == "end"

    def test_fix_cycle_max_iterations_forces_end(self):
        """fix 循环达到最大迭代次数 → 强制结束"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=True, max_iterations=3)
        )
        state = create_initial_state("修复 bug")

        # 模拟达到最大迭代次数后仍有失败
        state["iteration_count"] = 3
        state["test_result"] = {
            "passed": False,
            "fixable": True,
            "failures": [{"test": "test_edge_case", "error": "Still failing"}],
        }

        # 即使 fixable=True，也应强制结束
        next_node = builder._test_router(state)
        assert next_node == "end"


class TestNodeToFieldMapping:
    """验证 NODE_TO_FIELD 映射一致性"""

    def test_all_nodes_have_field_mapping(self):
        """所有节点都有对应的状态字段"""
        builder = DevelopmentPipelineBuilder()

        expected_nodes = ["requirements", "design", "develop", "review", "test", "fix"]
        for node in expected_nodes:
            assert node in builder.NODE_TO_FIELD, f"Missing mapping for {node}"

    def test_field_mapping_matches_typed_dict(self):
        """映射的目标字段与 WorkflowState TypedDict 一致"""
        builder = DevelopmentPipelineBuilder()

        # WorkflowState 定义的结果字段
        expected_fields = {
            "requirements": "requirements",
            "design": "design",
            "develop": "code_changes",
            "review": "review_result",
            "test": "test_result",
            "fix": "fix_result",
        }

        for node, field in expected_fields.items():
            assert builder.NODE_TO_FIELD[node] == field

    def test_routers_read_from_correct_fields(self):
        """路由器从正确的状态字段读取"""
        builder = DevelopmentPipelineBuilder(
            PipelineConfig(enable_human_review=False)
        )
        state = create_initial_state("test")

        # 确保路由器读取 review_result 而非 review
        state["review_result"] = {"approved": True}
        assert builder._review_router(state) == "test"

        # 确保路由器读取 test_result 而非 test
        state["test_result"] = {"passed": True}
        assert builder._test_router(state) == "end"
