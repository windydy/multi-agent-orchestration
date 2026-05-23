"""
Phase 9: ClarifierAgent 单元测试

测试维度评分、总分计算、判定函数、数据模型和 Agent 核心逻辑。
"""

import asyncio
import json

import pytest

from src.clarifier.dimensions import (
    CLARIFICATION_DIMENSIONS,
    DEFAULT_WEIGHTS,
    TASK_TYPE_WEIGHTS,
    THRESHOLD_CLARIFY,
    THRESHOLD_PASS,
    ClarificationDimension,
    DimensionScore,
    calculate_total_score,
    get_low_score_dimensions,
    get_recommendation,
    get_weights_for_task_type,
)
from src.clarifier.result import Assumption, ClarificationQuestion, ClarifierResult
from src.clarifier.agent import ClarifierAgent, create_clarifier


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def clarifier():
    """创建 ClarifierAgent 实例（使用模拟 LLM）"""
    return ClarifierAgent(model="mock", task_type="development")


@pytest.fixture
def sample_dimension_scores():
    """示例维度评分（中等清晰度）"""
    return {
        "functional_scope": DimensionScore(dimension="functional_scope", score=3, reason="部分明确"),
        "target_users": DimensionScore(dimension="target_users", score=2, reason="未说明"),
        "tech_constraints": DimensionScore(dimension="tech_constraints", score=4, reason="技术栈明确"),
        "timeline": DimensionScore(dimension="timeline", score=2, reason="未说明"),
        "budget": DimensionScore(dimension="budget", score=1, reason="完全未提及"),
        "quality_reqs": DimensionScore(dimension="quality_reqs", score=2, reason="未说明"),
        "integration": DimensionScore(dimension="integration", score=3, reason="部分明确"),
        "success_criteria": DimensionScore(dimension="success_criteria", score=2, reason="未说明"),
        "context": DimensionScore(dimension="context", score=3, reason="部分明确"),
    }


@pytest.fixture
def high_score_dimensions():
    """高分维度评分（清晰输入）"""
    return {
        "functional_scope": DimensionScore(dimension="functional_scope", score=5, reason="非常明确"),
        "target_users": DimensionScore(dimension="target_users", score=5, reason="非常明确"),
        "tech_constraints": DimensionScore(dimension="tech_constraints", score=5, reason="非常明确"),
        "timeline": DimensionScore(dimension="timeline", score=5, reason="非常明确"),
        "budget": DimensionScore(dimension="budget", score=4, reason="基本明确"),
        "quality_reqs": DimensionScore(dimension="quality_reqs", score=4, reason="基本明确"),
        "integration": DimensionScore(dimension="integration", score=5, reason="非常明确"),
        "success_criteria": DimensionScore(dimension="success_criteria", score=5, reason="非常明确"),
        "context": DimensionScore(dimension="context", score=4, reason="基本明确"),
    }


@pytest.fixture
def low_score_dimensions():
    """低分维度评分（模糊输入）"""
    return {
        "functional_scope": DimensionScore(dimension="functional_scope", score=1, reason="完全未提及"),
        "target_users": DimensionScore(dimension="target_users", score=1, reason="完全未提及"),
        "tech_constraints": DimensionScore(dimension="tech_constraints", score=1, reason="完全未提及"),
        "timeline": DimensionScore(dimension="timeline", score=1, reason="完全未提及"),
        "budget": DimensionScore(dimension="budget", score=1, reason="完全未提及"),
        "quality_reqs": DimensionScore(dimension="quality_reqs", score=1, reason="完全未提及"),
        "integration": DimensionScore(dimension="integration", score=1, reason="完全未提及"),
        "success_criteria": DimensionScore(dimension="success_criteria", score=1, reason="完全未提及"),
        "context": DimensionScore(dimension="context", score=1, reason="完全未提及"),
    }


# ============================================================
# 维度定义测试
# ============================================================

