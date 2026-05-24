        (80, "skip"),
        (79, "conservative"),
        (50, "conservative"),
        (49, "interactive"),
        (0, "interactive"),
    ])
    def test_recommendation_thresholds(self, score, expected):
        assert get_recommendation(score) == expected


class TestGetLowScoreDimensions:
    """测试低分维度识别"""
    
    def test_identify_low_scores(self):
        scores = {
            "functional_scope": DimensionScore("functional_scope", 2, ""),
            "target_users": DimensionScore("target_users", 4, ""),
            "tech_constraints": DimensionScore("tech_constraints", 1, ""),
        }
        low_dims = get_low_score_dimensions(scores, threshold=3)
        assert "functional_scope" in low_dims
        assert "tech_constraints" in low_dims
        assert "target_users" not in low_dims
```

#### 10.1.2 ClarifierAgent 测试

```python
# tests/clarifier/test_agent.py

@pytest.fixture
def clarifier():
    return ClarifierAgent(model="qwen3.6-turbo", task_type="development")


class TestClarifierAgentAnalyze:
    """测试 analyze 方法"""
    
    @pytest.mark.asyncio
    async def test_complete_task_skip(self, clarifier):
        """完整任务描述应返回 skip"""
        task = """
        实现一个用户管理系统，包括：
        - 用户注册、登录、个人信息修改
        - 角色权限管理（管理员、普通用户）
        - 使用 React + FastAPI 技术栈
        - 2 周内交付
        - 预算 5 万元
        - 支持 1000 并发用户
        - 对接现有 OAuth 系统
        - 验收标准：通过所有单元测试，代码覆盖率 > 80%
        - 背景：公司内部系统升级
        """
        result = await clarifier.analyze(task)
        assert result.recommendation == "skip"
        assert result.score >= 80
    
    @pytest.mark.asyncio
    async def test_vague_task_interactive(self, clarifier):
        """模糊任务描述应返回 interactive"""
        task = "做一个电商网站"
        result = await clarifier.analyze(task)
        assert result.recommendation == "interactive"
        assert len(result.questions) > 0
    
    @pytest.mark.asyncio
    async def test_partial_task_conservative(self, clarifier):
        """部分信息任务应返回 conservative"""
        task = """
        实现一个用户管理系统，使用 React + FastAPI。
        需要用户注册、登录功能。
        """
        result = await clarifier.analyze(task)
        assert result.recommendation in ("conservative", "interactive")
        assert len(result.assumptions) > 0 or len(result.questions) > 0


class TestClarifierAgentReEvaluate:
    """测试 re_evaluate 方法"""
    
    @pytest.mark.asyncio
    async def test_score_improvement(self, clarifier):
        """用户回复后分数应提高"""
        original_task = "做一个电商网站"
        user_answers = {
            "functional_scope": "需要商品展示、购物车、支付、订单管理",
            "target_users": "面向 C 端消费者",
            "tech_constraints": "使用 React + Node.js",
        }
        result = await clarifier.re_evaluate(original_task, user_answers)
        assert result.score > 30  # 应比初始分数高


class TestClarifierAgentRun:
    """测试 run 方法（BaseAgent 接口）"""
    
    @pytest.mark.asyncio
    async def test_run_success(self, clarifier):
        result = await clarifier.run("实现一个登录功能")
        assert result.success is True
        assert result.output is not None
    
    @pytest.mark.asyncio
    async def test_run_with_context(self, clarifier):
        context = {"task_type": "design"}
        result = await clarifier.run("设计一个用户界面", context)
        assert result.success is True
        assert result.metadata.get("score") is not None
```

#### 10.1.3 数据模型测试

```python
# tests/clarifier/test_result.py

