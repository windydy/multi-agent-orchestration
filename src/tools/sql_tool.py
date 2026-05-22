"""
SQL Tool — SQL query generation, DDL creation, basic validation.
"""

from __future__ import annotations

import re
from ..core.tool import BaseTool, ToolConfig, ToolResult


class SQLTool(BaseTool):
    """SQL 辅助工具 — 查询生成、DDL 生成、基本验证"""

    def __init__(self):
        config = ToolConfig(
            name="sql_tool",
            description="Generate SQL queries, DDL statements, and validate basic SQL syntax",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["select", "create_table", "validate"],
                    },
                    "table": {"type": "string"},
                    "columns": {"type": "array", "items": {"type": "string"}},
                    "where": {"type": "object"},
                    "order_by": {"type": "string"},
                    "limit": {"type": "integer"},
                    "ddl_columns": {
                        "type": "array",
                        "items": {"type": "array", "minItems": 2, "maxItems": 2},
                    },
                    "query": {"type": "string"},
                },
                "required": ["action"],
            },
        )
        super().__init__(config)

    async def run(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "select")
        if action == "select":
            query = self.generate_select(
                table=kwargs.get("table", ""),
                columns=kwargs.get("columns", ["*"]),
                where=kwargs.get("where"),
                order_by=kwargs.get("order_by"),
                limit=kwargs.get("limit"),
            )
            return ToolResult(success=True, output=query)
        if action == "create_table":
            ddl = self.create_table(
                table=kwargs.get("table", ""),
                columns=kwargs.get("ddl_columns", []),
            )
            return ToolResult(success=True, output=ddl)
        if action == "validate":
            result = self.validate_query(kwargs.get("query", ""))
            return ToolResult(success=result["valid"], output=result)
        return ToolResult(success=False, output=None, error=f"Unknown action: {action}")

    def generate_select(
        self,
        table: str,
        columns: list[str] | None = None,
        where: dict | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        group_by: list[str] | None = None,
    ) -> str:
        """生成 SELECT 查询"""
        cols = ", ".join(columns) if columns else "*"
        parts = [f"SELECT {cols}", f"FROM {table}"]

        if where:
            conditions = []
            for k, v in where.items():
                if isinstance(v, str):
                    conditions.append(f"{k} = '{v}'")
                elif v is None:
                    conditions.append(f"{k} IS NULL")
                else:
                    conditions.append(f"{k} = {v}")
            parts.append("WHERE " + " AND ".join(conditions))

        if group_by:
            parts.append("GROUP BY " + ", ".join(group_by))

        if order_by:
            parts.append(f"ORDER BY {order_by}")

        if limit:
            parts.append(f"LIMIT {limit}")

        return "\n".join(parts)

    def create_table(
        self,
        table: str,
        columns: list[tuple[str, str]],
        if_not_exists: bool = True,
    ) -> str:
        """生成 CREATE TABLE 语句"""
        parts = [f"CREATE TABLE"]
        if if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(table)
        parts.append("(")

        col_defs = []
        for name, dtype in columns:
            col_defs.append(f"    {name} {dtype}")
        parts.append(",\n".join(col_defs))
        parts.append(");")

        return "\n".join(parts)

    def validate_query(self, query: str) -> dict:
        """验证基本 SQL 语法"""
        errors: list[str] = []
        query_stripped = query.strip()

        if not query_stripped:
            return {"valid": False, "errors": ["Empty query"]}

        # Check for common SQL keywords
        first_word = query_stripped.split()[0].upper()
        valid_keywords = {"SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "WITH"}
        if first_word not in valid_keywords:
            errors.append(f"Query must start with a SQL keyword, got: {first_word}")

        # Check for common typos (use word-boundary matching)
        typos = {
            r'\bSELCT\b': 'SELECT',
            r'\bSLECT\b': 'SELECT',
            r'\bFRM\b': 'FROM',
            r'\bFORM\b': 'FROM',
            r'\bWHER\b': 'WHERE',
            r'\bROU\b': 'GROUP',
        }
        upper = query_stripped.upper()
        for typo, correct in typos.items():
            if re.search(typo, upper):
                errors.append(f"Possible typo: '{typo.replace(chr(92), '').replace('b', '')}' should be '{correct}'")

        # Check balanced parentheses
        open_count = query_stripped.count("(")
        close_count = query_stripped.count(")")
        if open_count != close_count:
            errors.append(f"Unbalanced parentheses: {open_count} open, {close_count} close")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "query_type": first_word,
        }