class TestDimensionDefinitions:
    """维度定义测试"""

    def test_dimensions_count(self):
        """应该有 9 个维度"""
        assert len(CLARIFICATION_DIMENSIONS) == 9

    def test_dimension_names(self):
        """维度名称应该正确"""
        expected_names = {
            "functional_scope", "target_users", "tech_constraints",
            "timeline", "budget", "quality_reqs", "integration",
            "success_criteria", "context",
        }
        assert set(CLARIFICATION_DIMENSIONS.keys()) == expected_names

    def test_dimension_has_required_fields(self):
        """每个维度应该有必要的字段"""
        for name, dim in CLARIFICATION_DIMENSIONS.items():
            assert isinstance(dim, ClarificationDimension)
            assert dim.name == name
            assert dim.label != ""
            assert dim.description != ""
            assert dim.weight > 0
            assert dim.example_question != ""

    def test_default_weights_match_dimensions(self):
        """默认权重应该覆盖所有维度"""
        assert set(DEFAULT_WEIGHTS.keys()) == set(CLARIFICATION_DIMENSIONS.keys())

    def test_task_type_weights_exist(self):
        """应该有预定义的任务类型权重"""
        assert "development" in TASK_TYPE_WEIGHTS
        assert "design" in TASK_TYPE_WEIGHTS
        assert "analysis" in TASK_TYPE_WEIGHTS


# ============================================================
# 总分计算测试
# ============================================================

class TestScoreCalculation:
    """总分计算测试"""

    def test_perfect_score(self):
        """全 5 分应该是 100"""
        dimensions = {
            name: DimensionScore(dimension=name, score=5)
            for name in CLARIFICATION_DIMENSIONS
        }
        score = calculate_total_score(dimensions)
        assert score == 100.0

    def test_minimum_score(self):
        """全 1 分应该是 0"""
        dimensions = {
            name: DimensionScore(dimension=name, score=1)
            for name in CLARIFICATION_DIMENSIONS
        }
        score = calculate_total_score(dimensions)
        assert score == 0.0

    def test_middle_score(self):
        """全 3 分应该是 50"""
        dimensions = {
            name: DimensionScore(dimension=name, score=3)
            for name in CLARIFICATION_DIMENSIONS
        }
        score = calculate_total_score(dimensions)
        assert score == 50.0

    def test_weighted_score(self, sample_dimension_scores):
        """加权计算应该正确"""
        # 使用自定义权重
        weights = {name: 2.0 for name in CLARIFICATION_DIMENSIONS}
        score = calculate_total_score(sample_dimension_scores, weights)
        # 加权平均应该与等权相同（因为所有权重相等）
        equal_score = calculate_total_score(sample_dimension_scores)
        assert abs(score - equal_score) < 0.1

    def test_empty_dimensions(self):
        """空维度应该返回 0"""
        score = calculate_total_score({})
        assert score == 0.0

    def test_partial_dimensions(self):
        """部分维度应该正确计算"""
        dimensions = {
            "functional_scope": DimensionScore(dimension="functional_scope", score=4),
            "target_users": DimensionScore(dimension="target_users", score=2),
        }
        score = calculate_total_score(dimensions)
        # (4 + 2) / 2 = 3, (3-1)/4 * 100 = 50
        assert score == 50.0

    def test_score_rounding(self):
        """分数应该保留一位小数"""
        dimensions = {
            "functional_scope": DimensionScore(dimension="functional_scope", score=4),
            "target_users": DimensionScore(dimension="target_users", score=3),
        }
        score = calculate_total_score(dimensions)
        assert isinstance(score, float)
        assert score == 62.5  # (4+3)/2 = 3.5, (3.5-1)/4 * 100 = 62.5


# ============================================================
# 判定函数测试
# ============================================================

class TestRecommendation:
    """判定函数测试"""

    def test_skip_recommendation(self):
        """>= 80 分应该建议跳过"""
        assert get_recommendation(80.0) == "skip"
        assert get_recommendation(90.0) == "skip"
        assert get_recommendation(100.0) == "skip"

    def test_conservative_recommendation(self):
        """50-79 分应该建议保守模式"""
        assert get_recommendation(50.0) == "conservative"
        assert get_recommendation(65.0) == "conservative"
        assert get_recommendation(79.0) == "conservative"

    def test_interactive_recommendation(self):
        """< 50 分应该建议交互模式"""
        assert get_recommendation(0.0) == "interactive"
        assert get_recommendation(25.0) == "interactive"
        assert get_recommendation(49.9) == "interactive"

    def test_threshold_values(self):
        """阈值应该正确"""
        assert THRESHOLD_PASS == 80.0
        assert THRESHOLD_CLARIFY == 50.0


