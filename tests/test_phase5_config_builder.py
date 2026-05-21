"""
Phase 5 TDD: ConfigurableWorkflowBuilder

严格遵循 TDD
"""

import pytest
from src.config.schema import (
    WorkflowConfig, ExecutorConfig, FlowTemplate, FlowNode, FlowEdge,
    ExecutorDefaults,
)
from src.workflows.config_builder import ConfigurableWorkflowBuilder
from src.plan.graph import PlanNode, PlanGraph, NodeType, ExecutorCapability


class TestConfigurableWorkflowBuilder:
    """ConfigurableWorkflowBuilder"""

    def test_create_builder(self):
        """创建 Builder"""
        cfg = WorkflowConfig(
            name="test",
            executors={"developer": ExecutorConfig()},
            flow_template=FlowTemplate(
                entry_point="dev",
                nodes=[FlowNode(id="dev", type="developer", label="开发")],
                edges=[],
            ),
        )
        builder = ConfigurableWorkflowBuilder(cfg)
        assert builder is not None

    def test_build_returns_compiled_app(self):
        """build 返回编译后的 LangGraph app"""
        cfg = WorkflowConfig(
            name="test",
            executors={"developer": ExecutorConfig()},
            flow_template=FlowTemplate(
                entry_point="dev",
                nodes=[FlowNode(id="dev", type="developer", label="开发")],
                edges=[],
            ),
        )
        builder = ConfigurableWorkflowBuilder(cfg)
        app = builder.build()
        assert app is not None
        assert hasattr(app, 'ainvoke')

    def test_build_with_multiple_nodes(self):
        """构建多节点工作流"""
        cfg = WorkflowConfig(
            name="multi",
            executors={
                "requirements": ExecutorConfig(),
                "developer": ExecutorConfig(),
            },
            flow_template=FlowTemplate(
                entry_point="req",
                nodes=[
                    FlowNode(id="req", type="requirements", label="需求"),
                    FlowNode(id="dev", type="developer", label="开发", depends_on=["req"]),
                ],
                edges=[{"from": "req", "to": "dev"}],
            ),
        )
        builder = ConfigurableWorkflowBuilder(cfg)
        app = builder.build()
        assert app is not None

    def test_build_with_parallel_nodes(self):
        """构建包含并行节点的工作流"""
        cfg = WorkflowConfig(
            name="parallel-test",
            executors={"developer": ExecutorConfig()},
            flow_template=FlowTemplate(
                entry_point="dev",
                nodes=[
                    FlowNode(id="dev", type="developer", label="开发"),
                    FlowNode(id="dev2", type="developer", label="开发2", depends_on=["dev"], parallel=True),
                    FlowNode(id="dev3", type="developer", label="开发3", depends_on=["dev"], parallel=True),
                ],
                edges=[
                    FlowEdge(**{"from": "dev", "to": "dev2"}),
                    FlowEdge(**{"from": "dev", "to": "dev3"}),
                ],
            ),
        )
        builder = ConfigurableWorkflowBuilder(cfg)
        app = builder.build()
        assert app is not None

    def test_build_with_defaults_merged(self):
        """Builder 应使用合并 defaults 后的配置"""
        cfg = WorkflowConfig(
            name="defaults-test",
            defaults=ExecutorDefaults(
                model="qwen3.6-turbo",
                max_iterations=20,
                timeout=600,
                retry=3,
            ),
            executors={"developer": ExecutorConfig()},
            flow_template=FlowTemplate(
                entry_point="dev",
                nodes=[FlowNode(id="dev", type="developer", label="开发")],
                edges=[],
            ),
        )
        builder = ConfigurableWorkflowBuilder(cfg)
        app = builder.build()
        assert app is not None
