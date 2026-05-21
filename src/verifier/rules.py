"""
Phase 4: VerifierFramework — 验证框架

src/verifier/rules.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import asyncio
import subprocess
import logging

logger = logging.getLogger(__name__)


class VerificationDimension(Enum):
    """验证维度"""
    QUALITY = "quality"
    SECURITY = "security"
    CORRECTNESS = "correctness"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"


class VerificationStatus(Enum):
    """验证状态"""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class VerificationItem:
    """单次验证的结果"""
    rule_id: str
    dimension: VerificationDimension
    status: VerificationStatus
    score: float
    message: str = ""


@dataclass
class VerificationRule:
    """验证规则定义"""
    rule_id: str
    dimension: VerificationDimension
    check: str = ""
    """shell 命令或验证逻辑描述"""
    timeout: int = 60
    severity: str = "warning"


@dataclass
class VerificationResult:
    """节点验证结果汇总"""
    node_id: str
    items: list[VerificationItem] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(item.status != VerificationStatus.FAILED for item in self.items)

    @property
    def overall_score(self) -> float:
        if not self.items:
            return 1.0
        return sum(item.score for item in self.items) / len(self.items)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "passed": self.passed,
            "overall_score": self.overall_score,
            "items": [
                {
                    "rule_id": item.rule_id,
                    "dimension": item.dimension.value,
                    "status": item.status.value,
                    "score": item.score,
                    "message": item.message,
                }
                for item in self.items
            ],
        }


class VerifierFramework:
    """
    验证框架。
    
    支持：
    - 注册验证规则
    - 执行规则（shell 命令或内建检查）
    - 聚合结果
    """

    def __init__(self):
        self._rules: dict[str, VerificationRule] = {}

    def register_rule(self, rule: VerificationRule) -> None:
        """注册一条验证规则"""
        self._rules[rule.rule_id] = rule

    def unregister_rule(self, rule_id: str) -> bool:
        """注销一条规则"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    async def verify_all(self, node_id: str, context: dict) -> VerificationResult:
        """
        执行所有已注册的规则。
        
        Args:
            node_id: 节点 ID
            context: 执行上下文（包含 output 等）
            
        Returns:
            VerificationResult: 验证结果汇总
        """
        items = []
        for rule in self._rules.values():
            item = await self._execute_rule(rule, context)
            items.append(item)

        return VerificationResult(node_id=node_id, items=items)

    async def _execute_rule(
        self, rule: VerificationRule, context: dict
    ) -> VerificationItem:
        """执行单条验证规则"""
        try:
            if rule.check:
                # shell 命令检查
                proc = await asyncio.create_subprocess_shell(
                    rule.check,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=rule.timeout
                    )
                    if proc.returncode == 0:
                        return VerificationItem(
                            rule_id=rule.rule_id,
                            dimension=rule.dimension,
                            status=VerificationStatus.PASSED,
                            score=1.0,
                            message=stdout.decode().strip()[:200],
                        )
                    else:
                        return VerificationItem(
                            rule_id=rule.rule_id,
                            dimension=rule.dimension,
                            status=VerificationStatus.FAILED,
                            score=0.0,
                            message=stderr.decode().strip()[:200],
                        )
                except asyncio.TimeoutError:
                    proc.kill()
                    return VerificationItem(
                        rule_id=rule.rule_id,
                        dimension=rule.dimension,
                        status=VerificationStatus.FAILED,
                        score=0.0,
                        message=f"Rule timed out after {rule.timeout}s",
                    )
            else:
                # 没有 check 命令，默认通过
                return VerificationItem(
                    rule_id=rule.rule_id,
                    dimension=rule.dimension,
                    status=VerificationStatus.PASSED,
                    score=1.0,
                    message="No check defined, passed by default",
                )
        except Exception as e:
            return VerificationItem(
                rule_id=rule.rule_id,
                dimension=rule.dimension,
                status=VerificationStatus.FAILED,
                score=0.0,
                message=str(e),
            )
