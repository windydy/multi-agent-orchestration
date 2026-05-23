"""
Phase 4: PlannerAgent — LLM 驱动的任务规划器

src/plan/planner.py
"""

from __future__ import annotations

from typing import Any, Optional
import json
import logging
import uuid
import os

from src.plan.graph import PlanGraph, PlanNode, NodeStatus, NodeType, ExecutorCapability

logger = logging.getLogger(__name__)

# 任务类型 → ExecutorCapability 映射
_TASK_TYPE_TO_CAPABILITY = {
    "requirements_analysis": ExecutorCapability.REQUIREMENTS_ANALYSIS,
    "technical_design": ExecutorCapability.TECHNICAL_DESIGN,
    "code_development": ExecutorCapability.CODE_DEVELOPMENT,
    "code_review": ExecutorCapability.CODE_REVIEW,
    "testing": ExecutorCapability.TESTING,
    "bug_fixing": ExecutorCapability.BUG_FIXING,
    "documentation": ExecutorCapability.DOCUMENTATION,
    "security_audit": ExecutorCapability.SECURITY_AUDIT,
    "deployment": ExecutorCapability.DEPLOYMENT,
    "devops_ci_cd": ExecutorCapability.DEVOPS_CI_CD,
    "devops_container": ExecutorCapability.DEVOPS_CONTAINER,
    "data_engineering": ExecutorCapability.DATA_ENGINEERING,
    "architecture_design": ExecutorCapability.ARCHITECTURE_DESIGN,
    "product_management": ExecutorCapability.PRODUCT_MANAGEMENT,
    "planner": ExecutorCapability.GENERIC,
}