# ============================================================
# 低分维度测试
# ============================================================

class TestLowScoreDimensions:
    """低分维度测试"""

    def test_get_low_score_dimensions(self, sample_dimension_scores):
        """应该返回评分 <= 3 的维度"""
        low_dims = get_low_score_dimensions(sample_dimension_scores, threshold=3)
        # score <= 3 的维度
        assert "target_users" in low_dims  # score=2
        assert "timeline" in low_dims      # score=2
        assert "budget" in low_dims        # score=1
        assert "quality_reqs" in low_dims  # score=2
        assert "success_criteria" in low_dims  # score=2

    def test_no_low_score_dimensions(self, high_score_dimensions):
        """高分输入应该没有低分维度"""
        low_dims = get_low_score_dimensions(high_score_dimensions, threshold=3)
        assert len(low_dims) == 0

    def test_all_low_score_dimensions(self, low_score_dimensions):
        """低分输入应该所有维度都是低分"""
        low_dims = get_low_score_dimensions(low_score_dimensions, threshold=3)
        assert len(low_dims) == 9

    def test_custom_threshold(self, sample_dimension_scores):
        """自定义阈值应该正确工作"""
        low_dims = get_low_score_dimensions(sample_dimension_scores, threshold=2)
        # score <= 2 的维度
        assert "budget" in low_dims  # score=1
        assert "functional_scope" not in low_dims  # score=3


# ============================================================
# 任务类型权重测试
# ============================================================

class TestTaskTypeWeights:
    """任务类型权重测试"""

    def test_development_weights(self):
        """开发类任务应该更关注功能和技术"""
        weights = get_weights_for_task_type("development")
        assert weights["functional_scope"] >= 1.0
        assert weights["tech_constraints"] >= 1.0

    def test_design_weights(self):
        """设计类任务应该更关注用户和质量"""
        weights = get_weights_for_task_type("design")
        assert weights["target_users"] >= 1.0
        assert weights["quality_reqs"] >= 1.0

    def test_analysis_weights(self):
        """分析类任务应该更关注背景和成功标准"""
        weights = get_weights_for_task_type("analysis")
        assert weights["context"] >= 1.0
        assert weights["success_criteria"] >= 1.0

    def test_unknown_task_type(self):
        """未知任务类型应该返回默认权重"""
        weights = get_weights_for_task_type("unknown")
        assert weights == DEFAULT_WEIGHTS


# ============================================================
# 数据模型测试
# ============================================================

class TestClarificationQuestion:
    """ClarificationQuestion 测试"""

    def test_basic_creation(self):
        """基本创建"""
        q = ClarificationQuestion(
            dimension="functional_scope",
            question="需要哪些功能？",
            importance="high",
        )
        assert q.dimension == "functional_scope"
        assert q.question == "需要哪些功能？"
        assert q.importance == "high"
        assert q.user_answer is None

    def test_dimension_label(self):
        """应该能获取维度标签"""
        q = ClarificationQuestion(
            dimension="functional_scope",
            question="需要哪些功能？",
        )
        assert q.dimension_label == "功能范围"

    def test_with_answer(self):
        """带用户回答"""
        q = ClarificationQuestion(
            dimension="timeline",
            question="交付时间？",
            user_answer="3 天",
        )
        assert q.user_answer == "3 天"


class TestAssumption:
    """Assumption 测试"""

    def test_basic_creation(self):
        """基本创建"""
        a = Assumption(
            dimension="functional_scope",
            assumption="实现核心 CRUD 功能",
            risk_level="medium",
        )
        assert a.dimension == "functional_scope"
        assert a.assumption == "实现核心 CRUD 功能"
        assert a.risk_level == "medium"

    def test_dimension_label(self):
        """应该能获取维度标签"""
        a = Assumption(
            dimension="target_users",
            assumption="面向一般用户",
        )
        assert a.dimension_label == "目标用户"


