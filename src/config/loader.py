"""
Phase 5: ConfigLoader — 配置加载器

src/config/loader.py
"""

import os
import yaml
from pathlib import Path
from typing import Optional
from .schema import WorkflowConfig


class ConfigLoader:
    """配置加载器
    
    功能:
    - 加载单个或多个 YAML 配置
    - 配置合并（基础 + 覆盖）
    - extends 模板继承
    - 环境变量解析
    - Schema 校验
    """
    
    BUILTIN_DIR = Path(__file__).parent.parent.parent / "config" / "workflows"
    
    def __init__(self):
        self._configs: dict[str, WorkflowConfig] = {}
        self._builtin_dir: Optional[Path] = None
    
    def load(self, path: str, resolve_vars: bool = True) -> WorkflowConfig:
        """加载单个配置文件
        
        Args:
            path: 配置文件路径（绝对路径或相对于项目根）
            resolve_vars: 是否解析环境变量
        
        Returns:
            验证后的 WorkflowConfig
        """
        file_path = self._resolve_path(path)
        
        with open(file_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        
        # 检查 extends 字段
        if "extends" in raw:
            parent_name = raw.pop("extends")
            # 查找父配置文件
            parent_path = self._resolve_parent_path(parent_name, file_path)
            parent_config = self.load(parent_path, resolve_vars=False)
            # 深度合并
            parent_data = parent_config.model_dump(by_alias=True)
            merged = self._deep_merge(parent_data, raw)
            config = WorkflowConfig(**merged)
        else:
            config = WorkflowConfig(**raw)
        
        if resolve_vars:
            config = config.resolve_vars()
        
        config = config.merge_executor_defaults()
        
        self._configs[config.name] = config
        return config
    
    def load_merged(self, paths: list[str]) -> WorkflowConfig:
        """加载并合并多个配置
        
        第一个为基础配置，后续为覆盖配置。
        """
        if not paths:
            raise ValueError("至少需要一个配置文件路径")
        
        base = self.load(paths[0])
        
        for override_path in paths[1:]:
            override = self.load(override_path)
            base = self._merge_configs(base, override)
        
        return base
    
    def load_builtin(self, name: str) -> WorkflowConfig:
        """加载内置工作流配置"""
        builtin_dir = self._get_builtin_dir()
        path = builtin_dir / f"{name}.yaml"
        if not path.exists():
            available = [f.stem for f in builtin_dir.glob("*.yaml")]
            raise FileNotFoundError(
                f"内置工作流 '{name}' 不存在。可用的: {available}"
            )
        return self.load(str(path))
    
    def validate_file(self, path: str) -> tuple[bool, list[str]]:
        """验证配置文件，不加载
        
        Returns:
            (是否有效, 错误列表)
        """
        try:
            self.load(path)
            return True, []
        except Exception as e:
            return False, [str(e)]
    
    def list_builtins(self) -> list[dict]:
        """列出所有内置工作流"""
        builtin_dir = self._get_builtin_dir()
        workflows = []
        for f in sorted(builtin_dir.glob("*.yaml")):
            with open(f) as fh:
                data = yaml.safe_load(fh)
            workflows.append({
                "name": data.get("name", f.stem),
                "display_name": data.get("display_name", ""),
                "description": data.get("description", ""),
                "path": str(f),
            })
        return workflows
    
    def _resolve_path(self, path: str) -> Path:
        """解析文件路径"""
        p = Path(path)
        if p.is_absolute():
            if p.exists():
                return p
            raise FileNotFoundError(f"配置文件未找到: {path}")
        
        # 相对路径从当前目录查找
        if p.exists():
            return p.resolve()
        
        # 从内置目录查找
        builtin = self._get_builtin_dir() / p
        if builtin.exists():
            return builtin
        
        raise FileNotFoundError(f"配置文件未找到: {path}")
    
    def _resolve_parent_path(self, parent_name: str, child_path: Path) -> Path:
        """解析 extends 的父配置路径"""
        p = Path(parent_name)
        
        # 如果是相对路径，相对于子配置文件的目录
        if not p.is_absolute():
            sibling = child_path.parent / p
            if sibling.exists():
                return sibling
        
        # 尝试从内置目录查找
        builtin = self._get_builtin_dir() / p
        if builtin.exists():
            return builtin
        
        raise FileNotFoundError(f"extends 父配置未找到: {parent_name}")
    
    def _merge_configs(self, base: WorkflowConfig, override: WorkflowConfig) -> WorkflowConfig:
        """合并两个配置，override 优先"""
        base_data = base.model_dump(by_alias=True)
        override_data = override.model_dump(by_alias=True)
        
        merged = self._deep_merge(base_data, override_data)
        return WorkflowConfig(**merged)
    
    def _deep_merge(self, base: dict, override: dict) -> dict:
        """深度合并字典"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def _get_builtin_dir(self) -> Path:
        """获取内置工作流目录"""
        if self._builtin_dir is None:
            if self.BUILTIN_DIR.exists():
                self._builtin_dir = self.BUILTIN_DIR
            else:
                # 如果内置目录不存在，创建它
                self.BUILTIN_DIR.mkdir(parents=True, exist_ok=True)
                self._builtin_dir = self.BUILTIN_DIR
        return self._builtin_dir
