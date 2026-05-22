"""
Phase 6.7: Bug Fix 工作流

Tester 复现 → Developer 修复 → Reviewer 审核 → Tester 验证的闭环
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio


class TestBugClassification:
    """Bug 自动分类测试"""

    def test_classify_test_failure(self):
        """测试失败应分类为 test_failure"""
        from src.bug.classifier import BugClassifier

        classifier = BugClassifier()
        result = classifier.classify(
            error_type="AssertionError",
            error_message="assert 2 + 2 == 5",
            traceback="tests/test_math.py:10: AssertionError",
        )
        assert result["category"] == "test_failure"

    def test_classify_runtime_error(self):
        """运行时错误应分类为 logic_error"""
        from src.bug.classifier import BugClassifier

        classifier = BugClassifier()
        result = classifier.classify(
            error_type="KeyError",
            error_message="'missing_key'",
            traceback="src/data/processor.py:25: KeyError",
        )
        assert result["category"] == "logic_error"

    def test_classify_import_error(self):
        """导入错误应分类为 environment_error"""
        from src.bug.classifier import BugClassifier

        classifier = BugClassifier()
        result = classifier.classify(
            error_type="ModuleNotFoundError",
            error_message="No module named 'pandas'",
            traceback="src/data/analysis.py:5: ModuleNotFoundError",
        )
        assert result["category"] == "environment_error"

    def test_classify_type_error(self):
        """类型错误应分类为 logic_error"""
        from src.bug.classifier import BugClassifier

        classifier = BugClassifier()
        result = classifier.classify(
            error_type="TypeError",
            error_message="unsupported operand type(s) for +: 'int' and 'str'",
            traceback="src/utils/calculator.py:15: TypeError",
        )
        assert result["category"] == "logic_error"

    def test_bug_severity_from_error_type(self):
        """不同错误类型应有不同严重性"""
        from src.bug.classifier import BugClassifier

        classifier = BugClassifier()

        # SyntaxError 是 HIGH（代码无法运行）
        r = classifier.classify(
            error_type="SyntaxError",
            error_message="invalid syntax",
            traceback="src/main.py:1",
        )
        assert r["severity"] in ("HIGH", "CRITICAL")

        # AssertionError 在测试中是 MEDIUM
        r = classifier.classify(
            error_type="AssertionError",
            error_message="assert False",
            traceback="tests/test_x.py:1",
        )
        assert r["severity"] in ("MEDIUM", "LOW")


class TestBugFixWorkflow:
    """Bug Fix 闭环工作流测试"""

    def test_bug_report_creation(self):
        """Bug 报告可以创建"""
        from src.bug.report import BugReport

        report = BugReport(
            title="测试失败: add 函数返回错误结果",
            category="test_failure",
            severity="MEDIUM",
            error_type="AssertionError",
            error_message="assert add(2, 3) == 6",
            file_path="tests/test_math.py",
            line_number=10,
        )
        assert report.title is not None
        assert report.category == "test_failure"
        assert report.status == "open"

    def test_bug_report_transition(self):
        """Bug 报告状态转换: open → in_progress → fixed → verified"""
        from src.bug.report import BugReport

        report = BugReport(title="test bug", category="logic_error", severity="HIGH")

        assert report.status == "open"
        report.mark_in_progress()
        assert report.status == "in_progress"
        report.mark_fixed()
        assert report.status == "fixed"
        report.mark_verified()
        assert report.status == "verified"

    def test_bug_report_reject(self):
        """Bug 可以被拒绝后重新打开"""
        from src.bug.report import BugReport

        report = BugReport(title="test bug", category="test_failure", severity="LOW")
        report.mark_in_progress()
        report.mark_fixed()
        report.mark_rejected("修复不完整")
        assert report.status == "rejected"
        report.reopen()
        assert report.status == "open"

    def test_bug_tracker_add_and_find(self):
        """BugTracker 可以添加和查找 Bug"""
        from src.bug.tracker import BugTracker
        from src.bug.report import BugReport

        tracker = BugTracker()
        bug = BugReport(title="test bug", category="logic_error", severity="HIGH")
        tracker.add(bug)

        assert tracker.count() == 1
        assert tracker.get(bug.id) is not None
        assert tracker.get("nonexistent") is None

    def test_bug_tracker_list_by_status(self):
        """BugTracker 可以按状态列出 Bug"""
        from src.bug.tracker import BugTracker
        from src.bug.report import BugReport

        tracker = BugTracker()
        bug1 = BugReport(title="open bug", category="test_failure", severity="MEDIUM")
        bug2 = BugReport(title="fixed bug", category="logic_error", severity="HIGH")
        bug2.mark_in_progress()
        bug2.mark_fixed()

        tracker.add(bug1)
        tracker.add(bug2)

        open_bugs = tracker.list_by_status("open")
        assert len(open_bugs) == 1
        assert open_bugs[0].title == "open bug"

        fixed_bugs = tracker.list_by_status("fixed")
        assert len(fixed_bugs) == 1

    def test_bug_tracker_list_by_severity(self):
        """BugTracker 可以按严重性列出 Bug"""
        from src.bug.tracker import BugTracker
        from src.bug.report import BugReport

        tracker = BugTracker()
        tracker.add(BugReport(title="critical bug", category="logic_error", severity="CRITICAL"))
        tracker.add(BugReport(title="low bug", category="test_failure", severity="LOW"))

        critical = tracker.list_by_severity("CRITICAL")
        assert len(critical) == 1
        assert critical[0].severity == "CRITICAL"

    def test_full_bug_fix_cycle(self):
        """完整 Bug Fix 周期: 创建 → 修复 → 审核 → 验证"""
        from src.bug.tracker import BugTracker
        from src.bug.report import BugReport
        from src.bug.classifier import BugClassifier

        tracker = BugTracker()
        classifier = BugClassifier()

        # 1. Tester 发现 bug
        classification = classifier.classify(
            error_type="AssertionError",
            error_message="assert add(2, 3) == 6",
            traceback="tests/test_math.py:10: AssertionError",
        )

        bug = BugReport(
            title="add(2, 3) 返回错误结果",
            category=classification["category"],
            severity=classification["severity"],
            error_type=classification["error_type"],
            error_message=classification["message"],
            file_path="tests/test_math.py",
            line_number=10,
        )
        tracker.add(bug)

        # 2. Developer 开始修复
        bug.mark_in_progress()
        bug.mark_fixed()

        # 3. Tester 验证
        bug.mark_verified()

        assert bug.status == "verified"
        assert tracker.count() == 1

    def test_bug_report_to_dict(self):
        """Bug 报告可以序列化为字典"""
        from src.bug.report import BugReport

        report = BugReport(
            title="test",
            category="test_failure",
            severity="MEDIUM",
            file_path="tests/test.py",
        )
        d = report.to_dict()
        assert isinstance(d, dict)
        assert d["title"] == "test"
        assert d["category"] == "test_failure"
        assert "id" in d

    def test_bug_report_from_dict(self):
        """Bug 报告可以从字典反序列化"""
        from src.bug.report import BugReport

        d = {
            "title": "test",
            "category": "logic_error",
            "severity": "HIGH",
            "status": "open",
        }
        report = BugReport.from_dict(d)
        assert report.title == "test"
        assert report.category == "logic_error"
