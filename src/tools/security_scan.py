"""
Security Scan Tool — static analysis for secrets, OWASP patterns, report generation.
"""

from __future__ import annotations

import re
from ..core.tool import BaseTool, ToolConfig, ToolResult


# ---- Secret detection patterns ----
SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("aws_access_key", re.compile(r'AKIA[0-9A-Z]{16}')),
    ("api_key_generic", re.compile(r'(?:api[_-]?key|apikey)\s*[=:]\s*["\'][\w\-]{10,}["\']', re.I)),
    ("password_assignment", re.compile(r'(?:password|passwd|pwd)\s*[=:]\s*["\'][^\s"\']{6,}["\']', re.I)),
    ("database_url", re.compile(r'(?:postgres|mysql|mongodb|redis)://\w+:\w+@[^\s"\']+', re.I)),
    ("private_key", re.compile(r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----')),
    ("bearer_token", re.compile(r'(?:bearer|token)\s*[=:]\s*["\'][\w\-\.]{20,}["\']', re.I)),
    ("sk_openai", re.compile(r'sk-[a-zA-Z0-9]{20,}')),
]

# ---- OWASP vulnerability patterns ----
OWASP_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("sql_injection", "SQL Injection via f-string/format",
     re.compile(r'(?:execute|cursor\.execute|query)\s*\(\s*f["\'].*(?:SELECT|INSERT|UPDATE|DELETE|DROP)', re.I)),
    ("sql_injection_concat", "SQL Injection via string concatenation",
     re.compile(r'(?:execute|query)\s*\(.*(?:\+|%).*?(?:SELECT|INSERT|UPDATE|DELETE)', re.I)),
    ("xss_reflected", "Reflected XSS via unescaped output",
     re.compile(r'(?:return|render|write)\s*.*f["\'].*<\w+.*\{.*\}.*</\w+>', re.I)),
    ("xss_html_injection", "HTML injection via unescaped user input",
     re.compile(r'(?:innerHTML|outerHTML|document\.write)\s*=', re.I)),
    ("path_traversal", "Path traversal risk",
     re.compile(r'open\s*\(\s*(?:f["\']|.*\+)', re.I)),
    ("eval_exec", "Dangerous eval/exec usage",
     re.compile(r'\b(?:eval|exec|compile)\s*\(', re.I)),
    ("deserialization", "Unsafe deserialization",
     re.compile(r'(?:pickle|yaml)\.(?:loads|load)\s*\(', re.I)),
    ("command_injection", "OS command injection",
     re.compile(r'(?:os\.system|subprocess\.(?:call|run|Popen))\s*\(.*(?:\+|f["\']|%s)', re.I)),
    ("hardcoded_secret", "Possible hardcoded credential",
     re.compile(r'(?:secret|token|key|password)\s*[=:]\s*["\'][^\s"\']{8,}["\']', re.I)),
]

SEVERITY_MAP = {
    "sql_injection": "CRITICAL",
    "sql_injection_concat": "CRITICAL",
    "command_injection": "CRITICAL",
    "eval_exec": "HIGH",
    "xss_reflected": "HIGH",
    "xss_html_injection": "HIGH",
    "deserialization": "HIGH",
    "path_traversal": "MEDIUM",
    "hardcoded_secret": "HIGH",
}


class SecurityScanTool(BaseTool):
    """安全扫描工具 — 检测硬编码凭证、OWASP 漏洞模式"""

    def __init__(self):
        config = ToolConfig(
            name="security_scan_tool",
            description="Static security scanning for secrets and OWASP vulnerability patterns",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["secrets", "owasp", "report"],
                    },
                    "content": {"type": "string", "description": "Source code to scan"},
                    "findings": {"type": "array", "description": "Findings for report generation"},
                },
                "required": ["action"],
            },
        )
        super().__init__(config)

    async def run(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "secrets")
        if action == "secrets":
            content = kwargs.get("content", "")
            result = self.scan_for_secrets(content)
            return ToolResult(success=True, output=result)
        if action == "owasp":
            content = kwargs.get("content", "")
            result = self.scan_owasp(content)
            return ToolResult(success=True, output=result)
        if action == "report":
            findings = kwargs.get("findings", [])
            report = self.generate_report(findings)
            return ToolResult(success=True, output=report)
        return ToolResult(success=False, output=None, error=f"Unknown action: {action}")

    def scan_for_secrets(self, code: str) -> dict:
        """扫描代码中的硬编码凭证"""
        findings: list[dict] = []
        for line_num, line in enumerate(code.splitlines(), 1):
            for name, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append({
                        "type": name,
                        "line": line_num,
                        "severity": "HIGH",
                        "snippet": line.strip()[:120],
                    })

        max_sev = "CRITICAL" if any(f["severity"] == "CRITICAL" for f in findings) else (
            "HIGH" if findings else "NONE"
        )
        return {
            "findings": findings,
            "severity": max_sev,
            "count": len(findings),
        }

    def scan_owasp(self, code: str) -> dict:
        """扫描 OWASP Top 10 漏洞模式"""
        findings: list[dict] = []
        for line_num, line in enumerate(code.splitlines(), 1):
            for vuln_type, description, pattern in OWASP_PATTERNS:
                if pattern.search(line):
                    findings.append({
                        "type": vuln_type,
                        "description": description,
                        "line": line_num,
                        "severity": SEVERITY_MAP.get(vuln_type, "MEDIUM"),
                        "snippet": line.strip()[:120],
                    })

        return {
            "findings": findings,
            "count": len(findings),
            "summary": self._owasp_summary(findings),
        }

    def generate_report(self, findings: list[dict]) -> str:
        """生成结构化安全报告"""
        if not findings:
            return "✅ No security issues found."

        lines = ["## 🔒 Security Audit Report\n"]
        by_sev: dict[str, list[dict]] = {}
        for f in findings:
            by_sev.setdefault(f.get("severity", "UNKNOWN"), []).append(f)

        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"):
            items = by_sev.get(sev, [])
            if not items:
                continue
            lines.append(f"\n### {sev} ({len(items)} issues)\n")
            for item in items:
                file_info = f"`{item.get('file', 'unknown')}`" if "file" in item else ""
                line_info = f" line {item['line']}" if "line" in item else ""
                lines.append(f"- [{item['type']}] {item.get('description', '')} {file_info}{line_info}")
                if "snippet" in item:
                    lines.append(f"  ```\n  {item['snippet']}\n  ```")

        total = len(findings)
        critical = len(by_sev.get("CRITICAL", []))
        high = len(by_sev.get("HIGH", []))
        lines.append(f"\n---\nTotal: {total} issues ({critical} CRITICAL, {high} HIGH)")
        if critical > 0:
            lines.append("\n⚠️ **BLOCKED**: CRITICAL vulnerabilities must be resolved before merge.")
        return "\n".join(lines)

    def _owasp_summary(self, findings: list[dict]) -> str:
        types = set(f["type"] for f in findings)
        return f"Found {len(findings)} potential issues across {len(types)} vulnerability categories: {', '.join(sorted(types))}"
