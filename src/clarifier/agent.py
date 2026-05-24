"""
Phase 9: ClarifierAgent — 需求澄清 Agent

在 PlannerAgent 之前对用户输入进行澄清评分，必要时生成澄清问题或保守假设。
"""

import json
import re

from ..core.agent import AgentConfig, AgentResult, AgentRole, BaseAgent
from .dimensions import (
    CLARIFICATION_DIMENSIONS,
    DimensionScore,
    calculate_total_score,
    get_low_score_dimensions,
    get_recommendation,
    get_weights_for_task_type,
)
from .prompts import (
    CLARIFIER_SYSTEM_PROMPT,
    CONSERVATIVE_ASSUMPTION_PROMPT,
    INTERACTIVE_QUESTION_PROMPT,
    RE_EVALUATE_PROMPT,
)
from .result import Assumption, ClarificationQuestion, ClarifierResult


class ClarifierAgent(BaseAgent):
    """ClarifierAgent: 需求澄清 Agent

    职责：
    - 分析用户输入的完整性（9 个维度）
    - 计算澄清分数（0-100）
    - 判断是否需要澄清
    - 生成澄清问题（交互模式）或保守假设（保守模式）
    - 根据用户回复重新评估
    """

    def __init__(
        self,
        model: str = "qwen3.6-turbo",
        task_type: str = "development",
        max_questions: int = 5,
    ):
        """初始化 ClarifierAgent

        Args:
            model: 使用的 LLM 模型
            task_type: 任务类型，影响维度权重
            max_questions: 最多生成的澄清问题数量
        """
        config = AgentConfig(
            name="clarifier",
            role=AgentRole.SPECIALIST,
            description="需求澄清专家 - 分析输入完整性，生成澄清问题或假设",
            model=model,
            tools=[],
            max_iterations=3,
            timeout=60,
            temperature=0.3,
            system_prompt=CLARIFIER_SYSTEM_PROMPT,
        )
        super().__init__(config)

        self.task_type = task_type
        self.max_questions = max_questions
        self._llm_client = None  # 延迟初始化

    async def analyze(
        self,
        task: str,
        task_type: str | None = None,
    ) -> ClarifierResult:
        """分析用户输入的完整性

        Args:
            task: 用户任务描述
            task_type: 任务类型（可选，覆盖构造函数设置）

        Returns:
            ClarifierResult: 澄清结果
        """
        task_type = task_type or self.task_type
        weights = get_weights_for_task_type(task_type)

        # 调用 LLM 进行维度评分
        dimension_scores = await self._score_dimensions(task)

        # 计算总分
        total_score = calculate_total_score(dimension_scores, weights)

        # 获取建议
        recommendation = get_recommendation(total_score)

        # 获取低分维度
        low_score_dims = get_low_score_dimensions(dimension_scores)

        # 生成澄清问题或假设
        questions = []
        assumptions = []
        enriched_task = task

        if recommendation in ("conservative", "interactive"):
            if recommendation == "interactive":
                questions = await self._generate_questions(task, low_score_dims)
            else:
                assumptions, enriched_task = await self._generate_assumptions(
                    task, low_score_dims
                )

        result = ClarifierResult(
            score=total_score,
            dimensions=dimension_scores,
            questions=questions,
            assumptions=assumptions,
            recommendation=recommendation,
            enriched_task=enriched_task,
            raw_input=task,
            task_type=task_type,
        )

        self.update_state("last_result", result.to_dict())
        return result

    async def re_evaluate(
        self,
        original_task: str,
        user_answers: dict[str, str],
        task_type: str | None = None,
    ) -> ClarifierResult:
        """根据用户回复重新评估

        Args:
            original_task: 原始任务描述
            user_answers: 用户回答 {维度名: 回答}
            task_type: 任务类型

        Returns:
            ClarifierResult: 重新评估后的结果
        """
        task_type = task_type or self.task_type
        weights = get_weights_for_task_type(task_type)

        # 构建用户回答文本
        answers_text = "\n".join(
            f"- {dim}: {answer}"
            for dim, answer in user_answers.items()
        )

        # 调用 LLM 重新评分
        prompt = RE_EVALUATE_PROMPT.format(
            raw_input=original_task,
            user_answers=answers_text,
        )

        response = await self._call_llm(prompt)
        dimension_scores = self._parse_dimension_scores(response)

        # 计算总分
        total_score = calculate_total_score(dimension_scores, weights)
        recommendation = get_recommendation(total_score)

        # 如果仍然需要澄清，生成新的问题
        questions = []
        assumptions = []
        enriched_task = original_task

        if recommendation in ("conservative", "interactive"):
            low_score_dims = get_low_score_dimensions(dimension_scores)
            if recommendation == "interactive":
                questions = await self._generate_questions(
                    original_task, low_score_dims
                )
            else:
                assumptions, enriched_task = await self._generate_assumptions(
                    original_task, low_score_dims
                )

        # 合并用户回答到问题中
        for q in questions:
            if q.dimension in user_answers:
                q.user_answer = user_answers[q.dimension]

        result = ClarifierResult(
            score=total_score,
            dimensions=dimension_scores,
            questions=questions,
            assumptions=assumptions,
            recommendation=recommendation,
            enriched_task=enriched_task,
            raw_input=original_task,
            task_type=task_type,
        )

        self.update_state("last_result", result.to_dict())
        return result

    async def run(self, input: str, context: dict = None) -> AgentResult:
        """执行澄清分析（BaseAgent 接口）

        Args:
            input: 用户任务描述
            context: 执行上下文

        Returns:
            AgentResult: 包含 ClarifierResult 的执行结果
        """
        try:
            task_type = context.get("task_type", "development") if context else "development"
            result = await self.analyze(input, task_type)
            return AgentResult(
                success=True,
                output=result,
                metadata={
                    "score": result.score,
                    "recommendation": result.recommendation,
                    "questions_count": len(result.questions),
                },
            )
        except Exception as e:
            return AgentResult(
                success=False,
                output=None,
                error=str(e),
                metadata={"fallback": "conservative"},
            )

    async def plan(self, task: str) -> list[str]:
        """规划澄清步骤（BaseAgent 接口）

        Args:
            task: 任务描述

        Returns:
            执行步骤列表
        """
        return [
            "Step 1: 分析任务描述的完整性",
            "Step 2: 对 9 个维度进行评分",
            "Step 3: 计算总分并判断是否需要澄清",
            "Step 4: 生成澄清问题或保守假设",
        ]

    # ============================================================
    # 内部方法
    # ============================================================

    async def _score_dimensions(self, task: str) -> dict[str, DimensionScore]:
        """调用 LLM 对 9 个维度进行评分"""
        prompt = self._build_scoring_prompt(task)
        response = await self._call_llm(prompt)
        return self._parse_dimension_scores(response)

    def _build_scoring_prompt(self, task: str) -> str:
        """构建评分提示词"""
        dimensions_desc = "\n".join(
            f"- {dim.name}: {dim.description}"
            for dim in CLARIFICATION_DIMENSIONS.values()
        )
        return f"""请对以下任务描述进行 9 维度完整性评估。

任务描述：{task}

评估维度：
{dimensions_desc}

评分标准（每个维度 1-5 分）：
- 5 分：信息非常充分，无需澄清
- 4 分：信息基本充分，可能有小疑问
- 3 分：信息部分缺失，需要澄清
- 2 分：信息严重缺失，必须澄清
- 1 分：完全没有相关信息

请以 JSON 格式输出：
```json
{{
    "dimensions": {{
        "functional_scope": {{
            "score": 2,
            "reason": "评分理由",
            "question": "如需澄清，生成的问题"
        }},
        ...
    }}
}}
```"""

    async def _generate_questions(
        self, task: str, low_score_dims: list[str]
    ) -> list[ClarificationQuestion]:
        """生成澄清问题"""
        if not low_score_dims:
            return []

        missing_desc = "\n".join(
            f"- {dim}: {CLARIFICATION_DIMENSIONS[dim].label} (score: {self._get_dimension_score_from_state(dim)})"
            for dim in low_score_dims
            if dim in CLARIFICATION_DIMENSIONS
        )

        prompt = INTERACTIVE_QUESTION_PROMPT.format(
            raw_input=task,
            missing_dimensions=missing_desc,
        )

        response = await self._call_llm(prompt)
        return self._parse_questions(response)

    async def _generate_assumptions(
        self, task: str, low_score_dims: list[str]
    ) -> tuple[list[Assumption], str]:
        """生成保守假设"""
        if not low_score_dims:
            return [], task

        missing_desc = "\n".join(
            f"- {dim}: {CLARIFICATION_DIMENSIONS[dim].label}"
            for dim in low_score_dims
            if dim in CLARIFICATION_DIMENSIONS
        )

        prompt = CONSERVATIVE_ASSUMPTION_PROMPT.format(
            raw_input=task,
            missing_dimensions=missing_desc,
        )

        response = await self._call_llm(prompt)
        return self._parse_assumptions(response)

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM

        实际项目中会调用真实的 LLM API。
        这里提供一个模拟实现，便于测试。
        """
        if self._llm_client:
            # 实际 LLM 调用
            response = await self._llm_client.generate(
                system_prompt=CLARIFIER_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=self.config.temperature,
            )
            return response
        else:
            # 模拟实现：返回合理的默认响应
            return self._mock_llm_response(prompt)

    def _mock_llm_response(self, prompt: str) -> str:
        """模拟 LLM 响应（用于测试）"""
        # 检测是否是评分请求
        if "9 维度完整性评估" in prompt or "dimensions" in prompt.lower():
            return self._mock_scoring_response(prompt)
        elif "澄清问题" in prompt or "questions" in prompt.lower():
            return self._mock_questions_response(prompt)
        elif "假设" in prompt or "assumptions" in prompt.lower():
            return self._mock_assumptions_response(prompt)
        elif "重新评估" in prompt or "re-evaluate" in prompt.lower():
            return self._mock_re_evaluate_response(prompt)
        else:
            return '{"dimensions": {}}'

    def _mock_scoring_response(self, prompt: str) -> str:
        """模拟评分响应"""
        # 简单启发式：根据任务描述长度和内容判断
        task_match = re.search(r"任务描述[：:]\s*(.+?)(?:\n\n|\n评估)", prompt, re.DOTALL)
        task = task_match.group(1).strip() if task_match else ""

        # 检查是否包含关键信息
        has_tech = any(kw in task for kw in ["React", "Vue", "Python", "FastAPI", "Java", "Node", "技术栈"])
        has_timeline = any(kw in task for kw in ["天", "周", "月", "交付", "截止", "deadline"])
        has_users = any(kw in task for kw in ["用户", "客户", "面向", "群体", "B端", "C端"])
        has_features = any(kw in task for kw in ["功能", "模块", "CRUD", "管理", "登录", "支付"])
        has_budget = any(kw in task for kw in ["预算", "成本", "万", "元", "$"])
        has_quality = any(kw in task for kw in ["性能", "安全", "可用性", "并发", "QPS"])
        has_integration = any(kw in task for kw in ["对接", "集成", "API", "第三方", "系统"])
        has_success = any(kw in task for kw in ["成功", "验收", "标准", "目标", "KPI"])
        has_context = any(kw in task for kw in ["背景", "场景", "业务", "为什么", "原因"])

        scores = {
            "functional_scope": 5 if has_features else 2,
            "target_users": 5 if has_users else 2,
            "tech_constraints": 5 if has_tech else 2,
            "timeline": 5 if has_timeline else 2,
            "budget": 5 if has_budget else 2,
            "quality_reqs": 5 if has_quality else 2,
            "integration": 5 if has_integration else 2,
            "success_criteria": 5 if has_success else 2,
            "context": 5 if has_context else 2,
        }

        reasons = {
            "functional_scope": "功能范围明确" if has_features else "未说明具体功能",
            "target_users": "目标用户明确" if has_users else "未说明目标用户",
            "tech_constraints": "技术栈明确" if has_tech else "未说明技术约束",
            "timeline": "时间要求明确" if has_timeline else "未说明时间要求",
            "budget": "预算明确" if has_budget else "未说明预算",
            "quality_reqs": "质量要求明确" if has_quality else "未说明质量要求",
            "integration": "集成需求明确" if has_integration else "未说明集成需求",
            "success_criteria": "成功标准明确" if has_success else "未说明成功标准",
            "context": "项目背景充分" if has_context else "未说明项目背景",
        }

        questions = {
            "functional_scope": "需要哪些核心功能？" if not has_features else None,
            "target_users": "面向什么用户群体？" if not has_users else None,
            "tech_constraints": "有技术栈偏好吗？" if not has_tech else None,
            "timeline": "期望的交付时间是？" if not has_timeline else None,
            "budget": "预算或成本限制是？" if not has_budget else None,
            "quality_reqs": "对性能、安全有什么要求？" if not has_quality else None,
            "integration": "需要对接现有系统吗？" if not has_integration else None,
            "success_criteria": "怎么判断项目成功？" if not has_success else None,
            "context": "项目的背景和业务场景是？" if not has_context else None,
        }

        dimensions_json = json.dumps({
            dim: {
                "score": scores[dim],
                "reason": reasons[dim],
                "question": questions[dim],
            }
            for dim in scores
        }, ensure_ascii=False)

        return f'```json\n{{"dimensions": {dimensions_json}}}\n```'

    def _mock_questions_response(self, prompt: str) -> str:
        """模拟问题生成响应"""
        return '''```json
{
    "questions": [
        {
            "dimension": "functional_scope",
            "question": "需要哪些核心功能？例如：用户管理、数据展示、报表等？",
            "importance": "high"
        },
        {
            "dimension": "target_users",
            "question": "面向什么用户群体？内部员工还是外部客户？",
            "importance": "high"
        },
        {
            "dimension": "tech_constraints",
            "question": "有技术栈偏好或限制吗？",
            "importance": "medium"
        }
    ]
}
```'''

    def _mock_assumptions_response(self, prompt: str) -> str:
        """模拟假设生成响应"""
        return '''```json
{
    "assumptions": [
        {
            "dimension": "functional_scope",
            "assumption": "实现核心 CRUD 功能",
            "risk_level": "medium"
        },
        {
            "dimension": "target_users",
            "assumption": "面向一般 Web 用户",
            "risk_level": "medium"
        },
        {
            "dimension": "tech_constraints",
            "assumption": "使用项目现有技术栈",
            "risk_level": "low"
        }
    ],
    "enriched_task": "基于以下假设：实现核心 CRUD 功能，面向一般 Web 用户，使用项目现有技术栈。"
}
```'''

    def _mock_re_evaluate_response(self, prompt: str) -> str:
        """模拟重新评估响应"""
        return '''```json
{
    "dimensions": {
        "functional_scope": {"score": 4, "reason": "用户已补充功能信息", "question": null},
        "target_users": {"score": 4, "reason": "用户已说明目标用户", "question": null},
        "tech_constraints": {"score": 3, "reason": "技术栈部分明确", "question": "具体版本要求？"},
        "timeline": {"score": 2, "reason": "未说明时间要求", "question": "期望的交付时间是？"},
        "budget": {"score": 2, "reason": "未说明预算", "question": "预算限制是？"},
        "quality_reqs": {"score": 2, "reason": "未说明质量要求", "question": "性能要求？"},
        "integration": {"score": 2, "reason": "未说明集成需求", "question": "需要对接系统吗？"},
        "success_criteria": {"score": 2, "reason": "未说明成功标准", "question": "验收标准？"},
        "context": {"score": 3, "reason": "背景部分明确", "question": null}
    }
}
```'''

    def _parse_dimension_scores(self, response: str) -> dict[str, DimensionScore]:
        """解析 LLM 返回的维度评分"""
        json_str = self._extract_json(response)
        if not json_str:
            # 返回默认低分
            return {
                name: DimensionScore(
                    dimension=name,
                    score=2,
                    reason="无法解析评分，默认低分",
                )
                for name in CLARIFICATION_DIMENSIONS
            }

        try:
            data = json.loads(json_str)
            dimensions_data = data.get("dimensions", {})
            result = {}
            for name, dim_data in dimensions_data.items():
                if name in CLARIFICATION_DIMENSIONS:
                    result[name] = DimensionScore(
                        dimension=name,
                        score=max(1, min(5, int(dim_data.get("score", 2)))),
                        reason=dim_data.get("reason", ""),
                        question=dim_data.get("question"),
                    )
            # 补充缺失的维度
            for name in CLARIFICATION_DIMENSIONS:
                if name not in result:
                    result[name] = DimensionScore(
                        dimension=name,
                        score=2,
                        reason="LLM 未返回该维度评分",
                    )
            return result
        except (json.JSONDecodeError, ValueError):
            return {
                name: DimensionScore(
                    dimension=name,
                    score=2,
                    reason="解析失败，默认低分",
                )
                for name in CLARIFICATION_DIMENSIONS
            }

    def _parse_questions(self, response: str) -> list[ClarificationQuestion]:
        """解析 LLM 返回的澄清问题"""
        json_str = self._extract_json(response)
        if not json_str:
            return []

        try:
            data = json.loads(json_str)
            questions_data = data.get("questions", [])
            questions = []
            for q in questions_data[:self.max_questions]:
                dim = q.get("dimension", "")
                if dim in CLARIFICATION_DIMENSIONS:
                    questions.append(ClarificationQuestion(
                        dimension=dim,
                        question=q.get("question", ""),
                        importance=q.get("importance", "medium"),
                    ))
            return questions
        except (json.JSONDecodeError, ValueError):
            return []

    def _parse_assumptions(self, response: str) -> tuple[list[Assumption], str]:
        """解析 LLM 返回的假设"""
        json_str = self._extract_json(response)
        if not json_str:
            return [], ""

        try:
            data = json.loads(json_str)
            assumptions_data = data.get("assumptions", [])
            assumptions = []
            for a in assumptions_data:
                dim = a.get("dimension", "")
                if dim in CLARIFICATION_DIMENSIONS:
                    assumptions.append(Assumption(
                        dimension=dim,
                        assumption=a.get("assumption", ""),
                        risk_level=a.get("risk_level", "medium"),
                    ))
            enriched_task = data.get("enriched_task", "")
            return assumptions, enriched_task
        except (json.JSONDecodeError, ValueError):
            return [], ""

    def _extract_json(self, text: str) -> str | None:
        """从文本中提取 JSON 字符串"""
        # 尝试提取 ```json ... ``` 块
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1)

        # 尝试直接解析
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return match.group(0)

        return None

    def _get_dimension_score_from_state(self, dim_name: str) -> int:
        """从状态中获取维度评分"""
        last_result = self.get_state("last_result")
        if last_result and "dimensions" in last_result:
            dim_data = last_result["dimensions"].get(dim_name, {})
            return dim_data.get("score", 2)
        return 2


async def create_clarifier(
    model: str = "qwen3.6-turbo",
    task_type: str = "development",
    max_questions: int = 5,
) -> ClarifierAgent:
    """创建 ClarifierAgent 实例"""
    return ClarifierAgent(
        model=model,
        task_type=task_type,
        max_questions=max_questions,
    )
