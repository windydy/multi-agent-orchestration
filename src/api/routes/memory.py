"""Memory API routes for querying AgentMemory.

Provides endpoints for:
- POST /api/memory/search - Search memories by keyword
- GET  /api/memory/stats  - Get memory statistics
"""

import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/memory", tags=["memory"])

logger = logging.getLogger(__name__)

# Module-level AgentMemory instance (lazy init)
_memory_instance = None


def _get_memory():
    global _memory_instance
    if _memory_instance is None:
        from src.knowledge.memory import AgentMemory
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "checkpoints", "agent_memory.db"
        )
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _memory_instance = AgentMemory(db_path=db_path)
    return _memory_instance


def set_memory_instance(memory) -> None:
    """Inject a custom AgentMemory instance (for testing)."""
    global _memory_instance
    _memory_instance = memory


# ── Request/Response models ──

class MemorySearchRequest(BaseModel):
    query: str = Field(default="", description="Search keyword (empty returns all)")
    project_id: str | None = Field(default=None, description="Filter by project")
    category: str | None = Field(default=None, description="Filter by category")
    limit: int = Field(default=10, ge=1, le=100, description="Max results")


class MemoryEntryResponse(BaseModel):
    key: str
    value: str
    category: str
    project_id: str
    tags: list[str] = []
    created_at: str | None = None
    updated_at: str | None = None


class MemorySearchResponse(BaseModel):
    results: list[MemoryEntryResponse]
    total: int


class MemoryStatsResponse(BaseModel):
    total: int
    by_category: dict[str, int]


# ── Routes ──

@router.post("/search", response_model=MemorySearchResponse)
async def search_memory(req: MemorySearchRequest):
    """Search memories by keyword.

    Accepts a search query and returns matching memory entries.
    If query is empty, returns recent entries ordered by access count.
    """
    try:
        memory = _get_memory()

        if req.query:
            # Keyword search across all projects (or filtered)
            # AgentMemory.search requires project_id, so we handle both cases
            if req.project_id:
                entries = memory.search(
                    project_id=req.project_id,
                    category=req.category,
                    query=req.query,
                    limit=req.limit,
                )
            else:
                # Search across all projects: use wildcard pattern
                # We'll collect from all projects if no project_id specified
                import sqlite3

                from src.knowledge.memory import MemoryEntry
                conn = sqlite3.connect(str(memory.db_path))
                sql = "SELECT * FROM memory WHERE (key LIKE ? OR value LIKE ?)"
                params = [f"%{req.query}%", f"%{req.query}%"]
                if req.category:
                    sql += " AND category = ?"
                    params.append(req.category)
                sql += " ORDER BY access_count DESC LIMIT ?"
                params.append(req.limit)
                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()
                conn.close()

                from datetime import datetime
                entries = []
                for r in rows:
                    entries.append(MemoryEntry(
                        key=r[0],
                        value=__import__("json").loads(r[1]),
                        category=r[2],
                        project_id=r[3],
                        tags=__import__("json").loads(r[4] or "[]"),
                        timestamps={
                            "created_at": datetime.fromisoformat(r[5]) if r[5] else None,
                            "updated_at": datetime.fromisoformat(r[6]) if r[6] else None,
                        },
                    ))
        else:
            # Empty query: return recent entries
            import sqlite3
            from datetime import datetime

            from src.knowledge.memory import MemoryEntry
            conn = sqlite3.connect(str(memory.db_path))
            sql = "SELECT * FROM memory"
            params: list = []
            if req.project_id:
                sql += " WHERE project_id = ?"
                params.append(req.project_id)
            if req.category:
                sql += " AND category = ?" if req.project_id else " WHERE category = ?"
                params.append(req.category)
            sql += " ORDER BY access_count DESC LIMIT ?"
            params.append(req.limit)
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            conn.close()

            entries = []
            for r in rows:
                entries.append(MemoryEntry(
                    key=r[0],
                    value=__import__("json").loads(r[1]),
                    category=r[2],
                    project_id=r[3],
                    tags=__import__("json").loads(r[4] or "[]"),
                    timestamps={
                        "created_at": datetime.fromisoformat(r[5]) if r[5] else None,
                        "updated_at": datetime.fromisoformat(r[6]) if r[6] else None,
                    },
                ))

        results = [
            MemoryEntryResponse(
                key=e.key,
                value=str(e.value),
                category=e.category,
                project_id=e.project_id,
                tags=e.tags,
                created_at=e.timestamps.get("created_at").isoformat() if e.timestamps.get("created_at") else None,
                updated_at=e.timestamps.get("updated_at").isoformat() if e.timestamps.get("updated_at") else None,
            )
            for e in entries
        ]

        return MemorySearchResponse(results=results, total=len(results))

    except Exception as e:
        logger.error("[Memory] Search failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Memory search failed: {str(e)}")


@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_stats(project_id: str | None = None):
    """Get memory statistics.

    Returns total count and breakdown by category.
    """
    try:
        memory = _get_memory()
        stats = memory.get_stats(project_id=project_id)
        return MemoryStatsResponse(
            total=stats["total"],
            by_category=stats["by_category"],
        )
    except Exception as e:
        logger.error("[Memory] Stats failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Memory stats failed: {str(e)}")
