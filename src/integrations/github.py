"""
GitHub API 集成

提供 Pull Request、Issue、Comment 等 GitHub 操作能力。
"""

from typing import Any

import requests


class GitHubIntegration:
    """GitHub REST API 集成类"""

    def __init__(self, token: str, owner: str, repo: str) -> None:
        """
        初始化 GitHub 集成。

        Args:
            token: GitHub Personal Access Token
            owner: 仓库所有者（组织或个人）
            repo: 仓库名称
        """
        self.token = token
        self.owner = owner
        self.repo = repo
        self.base_url = "https://api.github.com"
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
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

        return {
            "success": False,
            "error": data.get("message", f"HTTP {response.status_code}"),
            "status_code": response.status_code,
        }

    def create_pr(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict[str, Any]:
        """
        创建 Pull Request。

        Args:
            title: PR 标题
            body: PR 描述
            head: 源分支名
            base: 目标分支名，默认为 main

        Returns:
            PR 数据或错误信息
        """
        url = self._api_url(f"/repos/{self.owner}/{self.repo}/pulls")
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        }

        try:
            response = requests.post(url, headers=self._headers, json=payload)
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        创建 Issue。

        Args:
            title: Issue 标题
            body: Issue 描述
            labels: 标签列表

        Returns:
            Issue 数据或错误信息
        """
        url = self._api_url(f"/repos/{self.owner}/{self.repo}/issues")
        payload: dict[str, Any] = {
            "title": title,
            "body": body,
        }
        if labels:
            payload["labels"] = labels

        try:
            response = requests.post(url, headers=self._headers, json=payload)
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def list_issues(self, state: str = "open") -> list[dict[str, Any]]:
        """
        列出 Issue。

        Args:
            state: Issue 状态 (open, closed, all)

        Returns:
            Issue 列表
        """
        url = self._api_url(f"/repos/{self.owner}/{self.repo}/issues")
        params = {"state": state}

        try:
            response = requests.get(url, headers=self._headers, params=params)
            result = self._handle_response(response)
            if isinstance(result, list):
                return result
            return []
        except requests.exceptions.RequestException:
            return []

    def create_comment(self, issue_number: int, body: str) -> dict[str, Any]:
        """
        在 Issue 或 PR 上创建评论。

        Args:
            issue_number: Issue 或 PR 编号
            body: 评论内容

        Returns:
            评论数据或错误信息
        """
        url = self._api_url(f"/repos/{self.owner}/{self.repo}/issues/{issue_number}/comments")
        payload = {"body": body}

        try:
            response = requests.post(url, headers=self._headers, json=payload)
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
