# Phase 9 实施计划：ClarifierAgent 需求澄清机制

## 概述

在 PlannerAgent 之前引入 ClarifierAgent，对用户输入进行 9 维度评分，生成澄清问题或保守假设。

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/clarifier/__init__.py` | 新建 | 模块入口 |
| `src/clarifier/agent.py` | 新建 | ClarifierAgent 主类 |
| `src/clarifier/dimensions.py` | 新建 | 9 维度定义和评分模型 |
| `src/clarifier/prompts.py` | 新建 | 系统提示词 |
| `src/clarifier/result.py` | 新建 | ClarifierResult 数据类 |
| `src/workflows/runner.py` | 修改 | run() 加入澄清环节 |
| `src/api/routes/clarification.py` | 新建 | 澄清 API 路由 |
| `src/api/routes/__init__.py` | 修改 | 注册 clarification router |
| `src/api/server.py` | 修改 | 初始化 ClarifierAgent |
| `tests/test_phase9_clarifier.py` | 新建 | 单元测试 |

## 实施步骤

1. **TDD — 写 ClarifierResult 和 Dimensions 模型**
2. **TDD — 写 ClarifierAgent 单元测试**（评分逻辑、问题生成、保守模式）
3. **实现 ClarifierAgent 核心**
4. **集成到 WorkflowRunner**
5. **添加 API 路由**（/executions/{id}/clarify、/executions/{id}/clarification）
6. **注册到 server.py**
7. **运行全部测试**

## 验收

- ClarifierAgent 单元测试通过
- 对模糊输入 "帮我做一个电商网站" 生成 >= 3 个澄清问题
- 对清晰输入直接通过（分数 >= 80）
- 集成测试验证 run() 链路完整
- 所有现有 677 测试通过
