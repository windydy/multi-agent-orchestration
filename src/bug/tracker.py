"""
Bug Tracker — manages a collection of BugReports with querying capabilities.
"""

from __future__ import annotations

from typing import Optional
from .report import BugReport


class BugTracker:
    """Bug 跟踪器"""

    def __init__(self):
        self._bugs: dict[str, BugReport] = {}

    def add(self, bug: BugReport) -> None:
        """添加 Bug 报告"""
        self._bugs[bug.id] = bug

    def get(self, bug_id: str) -> Optional[BugReport]:
        """按 ID 查找 Bug"""
        return self._bugs.get(bug_id)

    def remove(self, bug_id: str) -> bool:
        """移除 Bug"""
        if bug_id in self._bugs:
            del self._bugs[bug_id]
            return True
        return False

    def count(self) -> int:
        """返回 Bug 总数"""
        return len(self._bugs)

    def list_by_status(self, status: str) -> list[BugReport]:
        """按状态列出 Bug"""
        return [b for b in self._bugs.values() if b.status == status]

    def list_by_severity(self, severity: str) -> list[BugReport]:
        """按严重性列出 Bug"""
        return [b for b in self._bugs.values() if b.severity == severity]

    def list_by_category(self, category: str) -> list[BugReport]:
        """按类别列出 Bug"""
        return [b for b in self._bugs.values() if b.category == category]

    def list_all(self) -> list[BugReport]:
        """列出所有 Bug"""
        return list(self._bugs.values())

    def summary(self) -> dict:
        """生成 Bug 统计摘要"""
        by_status: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_category: dict[str, int] = {}

        for bug in self._bugs.values():
            by_status[bug.status] = by_status.get(bug.status, 0) + 1
            by_severity[bug.severity] = by_severity.get(bug.severity, 0) + 1
            by_category[bug.category] = by_category.get(bug.category, 0) + 1

        return {
            "total": len(self._bugs),
            "by_status": by_status,
            "by_severity": by_severity,
            "by_category": by_category,
        }
