"""
LangGraph 多Agent协作示例

演示如何使用LangGraph构建一个简单的多Agent协作系统:
- 研究员: 搜索和收集信息
- 分析师: 分析信息并生成洞察
- 作者: 撰写最终报告
"""

# 注意: 需要先安装langgraph
# pip install langgraph langchain-openai

from typing import TypedDict, Annotated
import operator

# ============== 状态定义 ==============

class WorkflowState(TypedDict):
    """工作流状态"""
    messages: Annotated[list, operator.add]  # 消息列表，累加
    task: str                                 # 原始任务
    research_results: str                     # 研究结果
    analysis_results: str                     # 分析结果
    final_report: str                         # 最终报告
    current_step: str                         # 当前步骤


# ============== Agent函数定义 ==============

def researcher_node(state: WorkflowState) -> dict:
    """研究员节点: 搜索和收集信息"""
    task = state["task"]
    
    # 模拟研究过程 (实际会调用搜索API)
    research_results = f"""
    研究任务: {task}
    
    收集到的关键信息:
    1. 基础概念和定义
    2. 主要技术方案
    3. 行业最佳实践
    4. 相关案例研究
    
    数据来源: 学术论文、技术文档、行业报告
    """
    
    return {
        "research_results": research_results,
        "current_step": "research_complete",
        "messages": [{"role": "researcher", "content": "研究完成，已收集相关信息"}]
    }


def analyst_node(state: WorkflowState) -> dict:
    """分析师节点: 分析信息并生成洞察"""
    research = state["research_results"]
    
    # 模拟分析过程
    analysis_results = f"""
    基于研究结果的分析:
    
    {research}
    
    核心洞察:
    - 发现了3种主流方案
    - 方案A适合大规模场景
    - 方案B适合快速原型
    - 方案C平衡两者
    
    建议: 根据具体需求选择合适方案
    """
    
    return {
        "analysis_results": analysis_results,
        "current_step": "analysis_complete",
        "messages": [{"role": "analyst", "content": "分析完成，已生成洞察"}]
    }


def writer_node(state: WorkflowState) -> dict:
    """作者节点: 撰写最终报告"""
    research = state["research_results"]
    analysis = state["analysis_results"]
    task = state["task"]
    
    final_report = f"""
    # 任务报告: {task}
    
    ## 研究发现
    {research}
    
    ## 分析洞察
    {analysis}
    
    ## 结论
    本次调研提供了关于{task}的全面分析，建议根据实际场景选择合适方案。
    """
    
    return {
        "final_report": final_report,
        "current_step": "report_complete",
        "messages": [{"role": "writer", "content": "报告撰写完成"}]
    }


# ============== 构建工作流 ==============

def build_workflow():
    """构建LangGraph工作流"""
    
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        print("需要安装langgraph: pip install langgraph")
        return None
    
    # 创建状态图
    workflow = StateGraph(WorkflowState)
    
    # 添加节点
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("writer", writer_node)
    
    # 定义边 (工作流顺序)
    workflow.add_edge("researcher", "analyst")
    workflow.add_edge("analyst", "writer")
    workflow.add_edge("writer", END)
    
    # 设置入口点
    workflow.set_entry_point("researcher")
    
    # 编译工作流
    return workflow.compile()


# ============== 运行示例 ==============

def run_demo():
    """运行演示"""
    
    print("=" * 60)
    print("LangGraph 多Agent协作示例")
    print("=" * 60)
    
    # 构建工作流
    app = build_workflow()
    
    if app is None:
        print("工作流构建失败，请先安装langgraph")
        print("\n使用模拟方式演示:")
        return run_mock_demo()
    
    # 初始状态
    initial_state = {
        "task": "多Agent工作流编排技术调研",
        "messages": [],
        "research_results": "",
        "analysis_results": "",
        "final_report": "",
        "current_step": "start"
    }
    
    print(f"\n任务: {initial_state['task']}")
    print("\n执行工作流...")
    
    # 执行
    result = app.invoke(initial_state)
    
    print("\n" + "=" * 60)
    print("执行完成!")
    print("=" * 60)
    print(f"\n当前步骤: {result['current_step']}")
    print(f"\n消息历史:")
    for msg in result['messages']:
        print(f"  - [{msg['role']}]: {msg['content']}")
    
    print(f"\n最终报告:")
    print(result['final_report'])
    
    return result


def run_mock_demo():
    """模拟演示 (不需要langgraph)"""
    
    print("\n" + "-" * 40)
    print("模拟执行工作流")
    print("-" * 40)
    
    state = {
        "task": "多Agent工作流编排技术调研",
        "messages": [],
        "research_results": "",
        "analysis_results": "",
        "final_report": "",
        "current_step": "start"
    }
    
    print(f"\n初始任务: {state['task']}")
    
    # 顺序执行各节点
    print("\n[1] 研究员节点执行...")
    update = researcher_node(state)
    state.update(update)
    print(f"    -> 状态更新: {state['current_step']}")
    
    print("\n[2] 分析师节点执行...")
    update = analyst_node(state)
    state.update(update)
    print(f"    -> 状态更新: {state['current_step']}")
    
    print("\n[3] 作者节点执行...")
    update = writer_node(state)
    state.update(update)
    print(f"    -> 状态更新: {state['current_step']}")
    
    print("\n" + "=" * 60)
    print("模拟执行完成!")
    print("=" * 60)
    
    print("\n最终报告:")
    print(state['final_report'])
    
    return state


# ============== 可视化工作流 ==============

def visualize_workflow():
    """生成工作流可视化"""
    
    print("\n工作流结构 (Mermaid格式):")
    print("""
    graph TD
        START --> researcher[研究员]
        researcher --> analyst[分析师]
        analyst --> writer[作者]
        writer --> END
        
        researcher --> |研究信息| analyst
        analyst --> |分析洞察| writer
        writer --> |最终报告| END
    """)


if __name__ == "__main__":
    run_demo()
    visualize_workflow()