class TestClarifierResult:
    """ClarifierResult 测试"""

    def test_basic_creation(self):
        """基本创建"""
        result = ClarifierResult(
            score=65.0,
            dimensions={},
            questions=[],
            assumptions=[],
            recommendation="conservative",
        )
        assert result.score == 65.0
        assert result.recommendation == "conservative"

    def test_to_dict(self, sample_dimension_scores):
        """转换为字典"""
        result = ClarifierResult(
            score=45.0,
            dimensions=sample_dimension_scores,
            questions=[
                ClarificationQuestion(
                    dimension="budget",
                    question="预算是多少？",
                    importance="high",
                )
            ],
            assumptions=[
                Assumption(
                    dimension="timeline",
                    assumption="标准开发周期",
                    risk_level="medium",
                )
            ],
            recommendation="interactive",
            enriched_task="增强后的任务",
            raw_input="原始任务",
            task_type="development",
        )

        d = result.to_dict()
        assert d["score"] == 45.0
        assert d["recommendation"] == "interactive"
        assert len(d["questions"]) == 1
        assert len(d["assumptions"]) == 1
        assert d["enriched_task"] == "增强后的任务"

    def test_from_dict(self):
        """从字典反序列化"""
        data = {
            "score": 72.0,
            "dimensions": {
                "functional_scope": {
                    "dimension": "functional_scope",
                    "score": 4,
                    "reason": "明确",
                    "question": None,
                }
            },
            "questions": [
                {
                    "dimension": "budget",
                    "question": "预算？",
                    "importance": "high",
                    "user_answer": None,
                }
            ],
            "assumptions": [],
            "recommendation": "conservative",
            "enriched_task": "增强任务",
            "raw_input": "原始任务",
            "task_type": "development",
        }

        result = ClarifierResult.from_dict(data)
        assert result.score == 72.0
        assert "functional_scope" in result.dimensions
        assert len(result.questions) == 1
        assert result.recommendation == "conservative"

    def test_roundtrip(self, sample_dimension_scores):
        """序列化/反序列化往返"""
        original = ClarifierResult(
            score=55.0,
            dimensions=sample_dimension_scores,
            questions=[
                ClarificationQuestion(
                    dimension="budget",
                    question="预算？",
                    importance="high",
                )
            ],
            assumptions=[
                Assumption(
                    dimension="timeline",
                    assumption="标准周期",
                )
            ],
            recommendation="conservative",
            enriched_task="增强",
            raw_input="原始",
            task_type="design",
        )

        data = original.to_dict()
        restored = ClarifierResult.from_dict(data)

        assert restored.score == original.score
        assert restored.recommendation == original.recommendation
        assert len(restored.questions) == len(original.questions)
        assert len(restored.assumptions) == len(original.assumptions)


# ============================================================
# ClarifierAgent 测试
# ============================================================

class TestClarifierAgentBasic:
    """ClarifierAgent 基础测试"""

    def test_initialization(self):
        """初始化应该正确"""
        agent = ClarifierAgent(model="test-model", task_type="design")
        assert agent.config.name == "clarifier"
        assert agent.config.model == "test-model"
        assert agent.task_type == "design"
        assert agent.max_questions == 5

    def test_default_initialization(self):
        """默认初始化"""
        agent = ClarifierAgent()
        assert agent.config.model == "qwen3.6-turbo"
        assert agent.task_type == "development"

    @pytest.mark.asyncio
    async def test_create_clarifier(self):
        """create_clarifier 工厂函数"""
        agent = await create_clarifier(model="test", task_type="analysis")
        assert isinstance(agent, ClarifierAgent)
        assert agent.config.model == "test"
        assert agent.task_type == "analysis"


