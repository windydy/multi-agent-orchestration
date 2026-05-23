"""
Workspace 模块 TDD 测试

测试 ProjectConfig, WorkspaceConfig 数据类以及 WorkspaceManager 的所有方法。
"""

import os
import tempfile
import uuid
from pathlib import Path

import pytest
import yaml

from src.workspace import ProjectConfig, WorkspaceConfig, WorkspaceManager


class TestProjectConfig:
    """ProjectConfig 数据类测试"""

    def test_create_minimal(self):
        """最简创建"""
        proj = ProjectConfig(name="test", root_path="/tmp/test")
        assert proj.name == "test"
        assert proj.root_path == "/tmp/test"
        assert proj.description == ""
        assert proj.default_workflow == "software-development"
        assert proj.vars == {}
        assert proj.tags == []

    def test_create_full(self):
        """完整字段创建"""
        proj = ProjectConfig(
            name="my-project",
            root_path="/projects/my-project",
            description="A test project",
            default_workflow="data-analysis",
            vars={"env": "dev", "region": "us-east"},
            tags=["backend", "api"],
        )
        assert proj.name == "my-project"
        assert proj.root_path == "/projects/my-project"
        assert proj.description == "A test project"
        assert proj.default_workflow == "data-analysis"
        assert proj.vars == {"env": "dev", "region": "us-east"}
        assert proj.tags == ["backend", "api"]

    def test_auto_timestamps(self):
        """自动填充创建和更新时间"""
        proj = ProjectConfig(name="test", root_path="/tmp/test")
        assert proj.created_at != ""
        assert proj.updated_at != ""

    def test_custom_timestamps(self):
        """自定义时间戳不被覆盖"""
        proj = ProjectConfig(
            name="test",
            root_path="/tmp/test",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-02T00:00:00",
        )
        assert proj.created_at == "2024-01-01T00:00:00"
        assert proj.updated_at == "2024-01-02T00:00:00"


class TestWorkspaceConfig:
    """WorkspaceConfig 数据类测试"""

    def test_create_minimal(self):
        """最简创建"""
        ws = WorkspaceConfig(name="default")
        assert ws.name == "default"
        assert ws.projects == {}
        assert ws.default_project is None
        assert ws.shared_tools == []
        assert ws.shared_env == {}

    def test_create_full(self):
        """完整字段创建"""
        proj = ProjectConfig(name="p1", root_path="/p1")
        ws = WorkspaceConfig(
            name="my-workspace",
            projects={"p1": proj},
            default_project="p1",
            shared_tools=["read_file", "bash"],
            shared_env={"API_KEY": "secret"},
        )
        assert ws.name == "my-workspace"
        assert "p1" in ws.projects
        assert ws.default_project == "p1"
        assert ws.shared_tools == ["read_file", "bash"]
        assert ws.shared_env == {"API_KEY": "secret"}


