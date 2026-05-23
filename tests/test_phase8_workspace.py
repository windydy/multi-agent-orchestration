"""
Phase 8 Workspace 模块 100% 覆盖率测试

测试 ProjectConfig, WorkspaceConfig 数据类以及 WorkspaceManager 的所有方法。
覆盖所有边界情况、异常路径和持久化验证。
"""

import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from src.workspace import ProjectConfig, WorkspaceConfig, WorkspaceManager


# ============================================================================
# ProjectConfig 测试
# ============================================================================

class TestProjectConfig:
    """ProjectConfig 数据类测试"""

    def test_create_minimal(self):
        """最简创建 - 验证所有默认值"""
        proj = ProjectConfig(name="test", root_path="/tmp/test")
        assert proj.name == "test"
        assert proj.root_path == "/tmp/test"
        assert proj.description == ""
        assert proj.created_at != ""
        assert proj.updated_at != ""
        assert proj.default_workflow == "software-development"
        assert proj.vars == {}
        assert proj.tags == []

    def test_create_full(self):
        """完整字段创建"""
        proj = ProjectConfig(
            name="my-project",
            root_path="/projects/my-project",
            description="A test project",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-02T00:00:00",
            default_workflow="data-analysis",
            vars={"env": "dev", "region": "us-east"},
            tags=["backend", "api"],
        )
        assert proj.name == "my-project"
        assert proj.root_path == "/projects/my-project"
        assert proj.description == "A test project"
        assert proj.created_at == "2024-01-01T00:00:00"
        assert proj.updated_at == "2024-01-02T00:00:00"
        assert proj.default_workflow == "data-analysis"
        assert proj.vars == {"env": "dev", "region": "us-east"}
        assert proj.tags == ["backend", "api"]

    def test_auto_timestamps_when_empty(self):
        """空字符串时间戳自动填充"""
        proj = ProjectConfig(
            name="test",
            root_path="/tmp/test",
            created_at="",
            updated_at="",
        )
        assert proj.created_at != ""
        assert proj.updated_at != ""

    def test_custom_timestamps_not_overwritten(self):
        """自定义时间戳不被覆盖"""
        proj = ProjectConfig(
            name="test",
            root_path="/tmp/test",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-02T00:00:00",
        )
        assert proj.created_at == "2024-01-01T00:00:00"
        assert proj.updated_at == "2024-01-02T00:00:00"

    def test_vars_default_is_independent(self):
        """验证 vars 默认值是独立字典，不是共享引用"""
        proj1 = ProjectConfig(name="p1", root_path="/p1")
        proj2 = ProjectConfig(name="p2", root_path="/p2")
        proj1.vars["key"] = "value"
        assert "key" not in proj2.vars

    def test_tags_default_is_independent(self):
        """验证 tags 默认值是独立列表，不是共享引用"""
        proj1 = ProjectConfig(name="p1", root_path="/p1")
        proj2 = ProjectConfig(name="p2", root_path="/p2")
        proj1.tags.append("tag1")
        assert "tag1" not in proj2.tags

    def test_default_workflow_custom(self):
        """自定义 default_workflow"""
        proj = ProjectConfig(
            name="test",
            root_path="/tmp/test",
            default_workflow="custom-workflow",
        )
        assert proj.default_workflow == "custom-workflow"

    def test_timestamps_are_iso_format(self):
        """验证时间戳是 ISO 格式"""
        proj = ProjectConfig(name="test", root_path="/tmp/test")
        # ISO 格式包含 'T' 分隔符
        assert "T" in proj.created_at
        assert "T" in proj.updated_at


# ============================================================================
# WorkspaceConfig 测试
# ============================================================================

