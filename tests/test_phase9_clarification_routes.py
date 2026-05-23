"""
Phase 9: Clarification API routes 单元测试

测试 POST /api/clarification/analyze 和 GET /api/clarification/dimensions 接口。
"""

import pytest
from fastapi.testclient import TestClient

from src.api.routes.clarification import (
    router as clarification_router,
    set_clarifier,
)
from src.clarifier.agent import ClarifierAgent


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def clarifier():
    """创建 ClarifierAgent 实例（使用模拟 LLM）"""
    return ClarifierAgent(model="mock", task_type="development")


@pytest.fixture
def client(clarifier):
    """创建测试客户端"""
    from fastapi import FastAPI

    set_clarifier(clarifier)

    app = FastAPI()
    app.include_router(clarification_router)

    return TestClient(app)


# ============================================================
# POST /api/clarification/analyze 测试
# ============================================================

class TestAnalyzeEndpoint:
    """POST /api/clarification/analyze 测试"""

    def test_analyze_vague_task(self, client):
        """模糊任务应该返回低分和澄清问题"""
        response = client.post(
            "/api/clarification/analyze",
            json={"task": "帮我做一个电商网站"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "score" in data
        assert 0 <= data["score"] <= 100
        assert data["recommendation"] in ("skip", "conservative", "interactive")
        assert "dimensions" in data
        assert "raw_input" in data
        assert data["raw_input"] == "帮我做一个电商网站"

    def test_analyze_clear_task(self, client):
        """清晰任务应该返回高分"""
        clear_task = (
            "用 React + FastAPI 做一个用户管理系统，"
            "支持 CRUD 操作，面向企业内部员工，"
            "3 天交付，预算 5000 元，"
            "需要支持 100 并发，对接现有 LDAP 系统，"
            "验收标准是所有功能可用且无严重 bug，"
            "背景是公司需要替换老旧系统"
        )

        response = client.post(
            "/api/clarification/analyze",
            json={"task": clear_task},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["score"] >= 80.0
        assert data["recommendation"] == "skip"
        assert len(data["questions"]) == 0
        assert len(data["assumptions"]) == 0

    def test_analyze_with_task_type(self, client):
        """支持指定任务类型"""
        response = client.post(
            "/api/clarification/analyze",
            json={
                "task": "帮我做一个网站",
                "task_type": "design",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task_type"] == "design"

    def test_analyze_returns_dimensions(self, client):
        """应该返回 9 个维度的评分"""
        response = client.post(
            "/api/clarification/analyze",
            json={"task": "测试任务"},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["dimensions"]) == 9
        for dim_name, dim in data["dimensions"].items():
            assert "dimension" in dim
            assert "score" in dim
            assert "reason" in dim
            assert 1 <= dim["score"] <= 5

    def test_analyze_empty_task_fails(self, client):
        """空任务应该返回 422"""
        response = client.post(
            "/api/clarification/analyze",
            json={"task": ""},
        )

        assert response.status_code == 422

    def test_analyze_missing_task_fails(self, client):
        """缺少任务字段应该返回 422"""
        response = client.post(
            "/api/clarification/analyze",
            json={},
        )

        assert response.status_code == 422


# ============================================================
# GET /api/clarification/dimensions 测试
# ============================================================

class TestDimensionsEndpoint:
    """GET /api/clarification/dimensions 测试"""

    def test_get_dimensions(self, client):
        """应该返回 9 个维度定义"""
        response = client.get("/api/clarification/dimensions")

        assert response.status_code == 200
        data = response.json()

        assert "dimensions" in data
        assert len(data["dimensions"]) == 9

    def test_dimension_structure(self, client):
        """每个维度应该有正确的结构"""
        response = client.get("/api/clarification/dimensions")

        assert response.status_code == 200
        data = response.json()

        for dim in data["dimensions"]:
            assert "name" in dim
            assert "label" in dim
            assert "description" in dim
            assert "weight" in dim
            assert "example_question" in dim
            assert dim["weight"] > 0

    def test_dimension_names(self, client):
        """维度名称应该正确"""
        response = client.get("/api/clarification/dimensions")

        assert response.status_code == 200
        data = response.json()

        expected_names = {
            "functional_scope", "target_users", "tech_constraints",
            "timeline", "budget", "quality_reqs", "integration",
            "success_criteria", "context",
        }
        actual_names = {dim["name"] for dim in data["dimensions"]}
        assert actual_names == expected_names


# ============================================================
# 注入测试
# ============================================================

class TestClarifierInjection:
    """ClarifierAgent 注入测试"""

    def test_set_clarifier(self, clarifier):
        """set_clarifier 应该正确设置"""
        from src.api.routes import clarification

        clarification.set_clarifier(clarifier)
        assert clarification._clarifier is clarifier

    def test_get_clarifier_not_initialized(self):
        """未初始化时应该返回 None"""
        from src.api.routes import clarification

        # 保存原始值
        original = clarification._clarifier
        clarification._clarifier = None

        try:
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                clarification._get_clarifier()
            assert exc_info.value.status_code == 500
        finally:
            clarification._clarifier = original
