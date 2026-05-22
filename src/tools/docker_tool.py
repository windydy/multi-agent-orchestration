"""
Docker Tool — Docker command generation, Dockerfile validation, compose helpers.
"""

from __future__ import annotations

import re
from typing import Optional

from ..core.tool import BaseTool, ToolConfig, ToolResult


class DockerTool(BaseTool):
    """Docker 操作辅助工具"""

    def __init__(self):
        config = ToolConfig(
            name="docker_tool",
            description="Generate Docker commands, validate Dockerfiles, manage compose",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["build", "run", "validate", "compose"],
                    },
                    "context": {"type": "string"},
                    "tag": {"type": "string"},
                    "dockerfile": {"type": "string"},
                    "content": {"type": "string", "description": "Dockerfile content"},
                    "file": {"type": "string", "description": "Compose file path"},
                    "detach": {"type": "boolean"},
                    "build_flag": {"type": "boolean"},
                },
                "required": ["action"],
            },
        )
        super().__init__(config)

    async def run(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "build")
        if action == "build":
            cmd = self.build_command(
                context=kwargs.get("context", "."),
                tag=kwargs.get("tag", ""),
                dockerfile=kwargs.get("dockerfile", "Dockerfile"),
            )
            return ToolResult(success=True, output=cmd)
        if action == "validate":
            content = kwargs.get("content", "")
            result = self.validate_dockerfile(content)
            return ToolResult(success=result.get("valid", False), output=result)
        if action == "compose":
            cmd = self.compose_up(
                file=kwargs.get("file", "docker-compose.yml"),
                detach=kwargs.get("detach", True),
                build=kwargs.get("build_flag", False),
            )
            return ToolResult(success=True, output=cmd)
        return ToolResult(success=False, output=None, error=f"Unknown action: {action}")

    # ---- sync helpers (used by tests directly) ----

    def build_command(
        self,
        context: str = ".",
        tag: str = "",
        dockerfile: str = "Dockerfile",
        build_args: dict | None = None,
        extra_flags: list[str] | None = None,
    ) -> str:
        """生成 docker build 命令"""
        parts = ["docker build"]
        if dockerfile != "Dockerfile":
            parts.append(f"-f {dockerfile}")
        if tag:
            parts.append(f"-t {tag}")
        if build_args:
            for k, v in build_args.items():
                parts.append(f"--build-arg {k}={v}")
        if extra_flags:
            parts.extend(extra_flags)
        parts.append(context)
        return " ".join(parts)

    def validate_dockerfile(self, content: str) -> dict:
        """验证 Dockerfile 内容"""
        errors: list[str] = []
        warnings: list[str] = []
        base_image = ""

        lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]

        if not lines:
            return {"valid": False, "errors": ["Empty Dockerfile"]}

        first = lines[0]
        if not first.upper().startswith("FROM "):
            errors.append("Dockerfile must start with FROM instruction")
        else:
            base_image = first.split(None, 1)[1].split(" AS ")[0].strip()

        has_cmd_or_entrypoint = False
        for line in lines:
            upper = line.upper()
            if upper.startswith("CMD ") or upper.startswith("ENTRYPOINT "):
                has_cmd_or_entrypoint = True

            # Warnings
            if upper.startswith("RUN ") and "sudo" in line.lower():
                warnings.append("Avoid sudo in RUN instructions")
            if upper.startswith("COPY ") and "--chown" not in line and "root" not in line.lower():
                pass  # could warn about non-root user
            if "latest" in base_image and ":latest" in base_image:
                warnings.append("Using :latest tag is not recommended for reproducibility")

        if not has_cmd_or_entrypoint:
            warnings.append("No CMD or ENTRYPOINT found — container won't run anything by default")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "base_image": base_image,
            "instruction_count": len(lines),
        }

    def compose_up(
        self,
        file: str = "docker-compose.yml",
        detach: bool = True,
        build: bool = False,
        services: list[str] | None = None,
    ) -> str:
        """生成 docker compose up 命令"""
        parts = ["docker compose"]
        if file != "docker-compose.yml":
            parts.append(f"-f {file}")
        parts.append("up")
        if detach:
            parts.append("-d")
        if build:
            parts.append("--build")
        if services:
            parts.extend(services)
        return " ".join(parts)

    def generate_dockerfile(
        self,
        base_image: str = "python:3.11-slim",
        workdir: str = "/app",
        copy_files: list[tuple[str, str]] | None = None,
        install_cmd: str = "",
        run_cmd: str = "",
        multi_stage: bool = False,
    ) -> str:
        """生成基础 Dockerfile"""
        lines: list[str] = []

        if multi_stage:
            lines.append(f"FROM {base_image} AS builder")
        else:
            lines.append(f"FROM {base_image}")

        lines.append(f"WORKDIR {workdir}")

        if copy_files:
            for src, dst in copy_files:
                lines.append(f"COPY {src} {dst}")

        if install_cmd:
            lines.append(f"RUN {install_cmd}")

        lines.append('COPY . .')

        if multi_stage:
            lines.append(f"\nFROM {base_image}")
            lines.append(f"WORKDIR {workdir}")
            lines.append("COPY --from=builder /app /app")

        if run_cmd:
            lines.append(f'CMD ["{run_cmd}"]')
        else:
            lines.append('CMD ["bash"]')

        return "\n".join(lines) + "\n"