class TestClarifierAgentAnalyze:
    """ClarifierAgent.analyze 测试"""

    @pytest.mark.asyncio
    async def test_analyze_vague_input(self, clarifier):
        """模糊输入应该生成分数和建议"""
        result = await clarifier.analyze("帮我做一个电商网站")

        assert isinstance(result.score, float)
        assert 0 <= result.score <= 100
        assert result.raw_input == "帮我做一个电商网站"
        assert result.recommendation in ("skip", "conservative", "interactive")

    @pytest.mark.asyncio
    async def test_analyze_clear_input(self, clarifier):
        """清晰输入应该高分通过"""
        clear_task = (
            "用 React + FastAPI 做一个用户管理系统，"
            "支持 CRUD 操作，面向企业内部员工，"
            "3 天交付，预算 5000 元，"
            "需要支持 100 并发，对接现有 LDAP 系统，"
            "验收标准是所有功能可用且无严重 bug，"
            "背景是公司需要替换老旧系统"
        )
        result = await clarifier.analyze(clear_task)

        assert result.score >= 80.0
        assert result.recommendation == "skip"
        assert len(result.questions) == 0

    @pytest.mark.asyncio
    async def test_analyze_returns_result_type(self, clarifier):
        """应该返回 ClarifierResult 类型"""
        result = await clarifier.analyze("测试任务")
        assert isinstance(result, ClarifierResult)

    @pytest.mark.asyncio
    async def test_analyze_updates_state(self, clarifier):
        """分析后应该更新状态"""
        await clarifier.analyze("测试任务")
        state = clarifier.get_state("last_result")
        assert state is not None
        assert "score" in state


class TestClarifierAgentReEvaluate:
    """ClarifierAgent.re_evaluate 测试"""

    @pytest.mark.asyncio
    async def test_re_evaluate_improves_score(self, clarifier):
        """用户回答后分数应该提高"""
        # 初始分析
        result1 = await clarifier.analyze("帮我做一个网站")
        initial_score = result1.score

        # 用户回答
        user_answers = {
            "functional_scope": "需要用户注册、登录、商品展示功能",
            "target_users": "面向 C 端消费者",
            "tech_constraints": "使用 Vue.js 和 Python",
        }

        result2 = await clarifier.re_evaluate(
            "帮我做一个网站",
            user_answers,
        )

        # 分数应该提高
        assert result2.score >= initial_score

    @pytest.mark.asyncio
    async def test_re_evaluate_updates_questions(self, clarifier):
        """重新评估后问题应该更新"""
        result = await clarifier.re_evaluate(
            "帮我做一个网站",
            {"functional_scope": "需要用户管理功能"},
        )

        assert isinstance(result, ClarifierResult)
        # 已回答的维度不应该再有问题
        for q in result.questions:
            if q.dimension == "functional_scope":
                assert q.user_answer == "需要用户管理功能"


class TestClarifierAgentRun:
    """ClarifierAgent.run 测试（BaseAgent 接口）"""

    @pytest.mark.asyncio
    async def test_run_success(self, clarifier):
        """run 应该成功执行"""
        result = await clarifier.run("帮我做一个电商网站")

        assert result.success is True
        assert isinstance(result.output, ClarifierResult)
        assert "score" in result.metadata

    @pytest.mark.asyncio
    async def test_run_with_context(self, clarifier):
        """run 应该支持上下文"""
        result = await clarifier.run(
            "帮我做一个网站",
            context={"task_type": "design"},
        )

        assert result.success is True
        assert result.output.task_type == "design"


class TestClarifierAgentPlan:
    """ClarifierAgent.plan 测试（BaseAgent 接口）"""

    @pytest.mark.asyncio
    async def test_plan_returns_steps(self, clarifier):
        """plan 应该返回步骤列表"""
        steps = await clarifier.plan("测试任务")

        assert isinstance(steps, list)
        assert len(steps) > 0
        assert all(isinstance(s, str) for s in steps)


