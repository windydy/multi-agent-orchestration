"""
Workspace 模块 — 多项目管理

提供工作区配置管理和项目 CRUD 操作。
"""

from .manager import ProjectConfig, WorkspaceConfig, WorkspaceManager

__all__ = [
    "ProjectConfig",
    "WorkspaceConfig",
    "WorkspaceManager",
]
