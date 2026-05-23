"""
Summarizer Agent — 总结 Agent

工作流执行完成后自动运行，负责：
1. 归纳流程中出现的问题和经验
2. 提取可改进点和建议
3. 沉淀知识到 AgentMemory
4. 提取可复用流程模板
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional

from ..core.agent import AgentConfig, AgentRole, AgentResult
from ..knowledge.memory import AgentMemory, MemoryEntry


@dataclass
class WorkflowSummary:
    """工作流执行总结"""
    execution_id: str
    task: str
    workflow_name: str
    status: str  # success / failed / interrupted
    duration_seconds: float
    total_cost: float

    # 问题记录
    issues: list[dict] = field(default_factory=list)
    # 经验教训
    lessons_learned: list[str] = field(default_factory=list)
    # 改进建议
    improvement_suggestions: list[str] = field(default_factory=list)
    # 各节点表现
    node_summaries: list[dict] = field(default_factory=list)
    # 质量评分
    quality_score: float = 0.0
    # 总结摘要
    summary_text: str = ""
    # 可复用模板
    reusable_template: Optional[dict] = None
    # 时间戳
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class SummarizerAgent:
    """总结 Agent

    职责：
    - 分析工作流执行结果（事件日志 + 最终状态）
    - 归纳问题、经验、改进点
    - 沉淀知识到 AgentMemory
    - 生成可复用流程模板
    - 支持离线分析（不调用 LLM）和 LLM 增强分析两种模式
    """

    # 离线分析的系统提示
    OFFLINE_SYSTEM_PROMPT = """你是一个工作流执行总结专家。你的职责是分析多Agent编排系统的执行结果，
    归纳问题、经验教训和改进建议，帮助系统持续进化。"""

    def __init__(
        self,
        model: str = "qwen3.6-plus",
        memory: AgentMemory = None,
        offline_mode: bool = True,
    ):
        """初始化 SummarizerAgent

        Args:
            model: 使用的 LLM 模型（离线模式下不使用）
            memory: AgentMemory 实例，用于沉淀知识
            offline_mode: 是否使用离线分析模式（不调用 LLM）
        """
        self.model = model
        self.memory = memory
        self.offline_mode = offline_mode

    async def summarize(
        self,
        execution_id: str,
        task: str,
        workflow_name: str,
        final_state: dict,
        events: list[dict],
        node_outputs: dict,
        project_id: str = "default",
    ) -> WorkflowSummary:
        """总结工作流执行结果

        Args:
            execution_id: 执行 ID
            task: 任务描述
            workflow_name: 工作流名称
            final_state: 最终状态字典
            events: 事件日志列表
            node_outputs: 各节点输出字典
            project_id: 项目 ID

        Returns:
            WorkflowSummary: 执行总结
        """
        # 1. 分析事件日志，提取问题
        issues = self._analyze_events(events, node_outputs)

        # 2. 分析各节点表现
        node_summaries = self._analyze_nodes(events, node_outputs)

        # 3. 提取经验教训
        lessons = self._extract_lessons(issues, node_summaries, final_state)

        # 4. 生成改进建议
        suggestions = self._generate_suggestions(issues, lessons, node_summaries)

        # 5. 计算质量评分
        quality_score = self._calculate_quality_score(
            issues, node_summaries, final_state
        )

        # 6. 生成总结文本
        summary_text = self._generate_summary_text(
            task, workflow_name, issues, lessons, suggestions, quality_score
        )

        # 7. 计算执行时长和成本
        duration = self._calculate_duration(events)
        total_cost = final_state.get("total_cost", 0.0)
        status = final_state.get("current_stage", "unknown")
        if status == "completed":
            status = "success"
        elif status == "failed" or status == "error":
            status = "failed"
        elif "interrupt" in status:
            status = "interrupted"
        else:
            status = "running"

        # 8. 生成可复用模板
        template = self._extract_template(
            workflow_name, node_outputs, issues
        )

        summary = WorkflowSummary(
            execution_id=execution_id,
            task=task,
            workflow_name=workflow_name,
            status=status,
            duration_seconds=duration,
            total_cost=total_cost,
            issues=issues,
            lessons_learned=lessons,
            improvement_suggestions=suggestions,
            node_summaries=node_summaries,
            quality_score=quality_score,
            summary_text=summary_text,
            reusable_template=template,
        )

        # 9. 沉淀知识到记忆
        if self.memory:
            self._save_to_memory(summary, project_id)

        return summary

    # ============================================================
    # 分析方法
    # ============================================================

    def _analyze_events(
        self, events: list[dict], node_outputs: dict
    ) -> list[dict]:
        """分析事件日志，提取问题"""
        issues = []

        for event in events:
            event_type = event.get("event_type", "")
            node_name = event.get("node_name", "")
            data = event.get("data", {}) or {}

            # 节点失败
            if event_type == "node_failed":
                error = data.get("error", "未知错误")
                issues.append({
                    "type": "node_failure",
                    "node": node_name,
                    "severity": "critical",
                    "description": f"节点 {node_name} 执行失败: {error}",
                    "timestamp": event.get("timestamp"),
                })

            # 重新规划
            elif event_type == "replan_triggered":
                reason = data.get("reason", "未知原因")
                issues.append({
                    "type": "replan",
                    "node": node_name,
                    "severity": "warning",
                    "description": f"触发重新规划: {reason}",
                    "timestamp": event.get("timestamp"),
                })

            # 成本超限
            elif event_type == "budget_exceeded":
                issues.append({
                    "type": "budget_exceeded",
                    "severity": "critical",
                    "description": data.get("message", "成本超出预算"),
                    "timestamp": event.get("timestamp"),
                })

            # 验证失败
            elif event_type == "verification_failed":
                issues.append({
                    "type": "verification_failed",
                    "node": node_name,
                    "severity": "high",
                    "description": data.get("message", f"节点 {node_name} 验证失败"),
                    "timestamp": event.get("timestamp"),
                })

        return issues

    def _analyze_nodes(
        self, events: list[dict], node_outputs: dict
    ) -> list[dict]:
        """分析各节点表现"""
        node_stats: dict[str, dict] = {}

        for event in events:
            node_name = event.get("node_name")
            if not node_name:
                continue

            if node_name not in node_stats:
                node_stats[node_name] = {
                    "node_id": node_name,
                    "started": False,
                    "completed": False,
                    "failed": False,
                    "duration": 0.0,
                    "start_time": None,
                }

            event_type = event.get("event_type", "")
            ts = event.get("timestamp", 0)

            if event_type == "node_started":
                node_stats[node_name]["started"] = True
                node_stats[node_name]["start_time"] = ts

            elif event_type == "node_completed":
                node_stats[node_name]["completed"] = True
                if node_stats[node_name]["start_time"]:
                    node_stats[node_name]["duration"] = (
                        ts - node_stats[node_name]["start_time"]
                    )

            elif event_type == "node_failed":
                node_stats[node_name]["failed"] = True
                if node_stats[node_name]["start_time"]:
                    node_stats[node_name]["duration"] = (
                        ts - node_stats[node_name]["start_time"]
                    )

        summaries = []
        for node_id, stats in node_stats.items():
            # 获取节点输出详情
            output_info = {}
            if node_id in node_outputs:
                output_data = node_outputs[node_id]
                if isinstance(output_data, dict):
                    output_info = output_data

            summaries.append({
                "node_id": node_id,
                "status": "failed" if stats["failed"]
                          else ("completed" if stats["completed"]
                                else "incomplete"),
                "duration_seconds": round(stats["duration"], 2),
                "output_summary": self._summarize_output(output_info),
            })

        return summaries

    def _summarize_output(self, output_info: dict) -> str:
        """简化节点输出摘要"""
        if not output_info:
            return "无输出"

        parts = []
        for key in ["status", "summary", "result", "message"]:
            if key in output_info:
                val = output_info[key]
                parts.append(f"{key}: {str(val)[:200]}")
                break

        return "; ".join(parts) if parts else "输出已记录"

    def _extract_lessons(
        self,
        issues: list[dict],
        node_summaries: list[dict],
        final_state: dict,
    ) -> list[str]:
        """提取经验教训"""
        lessons = []

        # 从问题中提取
        failure_nodes = [i["node"] for i in issues if i.get("type") == "node_failure" and i.get("node")]
        if failure_nodes:
            lessons.append(
                f"失败节点: {', '.join(failure_nodes)}。需要检查这些节点的输入依赖和工具配置。"
            )

        # 从节点表现中提取
        slow_nodes = [n for n in node_summaries if n.get("duration_seconds", 0) > 60]
        if slow_nodes:
            lessons.append(
                f"耗时节点: {', '.join(n['node_id'] for n in slow_nodes)}。"
                "考虑增加超时时间或优化节点逻辑。"
            )

        # 从最终状态中提取
        iterations = final_state.get("iteration_count", 0)
        if iterations > 5:
            lessons.append(
                f"迭代次数过多 ({iterations} 次)。可能需要调整工作流配置以减少返工。"
            )

        cost = final_state.get("total_cost", 0)
        if cost > 1.0:
            lessons.append(f"本次执行成本较高 (${cost:.2f})。考虑使用更经济的模型或减少 LLM 调用次数。")

        # 成功执行的正面经验
        all_ok = (
            not issues
            and not any(n.get("status") == "failed" for n in node_summaries)
            and not any(l.startswith("耗时") for l in lessons)
            and not any("成本" in l for l in lessons)
            and not any("迭代" in l for l in lessons)
        )
        if all_ok and not lessons:
            lessons.append("本次执行无失败节点，工作流配置合理。")

        return lessons

    def _generate_suggestions(
        self,
        issues: list[dict],
        lessons: list[str],
        node_summaries: list[dict],
    ) -> list[str]:
        """生成改进建议"""
        suggestions = []

        # 针对失败的建议
        critical_issues = [i for i in issues if i["severity"] == "critical"]
        if critical_issues:
            suggestions.append(
                f"需要优先解决 {len(critical_issues)} 个严重问题。"
                "建议为这些节点添加更详细的错误处理和重试机制。"
            )

        # 针对验证失败的建议
        verification_issues = [i for i in issues if i["type"] == "verification_failed"]
        if verification_issues:
            suggestions.append(
                "验证失败频繁出现。建议加强 Verifier 规则的针对性，"
                "或在 Executor 输出前增加自检步骤。"
            )

        # 针对重新规划的建议
        replan_issues = [i for i in issues if i["type"] == "replan"]
        if replan_issues:
            suggestions.append(
                "多次触发重新规划。建议 Planner 在初始规划阶段就考虑更多边界情况。"
            )

        # 通用建议
        failed_nodes = [n for n in node_summaries if n["status"] == "failed"]
        if failed_nodes:
            suggestions.append(
                f"{len(failed_nodes)} 个节点失败。建议检查节点间的状态传递是否正确。"
            )

        if not suggestions:
            suggestions.append("本次执行表现良好，暂无改进建议。")

        return suggestions

    def _calculate_quality_score(
        self,
        issues: list[dict],
        node_summaries: list[dict],
        final_state: dict,
    ) -> float:
        """计算质量评分 (0-10)"""
        score = 10.0

        # 扣分：严重问题 -3，高问题 -2，中问题 -1，低问题 -0.5
        severity_penalties = {
            "critical": 3.0,
            "high": 2.0,
            "medium": 1.0,
            "low": 0.5,
        }
        for issue in issues:
            penalty = severity_penalties.get(issue.get("severity", "medium"), 1.0)
            score -= penalty

        # 扣分：失败节点 -2
        failed_nodes = sum(1 for n in node_summaries if n["status"] == "failed")
        score -= failed_nodes * 2

        # 扣分：迭代过多 -0.5 per excess
        iterations = final_state.get("iteration_count", 0)
        if iterations > 3:
            score -= (iterations - 3) * 0.5

        return max(0.0, min(10.0, round(score, 1)))

    def _generate_summary_text(
        self,
        task: str,
        workflow_name: str,
        issues: list[dict],
        lessons: list[str],
        suggestions: list[str],
        quality_score: float,
    ) -> str:
        """生成总结文本"""
        lines = [
            f"## 工作流执行总结: {workflow_name}",
            f"**任务**: {task}",
            f"**质量评分**: {quality_score}/10",
            f"**问题数**: {len(issues)}",
            "",
        ]

        if issues:
            lines.append("### 问题")
            for issue in issues:
                lines.append(f"- [{issue['severity']}] {issue['description']}")
            lines.append("")

        if lessons:
            lines.append("### 经验教训")
            for lesson in lessons:
                lines.append(f"- {lesson}")
            lines.append("")

        if suggestions:
            lines.append("### 改进建议")
            for suggestion in suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")

        return "\n".join(lines)

    def _calculate_duration(self, events: list[dict]) -> float:
        """计算执行时长（秒）"""
        if not events:
            return 0.0

        timestamps = [e.get("timestamp", 0) for e in events if e.get("timestamp")]
        if not timestamps:
            return 0.0

        return round(max(timestamps) - min(timestamps), 2)

    def _extract_template(
        self,
        workflow_name: str,
        node_outputs: dict,
        issues: list[dict],
    ) -> Optional[dict]:
        """提取可复用流程模板"""
        if not node_outputs:
            return None

        # 只提取成功节点的输出作为模板参考
        successful_nodes = {}
        for node_id, output in node_outputs.items():
            node_issues = [i for i in issues if i.get("node") == node_id]
            if not node_issues:
                # 简化输出，只保留结构化信息
                if isinstance(output, dict):
                    successful_nodes[node_id] = {
                        "type": output.get("type", "unknown"),
                        "status": output.get("status", "unknown"),
                    }

        if not successful_nodes:
            return None

        return {
            "workflow_name": workflow_name,
            "nodes": list(successful_nodes.keys()),
            "node_configs": successful_nodes,
            "created_at": datetime.now().isoformat(),
        }

    def _save_to_memory(self, summary: WorkflowSummary, project_id: str) -> None:
        """将总结沉淀到记忆"""
        # 1. 保存总结
        self.memory.remember(MemoryEntry(
            key=f"exec_summary:{summary.execution_id}",
            value={
                "task": summary.task,
                "workflow": summary.workflow_name,
                "status": summary.status,
                "quality_score": summary.quality_score,
                "issues_count": len(summary.issues),
                "summary": summary.summary_text,
            },
            category="execution_summary",
            project_id=project_id,
            tags=["summary", summary.workflow_name, summary.status],
        ))

        # 2. 保存经验教训
        for i, lesson in enumerate(summary.lessons_learned):
            self.memory.remember(MemoryEntry(
                key=f"lesson:{summary.execution_id}:{i}",
                value=lesson,
                category="lesson_learned",
                project_id=project_id,
                tags=["lesson"],
            ))

        # 3. 保存可复用模板
        if summary.reusable_template:
            self.memory.remember(MemoryEntry(
                key=f"template:{summary.workflow_name}:{summary.execution_id}",
                value=summary.reusable_template,
                category="reusable_template",
                project_id=project_id,
                tags=["template", summary.workflow_name],
            ))


async def create_summarizer(
    model: str = "qwen3.6-plus",
    memory: AgentMemory = None,
    offline_mode: bool = True,
) -> SummarizerAgent:
    """创建 SummarizerAgent 实例"""
    return SummarizerAgent(
        model=model,
        memory=memory,
        offline_mode=offline_mode,
    )
