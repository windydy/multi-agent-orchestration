"""
Architect Tool — trade-off analysis, tech stack evaluation, capacity planning.
"""

from __future__ import annotations

from ..core.tool import BaseTool, ToolConfig, ToolResult


class ArchitectTool(BaseTool):
    """架构师工具 — 技术权衡分析、技术选型评估、容量规划"""

    def __init__(self):
        config = ToolConfig(
            name="architect_tool",
            description="Trade-off analysis, tech stack evaluation, capacity planning",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["tradeoff", "evaluate", "capacity"],
                    },
                    "decision": {"type": "string"},
                    "pros": {"type": "array", "items": {"type": "string"}},
                    "cons": {"type": "array", "items": {"type": "string"}},
                    "alternatives": {"type": "array", "items": {"type": "string"}},
                    "requirement": {"type": "string"},
                    "candidates": {"type": "array", "items": {"type": "string"}},
                    "criteria": {"type": "array", "items": {"type": "string"}},
                    "qps": {"type": "integer"},
                    "avg_response_size_kb": {"type": "integer"},
                    "data_growth_gb_per_month": {"type": "integer"},
                },
                "required": ["action"],
            },
        )
        super().__init__(config)

    async def run(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "tradeoff")
        if action == "tradeoff":
            result = self.tradeoff_analysis(
                decision=kwargs.get("decision", ""),
                pros=kwargs.get("pros", []),
                cons=kwargs.get("cons", []),
                alternatives=kwargs.get("alternatives", []),
            )
            return ToolResult(success=True, output=result)
        if action == "evaluate":
            result = self.evaluate_tech_stack(
                requirement=kwargs.get("requirement", ""),
                candidates=kwargs.get("candidates", []),
                criteria=kwargs.get("criteria", []),
            )
            return ToolResult(success=True, output=result)
        if action == "capacity":
            result = self.capacity_estimate(
                qps=kwargs.get("qps", 0),
                avg_response_size_kb=kwargs.get("avg_response_size_kb", 0),
                data_growth_gb_per_month=kwargs.get("data_growth_gb_per_month", 0),
            )
            return ToolResult(success=True, output=result)
        return ToolResult(success=False, output=None, error=f"Unknown action: {action}")

    def tradeoff_analysis(
        self,
        decision: str,
        pros: list[str],
        cons: list[str],
        alternatives: list[str] | None = None,
    ) -> str:
        """生成技术权衡分析"""
        lines = [
            f"## 技术权衡分析: {decision}\n",
            "### ✅ 优势",
        ]
        for p in pros:
            lines.append(f"- {p}")

        lines.append("\n### ⚠️ 劣势")
        for c in cons:
            lines.append(f"- {c}")

        if alternatives:
            lines.append("\n### 🔄 替代方案")
            for a in alternatives:
                lines.append(f"- {a}")

        lines.append("\n### 💡 建议")
        if len(cons) > len(pros):
            lines.append(
                "⚠️ 劣势多于优势，建议进一步评估替代方案或制定风险缓解计划。"
            )
        else:
            lines.append(
                "✅ 优势明显，建议在制定详细实施计划后推进。"
            )

        return "\n".join(lines)

    def evaluate_tech_stack(
        self,
        requirement: str,
        candidates: list[str],
        criteria: list[str] | None = None,
    ) -> dict:
        """评估技术选型"""
        criteria = criteria or ["性能", "开发效率", "生态", "学习曲线", "可维护性"]

        # Scoring heuristics based on well-known tech profiles
        tech_scores: dict[str, dict[str, int]] = {
            "fastapi": {"性能": 9, "开发效率": 8, "生态": 7, "学习曲线": 7, "可维护性": 8},
            "flask": {"性能": 7, "开发效率": 8, "生态": 9, "学习曲线": 9, "可维护性": 7},
            "django": {"性能": 6, "开发效率": 7, "生态": 10, "学习曲线": 6, "可维护性": 8},
            "spring boot": {"性能": 8, "开发效率": 6, "生态": 10, "学习曲线": 5, "可维护性": 8},
            "express": {"性能": 7, "开发效率": 8, "生态": 9, "学习曲线": 8, "可维护性": 7},
            "golang": {"性能": 10, "开发效率": 7, "生态": 8, "学习曲线": 6, "可维护性": 9},
            "react": {"性能": 8, "开发效率": 8, "生态": 10, "学习曲线": 7, "可维护性": 8},
            "vue": {"性能": 8, "开发效率": 9, "生态": 8, "学习曲线": 9, "可维护性": 8},
        }

        evaluations = []
        for candidate in candidates:
            key = candidate.lower().strip()
            if key in tech_scores:
                scores = tech_scores[key]
                matched = {c: scores.get(c, 5) for c in criteria}
                total = sum(matched.values()) / len(matched) if matched else 0
                evaluations.append({
                    "name": candidate,
                    "scores": matched,
                    "avg_score": round(total, 1),
                })
            else:
                # Generic fallback
                evaluations.append({
                    "name": candidate,
                    "scores": {c: 5 for c in criteria},
                    "avg_score": 5.0,
                    "note": "No predefined score — requires manual assessment",
                })

        evaluations.sort(key=lambda x: x["avg_score"], reverse=True)
        recommendation = evaluations[0]["name"] if evaluations else ""

        return {
            "requirement": requirement,
            "evaluation": evaluations,
            "recommendation": recommendation,
        }

    def capacity_estimate(
        self,
        qps: int,
        avg_response_size_kb: int,
        data_growth_gb_per_month: int = 0,
    ) -> dict:
        """容量规划估算"""
        # Bandwidth: QPS × avg_response_size × 8 bits/byte
        bandwidth_mbps = (qps * avg_response_size_kb * 8) / 1000

        # Daily/monthly traffic
        requests_per_day = qps * 86400
        requests_per_month = requests_per_day * 30

        # Storage
        monthly_storage_gb = data_growth_gb_per_month

        # DB connections estimate (rule of thumb: QPS/10 + headroom)
        db_connections = max(10, qps // 10 + 5)

        # Memory estimate (rough: 100KB per concurrent request × peak concurrent)
        peak_concurrent = qps * 2  # 2-second avg latency assumption
        memory_mb = peak_concurrent * 0.1  # 100KB per request

        return {
            "bandwidth_mbps": round(bandwidth_mbps, 2),
            "requests_per_day": requests_per_day,
            "requests_per_month": requests_per_month,
            "monthly_storage_gb": monthly_storage_gb,
            "estimated_db_connections": db_connections,
            "peak_concurrent_requests": peak_concurrent,
            "estimated_memory_mb": round(memory_mb, 1),
        }
