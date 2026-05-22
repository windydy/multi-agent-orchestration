"""
Bug Classifier — automatic bug categorization based on error type, message, traceback.
"""

from __future__ import annotations

from typing import Optional


class BugClassifier:
    """Bug 自动分类器"""

    # Error type → category mapping
    CATEGORY_MAP: dict[str, str] = {
        "AssertionError": "test_failure",
        "Failed": "test_failure",
        "pytest.fail.Exception": "test_failure",
        "ModuleNotFoundError": "environment_error",
        "ImportError": "environment_error",
        "OSError": "environment_error",
        "FileNotFoundError": "environment_error",
        "PermissionError": "environment_error",
        "TimeoutError": "environment_error",
        "ConnectionError": "environment_error",
        "KeyError": "logic_error",
        "TypeError": "logic_error",
        "ValueError": "logic_error",
        "AttributeError": "logic_error",
        "IndexError": "logic_error",
        "ZeroDivisionError": "logic_error",
        "NameError": "logic_error",
        "SyntaxError": "code_error",
        "IndentationError": "code_error",
        "TabError": "code_error",
    }

    # Severity overrides based on error type
    SEVERITY_MAP: dict[str, str] = {
        "SyntaxError": "HIGH",
        "IndentationError": "HIGH",
        "ModuleNotFoundError": "HIGH",
        "TypeError": "MEDIUM",
        "KeyError": "MEDIUM",
        "AssertionError": "MEDIUM",
        "ValueError": "MEDIUM",
        "AttributeError": "MEDIUM",
        "NameError": "HIGH",
    }

    def classify(
        self,
        error_type: str,
        error_message: str,
        traceback: str = "",
    ) -> dict:
        """
        自动分类 Bug。

        Returns:
            dict with keys: category, severity, error_type, message
        """
        category = self.CATEGORY_MAP.get(error_type, "logic_error")

        # Determine severity
        severity = self.SEVERITY_MAP.get(error_type, "MEDIUM")

        # Boost severity for certain patterns
        lower_msg = (error_message + " " + traceback).lower()
        if any(kw in lower_msg for kw in ["production", "deploy", "database"]):
            severity = "CRITICAL" if severity != "CRITICAL" else severity
        elif any(kw in lower_msg for kw in ["security", "auth", "password", "token"]):
            severity = "HIGH" if severity in ("MEDIUM", "LOW") else severity

        return {
            "category": category,
            "severity": severity,
            "error_type": error_type,
            "message": error_message,
        }