class TestClarifierAgentParsing:
    """ClarifierAgent 解析测试"""

    def test_extract_json_from_code_block(self, clarifier):
        """应该能从代码块中提取 JSON"""
        text = '''一些前缀文字
```json
{"key": "value"}
```
一些后缀文字'''
        result = clarifier._extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_json_direct(self, clarifier):
        """应该能直接提取 JSON"""
        text = '{"key": "value"}'
        result = clarifier._extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_json_no_json(self, clarifier):
        """没有 JSON 应该返回 None"""
        text = "这不是 JSON"
        result = clarifier._extract_json(text)
        assert result is None

    def test_parse_dimension_scores(self, clarifier):
        """应该能解析维度评分"""
        response = '''```json
{
    "dimensions": {
        "functional_scope": {"score": 4, "reason": "明确", "question": null},
        "target_users": {"score": 2, "reason": "未说明", "question": "面向谁？"}
    }
}
```'''
        scores = clarifier._parse_dimension_scores(response)
        assert "functional_scope" in scores
        assert scores["functional_scope"].score == 4
        assert scores["target_users"].score == 2

    def test_parse_dimension_scores_invalid(self, clarifier):
        """无效响应应该返回默认评分"""
        response = "这不是有效的 JSON"
        scores = clarifier._parse_dimension_scores(response)
        assert len(scores) == 9
        assert all(s.score == 2 for s in scores.values())

    def test_parse_questions(self, clarifier):
        """应该能解析问题"""
        response = '''```json
{
    "questions": [
        {"dimension": "budget", "question": "预算？", "importance": "high"},
        {"dimension": "timeline", "question": "时间？", "importance": "medium"}
    ]
}
```'''
        questions = clarifier._parse_questions(response)
        assert len(questions) == 2
        assert questions[0].dimension == "budget"
        assert questions[0].importance == "high"

    def test_parse_assumptions(self, clarifier):
        """应该能解析假设"""
        response = '''```json
{
    "assumptions": [
        {"dimension": "budget", "assumption": "无限制", "risk_level": "low"}
    ],
    "enriched_task": "增强任务"
}
```'''
        assumptions, enriched = clarifier._parse_assumptions(response)
        assert len(assumptions) == 1
        assert assumptions[0].assumption == "无限制"
        assert enriched == "增强任务"


# ============================================================
# 集成测试
# ============================================================

class TestClarifierIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow_vague_input(self, clarifier):
        """模糊输入的完整工作流"""
        # 1. 初始分析
        result = await clarifier.analyze("帮我做一个电商网站")

        # 2. 验证结果
        assert result.score < 80.0  # 不应该直接通过
        assert result.recommendation in ("conservative", "interactive")

        # 3. 如果是交互模式，应该有澄清问题
        if result.recommendation == "interactive":
            assert len(result.questions) > 0

        # 4. 如果是保守模式，应该有假设
        if result.recommendation == "conservative":
            assert len(result.assumptions) > 0
            assert result.enriched_task != ""

    @pytest.mark.asyncio
    async def test_full_workflow_clear_input(self, clarifier):
        """清晰输入的完整工作流"""
        clear_task = (
            "用 React + FastAPI 做一个用户管理系统，"
            "支持 CRUD 操作，面向企业内部员工，"
            "3 天交付，预算 5000 元，"
            "需要支持 100 并发，对接现有 LDAP 系统，"
            "验收标准是所有功能可用且无严重 bug，"
            "背景是公司需要替换老旧系统"
        )

        result = await clarifier.analyze(clear_task)

        assert result.score >= 80.0
        assert result.recommendation == "skip"
        assert len(result.questions) == 0
        assert len(result.assumptions) == 0

    @pytest.mark.asyncio
    async def test_clarification_loop(self, clarifier):
        """澄清循环：分析 -> 回答 -> 重新评估"""
        # 初始分析
        result1 = await clarifier.analyze("帮我做一个网站")

        # 用户回答部分问题
        answers = {
            "functional_scope": "需要用户注册和登录",
            "target_users": "面向普通消费者",
        }

        # 重新评估
        result2 = await clarifier.re_evaluate(
            "帮我做一个网站",
            answers,
        )

        # 分数应该提高
        assert result2.score >= result1.score

        # 如果仍然需要澄清，问题应该更新
        if result2.recommendation != "skip":
            for q in result2.questions:
                if q.dimension in answers:
                    assert q.user_answer == answers[q.dimension]
