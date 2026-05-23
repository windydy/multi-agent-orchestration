"""
Phase 8: 第三方集成测试

测试 GitHub、Jira、Slack 集成类，使用 mock 避免实际 API 调用。
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.integrations.github import GitHubIntegration
from src.integrations.jira import JiraIntegration
from src.integrations.slack import SlackNotifier


# ─────────────────────────────────────────────
# GitHub Integration Tests
# ─────────────────────────────────────────────

class TestGitHubIntegration:
    """GitHubIntegration 单元测试"""

    @pytest.fixture
    def github(self):
        return GitHubIntegration(token="test-token", owner="test-org", repo="test-repo")

    def test_init(self):
        gh = GitHubIntegration(token="my-token", owner="my-org", repo="my-repo")
        assert gh.token == "my-token"
        assert gh.owner == "my-org"
        assert gh.repo == "my-repo"
        assert gh.base_url == "https://api.github.com"

    @patch("src.integrations.github.requests.post")
    def test_create_pr_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "number": 42,
            "title": "Add feature",
            "html_url": "https://github.com/test-org/test-repo/pull/42",
        }
        mock_post.return_value = mock_response

        gh = GitHubIntegration(token="token", owner="org", repo="repo")
        result = gh.create_pr(title="Add feature", body="Description", head="feature-branch", base="main")

        assert result["number"] == 42
        assert result["html_url"] == "https://github.com/test-org/test-repo/pull/42"

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer token"
        assert call_args.kwargs["json"]["title"] == "Add feature"
        assert call_args.kwargs["json"]["head"] == "feature-branch"
        assert call_args.kwargs["json"]["base"] == "main"

    @patch("src.integrations.github.requests.post")
    def test_create_pr_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.json.return_value = {"message": "Validation Failed"}
        mock_post.return_value = mock_response

        gh = GitHubIntegration(token="token", owner="org", repo="repo")
        result = gh.create_pr(title="Bad PR", body="No body", head="branch", base="main")

        assert result["success"] is False
        assert "error" in result

    @patch("src.integrations.github.requests.post")
    def test_create_issue_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "number": 100,
            "title": "Bug report",
            "html_url": "https://github.com/test-org/test-repo/issues/100",
        }
        mock_post.return_value = mock_response

        gh = GitHubIntegration(token="token", owner="org", repo="repo")
        result = gh.create_issue(
            title="Bug report",
            body="Something is broken",
            labels=["bug", "urgent"],
        )

        assert result["number"] == 100
        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["labels"] == ["bug", "urgent"]

    @patch("src.integrations.github.requests.post")
    def test_create_issue_without_labels(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"number": 101, "title": "Issue"}
        mock_post.return_value = mock_response

        gh = GitHubIntegration(token="token", owner="org", repo="repo")
        result = gh.create_issue(title="Issue", body="Body")

        assert result["number"] == 101
        call_args = mock_post.call_args
        assert "labels" not in call_args.kwargs["json"]

    @patch("src.integrations.github.requests.get")
    def test_list_issues_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"number": 1, "title": "Issue 1", "state": "open"},
            {"number": 2, "title": "Issue 2", "state": "open"},
        ]
        mock_get.return_value = mock_response

        gh = GitHubIntegration(token="token", owner="org", repo="repo")
        result = gh.list_issues(state="open")

        assert len(result) == 2
        assert result[0]["number"] == 1

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args.kwargs["params"]["state"] == "open"

    @patch("src.integrations.github.requests.get")
    def test_list_issues_empty(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        gh = GitHubIntegration(token="token", owner="org", repo="repo")
        result = gh.list_issues(state="closed")

        assert result == []

    @patch("src.integrations.github.requests.post")
    def test_create_comment_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": 12345,
            "body": "Fixed in #42",
            "html_url": "https://github.com/test-org/test-repo/issues/1#issuecomment-12345",
        }
        mock_post.return_value = mock_response

        gh = GitHubIntegration(token="token", owner="org", repo="repo")
        result = gh.create_comment(issue_number=1, body="Fixed in #42")

        assert result["id"] == 12345
        call_args = mock_post.call_args
        assert "/repos/org/repo/issues/1/comments" in call_args.args[0]
        assert call_args.kwargs["json"]["body"] == "Fixed in #42"

    @patch("src.integrations.github.requests.post")
    def test_create_pr_default_base(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"number": 1}
        mock_post.return_value = mock_response

        gh = GitHubIntegration(token="token", owner="org", repo="repo")
        gh.create_pr(title="PR", body="Body", head="branch")

        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["base"] == "main"

    @patch("src.integrations.github.requests.post")
    def test_create_pr_http_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        gh = GitHubIntegration(token="token", owner="org", repo="repo")
        result = gh.create_pr(title="PR", body="Body", head="branch")

        assert result["success"] is False
        assert "error" in result


# ─────────────────────────────────────────────
# Jira Integration Tests
# ─────────────────────────────────────────────

class TestJiraIntegration:
    """JiraIntegration 单元测试"""

    @pytest.fixture
    def jira(self):
        return JiraIntegration(server="https://jira.example.com", user="admin", api_token="secret-token")

    def test_init(self):
        j = JiraIntegration(server="https://jira.test.com", user="user", api_token="token")
        assert j.server == "https://jira.test.com"
        assert j.user == "user"
        assert j.api_token == "token"
        assert j.base_url == "https://jira.test.com/rest/api/3"

    @patch("src.integrations.jira.requests.post")
    def test_create_issue_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "10001",
            "key": "PROJ-123",
            "self": "https://jira.example.com/rest/api/3/issue/10001",
        }
        mock_post.return_value = mock_response

        j = JiraIntegration(server="https://jira.example.com", user="admin", api_token="token")
        result = j.create_issue(
            project="PROJ",
            summary="Implement feature",
            description="Detailed description",
            issue_type="Story",
        )

        assert result["key"] == "PROJ-123"
        assert result["id"] == "10001"

        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["fields"]["project"]["key"] == "PROJ"
        assert call_args.kwargs["json"]["fields"]["summary"] == "Implement feature"
        assert call_args.kwargs["json"]["fields"]["issuetype"]["name"] == "Story"

    @patch("src.integrations.jira.requests.post")
    def test_create_issue_default_type(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "10002", "key": "PROJ-124"}
        mock_post.return_value = mock_response

        j = JiraIntegration(server="https://jira.example.com", user="admin", api_token="token")
        j.create_issue(project="PROJ", summary="Task", description="Desc")

        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["fields"]["issuetype"]["name"] == "Task"

    @patch("src.integrations.jira.requests.post")
    def test_create_issue_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"errorMessages": ["Invalid project key"]}
        mock_post.return_value = mock_response

        j = JiraIntegration(server="https://jira.example.com", user="admin", api_token="token")
        result = j.create_issue(project="INVALID", summary="Test", description="Desc")

        assert result["success"] is False
        assert "error" in result

    @patch("src.integrations.jira.requests.get")
    def test_get_issue_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "10001",
            "key": "PROJ-123",
            "fields": {
                "summary": "Implement feature",
                "status": {"name": "In Progress"},
                "assignee": {"displayName": "John Doe"},
            },
        }
        mock_get.return_value = mock_response

        j = JiraIntegration(server="https://jira.example.com", user="admin", api_token="token")
        result = j.get_issue("PROJ-123")

        assert result["key"] == "PROJ-123"
        assert result["fields"]["summary"] == "Implement feature"

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "/rest/api/3/issue/PROJ-123" in call_args.args[0]

    @patch("src.integrations.jira.requests.get")
    def test_get_issue_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"errorMessages": ["Issue does not exist"]}
        mock_get.return_value = mock_response

        j = JiraIntegration(server="https://jira.example.com", user="admin", api_token="token")
        result = j.get_issue("PROJ-999")

        assert result["success"] is False

    @patch("src.integrations.jira.requests.post")
    def test_transition_issue_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response

        j = JiraIntegration(server="https://jira.example.com", user="admin", api_token="token")
        result = j.transition_issue("PROJ-123", transition_id="31")

        assert result["success"] is True

        call_args = mock_post.call_args
        assert "/rest/api/3/issue/PROJ-123/transitions" in call_args.args[0]
        assert call_args.kwargs["json"]["transition"]["id"] == "31"

    @patch("src.integrations.jira.requests.post")
    def test_add_comment_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "10100",
            "body": "This is a comment",
        }
        mock_post.return_value = mock_response

        j = JiraIntegration(server="https://jira.example.com", user="admin", api_token="token")
        result = j.add_comment("PROJ-123", body="This is a comment")

        assert result["id"] == "10100"
        assert result["body"] == "This is a comment"

        call_args = mock_post.call_args
        assert "/rest/api/3/issue/PROJ-123/comment" in call_args.args[0]
        assert call_args.kwargs["json"]["body"] == "This is a comment"

    @patch("src.integrations.jira.requests.post")
    def test_auth_header(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "1", "key": "PROJ-1"}
        mock_post.return_value = mock_response

        j = JiraIntegration(server="https://jira.example.com", user="admin", api_token="secret-token")
        j.create_issue(project="PROJ", summary="Test", description="Desc")

        call_args = mock_post.call_args
        assert "Authorization" in call_args.kwargs["headers"]
        # Basic auth: base64(user:token)
        assert call_args.kwargs["headers"]["Authorization"].startswith("Basic ")


# ─────────────────────────────────────────────
# Slack Notifier Tests
# ─────────────────────────────────────────────

class TestSlackNotifier:
    """SlackNotifier 单元测试"""

    @pytest.fixture
    def slack(self):
        return SlackNotifier(webhook_url="https://hooks.slack.com/services/T00/B00/XXX")

    def test_init(self):
        s = SlackNotifier(webhook_url="https://hooks.slack.com/services/T/B/X")
        assert s.webhook_url == "https://hooks.slack.com/services/T/B/X"

    @patch("src.integrations.slack.requests.post")
    def test_send_message_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        s = SlackNotifier(webhook_url="https://hooks.slack.com/services/T/B/X")
        result = s.send_message(text="Hello, world!")

        assert result["ok"] is True

        call_args = mock_post.call_args
        assert call_args.args[0] == "https://hooks.slack.com/services/T/B/X"
        assert call_args.kwargs["json"]["text"] == "Hello, world!"

    @patch("src.integrations.slack.requests.post")
    def test_send_message_with_blocks(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Bold text*"}},
        ]

        s = SlackNotifier(webhook_url="https://hooks.slack.com/services/T/B/X")
        result = s.send_message(text="Hello", blocks=blocks)

        assert result["ok"] is True
        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["blocks"] == blocks

    @patch("src.integrations.slack.requests.post")
    def test_send_message_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": False, "error": "invalid_payload"}
        mock_post.return_value = mock_response

        s = SlackNotifier(webhook_url="https://hooks.slack.com/services/T/B/X")
        result = s.send_message(text="Hello")

        assert result["ok"] is False
        assert result["error"] == "invalid_payload"

    @patch("src.integrations.slack.requests.post")
    def test_send_code_snippet_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        s = SlackNotifier(webhook_url="https://hooks.slack.com/services/T/B/X")
        result = s.send_code_snippet(text="print('hello')", language="python")

        assert result["ok"] is True

        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert "```python" in payload["text"]
        assert "print('hello')" in payload["text"]
        assert "```" in payload["text"]

    @patch("src.integrations.slack.requests.post")
    def test_send_code_snippet_default_language(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        s = SlackNotifier(webhook_url="https://hooks.slack.com/services/T/B/X")
        s.send_code_snippet(text="code here")

        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert "```python" in payload["text"]

    @patch("src.integrations.slack.requests.post")
    def test_send_code_snippet_custom_language(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        s = SlackNotifier(webhook_url="https://hooks.slack.com/services/T/B/X")
        s.send_code_snippet(text="SELECT * FROM users", language="sql")

        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert "```sql" in payload["text"]

    @patch("src.integrations.slack.requests.post")
    def test_send_message_http_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        s = SlackNotifier(webhook_url="https://hooks.slack.com/services/T/B/X")
        result = s.send_message(text="Hello")

        assert result["ok"] is False
        assert "error" in result

    @patch("src.integrations.slack.requests.post")
    def test_send_message_connection_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        s = SlackNotifier(webhook_url="https://hooks.slack.com/services/T/B/X")
        result = s.send_message(text="Hello")

        assert result["ok"] is False
        assert "error" in result
