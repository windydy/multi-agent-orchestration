"""
简单开发流水线示例

演示完整的开发流水线工作流
"""

import asyncio
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.workflows.runner import run_pipeline, WorkflowRunner
from src.workflows.builder import create_dev_pipeline


async def simple_pipeline_demo():
    """简单流水线演示
    
    自动运行完整流程（无人工审批）
    """
    print("=" * 60)
    print("简单开发流水线演示")
    print("=" * 60)
    
    # 检查API Key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n警告: 未设置ANTHROPIC_API_KEY环境变量")
        print("请设置: export ANTHROPIC_API_KEY='your-api-key'")
        print("\n使用模拟模式演示...")
        return mock_demo()
    
    # 定义任务
    task = """
    实现一个简单的Python计算器模块：
    
    1. 支持基本的四则运算（加减乘除）
    2. 支持括号优先级
    3. 提供错误处理（除零、无效表达式）
    4. 编写单元测试
    
    项目路径: ./demo_project/
    """
    
    print(f"\n任务: {task.strip()}")
    print("\n开始执行流水线...\n")
    
    # 运行流水线（禁用人工审批）
    result = await run_pipeline(
        task=task,
        project_path="./demo_project/",
        api_key=api_key,
        enable_human_review=False
    )
    
    if result.get("success"):
        print("\n✓ 流水线执行成功!")
        print(f"Thread ID: {result.get('thread_id')}")
        
        state = result.get("final_state", {})
        print(f"\n最终状态:")
        print(f"  当前阶段: {state.get('current_stage')}")
        print(f"  迭代次数: {state.get('iteration_count')}")
        print(f"  累计成本: ${state.get('total_cost', 0):.2f}")
        
        # 显示各阶段结果
        print("\n阶段结果摘要:")
        stages = ["requirements", "design", "code_changes", "review_result", "test_result"]
        for stage in stages:
            if state.get(stage):
                print(f"  ✓ {stage}: 已完成")
            else:
                print(f"  ○ {stage}: 未执行")
        
    else:
        print(f"\n✗ 流水线执行失败: {result.get('error')}")


async def interactive_pipeline_demo():
    """交互式流水线演示
    
    包含人工审批环节
    """
    print("=" * 60)
    print("交互式开发流水线演示")
    print("=" * 60)
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n警告: 未设置ANTHROPIC_API_KEY环境变量")
        return mock_demo()
    
    task = "实现一个Python函数，计算斐波那契数列的第N项"
    
    print(f"\n任务: {task}")
    
    runner = WorkflowRunner(api_key=api_key)
    
    # 运行直到中断
    print("\nPhase 1: 执行直到人工审批点...")
    result = await runner.run_until_interrupt(task, "./demo_project/")
    
    print(f"\nThread ID: {result['thread_id']}")
    print(f"当前状态: {result['current_state'].get('current_stage')}")
    
    # 模拟人工审批
    print("\n" + "=" * 60)
    print("模拟人工审批")
    print("=" * 60)
    
    print("\nReview结果:")
    review = result['current_state'].get('review_result', {})
    print(f"  通过: {review.get('approved', 'N/A')}")
    print(f"  分数: {review.get('overall_score', 'N/A')}")
    print(f"  总结: {review.get('summary', 'N/A')}")
    
    # 用户决定
    print("\n请选择:")
    print("  1. 审批通过")
    print("  2. 审批拒绝，返回修改")
    
    # 模拟用户选择（示例中自动通过）
    approval = True
    comment = "示例自动审批通过"
    
    print(f"\n选择: {'通过' if approval else '拒绝'}")
    
    # 恢复执行
    print("\nPhase 2: 恢复执行...")
    resume_result = await runner.resume(result['thread_id'], approval, comment)
    
    if resume_result.get("success"):
        print("\n✓ 流水线完成!")
        print_state(resume_result.get('final_state', {}))
    else:
        print(f"\n✗ 执行失败: {resume_result.get('error')}")


def print_state(state: dict):
    """打印状态摘要"""
    print("\n" + "-" * 40)
    print("执行摘要")
    print("-" * 40)
    print(f"任务: {state.get('task', 'N/A')}")
    print(f"最终阶段: {state.get('current_stage', 'N/A')}")
    print(f"迭代次数: {state.get('iteration_count', 0)}")
    print(f"成本: ${state.get('total_cost', 0):.2f}")
    
    messages = state.get('messages', [])
    print(f"\n消息 ({len(messages)} 条):")
    for msg in messages[-3:]:
        role = msg.get('role', 'unknown')
        content = str(msg.get('content', ''))[:50]
        print(f"  [{role}] {content}...")


def mock_demo():
    """模拟演示（无API Key时）"""
    print("\n" + "=" * 60)
    print("模拟演示")
    print("=" * 60)
    
    # 创建模拟状态
    mock_state = {
        "task": "实现斐波那契数列函数",
        "project_path": "./demo_project/",
        "current_stage": "test",
        "iteration_count": 1,
        "total_cost": 0.15,
        "messages": [
            {"role": "requirements", "content": "需求分析完成"},
            {"role": "design", "content": "技术设计完成"},
            {"role": "develop", "content": "代码实现完成"},
            {"role": "review", "content": "代码审查通过"},
            {"role": "test", "content": "测试通过"},
        ],
        "requirements": {"functional_requirements": [{"id": "FR-001", "description": "计算斐波那契数列"}]},
        "design": {"architecture": {"pattern": "单一模块"}},
        "code_changes": {"files_created": [{"path": "fibonacci.py"}]},
        "review_result": {"approved": True, "overall_score": 8},
        "test_result": {"passed": True, "coverage_percent": 95},
    }
    
    print_state(mock_state)
    
    print("\n工作流可视化:")
    pipeline = create_dev_pipeline()
    print(pipeline.get_workflow_graph())


if __name__ == "__main__":
    # 运行简单演示
    asyncio.run(simple_pipeline_demo())
    
    # 或运行交互式演示
    # asyncio.run(interactive_pipeline_demo())