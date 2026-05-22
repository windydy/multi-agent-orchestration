"""
Bug Report — bug report data model with state transitions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class BugReport:
    """Bug 报告数据模型"""

    title: str
    category: str
    severity: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str = "open"
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    description: str = ""
    fix_description: str = ""
    reject_reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def mark_in_progress(self) -> None:
        if self.status != "open":
            raise ValueError(f"Cannot transition from {self.status} to in_progress")
        self.status = "in_progress"
        self.updated_at = datetime.now().isoformat()

    def mark_fixed(self) -> None:
        if self.status != "in_progress":
            raise ValueError(f"Cannot transition from {self.status} to fixed")
        self.status = "fixed"
        self.updated_at = datetime.now().isoformat()

    def mark_verified(self) -> None:
        if self.status != "fixed":
            raise ValueError(f"Cannot transition from {self.status} to verified")
        self.status = "verified"
        self.updated_at = datetime.now().isoformat()

    def mark_rejected(self, reason: str = "") -> None:
        if self.status != "fixed":
            raise ValueError(f"Cannot transition from {self.status} to rejected")
        self.status = "rejected"
        self.reject_reason = reason
        self.updated_at = datetime.now().isoformat()

    def reopen(self) -> None:
        self.status = "open"
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "severity": self.severity,
            "status": self.status,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "description": self.description,
            "fix_description": self.fix_description,
            "reject_reason": self.reject_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BugReport":
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            title=data["title"],
            category=data["category"],
            severity=data["severity"],
            status=data.get("status", "open"),
            error_type=data.get("error_type"),
            error_message=data.get("error_message"),
            file_path=data.get("file_path"),
            line_number=data.get("line_number"),
            description=data.get("description", ""),
            fix_description=data.get("fix_description", ""),
            reject_reason=data.get("reject_reason", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )
