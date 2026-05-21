"""
Phase 5 TDD: 配置 Schema (Pydantic v2)

严格遵循 TDD: 先写失败测试 → 再写最小代码 → 重构
"""

import pytest
from src.config.schema import (
    SeverityLevel,
    PlannerConfig,
    ExecutorDefaults,
    ExecutorConfig,
    VerificationRule,
    VerifierConfig,
    FlowNode,
    FlowEdge,
    FlowTemplate,
    CostControlConfig,
    WorkflowConfig,
)


class TestSeverityLevel:
    """SeverityLevel 枚举"""

    def test_levels_exist(self):
        assert SeverityLevel.INFO == "info"
        assert SeverityLevel.WARNING == "warning"
        assert SeverityLevel.ERROR == "error"
        assert SeverityLevel.CRITICAL == "critical"


class TestPlannerConfig:
    """PlannerConfig"""

    def test_defaults(self):
        cfg = PlannerConfig()
        assert cfg.enabled is True
        assert cfg.model == "qwen3.6-plus"
        assert cfg.max_plan_depth == 5
        assert cfg.allow_parallel is True
        assert cfg.auto_replan is True


class TestExecutorDefaults:
    """ExecutorDefaults"""

    def test_defaults(self):
        cfg = ExecutorDefaults()
        assert cfg.model == "qwen3.6-plus"
        assert cfg.max_iterations == 10
        assert cfg.timeout == 300
        assert cfg.retry == 2
        assert cfg.tools == []


class TestExecutorConfig:
    """ExecutorConfig"""

    def test_create_with_all_fields(self):
        cfg = ExecutorConfig(
            model="qwen3.6-turbo",
            max_iterations=20,
            timeout=600,
            retry=3,
            tools=["read_file", "write_file", "bash"],
            system_prompt="You are a dev",
        )
        assert cfg.model == "qwen3.6-turbo"
        assert cfg.max_iterations == 20

    def test_merge_with_defaults(self):
        cfg = ExecutorConfig(tools=["bash"])
        defaults = ExecutorDefaults(
            model="qwen3.6-plus",
            max_iterations=15,
            timeout=600,
            retry=3,
            tools=["read_file"],
        )
        merged = cfg.merge_with_defaults(defaults)
        assert merged.model == "qwen3.6-plus"
        assert merged.max_iterations == 15
        assert merged.timeout == 600
        assert merged.tools == ["bash"]  # executor's own tools override


class TestVerificationRule:
    """VerificationRule"""

    def test_create_rule(self):
        rule = VerificationRule(
            name="lint",
            check="ruff check .",
            severity="error",
            timeout=60,
        )
        assert rule.name == "lint"
        assert rule.severity == SeverityLevel.ERROR

    def test_default_severity(self):
        rule = VerificationRule(name="test", check="true")
        assert rule.severity == SeverityLevel.WARNING


class TestFlowNode:
    """FlowNode"""

    def test_create_node(self):
        node = FlowNode(id="dev", type="developer", label="开发")
        assert node.id == "dev"
        assert node.type == "developer"
        assert node.label == "开发"
        assert node.timeout == 300
        assert node.retry == 2
        assert node.depends_on == []
        assert node.parallel is False

    def test_node_with_deps(self):
        node = FlowNode(
            id="review",
            type="reviewer",
            label="审查",
            depends_on=["develop"],
            timeout=600,
        )
        assert node.depends_on == ["develop"]
        assert node.timeout == 600


class TestFlowEdge:
    """FlowEdge"""

    def test_create_edge(self):
        edge = FlowEdge(**{"from": "review", "to": "test"})
        assert edge.from_node == "review"
        assert edge.to_node == "test"

    def test_conditional_edge(self):
        edge = FlowEdge(**{"from": "review", "to": "develop", "condition": "needs_revision"})
        assert edge.condition == "needs_revision"


class TestFlowTemplate:
    """FlowTemplate"""

    def test_create_template(self):
        tpl = FlowTemplate(
            entry_point="req",
            nodes=[FlowNode(id="req", type="requirements", label="需求")],
            edges=[],
        )
        assert tpl.entry_point == "req"
        assert len(tpl.nodes) == 1


class TestCostControlConfig:
    """CostControlConfig — 统一命名: warning_threshold / limit_threshold / stop_threshold"""

    def test_defaults(self):
        cfg = CostControlConfig()
        assert cfg.warning_threshold == 5.0
        assert cfg.limit_threshold == 10.0
        assert cfg.stop_threshold == 20.0

    def test_custom_values(self):
        cfg = CostControlConfig(warning_threshold=2.0, limit_threshold=5.0, stop_threshold=10.0)
        assert cfg.warning_threshold == 2.0


