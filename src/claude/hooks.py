"""
Claude Hooks实现

提供安全检查、日志记录、成本控制等Hooks
"""

from typing import Callable, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# 危险命令列表
DANGEROUS_COMMANDS = [
    "rm -rf",
    "rm -rf /",
    "sudo rm",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",
    "chmod -R 777 /",
    "chown -R",
    "> /dev/sda",
    "curl | sh",
    "wget | sh",
]

# 成本阈值
COST_THRESHOLDS = {
    "warning": 5.0,   # $5 警告
    "limit": 10.0,    # $10 限制
    "stop": 20.0      # $20 强制停止
}


def SafetyHook(hook_type: str, context: dict) -> Optional[dict]:
    """安全检查Hook
    
    检查危险命令并拦截
    """
    if hook_type == "pre_tool_call":
        tool = context.get("tool")
        input_data = context.get("input", {})
        
        # 检查bash命令
        if tool == "bash":
            command = input_data.get("command", "")
            
            # 检查危险命令
            for dangerous in DANGEROUS_COMMANDS:
                if dangerous in command:
                    logger.warning(f"安全拦截: 检测到危险命令 '{dangerous}'")
                    return {
                        "block": True,
                        "reason": f"安全检查: 禁止执行包含 '{dangerous}' 的命令"
                    }
            
            # 检查网络操作
            network_commands = ["curl", "wget", "nc", "telnet"]
            for net_cmd in network_commands:
                if net_cmd in command:
                    # 网络命令需要额外确认（可配置）
                    logger.info(f"网络命令检测: {net_cmd}")
        
        # 检查文件写入
        elif tool in ["write_file", "edit_file"]:
            path = input_data.get("path", "")
            
            # 禁止写入系统关键路径
            critical_paths = [
                "/etc/",
                "/usr/",
                "/bin/",
                "/sbin/",
                "/root/",
                "~/.ssh/",
            ]
            
            for critical in critical_paths:
                if critical in path or path.startswith(critical.replace("~", "")):
                    logger.warning(f"安全拦截: 禁止写入系统路径 '{critical}'")
                    return {
                        "block": True,
                        "reason": f"安全检查: 禁止写入系统路径 '{critical}'"
                    }
    
    return None


def LoggingHook(hook_type: str, context: dict) -> Optional[dict]:
    """日志记录Hook
    
    记录所有工具调用
    """
    if hook_type == "pre_tool_call":
        tool = context.get("tool")
        input_data = context.get("input", {})
        logger.info(f"[Tool Call] {tool}: {input_data}")
    
    elif hook_type == "post_tool_call":
        tool = context.get("tool")
        success = context.get("success")
        output_preview = str(context.get("output", ""))[:200]
        
        if success:
            logger.info(f"[Tool Success] {tool}: {output_preview}...")
        else:
            logger.error(f"[Tool Failed] {tool}: {output_preview}")
    
    return None


@dataclass
class CostTracker:
    """成本追踪器"""
    total_cost: float = 0.0
    thresholds: dict = None
    
    def __post_init__(self):
        self.thresholds = self.thresholds or COST_THRESHOLDS
    
    def check(self, cost: float) -> Optional[str]:
        """检查成本是否超限"""
        if cost > self.thresholds["stop"]:
            return "stop"
        elif cost > self.thresholds["limit"]:
            return "limit"
        elif cost > self.thresholds["warning"]:
            return "warning"
        return None


def CostHook(cost_tracker: CostTracker = None) -> Callable:
    """成本控制Hook
    
    返回一个配置好的Hook函数
    """
    tracker = cost_tracker or CostTracker()
    
    def hook(hook_type: str, context: dict) -> Optional[dict]:
        if hook_type == "post_tool_call":
            # 这里需要从Agent获取成本信息
            # 由于context中没有cost字段，我们假设Agent会传入
            current_cost = context.get("current_total_cost", 0.0)
            
            status = tracker.check(current_cost)
            
            if status == "stop":
                logger.error(f"成本超限: ${current_cost:.2f} > ${tracker.thresholds['stop']}")
                return {
                    "block": True,
                    "reason": f"成本控制: 已超过停止阈值 ${tracker.thresholds['stop']}"
                }
            
            elif status == "limit":
                logger.warning(f"成本警告: ${current_cost:.2f} > ${tracker.thresholds['limit']}")
            
            elif status == "warning":
                logger.info(f"成本提醒: ${current_cost:.2f} > ${tracker.thresholds['warning']}")
        
        return None
    
    return hook


def create_hooks(
    safety: bool = True,
    logging: bool = True,
    cost_control: bool = True,
    cost_thresholds: dict = None
) -> list[Callable]:
    """创建Hooks组合
    
    Args:
        safety: 启用安全检查
        logging: 启用日志记录
        cost_control: 启用成本控制
        cost_thresholds: 成本阈值配置
    
    Returns:
        Hooks列表
    """
    hooks = []
    
    if safety:
        hooks.append(SafetyHook)
    
    if logging:
        hooks.append(LoggingHook)
    
    if cost_control:
        tracker = CostTracker(thresholds=cost_thresholds)
        hooks.append(CostHook(tracker))
    
    return hooks