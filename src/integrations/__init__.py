"""
第三方集成模块

提供与外部服务的集成能力：
- GitHub: PR、Issue、Comment 管理
- Jira: Issue 创建、查询、状态流转
- Slack: 消息通知、代码片段分享
"""

from src.integrations.github import GitHubIntegration
from src.integrations.jira import JiraIntegration
from src.integrations.slack import SlackNotifier

__all__ = [
    "GitHubIntegration",
    "JiraIntegration",
    "SlackNotifier",
]