class TestClarifierResultSerialization:
    """测试 ClarifierResult 序列化"""
    
    def test_to_dict(self):
        result = ClarifierResult(
            score=72.5,
            dimensions={
                "functional_scope": DimensionScore("functional_scope", 3, "部分明确"),
            },
            questions=[
                ClarificationQuestion("functional_scope", "需要哪些功能？", "high"),
            ],
            assumptions=[],
            recommendation="interactive",
            raw_input="测试任务",
        )
        d = result.to_dict()
        assert d["score"] == 72.5
        assert "functional_scope" in d["dimensions"]
        assert len(d["questions"]) == 1
    
    def test_from_dict(self):
        data = {
            "score": 65.0,
            "dimensions": {
                "functional_scope": {
                    "dimension": "functional_scope",
                    "score": 3,
                    "reason": "部分明确",
                    "question": None,
                }
            },
            "questions": [],
            "assumptions": [],
            "recommendation": "conservative",
            "enriched_task": "增强任务",
            "raw_input": "原始任务",
            "task_type": "development",
        }
        result = ClarifierResult.from_dict(data)
        assert result.score == 65.0
        assert result.recommendation == "conservative"
        assert result.enriched_task == "增强任务"
```

### 10.2 集成测试

```python
# tests/clarifier/test_api.py

