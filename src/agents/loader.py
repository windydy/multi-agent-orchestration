"""
AgentLoader — 从 agents/*.md 文件加载 Agent 定义

支持从 Markdown 文件加载 Agent 定义（YAML frontmatter + system prompt body）。
"""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class AgentDefinition:
    """Agent 定义（从 .md 文件加载）"""
    name: str
    role: str = ""
    description: str = ""
    model: str = "qwen3.6-plus"
    max_iterations: int = 10
    timeout: int = 300
    temperature: float = 0.1
    tools: list[str] = field(default_factory=list)
    system_prompt: str = ""
    source_path: str = ""


class AgentLoader:
    """Agent 定义加载器
    
    从 agents/ 目录加载 .md 文件，解析 YAML frontmatter 和 system prompt。
    """
    
    def __init__(self, agents_dir: Optional[str] = None):
        if agents_dir:
            self.agents_dir = Path(agents_dir)
        else:
            # agents/ is at project root, same level as src/
            self.agents_dir = Path(__file__).parent.parent.parent / "agents"
        
        self._cache: dict[str, AgentDefinition] = {}
    
    def load(self, name: str) -> AgentDefinition:
        """加载指定 Agent 定义
        
        Args:
            name: Agent 名称（不含 .md 后缀）
            
        Returns:
            AgentDefinition
        """
        if name in self._cache:
            return self._cache[name]
        
        md_path = self.agents_dir / f"{name}.md"
        if not md_path.exists():
            raise FileNotFoundError(
                f"Agent 定义未找到: {md_path}\n"
                f"可用的 Agent: {self.list_agents()}"
            )
        
        with open(md_path, encoding="utf-8") as f:
            content = f.read()
        
        definition = self._parse_md(content, str(md_path))
        self._cache[name] = definition
        return definition
    
    def list_agents(self) -> list[str]:
        """列出所有可用的 Agent"""
        if not self.agents_dir.exists():
            return []
        return [f.stem for f in self.agents_dir.glob("*.md")]
    
    @staticmethod
    def _parse_md(content: str, source_path: str) -> AgentDefinition:
        """解析 Markdown 文件（YAML frontmatter + body）"""
        content = content.strip()
        
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                yaml_block = parts[1].strip()
                body = parts[2].strip()
            else:
                yaml_block = ""
                body = content[3:].strip()
        else:
            yaml_block = ""
            body = content
        
        if yaml_block:
            import yaml
            try:
                frontmatter = yaml.safe_load(yaml_block) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"YAML frontmatter 解析失败: {source_path}: {e}")
        else:
            frontmatter = {}
        
        # 校验 tools 字段类型
        raw_tools = frontmatter.get("tools", [])
        if not isinstance(raw_tools, list):
            raw_tools = [raw_tools] if raw_tools else []
        
        return AgentDefinition(
            name=frontmatter.get("name", Path(source_path).stem),
            role=frontmatter.get("role", ""),
            description=frontmatter.get("description", ""),
            model=frontmatter.get("model", "qwen3.6-plus"),
            max_iterations=frontmatter.get("max_iterations", 10),
            timeout=frontmatter.get("timeout", 300),
            temperature=frontmatter.get("temperature", 0.1),
            tools=raw_tools,
            system_prompt=body,
            source_path=source_path,
        )
