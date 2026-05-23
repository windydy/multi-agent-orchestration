"""
WorkspaceManager — 多项目管理器

功能:
- 工作区配置加载与持久化 (.workspace.yaml)
- 项目 CRUD 操作 (create, switch, list, delete)
- 项目模板应用
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class ProjectConfig:
    """项目配置"""
    name: str
    root_path: str
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    default_workflow: str = "software-development"
    vars: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """自动填充创建和更新时间"""
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class WorkspaceConfig:
    """工作区配置"""
    name: str
    projects: dict[str, ProjectConfig] = field(default_factory=dict)
    default_project: Optional[str] = None
    shared_tools: list[str] = field(default_factory=list)
    shared_env: dict[str, str] = field(default_factory=dict)


class WorkspaceManager:
    """工作区管理器

    管理多项目工作区，支持项目创建、切换、列表和删除操作。
    配置持久化到 .workspace.yaml 文件。
    """

    WORKSPACE_FILE = ".workspace.yaml"

    def __init__(self, root_path: str = "."):
        self.root = Path(root_path).resolve()
        self.config = self._load_workspace()

    def _load_workspace(self) -> WorkspaceConfig:
        """从 YAML 文件加载工作区配置

        Returns:
            WorkspaceConfig 实例，如果文件不存在或为空则返回默认配置
        """
        ws_file = self.root / self.WORKSPACE_FILE

        if not ws_file.exists():
            return WorkspaceConfig(name="default")

        try:
            with open(ws_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                return WorkspaceConfig(name="default")

            # 重建 projects 字典为 ProjectConfig 对象
            projects = {}
            for name, proj_data in data.get("projects", {}).items():
                projects[name] = ProjectConfig(
                    name=name,
                    root_path=proj_data.get("root_path", ""),
                    description=proj_data.get("description", ""),
                    created_at=proj_data.get("created_at", ""),
                    updated_at=proj_data.get("updated_at", ""),
                    default_workflow=proj_data.get("default_workflow", "software-development"),
                    vars=proj_data.get("vars", {}),
                    tags=proj_data.get("tags", []),
                )

            return WorkspaceConfig(
                name=data.get("name", "default"),
                projects=projects,
                default_project=data.get("default_project"),
                shared_tools=data.get("shared_tools", []),
                shared_env=data.get("shared_env", {}),
            )
        except Exception:
            return WorkspaceConfig(name="default")

    def _save_workspace(self) -> None:
        """保存工作区配置到 YAML 文件

        只保存 root_path, description, tags, vars 字段到项目配置中。
        """
        ws_file = self.root / self.WORKSPACE_FILE

        data = {
            "name": self.config.name,
            "default_project": self.config.default_project,
            "projects": {},
            "shared_tools": self.config.shared_tools,
            "shared_env": self.config.shared_env,
        }

        for name, proj in self.config.projects.items():
            data["projects"][name] = {
                "root_path": proj.root_path,
                "description": proj.description,
                "created_at": proj.created_at,
                "updated_at": proj.updated_at,
                "default_workflow": proj.default_workflow,
                "vars": proj.vars,
                "tags": proj.tags,
            }

        with open(ws_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    def create_project(
        self,
        name: str,
        path: str,
        description: str = "",
        template: Optional[str] = None,
        vars: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ) -> ProjectConfig:
        """创建新项目

        Args:
            name: 项目名称
            path: 项目根路径
            description: 项目描述
            template: 可选的模板名称
            vars: 项目变量
            tags: 项目标签

        Returns:
            创建的 ProjectConfig 实例
        """
        project = ProjectConfig(
            name=name,
            root_path=path,
            description=description,
            vars=vars or {},
            tags=tags or [],
        )

        # 如果指定了模板，应用模板
        if template:
            self._apply_template(name, path, template)

        # 覆盖已存在的项目或添加新项目
        self.config.projects[name] = project
        self._save_workspace()

        return project

    def switch_project(self, name: str) -> ProjectConfig:
        """切换到指定项目

        Args:
            name: 项目名称

        Returns:
            切换后的 ProjectConfig 实例

        Raises:
            ValueError: 如果项目不存在
        """
        if name not in self.config.projects:
            raise ValueError(f"项目 '{name}' 不存在")

        self.config.default_project = name
        self._save_workspace()

        return self.config.projects[name]

    def get_current_project(self) -> Optional[ProjectConfig]:
        """获取当前项目

        Returns:
            当前项目的 ProjectConfig，如果没有则返回 None
        """
        if self.config.default_project is None:
            return None

        return self.config.projects.get(self.config.default_project)

    def list_projects(self) -> list[ProjectConfig]:
        """列出所有项目

        Returns:
            所有项目的 ProjectConfig 列表
        """
        return list(self.config.projects.values())

    def delete_project(self, name: str) -> None:
        """删除项目

        Args:
            name: 项目名称
        """
        if name in self.config.projects:
            del self.config.projects[name]

            # 如果删除的是当前项目，清除 default_project
            if self.config.default_project == name:
                self.config.default_project = None

            self._save_workspace()

    def _apply_template(self, name: str, path: str, template: str) -> None:
        """应用项目模板

        从项目根目录的父级 templates/ 目录复制模板文件到项目路径。

        Args:
            name: 项目名称
            path: 项目目标路径
            template: 模板名称
        """
        template_path = self.root.parent / "templates" / template

        if not template_path.exists():
            return

        dest = Path(path)
        dest.mkdir(parents=True, exist_ok=True)

        shutil.copytree(template_path, dest, dirs_exist_ok=True)
