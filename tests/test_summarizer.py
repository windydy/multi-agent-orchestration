"""
测试 Summarizer Agent
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from src.agents.summarizer import SummarizerAgent, WorkflowSummary
from src.knowledge.memory import AgentMemory


@pytest.fixture
def memory():
    """创建临时 AgentMemory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "memory.db"
        yield AgentMemory(db_path=str(db_path))


@pytest.fixture
def summarizer(memory):
    """创建 SummarizerAgent 实例"""
    return SummarizerAgent(memory=memory, offline_mode=True)


# ============================================================
# 辅助函数
# ============================================================

def make_events(status="success"):
    """生成模拟事件日志"""
    events = [
        {"event_type": "execution_started", "thread_id": "exec_001", "timestamp": 1000.0, "node_name": None, "data": {}},
        {"event_type": "node_started", "thread_id": "exec_001", "timestamp": 1001.0, "node_name": "planner", "data": {}},
        {"event_type": "node_completed", "thread_id": "exec_001", "timestamp": 1010.0, "node_name": "planner", "data": {}},
        {"event_type": "node_started", "thread_id": "exec_001", "timestamp": 1011.0, "node_name": "developer", "data": {}},
        {"event_type": "node_completed", "thread_id": "exec_001", "timestamp": 1025.0, "node_name": "developer", "data": {}},
    ]
    if status == "success":
        events.append({
            "event_type": "execution_completed",
            "thread_id": "exec_001",
            "timestamp": 1026.0,
            "node_name": None,
            "data": {},
        })
    elif status == "failed":
        events.append({
            "event_type": "node_failed",
            "thread_id": "exec_001",
            "timestamp": 1020.0,
            "node_name": "tester",
            "data": {"error": "pytest 失败: 3 tests failed"},
        })
        events.append({
            "event_type": "execution_completed",
            "thread_id": "exec_001",
            "timestamp": 1026.0,
            "node_name": None,
            "data": {},
        })
    return events


def make_node_outputs():
    """生成模拟节点输出"""
    return {
        "planner": {"type": "plan", "status": "success", "summary": "生成了 5 节点计划"},
        "developer": {"type": "code", "status": "success", "summary": "编写了 main.py"},
    }


# ============================================================
# 测试
# ============================================================

class TestSummarizerBasic:
    """基础功能测试"""

    @pytest.mark.asyncio
    async def test_summarize_success(self, summarizer, memory):
        """成功执行的总结"""
        events = make_events("success")
        node_outputs = make_node_outputs()
        final_state = {"current_stage": "completed", "total_cost": 0.05, "iteration_count": 1}

        summary = await summarizer.summarize(
            execution_id="exec_001",
            task="创建 TODO list 应用",
            workflow_name="software-development",
            final_state=final_state,
            events=events,
            node_outputs=node_outputs,
            project_id="test_proj",
        )

        assert isinstance(summary, WorkflowSummary)
        assert summary.execution_id == "exec_001"
        assert summary.task == "创建 TODO list 应用"
        assert summary.workflow_name == "software-development"
        assert summary.status == "success"
        assert summary.duration_seconds > 0
        assert summary.quality_score > 0
        assert summary.summary_text != ""

    @pytest.mark.asyncio
    async def test_summarize_failed(self, summarizer, memory):
        """失败执行的总结"""
        events = make_events("failed")
        node_outputs = make_node_outputs()
        final_state = {"current_stage": "failed", "total_cost": 0.1, "iteration_count": 3}

        summary = await summarizer.summarize(
            execution_id="exec_002",
            task="创建 API 服务",
            workflow_name="software-development",
            final_state=final_state,
            events=events,
            node_outputs=node_outputs,
            project_id="test_proj",
        )

        assert summary.status == "failed"
        assert len(summary.issues) > 0
        assert any(i["type"] == "node_failure" for i in summary.issues)
        # 失败的质量评分应该更低
        assert summary.quality_score < 10.0

    @pytest.mark.asyncio
    async def test_summarize_empty_events(self, summarizer, memory):
        """空事件列表"""
        summary = await summarizer.summarize(
            execution_id="exec_003",
            task="空任务",
            workflow_name="test",
            final_state={"current_stage": "running"},
            events=[],
            node_outputs={},
        )

        assert summary.duration_seconds == 0.0
        assert summary.node_summaries == []


