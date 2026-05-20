"""
AutoGen 多Agent对话协作示例

演示如何使用AutoGen构建一个代码审查团队:
- 用户代理: 代表用户意图
- 开发者: 编写代码
- 审查者: 审查代码质量
- 测试者: 测试代码功能
"""

# 注意: 需要先安装autogen
# pip install pyautogen

# ============== 配置 ==============

def get_llm_config():
    """获取LLM配置"""
    return {
        "model": "gpt-4",
        "api_key": "YOUR_API_KEY",  # 实际使用时替换
        # 或使用其他提供商
        # "api_base": "https://api.deepseek.com/v1",
        # "model": "deepseek-chat",
    }


# ============== Agent定义 ==============

def create_agents():
    """创建AutoGen Agent团队"""
    
    try:
        import autogen
    except ImportError:
        print("需要安装autogen: pip install pyautogen")
        return None
    
    llm_config = {"config_list": [{"model": "gpt-4", "api_key": "YOUR_KEY"}]}
    
    # 用户代理
    user_proxy = autogen.UserProxyAgent(
        name="User",
        system_message="用户代表，提出需求和反馈",
        human_input_mode="TERMINATE",  # 最后需要用户确认终止
        code_execution_config={"use_docker": False},
        max_consecutive_auto_reply=3
    )
    
    # 开发者
    developer = autogen.AssistantAgent(
        name="Developer",
        system_message="""你是一名资深开发者。
        根据用户需求编写高质量代码。
        代码应该简洁、可读、遵循最佳实践。
        在代码中添加必要的注释和文档。""",
        llm_config=llm_config
    )
    
    # 审查者
    reviewer = autogen.AssistantAgent(
        name="Reviewer",
        system_message="""你是一名代码审查专家。
        审查代码的质量、安全性和性能。
        提出改进建议，指出潜在问题。
        确保代码符合团队规范。""",
        llm_config=llm_config
    )
    
    # 测试者
    tester = autogen.AssistantAgent(
        name="Tester",
        system_message="""你是一名测试工程师。
        设计测试用例，验证代码功能。
        关注边界条件和异常处理。
        提供测试报告和改进建议。""",
        llm_config=llm_config
    )
    
    return user_proxy, developer, reviewer, tester


def create_group_chat(agents):
    """创建群聊"""
    
    try:
        import autogen
    except ImportError:
        return None
    
    user_proxy, developer, reviewer, tester = agents
    
    # 创建群聊
    groupchat = autogen.GroupChat(
        agents=[user_proxy, developer, reviewer, tester],
        messages=[],
        max_round=10,  # 最大对话轮数
        speaker_selection_method="round_robin"  # 顺序发言
    )
    
    # 管理器
    manager = autogen.GroupChatManager(
        groupchat=groupchat,
        llm_config={"config_list": [{"model": "gpt-4", "api_key": "YOUR_KEY"}]}
    )
    
    return manager


# ============== 运行示例 ==============

def run_demo():
    """运行演示"""
    
    print("=" * 60)
    print("AutoGen 多Agent对话协作示例")
    print("=" * 60)
    
    agents = create_agents()
    
    if agents is None:
        print("Agent创建失败，请先安装autogen")
        print("\n使用模拟方式演示:")
        return run_mock_demo()
    
    user_proxy, developer, reviewer, tester = agents
    manager = create_group_chat(agents)
    
    # 启动对话
    print("\n任务: 实现一个简单的计算器类")
    print("\n开始多Agent对话...\n")
    
    user_proxy.initiate_chat(
        manager,
        message="请帮我实现一个Python计算器类，支持加减乘除和开方运算"
    )
    
    print("\n" + "=" * 60)
    print("对话完成!")
    print("=" * 60)


def run_mock_demo():
    """模拟演示"""
    
    print("\n" + "-" * 40)
    print("模拟多Agent对话流程")
    print("-" * 40)
    
    print("\n任务: 实现一个简单的计算器类")
    
    # 模拟对话
    conversations = [
        ("User", "请帮我实现一个Python计算器类，支持加减乘除和开方运算"),
        ("Developer", "好的，我来编写代码:\n\n```python\nclass Calculator:\n    def add(self, a, b): return a + b\n    def subtract(self, a, b): return a - b\n    def multiply(self, a, b): return a * b\n    def divide(self, a, b): return a / b if b != 0 else None\n    def sqrt(self, a): return a ** 0.5\n```"),
        ("Reviewer", "代码审查意见:\n1. divide方法需要处理除零异常\n2. 建议添加类型检查\n3. 可以添加日志记录"),
        ("Developer", "感谢审查，我来改进:\n\n```python\nclass Calculator:\n    def divide(self, a, b):\n        if b == 0:\n            raise ValueError('Division by zero')\n        return a / b\n```"),
        ("Tester", "测试建议:\n1. 测试正常计算\n2. 测试除零边界\n3. 测试负数开方"),
        ("User", "很好，完成了！TERMINATE")
    ]
    
    for speaker, message in conversations:
        print(f"\n[{speaker}]:")
        print(message[:200] + "..." if len(message) > 200 else message)
    
    print("\n" + "=" * 60)
    print("模拟对话完成!")
    print("=" * 60)


# ============== 可视化 ==============

def visualize_conversation():
    """可视化对话流程"""
    
    print("\n对话流程 (Mermaid格式):")
    print("""
    sequenceDiagram
        User->>Developer: 提出需求
        Developer->>Reviewer: 提交代码
        Reviewer->>Developer: 审查反馈
        Developer->>Tester: 改进代码
        Tester->>User: 测试报告
        User->>Manager: TERMINATE
    """)


if __name__ == "__main__":
    run_demo()
    visualize_conversation()