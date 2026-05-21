"""
Phase 5 TDD: ConfigLoader

严格遵循 TDD
"""

import pytest
import yaml
import os
import tempfile
from pathlib import Path
from src.config.loader import ConfigLoader
from src.config.schema import WorkflowConfig, ExecutorConfig, FlowTemplate, FlowNode


class TestConfigLoaderBasics:
    """ConfigLoader 基本功能"""

    def test_load_valid_yaml(self):
        """加载有效 YAML 配置"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "name": "test-workflow",
                "executors": {
                    "developer": {"model": "qwen3.6-plus"}
                },
                "flow_template": {
                    "entry_point": "dev",
                    "nodes": [{"id": "dev", "type": "developer", "label": "开发"}],
                    "edges": [],
                },
            }, f)
            f.flush()
            
            loader = ConfigLoader()
            cfg = loader.load(f.name)
            assert cfg.name == "test-workflow"
            assert "developer" in cfg.executors

    def test_load_file_not_found(self):
        """加载不存在的文件"""
        loader = ConfigLoader()
        with pytest.raises(FileNotFoundError):
            loader.load("/nonexistent/path/config.yaml")

    def test_load_and_resolve_vars(self):
        """加载并解析环境变量"""
        os.environ["TEST_LOADER_MODEL"] = "test-model"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "name": "test-vars",
                "executors": {
                    "developer": {"model": "${TEST_LOADER_MODEL}"}
                },
                "flow_template": {
                    "entry_point": "dev",
                    "nodes": [{"id": "dev", "type": "developer", "label": "开发"}],
                    "edges": [],
                },
            }, f)
            f.flush()
            
            loader = ConfigLoader()
            cfg = loader.load(f.name)
            assert cfg.executors["developer"].model == "test-model"
        del os.environ["TEST_LOADER_MODEL"]

    def test_load_merges_defaults(self):
        """加载时自动合并 defaults"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "name": "test-merge",
                "defaults": {
                    "model": "qwen3.6-turbo",
                    "max_iterations": 20,
                    "timeout": 600,
                    "retry": 3,
                },
                "executors": {
                    "developer": {}  # 无自定义字段，使用 defaults
                },
                "flow_template": {
                    "entry_point": "dev",
                    "nodes": [{"id": "dev", "type": "developer", "label": "开发"}],
                    "edges": [],
                },
            }, f)
            f.flush()
            
            loader = ConfigLoader()
            cfg = loader.load(f.name)
            assert cfg.executors["developer"].model == "qwen3.6-turbo"
            assert cfg.executors["developer"].max_iterations == 20

    def test_validate_file_valid(self):
        """验证有效文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "name": "valid-workflow",
                "executors": {"dev": {}},
                "flow_template": {
                    "entry_point": "dev",
                    "nodes": [{"id": "dev", "type": "developer", "label": "开发"}],
                    "edges": [],
                },
            }, f)
            f.flush()
            
            loader = ConfigLoader()
            valid, errors = loader.validate_file(f.name)
            assert valid is True
            assert errors == []

    def test_validate_file_invalid(self):
        """验证无效文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "name": "invalid",
                # 缺少 executors 和 flow_template
            }, f)
            f.flush()
            
            loader = ConfigLoader()
            valid, errors = loader.validate_file(f.name)
            assert valid is False
            assert len(errors) > 0

    def test_list_builtins(self):
        """列出内置工作流"""
        loader = ConfigLoader()
        workflows = loader.list_builtins()
        assert isinstance(workflows, list)
        # 至少有我们创建的内置工作流
        for wf in workflows:
            assert "name" in wf
            assert "path" in wf


class TestConfigLoaderMerging:
    """ConfigLoader 合并配置"""

    def test_load_merged(self):
        """合并多个配置文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f1:
            yaml.dump({
                "name": "base",
                "defaults": {"model": "qwen3.6-plus", "max_iterations": 10, "timeout": 300, "retry": 2},
                "executors": {"developer": {}},
                "flow_template": {
                    "entry_point": "dev",
                    "nodes": [{"id": "dev", "type": "developer", "label": "开发"}],
                    "edges": [],
                },
            }, f1)
            f1.flush()
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f2:
                yaml.dump({
                    "name": "override",
                    "executors": {"developer": {"max_iterations": 30}},
                    "flow_template": {
                        "entry_point": "dev",
                        "nodes": [{"id": "dev", "type": "developer", "label": "开发"}],
                        "edges": [],
                    },
                }, f2)
                f2.flush()
                
                loader = ConfigLoader()
                cfg = loader.load_merged([f1.name, f2.name])
                assert cfg.executors["developer"].max_iterations == 30


class TestConfigLoaderExtends:
    """ConfigLoader extends 模板继承"""

    def test_load_with_extends(self):
        """加载使用 extends 的配置"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = os.path.join(tmpdir, "base.yaml")
            child_path = os.path.join(tmpdir, "child.yaml")
            
            with open(base_path, 'w') as f:
                yaml.dump({
                    "name": "base-dev",
                    "defaults": {"model": "qwen3.6-plus", "max_iterations": 10, "timeout": 300, "retry": 2},
                    "executors": {"developer": {}},
                    "flow_template": {
                        "entry_point": "dev",
                        "nodes": [{"id": "dev", "type": "developer", "label": "开发"}],
                        "edges": [],
                    },
                }, f)
            
            with open(child_path, 'w') as f:
                yaml.dump({
                    "name": "extended-dev",
                    "extends": "base.yaml",
                    "executors": {"linter": {"tools": ["bash"]}},
                    "flow_template": {
                        "entry_point": "dev",
                        "nodes": [
                            {"id": "dev", "type": "developer", "label": "开发"},
                            {"id": "lint", "type": "linter", "label": "检查", "depends_on": ["dev"]},
                        ],
                        "edges": [{"from": "dev", "to": "lint"}],
                    },
                }, f)
            
            loader = ConfigLoader()
            cfg = loader.load(child_path)
            assert cfg.name == "extended-dev"
            assert "developer" in cfg.executors
            assert "linter" in cfg.executors
