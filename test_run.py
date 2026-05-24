"""
简单测试任务：实现一个斐波那契数列函数

测试多Agent开发流水线
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 初始化日志 ──
from src.logging_config import setup_logging
setup_logging(level="INFO")

from src.workflows.runner import run_pipeline


async def test_pipeline():
    """运行测试任务"""
    
    # 创建临时项目目录
    project_dir = tempfile.mkdtemp(prefix="pipeline_test_")
    
    task = """
    实现一个斐波那契数列函数：
    
    1. 创建 fibonacci.py 文件
    2. 实现 fib(n) 函数，返回第 n 项斐波那契数
    3. n=0 返回 0, n=1 返回 1
    4. 使用迭代方式实现（不要递归）
    5. 创建简单的测试文件 test_fibonacci.py
    
    项目路径: {project_dir}
    """.replace("{project_dir}", project_dir)
    
    print("=" * 60)
    print("测试任务: 实现斐波那契数列")
    print("=" * 60)
    print(f"\n项目目录: {project_dir}")
    print(f"\n开始执行流水线...\n")
    
    # 运行流水线
    result = await run_pipeline(
        task=task,
        project_path=project_dir,
        enable_human_review=False  # 自动模式，无人工审批
    )
    
    print("\n" + "=" * 60)
    print("执行结果")
    print("=" * 60)
    
    if result.get("success"):
        print("\n✓ 流水线执行成功!")
        
        state = result.get("final_state", {})
        print(f"\n最终阶段: {state.get('current_stage')}")
        print(f"迭代次数: {state.get('iteration_count')}")
        
        # 检查生成的文件
        print("\n生成的文件:")
        for f in os.listdir(project_dir):
            filepath = os.path.join(project_dir, f)
            if os.path.isfile(filepath):
                size = os.path.getsize(filepath)
                print(f"  {f} ({size} bytes)")
        
        # 显示代码内容
        fib_file = os.path.join(project_dir, "fibonacci.py")
        if os.path.exists(fib_file):
            print("\nfibonacci.py 内容:")
            with open(fib_file) as f:
                print(f.read())
        
    else:
        print(f"\n✗ 执行失败: {result.get('error')}")
    
    # 清理
    print(f"\n项目目录保留在: {project_dir}")
    print("(可手动删除查看结果)")
    
    return result


if __name__ == "__main__":
    asyncio.run(test_pipeline())