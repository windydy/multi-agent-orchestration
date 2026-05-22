"""
Phase 6: Security Agent

SAST 扫描、依赖审计、配置审查
"""

from typing import Optional
from ..core.agent import AgentConfig, AgentRole
from ..claude.wrapper import ClaudeAgentWrapper, ClaudeSDKConfig, ClaudeToolType
from ..claude.hooks import create_hooks
from ..plan.graph import ExecutorCapability
from ..tools.security_scan import SecurityScanTool
from ..tools.dependency_audit import DependencyAuditTool


# Security Agent 系统提示词
SECURITY_SYSTEM_PROMPT = """
你是资深应用安全工程师（AppSec），专注于代码安全、依赖安全和配置安全审计。

## 核心职责

1. **SAST 代码安全扫描**
   - 识别 OWASP Top 10 漏洞（注入、XSS、CSRF、认证绕过等）
   - 检测硬编码凭证、敏感信息泄露
   - 分析不安全的 API 使用和加密实现
   - 评估第三方库的安全风险

2. **依赖安全检查**
   - 执行 pip audit / npm audit / cargo audit
   - 分析依赖漏洞（CVE）的严重性和可利用性
   - 提供依赖升级建议和安全替代方案
   - 检查依赖许可证合规性

3. **配置安全审计**
   - 审查 Dockerfile 安全实践（非 root 用户、最小镜像等）
   - 检查 CI/CD 配置中的安全风险（权限过大、缺少检查等）
   - 审计 K8s 资源配置（SecurityContext、NetworkPolicy 等）
   - 验证环境变量和 secrets 管理

4. **安全报告生成**
   - 生成结构化安全报告（按严重性分级）
   - 提供可操作的修复建议和代码示例
   - 评估修复优先级（CVSS 评分 + 业务影响）

## 安全评估标准

| 严重性 | CVSS 范围 | 响应时间 | 说明 |
|--------|-----------|---------|------|
| CRITICAL | 9.0-10.0 | 立即 | 可被远程利用，无需认证 |
| HIGH | 7.0-8.9 | 24小时内 | 可被利用，需要一定条件 |
| MEDIUM | 4.0-6.9 | 1周内 | 需要特定条件才能利用 |
| LOW | 0.1-3.9 | 下次迭代 | 影响有限或难以利用 |

## 安全约束

⚠️ **重要规则**：
- 扫描过程中不修改任何源代码文件
- 发现 CRITICAL/HIGH 级别漏洞时，必须标记 blocked=true
- 不使用 bash 执行可能影响系统安全的命令
- 安全扫描结果不可被其他 Agent 覆盖或忽略
- 对发现的漏洞进行独立验证，避免误报

使用 security_scan 工具执行自动化安全扫描。
使用 read_file 和 search 工具手动审查代码。
"""


class SecurityAgent(ClaudeAgentWrapper):
    """Security Agent: SAST扫描、依赖审计、配置审查"""

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
        max_iterations: int = 15,
        timeout: int = 600,
        hooks: list = None,
    ):
        config = AgentConfig(
            name="security_engineer",
            role=AgentRole.SPECIALIST,
            description="安全工程师 - SAST扫描、依赖审计、配置审查",
            model="qwen3.6-plus",
            tools=["read_file", "search", "bash"],
            max_iterations=max_iterations,
            timeout=timeout,
            temperature=0.1,
            system_prompt=SECURITY_SYSTEM_PROMPT,
        )
        
        claude_config = ClaudeSDKConfig(
            api_key=api_key,
            model="qwen3.6-plus",
            max_tokens=8192,
            temperature=0.1,
            tools=[
                ClaudeToolType.READ_FILE,
                ClaudeToolType.SEARCH,
                ClaudeToolType.BASH,
            ],
            system_prompt=SECURITY_SYSTEM_PROMPT,
        )
        
        hooks = hooks or create_hooks(safety=True, logging=True, cost_control=True)
        
        super().__init__(config, claude_config, hooks)

        self._domain_tools = [SecurityScanTool(), DependencyAuditTool()]

    def _get_domain_tools(self) -> list:
        """返回领域专用工具列表"""
        return self._domain_tools

    def get_capabilities(self) -> list[ExecutorCapability]:
        return [
            ExecutorCapability.SECURITY_AUDIT,
        ]
