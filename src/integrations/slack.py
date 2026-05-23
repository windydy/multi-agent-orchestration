"""
Slack Webhook 通知器

通过 Incoming Webhook 向 Slack 频道发送消息和代码片段。
"""

from typing import Any

import requests


class SlackNotifier:
    """Slack Incoming Webhook 通知器"""

    def __init__(self, webhook_url: str) -> None:
        """
        初始化 Slack 通知器。

        Args:
            webhook_url: Slack Incoming Webhook URL
        """
        self.webhook_url = webhook_url
        self._headers = {
            "Content-Type": "application/json",
        }

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
            data = {"ok": False, "error": "Invalid JSON response"}

        return data

    def send_message(
        self,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        发送消息到 Slack 频道。

        Args:
            text: 消息文本
            blocks: Slack Block Kit 布局块 (可选)

        Returns:
            Slack API 响应
        """
        payload: dict[str, Any] = {"text": text}
        if blocks:
            payload["blocks"] = blocks

        try:
            response = requests.post(
                self.webhook_url,
                headers=self._headers,
                json=payload,
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {"ok": False, "error": str(e)}

    def send_code_snippet(
        self,
        text: str,
        language: str = "python",
    ) -> dict[str, Any]:
        """
        发送代码片段到 Slack 频道。

        代码会被格式化为 Markdown 代码块。

        Args:
            text: 代码内容
            language: 代码语言标识 (用于语法高亮)

        Returns:
            Slack API 响应
        """
        formatted_code = f"```{language}\n{text}\n```"
        return self.send_message(text=formatted_code)
