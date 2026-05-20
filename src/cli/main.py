"""
CLI入口

提供命令行交互界面
"""

import asyncio
import argparse
import json
import os
from datetime import datetime

from ..workflows.runner import WorkflowRunner, run_pipeline, print_state_summary
from ..workflows.builder import create_dev_pipeline


def main():
    """CLI主入口"""
    parser = argparse.ArgumentParser(
        description="LangGraph + Claude Agent SDK 开发流水线"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # run命令
    run_parser = subparsers.add_parser("run", help="运行开发流水线")
    run_parser.add_argument("task", help="任务描述")
    run_parser.add_argument("--path", default=".", help="项目路径")
    run_parser.add_argument("--api-key", help="Claude API密钥（默认从环境变量获取）")
    run_parser.add_argument("--no-review", action="store_true", help="禁用人工审批")
    run_parser.add_argument("--thread-id", help="会话ID（用于恢复）")
    
    # resume命令
    resume_parser = subparsers.add_parser("resume", help="恢复中断的工作流")
    resume_parser.add_argument("thread_id", help="会话ID")
    resume_parser.add_argument("--approve", action="store_true", default=True, help="审批通过")
    resume_parser.add_argument("--reject", action="store_false", dest="approve", help="审批拒绝")
    resume_parser.add_argument("--comment", default="", help="审批意见")
    resume_parser.add_argument("--api-key", help="Claude API密钥")
    
    # status命令
    status_parser = subparsers.add_parser("status", help="查看执行状态")
    status_parser.add_argument("thread_id", help="会话ID")
    status_parser.add_argument("--api-key", help="Claude API密钥")
    
    # history命令
    history_parser = subparsers.add_parser("history", help="查看执行历史")
    history_parser.add_argument("thread_id", help="会话ID")
    history_parser.add_argument("--api-key", help="Claude API密钥")
    
    # list命令
    list_parser = subparsers.add_parser("list", help="列出所有执行")
    list_parser.add_argument("--api-key", help="Claude API密钥")
    
    # visualize命令
    viz_parser = subparsers.add_parser("visualize", help="显示工作流图")
    
    args = parser.parse_args()
    
    if args.command == "run":
        asyncio.run(run_command(args))
    elif args.command == "resume":
        asyncio.run(resume_command(args))
    elif args.command == "status":
        status_command(args)
    elif args.command == "history":
        history_command(args)
    elif args.command == "list":
        list_command(args)
    elif args.command == "visualize":
        visualize_command()
    else:
        parser.print_help()


async def run_command(args):
    """执行run命令"""
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    
    runner = WorkflowRunner(api_key=api_key)
    
    print(f"\n任务: {args.task}")
    print(f"项目路径: {args.path}")
    print(f"人工审批: {'启用' if not args.no_review else '禁用'}")
    print("\n开始执行...\n")
    
    if args.no_review:
        # 直接运行完整流程
        result = await runner.run(args.task, args.path, args.thread_id)
        
        if result.get("success"):
            print("\n✓ 执行成功!")
            print_state_summary(result.get("final_state", {}))
        else:
            print(f"\n✗ 执行失败: {result.get('error')}")
    else:
        # 运行直到中断
        result = await runner.run_until_interrupt(args.task, args.path, args.thread_id)
        
        print("\n工作流已暂停，等待人工审批")
        print_state_summary(result.get("current_state", {}))
        
        print("\n使用以下命令继续:")
        print(f"  python -m src.cli.main resume {result['thread_id']} --approve/--reject --comment '意见'")
    
    # 保存thread_id
    thread_file = f".pipeline_thread_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(thread_file, "w") as f:
        f.write(result.get("thread_id", ""))
    print(f"\nThread ID 已保存到: {thread_file}")


async def resume_command(args):
    """执行resume命令"""
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    
    runner = WorkflowRunner(api_key=api_key)
    
    print(f"\n恢复工作流: {args.thread_id}")
    print(f"审批结果: {'通过' if args.approve else '拒绝'}")
    print(f"审批意见: {args.comment or '无'}")
    
    result = await runner.resume(args.thread_id, args.approve, args.comment)
    
    if result.get("success"):
        print("\n✓ 执行成功!")
        print_state_summary(result.get("final_state", {}))
    else:
        print(f"\n✗ 执行失败: {result.get('error')}")


def status_command(args):
    """执行status命令"""
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    
    runner = WorkflowRunner(api_key=api_key)
    state = runner.get_state(args.thread_id)
    
    print_state_summary(state.get("values", {}))
    
    if state.get("next"):
        print(f"\n下一步: {state['next']}")


def history_command(args):
    """执行history命令"""
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    
    runner = WorkflowRunner(api_key=api_key)
    history = runner.get_history(args.thread_id)
    
    print(f"\n执行历史 ({len(history)} 条记录)")
    print("-" * 60)
    
    for h in history:
        print(f"Step {h['step']}: {h['values'].get('current_stage', 'N/A')}")
        print(f"  时间: {h['created_at']}")


def list_command(args):
    """执行list命令"""
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    
    runner = WorkflowRunner(api_key=api_key)
    executions = runner.list_executions()
    
    if not executions:
        print("\n无执行记录")
        return
    
    print(f"\n执行记录 ({len(executions)} 条)")
    print("-" * 60)
    
    for e in executions:
        status_icon = "✓" if e["status"] == "completed" else "○"
        print(f"{status_icon} {e['thread_id']}")
        print(f"  任务: {e['task']}")
        print(f"  状态: {e['status']}")
        print(f"  开始: {e['start_time']}")


def visualize_command():
    """显示工作流可视化"""
    pipeline = create_dev_pipeline()
    
    print("\n工作流结构 (Mermaid格式):")
    print(pipeline.get_workflow_graph())
    
    print("\n提示: 将以上内容粘贴到 https://mermaid.live 进行可视化")


if __name__ == "__main__":
    main()