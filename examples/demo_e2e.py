"""
端到端真实流程 Demo — 从需求到代码的完整流程

使用真实 API（Hermes config.yaml 配置），演示：
1. 需求分析 Agent 真实执行
2. 设计 Agent 真实执行  
3. 开发 Agent 真实创建文件
4. 事件写入 EventLog（WebUI 可查看）
"""

import asyncio
import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def demo_e2e_pipeline():
    """端到端流水线执行 demo"""
    from src.api.services.event_log import EventLog
    from src.agents import create_requirements_agent, create_designer_agent, create_developer_agent
    from src.workflows.states import create_initial_state

    thread_id = f"demo_{uuid.uuid4().hex[:8]}"
    event_log = EventLog(db_path="./checkpoints/events.db")

    task = "创建一个 Python TODO list 应用，支持添加/删除/查看任务，保存到 JSON 文件"

    print(f"\n{'=' * 60}")
    print(f"🚀 端到端流水线 Demo（真实 API）")
    print(f"{'=' * 60}")
    print(f"📌 Thread ID: {thread_id}")
    print(f"📌 任务: {task[:50]}...")

    # 记录执行开始
    event_log.log(thread_id=thread_id, event_type="execution_started",
                  timestamp=time.time(), data={"task": task})

    # 创建项目目录
    project_dir = "./demo_project"
    os.makedirs(project_dir, exist_ok=True)

    # ===== 阶段 1: 需求分析 =====
    print(f"\n📋 阶段 1/3: 需求分析...")
    event_log.log(thread_id=thread_id, event_type="node_started",
                  timestamp=time.time(), node_name="requirements")

    req_agent = create_requirements_agent()
    req_result = await req_agent.run(task)

    print(f"   ✅ 需求分析完成 ({req_result.metadata.get('iterations', '?')} iterations)")
    if req_result.output:
        print(f"   📄 输出: {req_result.output[:200].replace(chr(10), ' ')}...")

        # 保存需求文档
        req_doc_path = os.path.join(project_dir, "docs", "requirements.md")
        os.makedirs(os.path.dirname(req_doc_path), exist_ok=True)
        with open(req_doc_path, "w") as f:
            f.write(f"# 需求分析文档\n\n")
            f.write(f"**任务**: {task}\n")
            f.write(f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(req_result.output)
        print(f"   📁 已保存: {req_doc_path}")

    event_log.log(thread_id=thread_id, event_type="node_completed",
                  timestamp=time.time(), node_name="requirements",
                  data={"success": req_result.success,
                        "output_summary": req_result.output[:500] if req_result.output else None})

    # ===== 阶段 2: 技术设计 =====
    print(f"\n📋 阶段 2/3: 技术设计...")
    event_log.log(thread_id=thread_id, event_type="node_started",
                  timestamp=time.time(), node_name="design")

    design_agent = create_designer_agent()
    design_context = {"previous_results": {"requirements": req_result.output}}
    design_result = await design_agent.run(task, design_context)

    print(f"   ✅ 技术设计完成 ({design_result.metadata.get('iterations', '?')} iterations)")
    if design_result.output:
        print(f"   📄 输出: {design_result.output[:200].replace(chr(10), ' ')}...")

        # 保存设计文档
        design_doc_path = os.path.join(project_dir, "docs", "design.md")
        os.makedirs(os.path.dirname(design_doc_path), exist_ok=True)
        with open(design_doc_path, "w") as f:
            f.write(f"# 技术设计文档\n\n")
            f.write(f"**任务**: {task}\n")
            f.write(f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(design_result.output)
        print(f"   📁 已保存: {design_doc_path}")

    event_log.log(thread_id=thread_id, event_type="node_completed",
                  timestamp=time.time(), node_name="design",
                  data={"success": design_result.success,
                        "output_summary": design_result.output[:500] if design_result.output else None})

    # ===== 阶段 3: 代码开发 =====
    print(f"\n📋 阶段 3/3: 代码开发...")
    event_log.log(thread_id=thread_id, event_type="node_started",
                  timestamp=time.time(), node_name="develop")

    dev_agent = create_developer_agent()
    dev_context = {
        "previous_results": {
            "requirements": req_result.output,
            "design": design_result.output
        },
        "project_path": project_dir
    }
    dev_result = await dev_agent.run(task, dev_context)

    print(f"   ✅ 代码开发完成 ({dev_result.metadata.get('iterations', '?')} iterations)")
    if dev_result.output:
        print(f"   📄 输出: {dev_result.output[:300].replace(chr(10), ' ')}...")

    event_log.log(thread_id=thread_id, event_type="node_completed",
                  timestamp=time.time(), node_name="develop",
                  data={"success": dev_result.success})

    # ===== 执行完成 =====
    event_log.log(thread_id=thread_id, event_type="execution_completed",
                  timestamp=time.time(),
                  data={"nodes": ["requirements", "design", "develop"]})

    # ===== 打印创建的文件 =====
    print(f"\n{'=' * 60}")
    print(f"✅ 流水线执行完成!")
    print(f"{'=' * 60}")

    print(f"\n📁 创建的文件:")
    for root, dirs, files in os.walk(project_dir):
        for f in files:
            filepath = os.path.join(root, f)
            size = os.path.getsize(filepath)
            print(f"   📄 {filepath} ({size} bytes)")

    print(f"\n📊 统计:")
    total_iters = (req_result.metadata.get('iterations', 0) +
                   design_result.metadata.get('iterations', 0) +
                   dev_result.metadata.get('iterations', 0))
    print(f"   总迭代: {total_iters}")

    return thread_id


async def main():
    try:
        thread_id = await demo_e2e_pipeline()

        print(f"\n{'=' * 60}")
        print(f"📌 WebUI 查看方式:")
        print(f"   1. 启动 WebUI: python -m src.api.server")
        print(f"   2. 浏览器访问: http://localhost:8000")
        print(f"   3. 找到 Thread ID: {thread_id}")
        print(f"{'=' * 60}\n")
    except Exception as e:
        print(f"\n❌ Demo 失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
