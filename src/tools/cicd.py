"""
CI/CD Tool — CI/CD pipeline parsing, validation, generation.
"""

from __future__ import annotations

import yaml
from typing import Optional

from ..core.tool import BaseTool, ToolConfig, ToolResult


class CICDTool(BaseTool):
    """CI/CD 配置解析、验证、生成工具"""

    def __init__(self):
        config = ToolConfig(
            name="cicd_tool",
            description="Parse, validate and generate CI/CD pipeline configurations",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["parse", "validate", "generate"],
                    },
                    "content": {"type": "string", "description": "Pipeline YAML content"},
                    "platform": {
                        "type": "string",
                        "enum": ["github_actions", "gitlab_ci", "jenkins"],
                    },
                    "language": {"type": "string"},
                    "stages": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["action"],
            },
        )
        super().__init__(config)

    async def run(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "parse")
        if action == "parse":
            content = kwargs.get("content", "")
            parsed = self.parse_workflow(content)
            return ToolResult(success=True, output=parsed)
        if action == "validate":
            content = kwargs.get("content", "")
            platform = kwargs.get("platform", "github_actions")
            result = self.validate_config(content, platform)
            return ToolResult(success=result.get("valid", False), output=result)
        if action == "generate":
            platform = kwargs.get("platform", "github_actions")
            language = kwargs.get("language", "python")
            stages = kwargs.get("stages", ["build", "test"])
            config = self.generate_pipeline(platform, language, stages)
            return ToolResult(success=True, output=config)
        return ToolResult(
            success=False, output=None, error=f"Unknown action: {action}"
        )

    # ---- sync helpers (used by tests directly) ----

    def parse_workflow(self, content: str) -> dict:
        """解析 CI/CD YAML workflow"""
        try:
            doc = yaml.safe_load(content)
            if not isinstance(doc, dict):
                return {"error": "invalid YAML"}
            return {
                "name": doc.get("name", ""),
                "on": doc.get("on", doc.get(True, {})),
                "jobs": list(doc.get("jobs", {}).keys()) if isinstance(doc.get("jobs"), dict) else [],
                "raw": doc,
            }
        except yaml.YAMLError as e:
            return {"error": str(e)}

    def validate_config(self, content: str, platform: str = "github_actions") -> dict:
        """验证 CI/CD 配置"""
        try:
            doc = yaml.safe_load(content)
            if not isinstance(doc, dict):
                return {"valid": False, "errors": ["Not a valid YAML mapping"]}

            errors: list[str] = []

            if platform == "github_actions":
                if "name" not in doc:
                    errors.append("Missing required field: name")
                if "jobs" not in doc or not isinstance(doc.get("jobs"), dict):
                    errors.append("Missing required field: jobs")
                else:
                    for jname, job in doc["jobs"].items():
                        if not isinstance(job, dict):
                            errors.append(f"Job '{jname}' must be a mapping")
                            continue
                        if "runs-on" not in job and "runs_on" not in job:
                            errors.append(f"Job '{jname}' missing 'runs-on'")
                        if "steps" not in job:
                            errors.append(f"Job '{jname}' missing 'steps'")

            return {"valid": len(errors) == 0, "errors": errors}
        except yaml.YAMLError as e:
            return {"valid": False, "errors": [str(e)]}

    def generate_pipeline(
        self,
        platform: str = "github_actions",
        language: str = "python",
        stages: list[str] | None = None,
    ) -> str:
        """生成 CI/CD pipeline 配置"""
        stages = stages or ["build", "test"]
        if platform == "github_actions":
            return self._generate_github_actions(language, stages)
        if platform == "gitlab_ci":
            return self._generate_gitlab_ci(language, stages)
        return f"# Unsupported platform: {platform}"

    def _generate_github_actions(self, language: str, stages: list[str]) -> str:
        lang_setup = {
            "python": {
                "setup": [
                    {"name": "Set up Python", "uses": "actions/setup-python@v5", "with": {"python-version": "3.11"}},
                ],
                "install": "pip install -r requirements.txt",
            },
            "node": {
                "setup": [
                    {"name": "Set up Node", "uses": "actions/setup-node@v4", "with": {"node-version": "20"}},
                ],
                "install": "npm ci",
            },
        }
        info = lang_setup.get(language, {"setup": [], "install": "echo install"})

        stage_steps = {
            "lint": [{"run": "echo 'run lint'"}],
            "test": [{"run": "echo 'run tests'"}],
            "build": [{"run": "echo 'build project'"}],
        }

        jobs = {}
        for stage in stages:
            steps = list(info["setup"])
            if stage != stages[0]:
                steps.append({"run": info["install"]})
            steps.extend(stage_steps.get(stage, [{"run": f"echo '{stage} stage'"}]))
            jobs[stage] = {
                "runs-on": "ubuntu-latest",
                "steps": steps,
            }

        workflow = {"name": "CI", "on": ["push", "pull_request"], "jobs": jobs}
        return yaml.dump(workflow, default_flow_style=False, sort_keys=False)

    def _generate_gitlab_ci(self, language: str, stages: list[str]) -> str:
        lines = [f"stages:"]
        for s in stages:
            lines.append(f"  - {s}")
        lines.append("")
        for s in stages:
            lines.append(f"{s}:")
            lines.append(f"  stage: {s}")
            lines.append(f"  script:")
            lines.append(f"    - echo 'run {s}'")
            lines.append("")
        return "\n".join(lines)