class TestClarificationAPI:
    """测试澄清 API 端点"""
    
    @pytest.mark.asyncio
    async def test_analyze_endpoint(self, async_client):
        response = await async_client.post(
            "/api/clarification/analyze",
            json={"task": "做一个电商网站", "task_type": "development"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "score" in data
        assert "recommendation" in data
        assert "dimensions" in data
    
    @pytest.mark.asyncio
    async def test_re_evaluate_endpoint(self, async_client):
        response = await async_client.post(
            "/api/clarification/re-evaluate",
            json={
                "original_task": "做一个电商网站",
                "user_answers": {
                    "functional_scope": "商品展示、购物车、支付",
                },
                "task_type": "development",
            },
        )
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_dimensions_endpoint(self, async_client):
        response = await async_client.get("/api/clarification/dimensions")
        assert response.status_code == 200
        data = response.json()
        assert len(data["dimensions"]) == 9
        assert "default_weights" in data
        assert "task_type_weights" in data
    
    @pytest.mark.asyncio
    async def test_analyze_validation(self, async_client):
        """测试输入校验"""
        response = await async_client.post(
            "/api/clarification/analyze",
            json={"task": "", "task_type": "development"},  # 空任务
        )
        assert response.status_code == 422  # 验证失败
```

### 10.3 前端组件测试

```typescript
// web/src/components/__tests__/ClarificationModal.test.tsx

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ClarificationModal } from '../ClarificationModal';

describe('ClarificationModal', () => {
  const mockQuestions = [
    {
      dimension: 'functional_scope',
      dimension_label: '功能范围',
      question: '需要哪些核心功能？',
      importance: 'high',
      user_answer: null,
    },
  ];

  it('renders questions when status is questions_ready', () => {
    render(
      <ClarificationModal
        isOpen={true}
        status="questions_ready"
        questions={mockQuestions}
        currentScore={45}
        recommendation="interactive"
        onSubmit={jest.fn()}
        onClose={jest.fn()}
      />
    );
    expect(screen.getByText('需要哪些核心功能？')).toBeInTheDocument();
  });

  it('calls onSubmit with answers when submitted', async () => {
    const mockSubmit = jest.fn();
    render(
      <ClarificationModal
        isOpen={true}
        status="questions_ready"
        questions={mockQuestions}
        currentScore={45}
        recommendation="interactive"
        onSubmit={mockSubmit}
        onClose={jest.fn()}
      />
    );

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '商品展示、购物车' } });
    
    const submitBtn = screen.getByText('提交回复');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledWith({
        functional_scope: '商品展示、购物车',
      });
    });
  });

  it('shows score indicator', () => {
    render(
      <ClarificationModal
        isOpen={true}
        status="questions_ready"
        questions={mockQuestions}
        currentScore={45}
        recommendation="interactive"
        onSubmit={jest.fn()}
        onClose={jest.fn()}
      />
    );
    expect(screen.getByText(/45/)).toBeInTheDocument();
  });
});
```

### 10.4 端到端测试场景

| 场景 ID | 描述 | 前置条件 | 步骤 | 预期结果 |
|---------|------|----------|------|----------|
| E2E-01 | 完整任务直接通过 | 无 | 1. 输入完整任务描述<br>2. 提交分析 | 1. 评分 ≥ 80<br>2. 推荐 skip<br>3. 直接进入规划 |
| E2E-02 | 模糊任务交互澄清 | 无 | 1. 输入"做一个网站"<br>2. 查看问题<br>3. 逐条回复<br>4. 提交 | 1. 评分 < 50<br>2. 生成 3-5 个问题<br>3. 回复后分数提升<br>4. 达到阈值后关闭 |
| E2E-03 | 保守模式假设填充 | 无 | 1. 输入部分信息任务<br>2. 查看假设<br>3. 接受假设 | 1. 评分 50-79<br>2. 生成合理假设<br>3. 任务描述被增强 |
| E2E-04 | 多次迭代澄清 | 无 | 1. 输入模糊任务<br>2. 回复部分问题<br>3. 仍低于阈值<br>4. 继续回复 | 1. 第一次重评后仍 < 50<br>2. 生成新问题<br>3. 最多 3 次迭代 |
| E2E-05 | 断线恢复 | 用户正在回复 | 1. 断开网络<br>2. 重新连接 | 1. 草稿自动保存<br>2. 恢复未提交内容 |

---\n\n## 11. 风险与注意事项\n\n### 11.1 技术风险\n\n| 风险 | 影响 | 概率 | 缓解措施 |\n|------|------|------|----------|\n| LLM 响应不稳定 | 评分不一致 | 中 | 添加重试机制、温度设为 0.3、JSON Schema 校验 |\n| Prompt 注入攻击 | 系统行为异常 | 低 | 输入清洗、系统提示词隔离、输出校验 |\n| WebSocket 断连 | 用户交互中断 | 中 | 心跳检测、自动重连、降级为轮询 |\n| SQLite 并发写入 | 数据丢失 | 低 | WAL 模式、连接池、事务管理 |\n| 评分阈值不合理 | 误判澄清需求 | 中 | A/B 测试、可配置阈值、人工修正 |\n\n### 11.2 性能注意事项\n\n1. **LLM 调用延迟**：澄清分析依赖 LLM，首次评分可能耗时 2-5 秒\n   - 缓解：前端显示加载动画，支持后台异步分析\n   \n2. **多次迭代成本**：交互模式可能需要 2-3 轮 LLM 调用\n   - 缓解：设置最大迭代次数（默认 3），超时自动降级\n   \n3. **WebSocket 连接数**：大量并发用户可能占用较多连接\n   - 缓解：连接池管理、空闲超时断开、支持轮询降级\n\n### 11.3 安全注意事项\n\n1. **输入清洗**：所有用户输入必须经过清洗，防止 Prompt 注入\n   ```python\n   def sanitize_input(text: str) -> str:\n       # 移除系统指令模式\n       text = re.sub(r'(system|ignore|override)\\s*:', '', text, flags=re.IGNORECASE)\n       # 限制长度\n       return text[:10000]\n   ```\n\n2. **CSRF 防护**：API 端点需实施 CSRF Token 验证\n\n3. **速率限制**：澄清接口需限制调用频率，防止滥用\n\n4. **数据脱敏**：日志中不记录完整的用户任务描述\n\n### 11.4 可扩展性设计\n\n1. **维度可配置**：9 维度定义通过 YAML 配置，支持动态增删\n   ```yaml\n   # config/clarification_dimensions.yaml\n   dimensions:\n     functional_scope:\n       label: "功能范围"\n       description: "需要实现哪些核心功能？"\n       weight: 1.5\n   ```\n\n2. **权重可调整**：不同任务类型使用不同权重配置\n\n3. **评分模型可替换**：支持规则评分、LLM 评分、混合评分三种模式\n\n4. **多模型路由**：复用 `src/claude` 封装，支持 DashScope/Anthropic 切换\n\n### 11.5 待澄清问题跟进\n\n基于需求分析文档中的待澄清问题，当前设计假设如下：\n\n| 问题 | 当前假设 | 后续行动 |\n|------|----------|----------|\n| 9 维度评分权重 | 已定义默认权重和任务类型权重 | 需产品确认最终权重 |\n| 澄清触发条件 | 仅在 Planner 前触发 | 后续可扩展执行中动态触发 |\n| 回复格式限制 | 纯文本，最大 1000 字符 | 后续可支持富文本 |\n| 评分数据来源 | LLM 自动评估 + 规则校验 | 后续接入 CI/CD 指标 |\n| 权限控制 | 所有登录用户可创建任务 | 需确认角色隔离需求 |\n\n---\n\n## 12. 附录\n\n### 12.1 9 维度详细说明\n\n| 维度 | 标签 | 说明 | 示例问题 |\n|------|------|------|----------|\n| `functional_scope` | 功能范围 | 需要实现哪些核心功能？功能边界在哪里？ | 需要哪些核心功能？功能的边界是什么？ |\n| `target_users` | 目标用户 | 面向什么用户群体？用户画像是什么？ | 面向什么用户群体？他们的特征和使用场景是什么？ |\n| `tech_constraints` | 技术约束 | 有技术栈偏好或限制吗？需要兼容哪些平台？ | 有技术栈偏好或限制吗？需要兼容哪些平台或浏览器？ |\n| `timeline` | 时间要求 | 期望的交付时间是？有里程碑节点吗？ | 期望的交付时间是？有没有关键的里程碑节点？ |\n| `budget` | 预算范围 | 预算或成本限制是？ | 预算或成本限制是多少？ |\n| `quality_reqs` | 质量要求 | 对性能、安全、可用性有什么要求？ | 对性能、安全性、可用性有什么具体要求？ |\n| `integration` | 集成需求 | 需要对接现有系统或第三方服务吗？ | 需要对接现有系统或第三方 API 吗？ |\n| `success_criteria` | 成功标准 | 怎么判断这个项目成功了？验收标准是什么？ | 怎么判断这个项目成功了？验收标准是什么？ |\n| `context` | 项目背景 | 这个项目的背景和业务场景是什么？ | 这个项目的背景和业务场景是什么？为什么要做这个项目？ |\n\n### 12.2 文件清单\n\n| 文件 | 状态 | 说明 |\n|------|------|------|\n| `src/clarifier/__init__.py` | ✅ 已有 | 模块入口 |\n| `src/clarifier/agent.py` | ✅ 已有 | ClarifierAgent 核心实现 |\n| `src/clarifier/dimensions.py` | ✅ 已有 | 9 维度定义与评分算法 |\n| `src/clarifier/prompts.py` | ✅ 已有 | LLM 提示词模板 |\n| `src/clarifier/result.py` | ✅ 已有 | 数据类定义 |\n| `src/api/routes/clarification.py` | ✅ 已有 | API 路由 |\n| `src/api/services/clarification.py` | 📝 待实现 | 会话管理服务 |\n| `src/api/services/scoring.py` | 📝 待实现 | 评分服务 |\n| `src/api/websocket/clarification.py` | 📝 待实现 | WebSocket 管理 |\n| `web/src/components/TaskEntryForm.tsx` | 📝 待实现 | 任务入口组件 |\n| `web/src/components/ClarificationModal.tsx` | 📝 待实现 | 澄清交互组件 |\n| `web/src/components/ScoreCard.tsx` | 📝 待实现 | 评分展示组件 |\n| `config/clarification_weights.yaml` | 📝 待实现 | 权重配置 |\n| `tests/clarifier/test_dimensions.py` | 📝 待实现 | 维度测试 |\n| `tests/clarifier/test_agent.py` | 📝 待实现 | Agent 测试 |\n| `tests/clarifier/test_api.py` | 📝 待实现 | API 测试 |\n\n### 12.3 参考文档\n\n- [需求分析文档](../report/phase9-requirements-analysis.md)\n- [现有 ClarifierAgent 代码](../../src/clarifier/)\n- [现有 API 路由](../../src/api/routes/clarification.py)\n- [WorkflowRunner 集成](../../src/workflows/runner.py)\n\n