class TestWorkspaceManager:
    """WorkspaceManager 类测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, temp_dir):
        """创建 WorkspaceManager 实例"""
        return WorkspaceManager(root_path=temp_dir)

    def test_init_no_workspace_file(self, temp_dir):
        """初始化时没有 workspace 文件，创建默认配置"""
        mgr = WorkspaceManager(root_path=temp_dir)
        assert mgr.config.name == "default"
        assert mgr.config.projects == {}
        assert mgr.config.default_project is None

    def test_load_existing_workspace(self, temp_dir):
        """加载已存在的 workspace 文件"""
        ws_file = Path(temp_dir) / ".workspace.yaml"
        ws_data = {
            "name": "test-workspace",
            "default_project": "proj1",
            "projects": {
                "proj1": {
                    "root_path": "/projects/proj1",
                    "description": "Project 1",
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00",
                    "default_workflow": "software-development",
                    "vars": {"env": "prod"},
                    "tags": ["backend"],
                }
            },
            "shared_tools": ["bash"],
            "shared_env": {"KEY": "value"},
        }
        with open(ws_file, "w", encoding="utf-8") as f:
            yaml.dump(ws_data, f)

        mgr = WorkspaceManager(root_path=temp_dir)
        assert mgr.config.name == "test-workspace"
        assert mgr.config.default_project == "proj1"
        assert "proj1" in mgr.config.projects
        assert mgr.config.projects["proj1"].root_path == "/projects/proj1"
        assert mgr.config.shared_tools == ["bash"]
        assert mgr.config.shared_env == {"KEY": "value"}

    def test_load_empty_workspace_file(self, temp_dir):
        """加载空的 workspace 文件"""
        ws_file = Path(temp_dir) / ".workspace.yaml"
        with open(ws_file, "w", encoding="utf-8") as f:
            f.write("")

        mgr = WorkspaceManager(root_path=temp_dir)
        assert mgr.config.name == "default"

    def test_load_invalid_yaml(self, temp_dir):
        """加载无效的 YAML 文件，返回默认配置"""
        ws_file = Path(temp_dir) / ".workspace.yaml"
        with open(ws_file, "w", encoding="utf-8") as f:
            f.write("invalid: yaml: content: [")

        mgr = WorkspaceManager(root_path=temp_dir)
        assert mgr.config.name == "default"

    def test_create_project(self, manager):
        """创建项目"""
        proj = manager.create_project(
            name="test-project",
            path="/projects/test",
            description="A test project",
            vars={"env": "dev"},
            tags=["test"],
        )
        assert proj.name == "test-project"
        assert proj.root_path == "/projects/test"
        assert proj.description == "A test project"
        assert proj.vars == {"env": "dev"}
        assert proj.tags == ["test"]
        assert "test-project" in manager.config.projects

    def test_create_project_persists(self, manager, temp_dir):
        """创建项目后持久化到文件"""
        manager.create_project(name="p1", path="/p1")
        ws_file = Path(temp_dir) / ".workspace.yaml"
        assert ws_file.exists()

        with open(ws_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "p1" in data["projects"]

    def test_create_project_overwrite(self, manager):
        """创建同名项目会覆盖"""
        manager.create_project(name="p1", path="/old-path")
        proj = manager.create_project(name="p1", path="/new-path")
        assert proj.root_path == "/new-path"
        assert manager.config.projects["p1"].root_path == "/new-path"

    def test_switch_project(self, manager):
        """切换项目"""
        manager.create_project(name="p1", path="/p1")
        manager.create_project(name="p2", path="/p2")

        proj = manager.switch_project("p2")
        assert proj.name == "p2"
        assert manager.config.default_project == "p2"

    def test_switch_project_not_exists(self, manager):
        """切换到不存在的项目抛出异常"""
        with pytest.raises(ValueError, match="项目 'nonexistent' 不存在"):
            manager.switch_project("nonexistent")

    def test_get_current_project_none(self, manager):
        """没有当前项目时返回 None"""
        assert manager.get_current_project() is None

    def test_get_current_project(self, manager):
        """获取当前项目"""
        manager.create_project(name="p1", path="/p1")
        manager.switch_project("p1")
        proj = manager.get_current_project()
        assert proj is not None
        assert proj.name == "p1"

    def test_list_projects(self, manager):
        """列出所有项目"""
        manager.create_project(name="p1", path="/p1")
        manager.create_project(name="p2", path="/p2")
        manager.create_project(name="p3", path="/p3")

        projects = manager.list_projects()
        assert len(projects) == 3
        names = {p.name for p in projects}
        assert names == {"p1", "p2", "p3"}

    def test_list_projects_empty(self, manager):
        """空工作区列出项目"""
        projects = manager.list_projects()
        assert projects == []

    def test_delete_project(self, manager):
        """删除项目"""
        manager.create_project(name="p1", path="/p1")
        manager.create_project(name="p2", path="/p2")
        manager.delete_project("p1")

        assert "p1" not in manager.config.projects
        assert "p2" in manager.config.projects

    def test_delete_current_project(self, manager):
        """删除当前项目时清除 default_project"""
        manager.create_project(name="p1", path="/p1")
        manager.switch_project("p1")
        manager.delete_project("p1")

        assert manager.config.default_project is None
        assert manager.get_current_project() is None

    def test_delete_nonexistent_project(self, manager):
        """删除不存在的项目不报错"""
        manager.delete_project("nonexistent")
        assert manager.config.projects == {}

    def test_save_and_reload(self, temp_dir):
        """保存后重新加载数据一致"""
        mgr1 = WorkspaceManager(root_path=temp_dir)
        mgr1.create_project(name="p1", path="/p1", description="Project 1", tags=["tag1"])
        mgr1.switch_project("p1")

        mgr2 = WorkspaceManager(root_path=temp_dir)
        assert mgr2.config.name == "default"
        assert "p1" in mgr2.config.projects
        assert mgr2.config.projects["p1"].description == "Project 1"
        assert mgr2.config.projects["p1"].tags == ["tag1"]
        assert mgr2.config.default_project == "p1"

    def test_create_project_with_template(self, temp_dir):
        """创建项目时应用模板"""
        # 创建模板目录（使用唯一名称避免冲突）
        template_name = f"python-lib-{uuid.uuid4().hex[:8]}"
        templates_dir = Path(temp_dir).parent / "templates" / template_name
        templates_dir.mkdir(parents=True, exist_ok=True)
        (templates_dir / "setup.py").write_text("# setup.py")
        (templates_dir / "src").mkdir(exist_ok=True)
        (templates_dir / "src" / "__init__.py").write_text("# init")

        mgr = WorkspaceManager(root_path=temp_dir)
        proj_path = Path(temp_dir) / "my-project"
        mgr.create_project(
            name="my-project",
            path=str(proj_path),
            template=template_name,
        )

        assert (proj_path / "setup.py").exists()
        assert (proj_path / "src" / "__init__.py").exists()

    def test_create_project_with_nonexistent_template(self, manager):
        """创建项目时使用不存在的模板，不报错"""
        proj = manager.create_project(
            name="p1",
            path="/p1",
            template="nonexistent-template",
        )
        assert proj.name == "p1"

    def test_workspace_file_path(self, temp_dir):
        """workspace 文件路径正确"""
        mgr = WorkspaceManager(root_path=temp_dir)
        expected = Path(temp_dir) / ".workspace.yaml"
        assert mgr.root == Path(temp_dir).resolve()

    def test_shared_config_persistence(self, temp_dir):
        """共享配置持久化"""
        mgr = WorkspaceManager(root_path=temp_dir)
        mgr.config.shared_tools = ["bash", "read_file"]
        mgr.config.shared_env = {"API_URL": "http://api.example.com"}
        mgr._save_workspace()

        mgr2 = WorkspaceManager(root_path=temp_dir)
        assert mgr2.config.shared_tools == ["bash", "read_file"]
        assert mgr2.config.shared_env == {"API_URL": "http://api.example.com"}