class TestWorkspaceConfig:
    """WorkspaceConfig 数据类测试"""

    def test_create_minimal(self):
        """最简创建 - 验证所有默认值"""
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

    def test_projects_default_is_independent(self):
        """验证 projects 默认值是独立字典"""
        ws1 = WorkspaceConfig(name="ws1")
        ws2 = WorkspaceConfig(name="ws2")
        ws1.projects["p1"] = ProjectConfig(name="p1", root_path="/p1")
        assert "p1" not in ws2.projects

    def test_shared_tools_default_is_independent(self):
        """验证 shared_tools 默认值是独立列表"""
        ws1 = WorkspaceConfig(name="ws1")
        ws2 = WorkspaceConfig(name="ws2")
        ws1.shared_tools.append("tool1")
        assert "tool1" not in ws2.shared_tools

    def test_shared_env_default_is_independent(self):
        """验证 shared_env 默认值是独立字典"""
        ws1 = WorkspaceConfig(name="ws1")
        ws2 = WorkspaceConfig(name="ws2")
        ws1.shared_env["KEY"] = "value"
        assert "KEY" not in ws2.shared_env


# ============================================================================
# WorkspaceManager 测试
# ============================================================================

class TestWorkspaceManagerInit:
    """WorkspaceManager 初始化测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_init_no_workspace_file(self, temp_dir):
        """初始化时没有 workspace 文件，创建默认配置"""
        mgr = WorkspaceManager(root_path=temp_dir)
        assert mgr.config.name == "default"
        assert mgr.config.projects == {}
        assert mgr.config.default_project is None
        assert mgr.config.shared_tools == []
        assert mgr.config.shared_env == {}

    def test_init_with_relative_path(self, temp_dir):
        """初始化时使用相对路径，root 被解析为绝对路径"""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            mgr = WorkspaceManager(root_path=".")
            assert mgr.root == Path(temp_dir).resolve()
        finally:
            os.chdir(original_cwd)

    def test_init_with_absolute_path(self, temp_dir):
        """初始化时使用绝对路径"""
        mgr = WorkspaceManager(root_path=temp_dir)
        assert mgr.root == Path(temp_dir).resolve()

    def test_init_root_attribute(self, temp_dir):
        """验证 root 属性是 Path 对象"""
        mgr = WorkspaceManager(root_path=temp_dir)
        assert isinstance(mgr.root, Path)


class TestWorkspaceManagerLoad:
    """WorkspaceManager._load_workspace() 测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_load_nonexistent_file(self, temp_dir):
        """加载不存在的文件，返回默认配置"""
        mgr = WorkspaceManager(root_path=temp_dir)
        assert mgr.config.name == "default"

    def test_load_empty_file(self, temp_dir):
        """加载空文件，返回默认配置"""
        ws_file = Path(temp_dir) / ".workspace.yaml"
        ws_file.write_text("")
        mgr = WorkspaceManager(root_path=temp_dir)
        assert mgr.config.name == "default"

    def test_load_invalid_yaml(self, temp_dir):
        """加载无效 YAML，返回默认配置"""
        ws_file = Path(temp_dir) / ".workspace.yaml"
        ws_file.write_text("invalid: yaml: content: [")
        mgr = WorkspaceManager(root_path=temp_dir)
        assert mgr.config.name == "default"

    def test_load_valid_workspace(self, temp_dir):
        """加载有效的工作区配置"""
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
        assert mgr.config.projects["proj1"].description == "Project 1"
        assert mgr.config.projects["proj1"].vars == {"env": "prod"}
        assert mgr.config.projects["proj1"].tags == ["backend"]
        assert mgr.config.shared_tools == ["bash"]
        assert mgr.config.shared_env == {"KEY": "value"}

    def test_load_workspace_with_empty_projects(self, temp_dir):
        """加载 projects 为空的工作区"""
        ws_file = Path(temp_dir) / ".workspace.yaml"
        ws_data = {
            "name": "empty-workspace",
            "projects": {},
            "default_project": None,
            "shared_tools": [],
            "shared_env": {},
        }
        with open(ws_file, "w", encoding="utf-8") as f:
            yaml.dump(ws_data, f)

        mgr = WorkspaceManager(root_path=temp_dir)
        assert mgr.config.name == "empty-workspace"
        assert mgr.config.projects == {}

    def test_load_workspace_with_partial_project_data(self, temp_dir):
        """加载只有部分字段的项目数据"""
        ws_file = Path(temp_dir) / ".workspace.yaml"
        ws_data = {
            "name": "partial-workspace",
            "projects": {
                "proj1": {
                    "root_path": "/projects/proj1",
                }
            },
        }
        with open(ws_file, "w", encoding="utf-8") as f:
            yaml.dump(ws_data, f)

        mgr = WorkspaceManager(root_path=temp_dir)
        proj = mgr.config.projects["proj1"]
        assert proj.root_path == "/projects/proj1"
        assert proj.description == ""
        assert proj.default_workflow == "software-development"
        assert proj.vars == {}
        assert proj.tags == []

    def test_load_workspace_missing_optional_fields(self, temp_dir):
        """加载缺少可选字段的工作区"""
        ws_file = Path(temp_dir) / ".workspace.yaml"
        ws_data = {
            "name": "minimal-workspace",
        }
        with open(ws_file, "w", encoding="utf-8") as f:
            yaml.dump(ws_data, f)

        mgr = WorkspaceManager(root_path=temp_dir)
        assert mgr.config.name == "minimal-workspace"
        assert mgr.config.projects == {}
        assert mgr.config.default_project is None
        assert mgr.config.shared_tools == []
        assert mgr.config.shared_env == {}


