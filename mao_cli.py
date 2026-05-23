#!/usr/bin/env python3
"""
Multi-Agent Orchestration CLI — standalone entry point for PyInstaller packaging.
"""

import sys
import os
import asyncio
import argparse
import json
from datetime import datetime

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.plan.planner import PlannerAgent
from src.workflows.runner import WorkflowRunner, print_state_summary


def main():
    """CLI主入口"""
    parser = argparse.ArgumentParser(
        description="Multi-Agent Orchestration CLI — Planner-driven workflow"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # run命令
    run_parser = subparsers.add_parser("run", help="运行工作流（Planner自动规划）")
    run_parser.add_argument("task", help="任务描述")
    run_parser.add_argument("--path", default=".", help="项目路径")
    run_parser.add_argument("--model", default="qwen3.6-plus", help="Planner使用的模型")
    run_parser.add_argument("--thread-id", help="会话ID")
    
    # status命令
    status_parser = subparsers.add_parser("status", help="查看执行状态")
    status_parser.add_argument("thread_id", help="会话ID")
    
    # list命令
    list_parser = subparsers.add_parser("list", help="列出当前进程的执行记录")
    
    args = parser.parse_args()
    
    if args.command == "run":
        asyncio.run(run_command(args))
    elif args.command == "status":
        status_command(args)
    elif args.command == "list":
        list_command(args)
    else:
        parser.print_help()


async def run_command(args):
    """执行run命令"""
    print(f"\n任务: {args.task}")
    print(f"项目路径: {args.path}")
    print(f"Planner模型: {args.model}")
    print("\n开始执行...\n")
    
    # 初始化 PlannerAgent（必须路径）
    try:
        planner = PlannerAgent(model=args.model)
    except Exception as e:
        print(f"\n✗ PlannerAgent 初始化失败: {e}")
        print("请确保 API Key 已配置 (DASHSCOPE_API_KEY / ANTHROPIC_API_KEY)")
        return
    
    # 创建 WorkflowRunner
    runner = WorkflowRunner(planner=planner)
    
    # 执行
    result = await runner.run(args.task, args.path, args.thread_id)
    
    if result.get("success"):
        print("\n✓ 执行成功!")
        summary = result.get("summary", {})
        print(f"  计划ID: {result.get('plan_id', 'N/A')}")
        print(f"  节点数: {result.get('node_count', 0)}")
        print(f"  验证结果: {summary.get('verification', 'N/A')}")
        print(f"  执行节点: {', '.join(summary.get('nodes', []))}")
    else:
        print(f"\n✗ 执行失败: {result.get('error')}")
    
    # 保存thread_id
    thread_file = f".pipeline_thread_{datetime.now().strftime('%Y%m%d')}.txt"
    tid = result.get("thread_id", "")
    if tid:
        with open(thread_file, "w") as f:
            f.write(tid)
        print(f"\nThread ID: {tid}")
        print(f"已保存到: {thread_file}")


def status_command(args):
    """执行status命令"""
    planner = PlannerAgent()
    runner = WorkflowRunner(planner=planner)
    state = runner.get_state(args.thread_id)
    
    if "error" in state:
        print(f"\n{state['error']}")
        return
    
    print(f"\n执行: {args.thread_id}")
    print(f"  状态: {state.get('status', 'N/A')}")
    print(f"  任务: {state.get('task', 'N/A')}")
    print(f"  开始: {state.get('start_time', 'N/A')}")


def list_command(args):
    """执行list命令"""
    planner = PlannerAgent()
    runner = WorkflowRunner(planner=planner)
    executions = runner.list_executions()
    
    if not executions:
        print("\n无执行记录（当前进程）")
        return
    
    print(f"\n执行记录 ({len(executions)} 条)")
    print("-" * 60)
    
    for e in executions:
        status_icon = "✓" if e.get("status") == "completed" else "✗" if e.get("status") == "failed" else "○"
        print(f"{status_icon} {e['thread_id']}")
        print(f"  任务: {e.get('task', 'N/A')}")
        print(f"  状态: {e.get('status', 'N/A')}")
        print(f"  开始: {e.get('start_time', 'N/A')}")


if __name__ == "__main__":
    main()
