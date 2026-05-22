"""
Data Analysis Tool — CSV parsing, descriptive stats, data quality checks.
"""

from __future__ import annotations

import csv
import io
import statistics
from ..core.tool import BaseTool, ToolConfig, ToolResult


def _parse_csv(text: str) -> tuple[list[str], list[list[str]]]:
    """Parse CSV text into (headers, rows)."""
    reader = csv.reader(io.StringIO(text.strip()))
    rows = list(reader)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _numeric_stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": round(statistics.stdev(values), 4) if len(values) > 1 else 0,
        "min": min(values),
        "max": max(values),
    }


class DataAnalysisTool(BaseTool):
    """数据分析工具 — CSV 解析、描述统计、数据质量检测"""

    def __init__(self):
        config = ToolConfig(
            name="data_analysis_tool",
            description="Parse CSV data, compute descriptive statistics, detect data quality issues",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["describe", "detect_issues"],
                    },
                    "content": {"type": "string", "description": "CSV data content"},
                },
                "required": ["action", "content"],
            },
        )
        super().__init__(config)

    async def run(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "describe")
        content = kwargs.get("content", "")
        if action == "describe":
            result = self.describe_csv(content)
            return ToolResult(success=True, output=result)
        if action == "detect_issues":
            result = self.detect_issues(content)
            return ToolResult(success=True, output=result)
        return ToolResult(success=False, output=None, error=f"Unknown action: {action}")

    def describe_csv(self, csv_text: str) -> dict:
        """生成 CSV 数据的描述统计"""
        headers, rows = _parse_csv(csv_text)
        row_count = len(rows)
        col_info: dict[str, dict] = {}

        for col_idx, col_name in enumerate(headers):
            raw_values = [row[col_idx] if col_idx < len(row) else "" for row in rows]
            non_empty = [v for v in raw_values if v.strip()]

            # Try numeric
            numeric = []
            for v in non_empty:
                try:
                    numeric.append(float(v))
                except ValueError:
                    pass

            if len(numeric) > len(non_empty) * 0.5 and numeric:
                col_info[col_name] = {
                    "type": "numeric",
                    "non_null": len(non_empty),
                    "null_count": row_count - len(non_empty),
                    **_numeric_stats(numeric),
                }
            else:
                unique = set(non_empty)
                col_info[col_name] = {
                    "type": "categorical",
                    "non_null": len(non_empty),
                    "null_count": row_count - len(non_empty),
                    "unique_count": len(unique),
                }

        return {
            "row_count": row_count,
            "column_count": len(headers),
            "columns": col_info,
        }

    def detect_issues(self, csv_text: str) -> dict:
        """检测数据质量问题"""
        headers, rows = _parse_csv(csv_text)
        issues: list[dict] = []
        missing_count = 0
        duplicate_count = 0

        # Missing values
        for row_idx, row in enumerate(rows):
            for col_idx, col_name in enumerate(headers):
                val = row[col_idx] if col_idx < len(row) else ""
                if not val.strip():
                    missing_count += 1
                    issues.append({
                        "type": "missing_value",
                        "row": row_idx + 2,  # 1-indexed + header
                        "column": col_name,
                    })

        # Duplicate rows
        seen: set[tuple] = set()
        for row_idx, row in enumerate(rows):
            key = tuple(row)
            if key in seen:
                duplicate_count += 1
                issues.append({
                    "type": "duplicate_row",
                    "row": row_idx + 2,
                })
            seen.add(key)

        return {
            "issues": issues,
            "missing_values": missing_count,
            "duplicate_rows": duplicate_count,
            "total_issues": len(issues),
        }