class TestEventAnalysis:
    """事件分析测试"""

    def test_analyze_node_failures(self, summarizer):
        events = [
            {"event_type": "node_failed", "node_name": "tester",
             "timestamp": 100.0, "data": {"error": "test failed"}},
        ]
        issues = summarizer._analyze_events(events, {})
        assert len(issues) == 1
        assert issues[0]["type"] == "node_failure"
        assert issues[0]["severity"] == "critical"
        assert "tester" in issues[0]["description"]

    def test_analyze_verification_failure(self, summarizer):
        events = [
            {"event_type": "verification_failed", "node_name": "developer",
             "timestamp": 100.0, "data": {"message": "代码风格检查失败"}},
        ]
        issues = summarizer._analyze_events(events, {})
        assert len(issues) == 1
        assert issues[0]["type"] == "verification_failed"

    def test_analyze_budget_exceeded(self, summarizer):
        events = [
            {"event_type": "budget_exceeded", "timestamp": 100.0,
             "data": {"message": "超出预算限制 $5.00"}},
        ]
        issues = summarizer._analyze_events(events, {})
        assert len(issues) == 1
        assert issues[0]["type"] == "budget_exceeded"

    def test_analyze_replan(self, summarizer):
        events = [
            {"event_type": "replan_triggered", "node_name": "planner",
             "timestamp": 100.0, "data": {"reason": "依赖缺失"}},
        ]
        issues = summarizer._analyze_events(events, {})
        assert len(issues) == 1
        assert issues[0]["type"] == "replan"


class TestNodeAnalysis:
    """节点分析测试"""

    def test_analyze_nodes_basic(self, summarizer):
        events = [
            {"event_type": "node_started", "node_name": "dev", "timestamp": 10.0},
            {"event_type": "node_completed", "node_name": "dev", "timestamp": 30.0},
        ]
        summaries = summarizer._analyze_nodes(events, {})
        assert len(summaries) == 1
        assert summaries[0]["node_id"] == "dev"
        assert summaries[0]["status"] == "completed"
        assert summaries[0]["duration_seconds"] == 20.0

    def test_analyze_nodes_failed(self, summarizer):
        events = [
            {"event_type": "node_started", "node_name": "test", "timestamp": 10.0},
            {"event_type": "node_failed", "node_name": "test", "timestamp": 15.0},
        ]
        summaries = summarizer._analyze_nodes(events, {})
        assert summaries[0]["status"] == "failed"
        assert summaries[0]["duration_seconds"] == 5.0

    def test_analyze_nodes_no_events(self, summarizer):
        summaries = summarizer._analyze_nodes([], {})
        assert summaries == []


class TestLessonsAndSuggestions:
    """经验教训和建议测试"""

    def test_extract_lessons_from_failures(self, summarizer):
        issues = [{"type": "node_failure", "node": "tester", "severity": "critical"}]
        lessons = summarizer._extract_lessons(issues, [], {})
        assert any("tester" in l for l in lessons)

    def test_extract_lessons_from_slow_nodes(self, summarizer):
        node_summaries = [{"node_id": "planner", "duration_seconds": 120.0}]
        lessons = summarizer._extract_lessons([], node_summaries, {})
        assert any("耗时" in l for l in lessons)

    def test_extract_lessons_from_iterations(self, summarizer):
        final_state = {"iteration_count": 8}
        lessons = summarizer._extract_lessons([], [], final_state)
        assert any("8" in l for l in lessons)

    def test_extract_lessons_from_cost(self, summarizer):
        final_state = {"total_cost": 5.0}
        lessons = summarizer._extract_lessons([], [], final_state)
        assert any("成本" in l for l in lessons)

    def test_extract_lessons_success(self, summarizer):
        lessons = summarizer._extract_lessons([], [], {})
        assert len(lessons) > 0
        assert "无失败" in lessons[0] or "良好" in lessons[0] or "合理" in lessons[0]

    def test_generate_suggestions_critical_issues(self, summarizer):
        issues = [
            {"severity": "critical", "type": "node_failure"},
            {"severity": "critical", "type": "budget_exceeded"},
        ]
        suggestions = summarizer._generate_suggestions(issues, [], [])
        assert any("严重" in s for s in suggestions)

    def test_generate_suggestions_no_issues(self, summarizer):
        suggestions = summarizer._generate_suggestions([], [], [])
        assert any("良好" in s for s in suggestions)