class TestWorkflowConfig:
    """WorkflowConfig 根配置"""

    def test_create_minimal_config(self):
        """最简配置"""
        cfg = WorkflowConfig(
            name="test",
            executors={"developer": ExecutorConfig()},
            flow_template=FlowTemplate(
                entry_point="dev",
                nodes=[FlowNode(id="dev", type="developer", label="开发")],
                edges=[],
            ),
        )
        assert cfg.name == "test"
        assert "developer" in cfg.executors

    def test_create_full_config(self):
        """完整配置"""
        cfg = WorkflowConfig(
            name="full-dev",
            display_name="完整开发流水线",
            description="需求 → 设计 → 开发 → 审查 → 测试",
            executors={
                "requirements": ExecutorConfig(model="qwen3.6-plus", max_iterations=15),
                "developer": ExecutorConfig(model="qwen3.6-plus", tools=["read_file", "write_file", "bash"]),
            },
            flow_template=FlowTemplate(
                entry_point="req",
                nodes=[
                    FlowNode(id="req", type="requirements", label="需求"),
                    FlowNode(id="dev", type="developer", label="开发", depends_on=["req"]),
                ],
                edges=[
                    FlowEdge(**{"from": "req", "to": "dev"}),
                ],
            ),
            cost_control=CostControlConfig(warning_threshold=5.0, limit_threshold=10.0, stop_threshold=20.0),
        )
        assert cfg.display_name == "完整开发流水线"
        assert len(cfg.executors) == 2
        assert len(cfg.flow_template.nodes) == 2
        assert cfg.cost_control.warning_threshold == 5.0

    def test_validate_name_invalid(self):
        """名称不能包含特殊字符"""
        with pytest.raises(Exception):
            WorkflowConfig(
                name="test workflow!",
                executors={"dev": ExecutorConfig()},
                flow_template=FlowTemplate(
                    entry_point="dev",
                    nodes=[FlowNode(id="dev", type="developer", label="dev")],
                    edges=[],
                ),
            )

    def test_validate_entry_point_exists(self):
        """entry_point 必须在节点列表中存在"""
        with pytest.raises(Exception):
            WorkflowConfig(
                name="test",
                executors={"dev": ExecutorConfig()},
                flow_template=FlowTemplate(
                    entry_point="nonexistent",
                    nodes=[FlowNode(id="dev", type="developer", label="开发")],
                    edges=[],
                ),
            )

    def test_validate_dependency_exists(self):
        """依赖的节点必须存在"""
        with pytest.raises(Exception):
            WorkflowConfig(
                name="test",
                executors={"dev": ExecutorConfig()},
                flow_template=FlowTemplate(
                    entry_point="dev",
                    nodes=[FlowNode(id="dev", type="developer", label="开发", depends_on=["nonexistent"])],
                    edges=[],
                ),
            )

    def test_validate_no_cycles(self):
        """流程图中不能存在循环依赖"""
        with pytest.raises(Exception):
            WorkflowConfig(
                name="test",
                executors={"a": ExecutorConfig(), "b": ExecutorConfig()},
                flow_template=FlowTemplate(
                    entry_point="a",
                    nodes=[
                        FlowNode(id="a", type="x", label="A", depends_on=["b"]),
                        FlowNode(id="b", type="y", label="B", depends_on=["a"]),
                    ],
                    edges=[],
                ),
            )

    def test_resolve_vars(self):
        """解析环境变量"""
        import os
        os.environ["TEST_MODEL"] = "test-model"
        cfg = WorkflowConfig(
            name="test",
            executors={"dev": ExecutorConfig(model="${TEST_MODEL}")},
            flow_template=FlowTemplate(
                entry_point="dev",
                nodes=[FlowNode(id="dev", type="developer", label="开发")],
                edges=[],
            ),
        )
        resolved = cfg.resolve_vars()
        assert resolved.executors["dev"].model == "test-model"
        del os.environ["TEST_MODEL"]

    def test_resolve_vars_with_default(self):
        """解析带默认值的环境变量"""
        cfg = WorkflowConfig(
            name="test",
            executors={"dev": ExecutorConfig(model="${NONEXISTENT_VAR:-qwen3.6-plus}")},
            flow_template=FlowTemplate(
                entry_point="dev",
                nodes=[FlowNode(id="dev", type="developer", label="开发")],
                edges=[],
            ),
        )
        resolved = cfg.resolve_vars()
        assert resolved.executors["dev"].model == "qwen3.6-plus"
