"""
Jira API 集成

提供 Jira Issue 创建、查询、状态流转、评论等功能。
使用 Jira REST API v3。
"""

import base64
from typing import Any

import requests


class JiraIntegration:
    """Jira REST API v3 集成类"""

    def __init__(self, server: str, user: str, api_token: str) -> None:
        """
        初始化 Jira 集成。

        Args:
            server: Jira 服务器地址 (如 https://jira.example.com)
            user: Jira 用户名或邮箱
            api_token: Jira API Token
        """
        self.server = server.rstrip("/")
        self.user = user
        self.api_token = api_token
        self.base_url = f"{self.server}/rest/api/3"

        # Basic Auth: base64(user:api_token)
        credentials = base64.b64encode(f"{user}:{api_token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _api_url(self, path: str) -> str:
        """构建完整的 API URL"""
        return f"{self.base_url}{path}"

    def _handle_response(self, response: requests.Response) -> dict[str, Any]:
        """
        处理 HTTP 响应。

        Args:
            response: requests 响应对象

        Returns:
            解析后的响应数据或错误信息
        """
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            data = {}

        if response.status_code in (200, 201, 204):
            return data

        error_messages = data.get("errorMessages", [])
        error = data.get("error", data.get("message", f"HTTP {response.status_code}"))
        if error_messages:
            error = "; ".join(error_messages)

        return {
            "success": False,
            "error": error,
            "status_code": response.status_code,
        }

    def create_issue(
        self,
        project: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
    ) -> dict[str, Any]:
        """
        创建 Jira Issue。

        Args:
            project: 项目 Key
            summary: Issue 摘要
            description: Issue 描述
            issue_type: Issue 类型 (Task, Story, Bug 等)

        Returns:
            Issue 数据或错误信息
        """
        url = self._api_url("/issue")
        payload = {
            "fields": {
                "project": {"key": project},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
            },
        }

        try:
            response = requests.post(url, headers=self._headers, json=payload)
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def get_issue(self, issue_key: str) -> dict[str, Any]:
        """
        获取 Issue 详情。

        Args:
            issue_key: Issue Key (如 PROJ-123)

        Returns:
            Issue 数据或错误信息
        """
        url = self._api_url(f"/issue/{issue_key}")

        try:
            response = requests.get(url, headers=self._headers)
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def transition_issue(self, issue_key: str, transition_id: str) -> dict[str, Any]:
        """
        流转 Issue 状态。

        Args:
            issue_key: Issue Key (如 PROJ-123)
            transition_id: 转换 ID

        Returns:
            操作结果或错误信息
        """
        url = self._api_url(f"/issue/{issue_key}/transitions")
        payload = {
            "transition": {"id": transition_id},
        }

        try:
            response = requests.post(url, headers=self._headers, json=payload)
            result = self._handle_response(response)
            # 204 No Content is success
            if response.status_code == 204:
                return {"success": True}
            return result
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def add_comment(self, issue_key: str, body: str) -> dict[str, Any]:
        """
        在 Issue 上添加评论。

        Args:
            issue_key: Issue Key (如 PROJ-123)
            body: 评论内容

        Returns:
            评论数据或错误信息
        """
        url = self._api_url(f"/issue/{issue_key}/comment")
        payload = {"body": body}

        try:
            response = requests.post(url, headers=self._headers, json=payload)
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
