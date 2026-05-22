"""
Phase 6: DevOps Agent

CI/CD、容器化、基础设施管理
"""

from typing import Optional
from ..core.agent import AgentConfig, AgentRole
from ..claude.wrapper import ClaudeAgentWrapper, ClaudeSDKConfig, ClaudeToolType
from ..claude.hooks import create_hooks
from ..plan.graph import ExecutorCapability


# DevOps Agent 系统提示词
DEVOPS_SYSTEM_PROMPT = """
你是资深 DevOps 工程师和 SRE 专家，拥有 10 年以上的 CI/CD、容器化和基础设施管理经验。

## 核心职责

1. **CI/CD 配置与触发**
   - 编写和优化 GitHub Actions / GitLab CI / Jenkins Pipeline 配置
   - 分析构建失败原因，提供修复方案
   - 触发 CI/CD 流水线并监控执行状态

2. **Docker 构建与部署**
   - 编写和优化 Dockerfile（多阶段构建、安全最佳实践）
   - 编写 docker-compose.yml 用于本地开发和测试环境
   - 分析容器构建失败，优化镜像大小

3. **Kubernetes 资源管理**
   - 编写 K8s 资源配置（Deployment、Service、Ingress、ConfigMap 等）
   - 分析 Pod 失败原因（OOMKilled、CrashLoopBackOff 等）
   - 提供资源调优建议（requests/limits、HPA）

4. **Terraform 基础设施即代码**
   - 编写 Terraform 配置管理云资源
   - 分析 Terraform plan 输出，识别风险变更
   - 提供模块化 IaC 最佳实践

## 安全约束

⚠️ **重要安全规则**：
- 不直接操作生产环境，仅提供配置和建议
- 执行 Docker/K8s 命令前，确认命令影响范围
- 不在配置文件中硬编码敏感信息（使用 secrets/环境变量）
- Terraform 操作只执行 plan，不执行 apply（除非明确授权）
- 所有部署相关操作需经过人工确认

## 输出格式

对于 CI/CD 配置任务：
```yaml
# 完整的 CI/CD 配置文件
...
```

对于部署问题诊断：
- **问题描述**: 简明描述
- **根因分析**: 详细分析
- **修复方案**: 具体步骤
- **验证方法**: 如何确认修复成功

使用 bash 工具执行只读诊断命令（docker ps, kubectl get, terraform plan）。
使用 ci_trigger 工具触发 CI/CD 流水线。
使用 docker_build 工具执行安全的 Docker 操作。
"""


class DevOpsAgent(ClaudeAgentWrapper):
    """DevOps Agent: CI/CD、容器化、基础设施管理"""

    @property
    def capabilities(self) -> list[ExecutorCapability]:
        return self.get_capabilities()

    @property
    def executor_id(self) -> str:
        return self.config.name

    @property
    def name(self) -> str:
        return self.config.name

    def match_score(self, capability: ExecutorCapability) -> float:
        """计算此 Agent 与指定能力的匹配分数"""
        if capability in self.get_capabilities():
            return 1.0
        return 0.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_iterations: int = 20,
        timeout: int = 900,
        hooks: list = None,
    ):
        config = AgentConfig(
            name="devops_engineer",
            role=AgentRole.SPECIALIST,
            description="DevOps工程师 - CI/CD、容器化、基础设施管理",
            model="qwen3.6-plus",
            tools=["read_file", "write_file", "search", "bash"],
            max_iterations=max_iterations,
            timeout=timeout,
            temperature=0.2,
            system_prompt=DEVOPS_SYSTEM_PROMPT,
        )
        
        claude_config = ClaudeSDKConfig(
            api_key=api_key,
            model="qwen3.6-plus",
            max_tokens=8192,
            temperature=0.2,
            tools=[
                ClaudeToolType.READ_FILE,
                ClaudeToolType.WRITE_FILE,
                ClaudeToolType.SEARCH,
                ClaudeToolType.BASH,
            ],
            system_prompt=DEVOPS_SYSTEM_PROMPT,
        )
        
        hooks = hooks or create_hooks(safety=True, logging=True, cost_control=True)
        
        super().__init__(config, claude_config, hooks)

    def get_capabilities(self) -> list[ExecutorCapability]:
        return [
            ExecutorCapability.DEVOPS_CI_CD,
            ExecutorCapability.DEVOPS_CONTAINER,
            ExecutorCapability.DEVOPS_INFRA,
        ]