class TestWorkspaceManagerSave:
    """WorkspaceManager._save_workspace() 测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_save_creates_file(self, temp_dir):
        """保存操作创建文件"""
        mgr = WorkspaceManager(root_path=temp_dir)
        ws_file = Path(temp_dir) / ".workspace.yaml"
        assert not ws_file.exists()
        mgr._save_workspace()
        assert ws_file.exists()

    def test_save_content_structure(self, temp_dir):
        """保存的文件内容结构正确"""
        mgr = WorkspaceManager(root_path=temp_dir)
        mgr.config.name = "test-ws"
        mgr.config.default_project = "p1"
        mgr.config.shared_tools = ["bash"]
        mgr.config.shared_env = {"KEY": "val"}
        mgr.config.projects["p1"] = ProjectConfig(
            name="p1",
            root_path="/p1",
            description="Test",
            created_at="2024-01-01",
            updated_at="2024-01-01",
            default_workflow="workflow1",
            vars={"a": "b"},
            tags=["tag1"],
        )
        mgr._save_workspace()

        ws_file = Path(temp_dir) / ".workspace.yaml"
        with open(ws_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["name"] == "test-ws"
        assert data["default_project"] == "p1"
        assert data["shared_tools"] == ["bash"]
        assert data["shared_env"] == {"KEY": "val"}
        assert "p1" in data["projects"]
        assert data["projects"]["p1"]["root_path"] == "/p1"
        assert data["projects"]["p1"]["description"] == "Test"
        assert data["projects"]["p1"]["vars"] == {"a": "b"}
        assert data["projects"]["p1"]["tags"] == ["tag1"]

    def test_save_overwrites_existing_file(self, temp_dir):
        """保存操作覆盖已存在的文件"""
        ws_file = Path(temp_dir) / ".workspace.yaml"
        ws_file.write_text("old: content")

        mgr = WorkspaceManager(root_path=temp_dir)
        mgr.config.name = "new-name"
        mgr._save_workspace()

        with open(ws_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["name"] == "new-name"


class TestWorkspaceManagerCreateProject:
    """WorkspaceManager.create_project() 测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, temp_dir):
        return WorkspaceManager(root_path=temp_dir)

    def test_create_project_basic(self, manager):
        """基本创建项目"""
        proj = manager.create_project(
            name="test-project",
            path="/projects/test",
            description="A test project",
        )
        assert proj.name == "test-project"
        assert proj.root_path == "/projects/test"
        assert proj.description == "A test project"
        assert "test-project" in manager.config.projects

    def test_create_project_with_vars_and_tags(self, manager):
        """创建项目带 vars 和 tags"""
        proj = manager.create_project(
            name="p1",
            path="/p1",
            vars={"env": "dev"},
            tags=["test", "backend"],
        )
        assert proj.vars == {"env": "dev"}
        assert proj.tags == ["test", "backend"]

    def test_create_project_with_none_vars_and_tags(self, manager):
        """创建项目时 vars 和 tags 为 None，使用默认值"""
        proj = manager.create_project(
            name="p1",
            path="/p1",
            vars=None,
            tags=None,
        )
        assert proj.vars == {}
        assert proj.tags == []

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

    def test_create_project_auto_timestamps(self, manager):
        """创建项目自动填充时间戳"""
        proj = manager.create_project(name="p1", path="/p1")
        assert proj.created_at != ""
        assert proj.updated_at != ""

    def test_create_multiple_projects(self, manager):
        """创建多个项目"""
        manager.create_project(name="p1", path="/p1")
        manager.create_project(name="p2", path="/p2")
        manager.create_project(name="p3", path="/p3")
        assert len(manager.config.projects) == 3


