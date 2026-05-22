"""
PM Tool — user story generation, RICE prioritization, requirements parsing.
"""

from __future__ import annotations

import re
from ..core.tool import BaseTool, ToolConfig, ToolResult


class PMTool(BaseTool):
    """产品经理工具 — 用户故事生成、RICE 优先级排序、需求解析"""

    def __init__(self):
        config = ToolConfig(
            name="pm_tool",
            description="Generate user stories, RICE prioritization, requirements parsing",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["user_story", "rice", "parse_requirements"],
                    },
                    "role": {"type": "string"},
                    "goal": {"type": "string"},
                    "value": {"type": "string"},
                    "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                    "items": {"type": "array"},
                    "content": {"type": "string"},
                },
                "required": ["action"],
            },
        )
        super().__init__(config)

    async def run(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "user_story")
        if action == "user_story":
            story = self.generate_user_story(
                role=kwargs.get("role", "用户"),
                goal=kwargs.get("goal", ""),
                value=kwargs.get("value", ""),
                acceptance_criteria=kwargs.get("acceptance_criteria", []),
            )
            return ToolResult(success=True, output=story)
        if action == "rice":
            items = kwargs.get("items", [])
            result = self.rice_prioritize(items)
            return ToolResult(success=True, output=result)
        if action == "parse_requirements":
            content = kwargs.get("content", "")
            result = self.parse_requirements(content)
            return ToolResult(success=True, output=result)
        return ToolResult(success=False, output=None, error=f"Unknown action: {action}")

    def generate_user_story(
        self,
        role: str,
        goal: str,
        value: str,
        acceptance_criteria: list[str] | None = None,
        priority: str = "P1",
    ) -> str:
        """生成格式化的用户故事"""
        lines = [
            "## 用户故事",
            "",
            f"**作为** {role}，",
            f"**我想** {goal}，",
            f"**以便** {value}。",
            "",
            f"**优先级**: {priority}",
        ]

        if acceptance_criteria:
            lines.append("")
            lines.append("### 验收标准")
            lines.append("")
            for i, ac in enumerate(acceptance_criteria, 1):
                lines.append(f"{i}. {ac}")

        return "\n".join(lines)

    def rice_prioritize(
        self,
        items: list[dict],
    ) -> list[dict]:
        """
        使用 RICE 模型排优先级。

        RICE Score = (Reach × Impact × Confidence) / Effort
        """
        scored = []
        for item in items:
            reach = item.get("reach", 0)
            impact = item.get("impact", 1)
            confidence = item.get("confidence", 50) / 100  # 0-1
            effort = item.get("effort", 1)

            if effort == 0:
                effort = 1

            score = (reach * impact * confidence) / effort
            scored.append({
                **item,
                "rice_score": round(score, 2),
            })

        scored.sort(key=lambda x: x["rice_score"], reverse=True)
        return scored

    def parse_requirements(self, text: str) -> dict:
        """解析需求文档，区分功能性和非功能性需求"""
        functional: list[str] = []
        non_functional: list[str] = []
        assumptions: list[str] = []

        lines = text.strip().splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Remove numbering
            cleaned = re.sub(r'^\d+[\.\)]\s*', '', line).strip()

            lower = cleaned.lower()
            # Non-functional keywords
            nf_keywords = ["响应时间", "性能", "安全", "可用性", "可靠性",
                          "可扩展", "并发", "延迟", "吞吐量", "容量",
                          "response time", "performance", "security",
                          "availability", "latency", "throughput"]

            if any(kw in lower for kw in nf_keywords):
                non_functional.append(cleaned)
            elif cleaned.startswith(("应该", "需要", "必须")) or re.match(r'.*should.*|.*must.*', lower):
                functional.append(cleaned)
            elif cleaned.startswith(("假设", "assume")):
                assumptions.append(cleaned)
            else:
                # Default to functional if it looks like a requirement
                if len(cleaned) > 10 and not cleaned.startswith(("需求", "描述", "背景")):
                    functional.append(cleaned)

        return {
            "functional": functional,
            "non_functional": non_functional,
            "assumptions": assumptions,
            "total": len(functional) + len(non_functional),
        }