class PlannerAgent:
    """
    规划器 Agent。
    
    职责：
    - 理解用户意图
    - 任务分解
    - 构建依赖 DAG
    - 输出 PlanGraph
    
    调用 LLM (通过 DashScope/Anthropic 兼容 API) 动态生成执行计划。
    """

    SYSTEM_PROMPT = """你是一个任务规划专家。你的职责是将复杂任务分解为可执行的 DAG 计划。

你必须以严格的 JSON 格式输出，不要包含任何额外文字或 Markdown 代码块。

JSON Schema:
{
  "nodes": [
    {
      "id": "唯一ID（小写字母+下划线）",
      "name": "节点名称",
      "description": "详细描述，包含该节点需要做什么",
      "type": "任务类型（requirements_analysis/technical_design/code_development/code_review/testing/bug_fixing/documentation/security_audit/deployment/devops_ci_cd/data_engineering/architecture_design/product_management/planner）",
      "dependencies": ["依赖的节点ID列表"],
      "parallel_group": "可选，并行组名（字符串）",
      "max_retries": 2,
      "timeout_seconds": 300
    }
  ]
}

规则：
1. 每个节点必须有唯一的 id
2. 依赖关系必须形成 DAG（无环）
3. 入口节点（无依赖）最多 2 个
4. type 必须是上述枚举值之一
5. parallel_group 用于标记可以并行执行的节点
6. 为测试任务添加 testing 节点，为代码任务添加 code_review 节点"""

    def __init__(self, model: str = "qwen3.6-plus", api_key: str = None, base_url: str = None):
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._client = None
        self._init_client()

    def _init_client(self):
        """初始化 API 客户端"""
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError("anthropic 包未安装: pip install anthropic")

        api_key = self._api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            # 尝试从 Hermes config 读取
            hermes_conf = self._load_hermes_config()
            api_key = hermes_conf.get("api_key")

        if not api_key:
            raise ValueError("需要配置 API Key (DASHSCOPE_API_KEY / ANTHROPIC_API_KEY / Hermes config)")

        base_url = self._base_url
        if not base_url:
            hermes_conf = self._load_hermes_config()
            base_url = hermes_conf.get("base_url")
        if not base_url and os.environ.get("DASHSCOPE_API_KEY"):
            base_url = "https://coding.dashscope.aliyuncs.com/apps/anthropic"

        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        self._client = AsyncAnthropic(**kwargs)

    def _load_hermes_config(self) -> dict:
        """从 Hermes config.yaml 读取配置"""
        import yaml
        from pathlib import Path

        config_path = Path.home() / ".hermes" / "config.yaml"
        if not config_path.exists():
            return {}

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
            model_config = config.get("model", {})
            result = {
                "api_key": model_config.get("api_key"),
                "base_url": model_config.get("base_url"),
            }
            if model_config.get("provider") == "custom":
                providers = config.get("providers", {})
                for pconf in providers.values():
                    if pconf.get("base_url"):
                        result.setdefault("base_url", pconf.get("base_url"))
                    if pconf.get("api_key"):
                        result.setdefault("api_key", pconf.get("api_key"))
            return result
        except Exception:
            return {}

    async def generate_plan(self, task: str, context: dict = None) -> PlanGraph:
        """
        根据任务描述调用 LLM 生成执行计划。
        
        Args:
            task: 任务描述
            context: 可选上下文（项目路径、参考文档等）
            
        Returns:
            PlanGraph: LLM 生成的执行计划
        """
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"

        # 构建 prompt
        user_prompt = f"任务: {task}"
        if context:
            parts = []
            if context.get("project_path"):
                parts.append(f"项目路径: {context['project_path']}")
            if context.get("reference_docs"):
                parts.append(f"参考文档: {', '.join(context['reference_docs'])}")
            if context.get("previous_results"):
                parts.append(f"前置结果: {json.dumps(context['previous_results'], ensure_ascii=False)}")
            if context.get("extra_info"):
                parts.append(f"补充信息: {context['extra_info']}")
            if parts:
                user_prompt += "\n\n" + "\n".join(parts)

        # 调用 LLM
        response_text = await self._call_llm(user_prompt)

        # 解析 LLM 输出为 PlanGraph
        plan = self._parse_llm_response(response_text, task, plan_id)

        # 如果 LLM 返回空或解析失败，降级到默认计划
        if not plan.nodes:
            plan = self._default_plan(task, plan_id)

        return plan

    async def replan(self, current_plan: PlanGraph, failure_info: dict) -> PlanGraph:
        """
        根据失败信息重新规划。
        
        Args:
            current_plan: 当前计划
            failure_info: 失败信息 {"failed_node_id": "...", "error": "...", "context": {...}}
        """
        failed_id = failure_info.get("failed_node_id", "")
        error = failure_info.get("error", "")

        replan_prompt = f"""原任务: {current_plan.task}

当前计划:
{current_plan.to_json()}

失败节点: {failed_id}
失败原因: {error}

请调整计划：
1. 如果失败节点可以修复，添加 fix 节点并重新路由
2. 如果失败节点无法修复，移除该节点及其下游依赖
3. 保持 DAG 结构有效

以 JSON 格式输出调整后的 nodes 数组。"""

        response_text = await self._call_llm(replan_prompt)

        try:
            data = self._extract_json(response_text)
            plan = PlanGraph(
                id=f"{current_plan.id}-replan",
                task=f"{current_plan.task} (replanned)",
                plan_type="replan",
                status="draft",
                planner_model=self.model,
                metadata={"original_plan_id": current_plan.id, "failure_info": failure_info},
            )
            for node_data in data.get("nodes", []):
                node = self._parse_node(node_data)
                if node:
                    plan.add_node(node)
            if plan.nodes:
                plan.status = "approved"
                return plan
        except Exception as e:
            logger.warning("Replan 解析失败: %s", e)

        # 降级：在原计划上标记失败节点
        current_plan.status = "replan_failed"
        if failed_id in current_plan.nodes:
            current_plan.nodes[failed_id].status = NodeStatus.FAILED
            current_plan.nodes[failed_id].error = error
        return current_plan

    def validate_plan(self, plan: PlanGraph) -> tuple[bool, list[str]]:
        """验证 PlanGraph 是否有效"""
        errors = []

        if not plan.nodes:
            errors.append("计划中没有节点")
            return False, errors

        entry_nodes = plan.get_entry_nodes()
        if not entry_nodes:
            errors.append("没有入口节点（所有节点都有依赖）")

        try:
            plan.topological_sort()
        except ValueError as e:
            errors.append(str(e))

        for node_id, node in plan.nodes.items():
            if not node.name:
                errors.append(f"节点 {node_id} 缺少名称")
            for dep in node.dependencies:
                if dep not in plan.nodes:
                    errors.append(f"节点 {node_id} 依赖不存在的节点 {dep}")

        return len(errors) == 0, errors

    # ── 内部方法 ──

    async def _call_llm(self, user_prompt: str) -> str:
        """调用 LLM API"""
        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.3,  # 低温度保证 JSON 格式稳定
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            for block in response.content:
                if block.type == "text":
                    return block.text
            return ""
        except Exception as e:
            logger.error("LLM 调用失败: %s", e)
            raise

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从 LLM 响应中提取 JSON"""
        # 尝试直接解析
        text = text.strip()
        # 移除 Markdown 代码块
        if text.startswith("```"):
            lines = text.split("\n")
            # 去掉第一行 ```json 或 ```
            if lines[0].startswith("```"):
                lines = lines[1:]
            # 去掉最后一行 ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        return json.loads(text)

    def _parse_llm_response(self, text: str, task: str, plan_id: str) -> PlanGraph:
        """解析 LLM 输出为 PlanGraph"""
        try:
            data = self._extract_json(text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("LLM 响应 JSON 解析失败: %s\n原文: %s", e, text[:500])
            return PlanGraph(id=plan_id, task=task, plan_type="llm_failed", status="draft", planner_model=self.model)

        plan = PlanGraph(
            id=plan_id,
            task=task,
            plan_type="llm_generated",
            status="draft",
            planner_model=self.model,
        )

        nodes_data = data.get("nodes", [])
        if not isinstance(nodes_data, list):
            return plan

        for node_data in nodes_data:
            node = self._parse_node(node_data)
            if node:
                plan.add_node(node)

        if plan.nodes:
            plan.status = "approved"

        return plan

    def _parse_node(self, data: dict) -> Optional[PlanNode]:
        """解析单个节点数据"""
        try:
            node_id = data.get("id", "")
            name = data.get("name", "")
            description = data.get("description", "")
            node_type_str = data.get("type", "code_development")
            dependencies = data.get("dependencies", [])
            parallel_group = data.get("parallel_group")
            max_retries = data.get("max_retries", 2)
            timeout_seconds = data.get("timeout_seconds", 300)

            capability = _TASK_TYPE_TO_CAPABILITY.get(node_type_str, ExecutorCapability.GENERIC)

            return PlanNode(
                id=node_id,
                name=name,
                node_type=NodeType.TASK,
                description=description,
                required_capability=capability,
                dependencies=dependencies,
                parallel_group=parallel_group,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
            )
        except Exception as e:
            logger.warning("节点解析失败: %s, 数据: %s", e, data)
            return None

    @staticmethod
    def _default_plan(task: str, plan_id: str) -> PlanGraph:
        """降级默认计划"""
        plan = PlanGraph(
            id=plan_id,
            task=task,
            plan_type="default_fallback",
            status="draft",
        )

        default_steps = [
            ("req", "需求分析", ExecutorCapability.REQUIREMENTS_ANALYSIS, []),
            ("design", "技术设计", ExecutorCapability.TECHNICAL_DESIGN, ["req"]),
            ("dev", "开发实现", ExecutorCapability.CODE_DEVELOPMENT, ["design"]),
            ("review", "代码审查", ExecutorCapability.CODE_REVIEW, ["dev"]),
            ("test", "测试验证", ExecutorCapability.TESTING, ["review"]),
        ]

        for nid, name, cap, deps in default_steps:
            node = PlanNode(
                id=nid,
                name=name,
                required_capability=cap,
                dependencies=deps,
            )
            plan.add_node(node)

        plan.status = "approved"
        return plan

    def validate_plan(self, plan: PlanGraph) -> tuple[bool, list[str]]:
        """
        验证 PlanGraph 是否有效。
        
        Returns:
            (是否有效, 错误列表)
        """
        errors = []

        # 检查是否有节点
        if not plan.nodes:
            errors.append("计划中没有节点")
            return False, errors

        # 检查入口节点
        entry_nodes = plan.get_entry_nodes()
        if not entry_nodes:
            errors.append("没有入口节点（所有节点都有依赖）")

        # 检查拓扑排序（检测循环）
        try:
            plan.topological_sort()
        except ValueError as e:
            errors.append(str(e))

        # 检查每个节点
        for node_id, node in plan.nodes.items():
            if not node.name:
                errors.append(f"节点 {node_id} 缺少名称")
            # 检查依赖是否存在
            for dep in node.dependencies:
                if dep not in plan.nodes:
                    errors.append(f"节点 {node_id} 依赖不存在的节点 {dep}")

        return len(errors) == 0, errors
