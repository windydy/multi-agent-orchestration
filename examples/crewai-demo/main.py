"""
CrewAI 角色扮演协作示例

演示如何使用CrewAI构建一个内容创作团队:
- 编辑: 确定内容方向和主题
- 研究员: 收集素材和信息
- 作者: 撰写内容
- 审校: 检查和完善内容
"""

# 注意: 需要先安装crewai
# pip install crewai

# ============== Agent定义 ==============

def create_agents():
    """创建CrewAI Agent团队"""
    
    try:
        from crewai import Agent
    except ImportError:
        print("需要安装crewai: pip install crewai")
        return None
    
    # 编辑
    editor = Agent(
        role="内容编辑",
        goal="确定内容方向，规划文章结构",
        backstory="""你是一位资深编辑，擅长内容策划。
        你能够把握读者需求，制定清晰的内容规划。
        你注重内容的逻辑性和可读性。""",
        verbose=True,
        allow_delegation=True
    )
    
    # 研究员
    researcher = Agent(
        role="内容研究员",
        goal="收集素材，挖掘关键信息",
        backstory="""你是一名专业研究员。
        你擅长从各种来源收集信息。
        你能够识别关键事实和数据。
        你的研究为内容提供坚实基础。""",
        verbose=True
    )
    
    # 作者
    writer = Agent(
        role="内容作者",
        goal="撰写高质量内容",
        backstory="""你是一位优秀的内容创作者。
        你能够将复杂信息转化为易懂的文字。
        你注重文笔优美和表达准确。
        你的文章深受读者喜爱。""",
        verbose=True
    )
    
    # 审校
    proofreader = Agent(
        role="内容审校",
        goal="检查和完善内容",
        backstory="""你是一位专业的审校编辑。
        你擅长发现文字错误和逻辑问题。
        你确保内容准确、流畅、规范。
        你的审校让内容更加完美。""",
        verbose=True
    )
    
    return editor, researcher, writer, proofreader


def create_tasks(agents):
    """创建任务"""
    
    try:
        from crewai import Task
    except ImportError:
        return None
    
    editor, researcher, writer, proofreader = agents
    
    # 任务1: 内容规划
    plan_task = Task(
        description="根据主题 {topic} 制定内容规划，确定文章结构",
        agent=editor,
        expected_output="文章大纲和关键要点"
    )
    
    # 任务2: 研究素材
    research_task = Task(
        description="围绕 {topic} 收集素材和关键信息",
        agent=researcher,
        expected_output="素材清单和关键发现"
    )
    
    # 任务3: 撰写内容
    write_task = Task(
        description="基于大纲和素材撰写完整文章",
        agent=writer,
        expected_output="完整文章初稿",
        context=[plan_task, research_task]  # 依赖前两个任务
    )
    
    # 任务4: 审校内容
    proofread_task = Task(
        description="审校文章，修正错误，优化表达",
        agent=proofreader,
        expected_output="最终版本文章",
        context=[write_task]
    )
    
    return [plan_task, research_task, write_task, proofread_task]


def create_crew(agents, tasks):
    """创建Crew"""
    
    try:
        from crewai import Crew, Process
    except ImportError:
        return None
    
    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,  # 顺序执行
        verbose=True
    )
    
    return crew


# ============== 运行示例 ==============

def run_demo():
    """运行演示"""
    
    print("=" * 60)
    print("CrewAI 角色扮演协作示例")
    print("=" * 60)
    
    agents = create_agents()
    
    if agents is None:
        print("Agent创建失败，请先安装crewai")
        print("\n使用模拟方式演示:")
        return run_mock_demo()
    
    tasks = create_tasks(agents)
    crew = create_crew(agents, tasks)
    
    print("\n任务: 撰写一篇关于AI发展趋势的文章")
    print("\n开始CrewAI协作...\n")
    
    # 执行
    result = crew.kickoff(inputs={"topic": "2024年AI发展趋势"})
    
    print("\n" + "=" * 60)
    print("协作完成!")
    print("=" * 60)
    print(f"\n最终输出:\n{result}")
    
    return result


def run_mock_demo():
    """模拟演示"""
    
    print("\n" + "-" * 40)
    print("模拟CrewAI协作流程")
    print("-" * 40)
    
    print("\n任务主题: 2024年AI发展趋势")
    
    # 模拟顺序执行
    steps = [
        ("内容编辑", "制定大纲", """
        文章大纲:
        1. 引言 - AI的快速发展
        2. 大语言模型进展
        3. 多模态AI兴起
        4. Agent自主化趋势
        5. AI安全和伦理
        6. 总结展望
        """),
        
        ("内容研究员", "收集素材", """
        关键素材:
        - GPT-4V多模态能力
        - AutoGen/CrewAI等Agent框架
        - 各公司AI安全举措
        - 行业预测报告数据
        """),
        
        ("内容作者", "撰写文章", """
        文章初稿(摘要):
        2024年AI领域迎来多项突破...
        大语言模型向多模态发展...
        自主Agent成为新热点...
        """),
        
        ("内容审校", "审校完善", """
        最终版本:
        [修正了3处表述]
        [优化了2处逻辑]
        [补充了关键数据]
        
        文章已完善，可以发布。
        """)
    ]
    
    for agent, action, output in steps:
        print(f"\n[{agent}] 执行: {action}")
        print(output[:150] + "..." if len(output) > 150 else output)
    
    print("\n" + "=" * 60)
    print("模拟协作完成!")
    print("=" * 60)


# ============== 可视化 ==============

def visualize_workflow():
    """可视化工作流"""
    
    print("\nCrewAI工作流 (Mermaid格式):")
    print("""
    graph TD
        Editor[编辑] -->|大纲| Researcher[研究员]
        Researcher -->|素材| Writer[作者]
        Writer -->|初稿| Proofreader[审校]
        Proofreader -->|终稿| Output
        
        subgraph 顺序执行
        Editor --> Researcher --> Writer --> Proofreader
        end
    """)


if __name__ == "__main__":
    run_demo()
    visualize_workflow()