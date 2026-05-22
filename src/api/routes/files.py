"""Files API route - with directory traversal protection (P0-3)."""

from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api", tags=["api"])

# Module-level project root (injected at startup)
_project_root: str = ""


def set_project_root(root: str) -> None:
    """Set the allowed project root for file access."""
    global _project_root
    _project_root = str(Path(root).resolve())


def _get_project_root() -> str:
    if not _project_root:
        raise HTTPException(500, "Project root not configured")
    return _project_root


def _safe_resolve_path(relative_path: str) -> Path:
    """P0-3: Resolve and validate that a file path is within the project root.

    Uses pathlib.Path.resolve() to canonicalize the path, then verifies
    it stays within the allowed project directory.

    Args:
        relative_path: Relative path from the project root (e.g., 'src/api/routes.py')

    Returns:
        Absolute Path object if valid.

    Raises:
        HTTPException 400: If path is empty or contains invalid characters.
        HTTPException 403: If resolved path escapes the project root.
        HTTPException 404: If the file does not exist.
    """
    project_root = _get_project_root()

    # Reject obviously malicious patterns
    if not relative_path or relative_path.strip() == "":
        raise HTTPException(400, "Path cannot be empty")

    # Build the full path and resolve it to eliminate '..' and symlinks
    base = Path(project_root)
    full_path = (base / relative_path).resolve()

    # Verify the resolved path is within the project root
    # Use str comparison with trailing separator to prevent prefix attacks
    # e.g., /project-root-evil should not match /project-root
    root_str = str(base) + "/"
    if not str(full_path).startswith(root_str) and str(full_path) != str(base):
        raise HTTPException(
            403,
            f"Access denied: path escapes project root. "
            f"Resolved: {full_path}, Root: {base}"
        )

    # Check file exists
    if not full_path.is_file():
        raise HTTPException(404, f"File not found: {relative_path}")

    return full_path


class FileInfo(BaseModel):
    """Information about a file in the project."""
    path: str
    name: str
    size: int
    is_text: bool


class FileContent(BaseModel):
    """File content response."""
    path: str
    content: str
    size: int
    encoding: str = "utf-8"


class FileListResponse(BaseModel):
    """List of files changed during an execution."""
    thread_id: str
    files: list[FileInfo]


class ExecutionFileQuery(BaseModel):
    """Query model for file content request."""
    path: str


@router.get("/executions/{thread_id}/files", response_model=FileListResponse)
async def list_execution_files(thread_id: str):
    """List files that were created/modified during an execution.

    P0-3: Does NOT use path parameters for file paths.
    Returns a list of files that the execution touched.
    The actual file content is fetched via GET with query parameter.
    """
    # TODO: In a real implementation, this would query a file tracker
    # that recorded which files were modified during the execution.
    # For now, return an empty list as a placeholder.
    return FileListResponse(thread_id=thread_id, files=[])


@router.get("/executions/{thread_id}/file", response_model=FileContent)
async def get_execution_file(thread_id: str, path: str = Query(..., description="Relative file path within project root")):
    """Get the content of a file created/modified during an execution.

    P0-3: Uses query parameter (?path=...) instead of path parameter to prevent
    directory traversal attacks. Validates the resolved path is within the
    project root using pathlib.Path.resolve().

    Usage: GET /api/executions/{thread_id}/file?path=src/api/routes.py
    """
    full_path = _safe_resolve_path(path)

    # Read file content
    try:
        content = full_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, f"File is not a text file: {path}")
    except PermissionError:
        raise HTTPException(403, f"Permission denied: {path}")

    return FileContent(
        path=path,
        content=content,
        size=full_path.stat().st_size,
    )


@router.get("/files/{path_param:path}")
async def get_file_by_path(path_param: str, raw: bool = Query(False)):
    """Get a file from the project directory.

    P0-3: Despite using a path parameter for convenience, validates the resolved
    path is within the project root. The 'raw' parameter can be used to get
    raw file content (e.g., for binary files).

    DEPRECATED: Prefer GET /api/executions/{id}/file?path=... for execution files.
    """
    full_path = _safe_resolve_path(path_param)

    try:
        content = full_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        if raw:
            # Return base64-encoded content for binary files
            import base64
            data = full_path.read_bytes()
            return {"path": path_param, "content": base64.b64encode(data).decode(), "encoding": "base64"}
        raise HTTPException(400, f"File is not a text file: {path_param}")
    except PermissionError:
        raise HTTPException(403, f"Permission denied: {path_param}")

    return FileContent(
        path=path_param,
        content=content,
        size=full_path.stat().st_size,
    )
