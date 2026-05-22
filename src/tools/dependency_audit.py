"""
Dependency Audit Tool — analyze requirements.txt / package.json for known
vulnerabilities, outdated packages, and generate secure dependency lists.
"""

from __future__ import annotations

import re
from typing import Optional

from ..core.tool import BaseTool, ToolConfig, ToolResult


# Simulated known-vulnerable packages (would normally come from OSV / Snyk / GitHub Advisory DB)
KNOWN_VULNS: dict[str, list[dict]] = {
    "flask": [
        {"cve": "CVE-2023-30861", "severity": "HIGH", "fixed_in": "2.3.2", "description": "Cookie session vulnerability"},
    ],
    "django": [
        {"cve": "CVE-2023-36053", "severity": "HIGH", "fixed_in": "3.2.20", "description": "ReDoS in django.utils.text.Truncator"},
        {"cve": "CVE-2023-24580", "severity": "MEDIUM", "fixed_in": "3.2.18", "description": "Potential denial-of-service in file upload"},
    ],
    "urllib3": [
        {"cve": "CVE-2023-43804", "severity": "HIGH", "fixed_in": "1.26.18", "description": "Cookie header leakage on cross-origin redirect"},
        {"cve": "CVE-2023-45803", "severity": "MEDIUM", "fixed_in": "1.26.18", "description": "Request body not stripped after redirect"},
    ],
    "requests": [
        {"cve": "CVE-2023-32681", "severity": "MEDIUM", "fixed_in": "2.31.0", "description": "Unintended leak of Proxy-Auth header"},
    ],
    "sqlalchemy": [
        {"cve": "CVE-2024-2616", "severity": "HIGH", "fixed_in": "2.0.30", "description": "SQL injection via crafted order_by parameter"},
    ],
}

# Known-safe minimum versions for popular packages
SAFE_VERSIONS: dict[str, str] = {
    "flask": "2.3.2",
    "django": "4.2.7",
    "requests": "2.31.0",
    "urllib3": "2.0.7",
    "sqlalchemy": "2.0.30",
    "numpy": "1.26.0",
    "pandas": "2.1.0",
    "pyyaml": "6.0.1",
    "cryptography": "41.0.5",
    "pillow": "10.1.0",
}


def _parse_requirements(text: str) -> list[dict]:
    """Parse requirements.txt content into structured data."""
    packages = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = re.match(r'^([a-zA-Z0-9_.-]+)\s*(?:[>=<!=]+\s*([^\s;,#]+))?', line)
        if m:
            packages.append({
                "name": m.group(1).lower(),
                "version": m.group(2) or None,
                "raw": line,
            })
    return packages


class DependencyAuditTool(BaseTool):
    """依赖审计工具 — 分析 requirements.txt / package.json 依赖风险"""

    def __init__(self):
        config = ToolConfig(
            name="dependency_audit_tool",
            description="Analyze package dependencies for known vulnerabilities and outdated versions",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["analyze", "generate"],
                    },
                    "content": {"type": "string", "description": "requirements.txt content"},
                    "packages": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["action"],
            },
        )
        super().__init__(config)

    async def run(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "analyze")
        if action == "analyze":
            content = kwargs.get("content", "")
            result = self.analyze_requirements(content)
            return ToolResult(success=True, output=result)
        if action == "generate":
            packages = kwargs.get("packages", [])
            content = self.generate_secure_requirements(packages)
            return ToolResult(success=True, output=content)
        return ToolResult(success=False, output=None, error=f"Unknown action: {action}")

    def analyze_requirements(self, content: str) -> dict:
        """分析 requirements.txt 中的依赖风险"""
        packages = _parse_requirements(content)
        findings: list[dict] = []
        has_vulns = False
        has_outdated = False

        for pkg in packages:
            name = pkg["name"]
            version = pkg["version"]

            # Check known vulnerabilities
            if name in KNOWN_VULNS:
                for vuln in KNOWN_VULNS[name]:
                    if version and self._is_version_affected(version, vuln["fixed_in"]):
                        has_vulns = True
                        findings.append({
                            "package": name,
                            "current_version": version,
                            "cve": vuln["cve"],
                            "severity": vuln["severity"],
                            "fixed_in": vuln["fixed_in"],
                            "description": vuln["description"],
                        })

            # Check outdated
            if name in SAFE_VERSIONS and (not version or self._is_version_less(version, SAFE_VERSIONS[name])):
                has_outdated = True
                if not any(f["package"] == name for f in findings):
                    findings.append({
                        "package": name,
                        "current_version": version or "unspecified",
                        "latest_safe": SAFE_VERSIONS[name],
                        "issue": "outdated",
                        "severity": "LOW",
                    })

        return {
            "packages": packages,
            "findings": findings,
            "has_known_vulnerabilities": has_vulns,
            "has_outdated": has_outdated,
            "total_packages": len(packages),
            "vulnerable_count": len(findings),
        }

    def generate_secure_requirements(
        self,
        base_packages: list[str],
    ) -> str:
        """生成使用安全版本的 requirements.txt"""
        lines = ["# Auto-generated secure requirements.txt", f"# Generated with {len(base_packages)} packages\n"]
        for pkg in sorted(base_packages):
            name = pkg.lower().strip()
            version = SAFE_VERSIONS.get(name, "")
            if version:
                lines.append(f"{name}>={version}")
            else:
                lines.append(name)
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _parse_version(v: str) -> tuple[int, ...]:
        """Parse version string to tuple of ints for comparison."""
        parts = re.split(r'[.\-]', v.strip().lstrip("v"))
        result = []
        for p in parts[:4]:
            try:
                result.append(int(p))
            except ValueError:
                result.append(0)
        return tuple(result)

    @classmethod
    def _is_version_less(cls, a: str, b: str) -> bool:
        return cls._parse_version(a) < cls._parse_version(b)

    @classmethod
    def _is_version_affected(cls, current: str, fixed_in: str) -> bool:
        """Check if current version is before the fix."""
        return cls._parse_version(current) < cls._parse_version(fixed_in)