class TestWorkspaceManagerSwitchProject:
    """WorkspaceManager.switch_project() 测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, temp_dir):
        return WorkspaceManager(root_path=temp_dir)

    def test_switch_project_success(self, manager):
        """成功切换项目"""
        manager.create_project(name="p1", path="/p1")
        manager.create_project(name="p2", path="/p2")

        proj = manager.switch_project("p2")
        assert proj.name == "p2"
        assert manager.config.default_project == "p2"

    def test_switch_project_not_exists(self, manager):
        """切换到不存在的项目抛出 ValueError"""
        with pytest.raises(ValueError, match="项目 'nonexistent' 不存在"):
            manager.switch_project("nonexistent")

    def test_switch_project_persists(self, manager, temp_dir):
        """切换项目后持久化"""
        manager.create_project(name="p1", path="/p1")
        manager.switch_project("p1")

        ws_file = Path(temp_dir) / ".workspace.yaml"
        with open(ws_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["default_project"] == "p1"

    def test_switch_project_returns_project_config(self, manager):
        """切换项目返回 ProjectConfig 实例"""
        manager.create_project(name="p1", path="/p1", description="Test")
        proj = manager.switch_project("p1")
        assert isinstance(proj, ProjectConfig)
        assert proj.description == "Test"


class TestWorkspaceManagerGetCurrentProject:
    """WorkspaceManager.get_current_project() 测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, temp_dir):
        return WorkspaceManager(root_path=temp_dir)

    def test_get_current_project_none(self, manager):
        """没有当前项目时返回 None"""
        assert manager.get_current_project() is None

    def test_get_current_project_exists(self, manager):
        """获取当前项目"""
        manager.create_project(name="p1", path="/p1")
        manager.switch_project("p1")
        proj = manager.get_current_project()
        assert proj is not None
        assert proj.name == "p1"

    def test_get_current_project_after_switch(self, manager):
        """切换后获取当前项目"""
        manager.create_project(name="p1", path="/p1")
        manager.create_project(name="p2", path="/p2")
        manager.switch_project("p2")
        proj = manager.get_current_project()
        assert proj.name == "p2"

    def test_get_current_project_returns_correct_type(self, manager):
        """返回类型是 ProjectConfig"""
        manager.create_project(name="p1", path="/p1")
        manager.switch_project("p1")
        proj = manager.get_current_project()
        assert isinstance(proj, ProjectConfig)