class TestQualityScore:
    """质量评分测试"""

    def test_perfect_score(self, summarizer):
        score = summarizer._calculate_quality_score([], [], {})
        assert score == 10.0

    def test_critical_issue_penalty(self, summarizer):
        issues = [{"severity": "critical"}]
        score = summarizer._calculate_quality_score(issues, [], {})
        assert score == 7.0

    def test_failed_node_penalty(self, summarizer):
        nodes = [{"status": "failed"}]
        score = summarizer._calculate_quality_score([], nodes, {})
        assert score == 8.0

    def test_excess_iteration_penalty(self, summarizer):
        state = {"iteration_count": 5}
        score = summarizer._calculate_quality_score([], [], state)
        assert score == 9.0

    def test_score_bounds(self, summarizer):
        issues = [{"severity": "critical"}, {"severity": "critical"}, {"severity": "high"}]
        nodes = [{"status": "failed"}, {"status": "failed"}]
        score = summarizer._calculate_quality_score(issues, nodes, {})
        assert 0.0 <= score <= 10.0


class TestTemplate:
    """可复用模板测试"""

    def test_extract_template(self, summarizer):
        node_outputs = {
            "planner": {"type": "plan", "status": "success"},
            "developer": {"type": "code", "status": "success"},
        }
        template = summarizer._extract_template("dev", node_outputs, [])
        assert template is not None
        assert template["workflow_name"] == "dev"
        assert "planner" in template["nodes"]

    def test_extract_template_with_issues(self, summarizer):
        node_outputs = {
            "planner": {"type": "plan", "status": "success"},
            "tester": {"type": "test", "status": "failed"},
        }
        issues = [{"type": "node_failure", "node": "tester"}]
        template = summarizer._extract_template("dev", node_outputs, issues)
        assert template is not None
        # tester 有 issue，不应在模板中
        assert "planner" in template["node_configs"]
        assert "tester" not in template["node_configs"]

    def test_extract_template_empty(self, summarizer):
        template = summarizer._extract_template("dev", {}, [])
        assert template is None


class TestMemory:
    """记忆持久化测试"""

    @pytest.mark.asyncio
    async def test_save_to_memory(self, summarizer, memory):
        summary = WorkflowSummary(
            execution_id="exec_mem",
            task="测试任务",
            workflow_name="test",
            status="success",
            duration_seconds=30.0,
            total_cost=0.05,
            lessons_learned=["测试教训"],
            quality_score=8.0,
            summary_text="测试总结",
        )
        summarizer._save_to_memory(summary, "proj_1")

        # 验证总结已保存
        entry = memory.recall("exec_summary:exec_mem")
        assert entry is not None
        assert entry.value["status"] == "success"

        # 验证教训已保存
        lesson = memory.recall("lesson:exec_mem:0")
        assert lesson is not None
        assert lesson.value == "测试教训"

    @pytest.mark.asyncio
    async def test_save_template_to_memory(self, summarizer, memory):
        summary = WorkflowSummary(
            execution_id="exec_tmpl",
            task="模板任务",
            workflow_name="template_test",
            status="success",
            duration_seconds=10.0,
            total_cost=0.0,
            reusable_template={"workflow_name": "template_test", "nodes": ["a"]},
        )
        summarizer._save_to_memory(summary, "proj_2")

        keys = memory.get_all_keys("proj_2")
        assert any("template" in k for k in keys)


class TestDuration:
    """时长计算测试"""

    def test_duration_calculation(self, summarizer):
        events = [
            {"timestamp": 100.0},
            {"timestamp": 110.0},
            {"timestamp": 125.0},
        ]
        duration = summarizer._calculate_duration(events)
        assert duration == 25.0

    def test_duration_empty(self, summarizer):
        assert summarizer._calculate_duration([]) == 0.0

    def test_duration_no_timestamps(self, summarizer):
        events = [{"event_type": "test"}]
        assert summarizer._calculate_duration(events) == 0.0


class TestSummaryText:
    """总结文本测试"""

    def test_summary_text_with_issues(self, summarizer):
        issues = [{"severity": "high", "description": "测试问题"}]
        text = summarizer._generate_summary_text(
            "task", "wf", issues, ["教训"], ["建议"], 7.0
        )
        assert "## 工作流执行总结" in text
        assert "7.0/10" in text
        assert "测试问题" in text

    def test_summary_text_no_issues(self, summarizer):
        text = summarizer._generate_summary_text("task", "wf", [], [], [], 10.0)
        assert "10.0/10" in text
        assert "0" in text