class TestWorkspaceManagerListProjects:
    """WorkspaceManager.list_projects() 测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, temp_dir):
        return WorkspaceManager(root_path=temp_dir)

    def test_list_projects_empty(self, manager):
        """空工作区列出项目"""
        projects = manager.list_projects()
        assert projects == []

    def test_list_projects_single(self, manager):
        """列出单个项目"""
        manager.create_project(name="p1", path="/p1")
        projects = manager.list_projects()
        assert len(projects) == 1
        assert projects[0].name == "p1"

    def test_list_projects_multiple(self, manager):
        """列出多个项目"""
        manager.create_project(name="p1", path="/p1")
        manager.create_project(name="p2", path="/p2")
        manager.create_project(name="p3", path="/p3")

        projects = manager.list_projects()
        assert len(projects) == 3
        names = {p.name for p in projects}
        assert names == {"p1", "p2", "p3"}

    def test_list_projects_returns_list(self, manager):
        """返回类型是 list"""
        projects = manager.list_projects()
        assert isinstance(projects, list)

    def test_list_projects_returns_copies(self, manager):
        """返回列表是副本，修改不影响原数据"""
        manager.create_project(name="p1", path="/p1")
        projects = manager.list_projects()
        projects.clear()
        assert len(manager.list_projects()) == 1


class TestWorkspaceManagerDeleteProject:
    """WorkspaceManager.delete_project() 测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, temp_dir):
        return WorkspaceManager(root_path=temp_dir)

    def test_delete_project_exists(self, manager):
        """删除存在的项目"""
        manager.create_project(name="p1", path="/p1")
        manager.create_project(name="p2", path="/p2")
        manager.delete_project("p1")

        assert "p1" not in manager.config.projects
        assert "p2" in manager.config.projects

    def test_delete_project_not_exists(self, manager):
        """删除不存在的项目不报错"""
        manager.delete_project("nonexistent")
        assert manager.config.projects == {}

    def test_delete_current_project(self, manager):
        """删除当前项目时清除 default_project"""
        manager.create_project(name="p1", path="/p1")
        manager.switch_project("p1")
        manager.delete_project("p1")

        assert manager.config.default_project is None
        assert manager.get_current_project() is None

    def test_delete_project_persists(self, manager, temp_dir):
        """删除项目后持久化"""
        manager.create_project(name="p1", path="/p1")
        manager.delete_project("p1")

        ws_file = Path(temp_dir) / ".workspace.yaml"
        with open(ws_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "p1" not in data["projects"]

    def test_delete_non_current_project_keeps_default(self, manager):
        """删除非当前项目不影响 default_project"""
        manager.create_project(name="p1", path="/p1")
        manager.create_project(name="p2", path="/p2")
        manager.switch_project("p1")
        manager.delete_project("p2")

        assert manager.config.default_project == "p1"

    def test_delete_last_project(self, manager):
        """删除最后一个项目"""
        manager.create_project(name="p1", path="/p1")
        manager.delete_project("p1")
        assert manager.config.projects == {}
        assert manager.list_projects() == []


class TestWorkspaceManagerApplyTemplate:
    """WorkspaceManager._apply_template() 测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def _create_template(self, temp_dir, template_name, files):
        """创建模板目录的辅助方法，使用唯一名称避免冲突"""
        unique_name = f"{template_name}_{uuid.uuid4().hex[:8]}"
        templates_dir = Path(temp_dir).parent / "templates" / unique_name
        templates_dir.mkdir(parents=True, exist_ok=True)
        for file_path, content in files.items():
            full_path = templates_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        return unique_name

    def test_apply_template_exists(self, temp_dir):
        """应用存在的模板"""
        template_name = self._create_template(
            temp_dir,
            "python-lib",
            {
                "setup.py": "# setup.py",
                "src/__init__.py": "# init",
            }
        )

        mgr = WorkspaceManager(root_path=temp_dir)
        proj_path = Path(temp_dir) / "my-project"
        mgr.create_project(
            name="my-project",
            path=str(proj_path),
            template=template_name,
        )

        assert (proj_path / "setup.py").exists()
        assert (proj_path / "src" / "__init__.py").exists()

    def test_apply_template_nonexistent(self, temp_dir):
        """应用不存在的模板，不报错"""
        mgr = WorkspaceManager(root_path=temp_dir)
        proj_path = Path(temp_dir) / "my-project"
        proj = mgr.create_project(
            name="my-project",
            path=str(proj_path),
            template="nonexistent-template",
        )
        assert proj.name == "my-project"
        # 项目目录不会被创建（因为模板不存在）
        assert not proj_path.exists()

    def test_apply_template_creates_destination_dir(self, temp_dir):
        """应用模板时创建目标目录"""
        template_name = self._create_template(
            temp_dir,
            "simple",
            {"file.txt": "content"}
        )

        mgr = WorkspaceManager(root_path=temp_dir)
        proj_path = Path(temp_dir) / "nested" / "dir" / "project"
        mgr.create_project(
            name="nested-project",
            path=str(proj_path),
            template=template_name,
        )

        assert proj_path.exists()
        assert (proj_path / "file.txt").exists()

    def test_apply_template_overwrites_existing(self, temp_dir):
        """应用模板到已存在的目录"""
        template_name = self._create_template(
            temp_dir,
            "overwrite",
            {"file.txt": "template content"}
        )

        mgr = WorkspaceManager(root_path=temp_dir)
        proj_path = Path(temp_dir) / "project"
        proj_path.mkdir(parents=True)
        (proj_path / "file.txt").write_text("old content")

        mgr.create_project(
            name="project",
            path=str(proj_path),
            template=template_name,
        )

        assert (proj_path / "file.txt").read_text() == "template content"

    def test_apply_template_with_subdirectories(self, temp_dir):
        """应用包含子目录的模板"""
        template_name = self._create_template(
            temp_dir,
            "complex",
            {"a/b/file.txt": "deep file"}
        )

        mgr = WorkspaceManager(root_path=temp_dir)
        proj_path = Path(temp_dir) / "project"
        mgr.create_project(
            name="project",
            path=str(proj_path),
            template=template_name,
        )

        assert (proj_path / "a" / "b" / "file.txt").exists()


class TestWorkspaceManagerIntegration:
    """WorkspaceManager 集成测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_full_lifecycle(self, temp_dir):
        """完整生命周期：创建、切换、列表、删除"""
        mgr = WorkspaceManager(root_path=temp_dir)

        # 创建项目
        p1 = mgr.create_project(name="proj1", path="/proj1", description="Project 1")
        p2 = mgr.create_project(name="proj2", path="/proj2", description="Project 2")

        # 验证列表
        assert len(mgr.list_projects()) == 2

        # 切换项目
        mgr.switch_project("proj2")
        assert mgr.get_current_project().name == "proj2"

        # 删除项目
        mgr.delete_project("proj1")
        assert len(mgr.list_projects()) == 1

        # 验证当前项目不受影响
        assert mgr.get_current_project().name == "proj2"

    def test_save_and_reload_consistency(self, temp_dir):
        """保存后重新加载数据一致"""
        mgr1 = WorkspaceManager(root_path=temp_dir)
        mgr1.create_project(name="p1", path="/p1", description="Project 1", tags=["tag1"])
        mgr1.switch_project("p1")
        mgr1.config.shared_tools = ["bash"]
        mgr1.config.shared_env = {"KEY": "value"}
        mgr1._save_workspace()

        mgr2 = WorkspaceManager(root_path=temp_dir)
        assert mgr2.config.name == "default"
        assert "p1" in mgr2.config.projects
        assert mgr2.config.projects["p1"].description == "Project 1"
        assert mgr2.config.projects["p1"].tags == ["tag1"]
        assert mgr2.config.default_project == "p1"
        assert mgr2.config.shared_tools == ["bash"]
        assert mgr2.config.shared_env == {"KEY": "value"}

    def test_multiple_managers_same_workspace(self, temp_dir):
        """多个管理器实例操作同一工作区"""
        mgr1 = WorkspaceManager(root_path=temp_dir)
        mgr2 = WorkspaceManager(root_path=temp_dir)

        mgr1.create_project(name="p1", path="/p1")

        # mgr2 需要重新加载才能看到变化
        mgr2 = WorkspaceManager(root_path=temp_dir)
        assert "p1" in mgr2.config.projects

    def test_workspace_file_location(self, temp_dir):
        """验证 workspace 文件位置"""
        mgr = WorkspaceManager(root_path=temp_dir)
        expected_file = Path(temp_dir) / ".workspace.yaml"
        mgr._save_workspace()
        assert expected_file.exists()

    def test_project_timestamps_persist(self, temp_dir):
        """项目时间戳持久化后保持一致"""
        mgr1 = WorkspaceManager(root_path=temp_dir)
        proj = mgr1.create_project(name="p1", path="/p1")
        created_at = proj.created_at
        updated_at = proj.updated_at

        mgr2 = WorkspaceManager(root_path=temp_dir)
        assert mgr2.config.projects["p1"].created_at == created_at
        assert mgr2.config.projects["p1"].updated_at == updated_at
