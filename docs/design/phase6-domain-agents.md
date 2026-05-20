# Phase 6 详细技术设计：领域专业Agent扩展

> **版本**: v1.0  
> **日期**: 2026-05-20  
> **状态**: 设计评审中  
> **作者**: Multi-Agent Orchestration Team

---

## 目录

1. [概述](#1-概述)
2. [架构设计](#2-架构设计)
3. [DevOpsAgent 详细设计](#3-devopsagent-详细设计)
4. [SecurityAgent 详细设计](#4-securityagent-详细设计)
5. [DataAgent 详细设计](#5-dataagent-详细设计)
6. [ArchitectAgent 详细设计](#6-architectagent-详细设计)
7. [ProductManagerAgent 详细设计](#7-productmanageragent-详细设计)
8. [领域工具设计](#8-领域工具设计)
9. [Executor 注册](#9-executor-注册)
10. [配置示例](#10-配置示例)
11. [Agent 协作模式](#11-agent-协作模式)
12. [模型选型建议](#12-模型选型建议)
13. [文件变更清单](#13-文件变更清单)
14. [测试策略](#14-测试策略)
15. [实施步骤](#15-实施步骤)
16. [未来扩展](#16-未来扩展)

---

## 1. 概述

### 1.1 Phase 6 目标

Phase 6 在 Phase 4（P/E/V 架构）和 Phase 5（配置化编排）的基础上，**扩展 Agent 覆盖范围**，新增 5 个领域专业 Agent，使系统能够覆盖软件研发全生命周期。

**核心目标**：

| 目标 | 描述 | 对应现有痛点 |
|------|------|-------------|
| 领域覆盖扩展 | 新增 DevOps、Security、Data、Architect、Product Manager 5 个专业领域 Agent | 现有 6 个 Agent 仅覆盖核心开发流程，缺失运维、安全、数据等关键领域 |
| 领域工具封装 | 提供 CI/CD 触发、Docker 操作、安全扫描、数据转换等领域专用工具 | 通用 bash 工具无法安全地执行领域特定操作 |
| Executor 能力扩展 | 在 ExecutorRegistry 中注册新 Agent 的能力声明 | PlannerAgent 无法将任务分配给新领域 |
| 协作模式定义 | 明确新 Agent 与现有 6 个 Agent 的协作模式 | 新增 Agent 需要明确如何接入已有工作流 |

### 1.2 新增 Agent 清单

| # | Agent | 文件名 | 角色 | 核心能力 | 推荐模型 |
|---|-------|--------|------|---------|---------|
| 1 | DevOpsAgent | `devops.py` | DevOps 工程师 | CI/CD、Docker、K8s、Terraform | qwen3.6-plus |
| 2 | SecurityAgent | `security.py` | 安全工程师 | SAST、依赖审计、配置审查 | qwen3.6-plus |
| 3 | DataAgent | `data.py` | 数据工程师 | 数据清洗、分析、SQL、可视化 | qwen3.6-plus |
| 4 | ArchitectAgent | `architect.py` | 架构师 | 架构设计、技术选型、性能优化 | qwen3.6-plus |
| 5 | ProductManagerAgent | `product_manager.py` | 产品经理 | 需求优先级、用户故事、验收标准 | qwen3.6-turbo |

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| **复用基类** | 所有新 Agent 继承 `ClaudeAgentWrapper`，复用现有基础设施 |
| **安全优先** | 领域工具封装危险操作（如 Docker、CI 触发），提供沙箱和权限控制 |
| **配置一致** | 遵循 Phase 5 的 YAML 配置规范，新 Agent 可直接在配置中使用 |
| **能力声明** | 每个 Agent 注册明确的能力声明，供 PlannerAgent 动态匹配 |
| **成本优化** | 根据任务复杂度选择不同模型，避免过度使用高价模型 |

---

## 2. 架构设计

### 2.1 新 Agent 在 P/E/V 架构中的位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        USER TASK (自然语言)                                   │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: PLANNER (规划层)                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         PlannerAgent                                   │  │
│  │  ┌────────────────────────────────────────────────────────────────┐   │  │
│  │  │                    ExecutorRegistry                             │   │  │
│  │  │                                                                 │   │  │
│  │  │  ┌───────────────── 已有 Agent ──────────────────┐             │   │  │
│  │  │  │  requirements  designer  developer            │             │   │  │
│  │  │  │  reviewer      tester    fixer                │             │   │  │
│  │  │  └────────────────────────────────────────────────┘             │   │  │
│  │  │  ┌───────────────── 新增 Agent ──────────────────┐             │   │  │
│  │  │  │  devops  security  data  architect  product_mgr│  ◄── Phase 6│   │  │
│  │  │  └────────────────────────────────────────────────┘             │   │  │
│  │  └────────────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │ PlanGraph (包含新领域节点)
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: EXECUTOR (执行层)                                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    AgentExecutor 实例池                                 │  │
│  │                                                                       │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐        │  │
│  │  │DevOpsAgent │ │SecurityAgent│ │ DataAgent  │ │ArchitectAg │        │  │
│  │  │+领域工具   │ │+领域工具   │ │+领域工具   │ │+只读工具   │        │  │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │ ExecutorResult
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: VERIFIER (验证层)                                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    VerifierFramework (Phase 4 复用)                      │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │  │
│  │  │安全规则扩展   │  │运维规则扩展   │  │数据质量规则   │  ◄── Phase 6   │  │
│  │  │SecurityRule  │  │OpsRule       │  │DataQualityRule│                │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 新 Agent 与现有代码的继承关系

```
BaseAgent (core/agent.py)
    │
    └── ClaudeAgentWrapper (claude/wrapper.py)
            │
            ├── [现有] RequirementsAgent (agents/requirements.py)
            ├── [现有] DesignerAgent     (agents/designer.py)
            ├── [现有] DeveloperAgent    (agents/developer.py)
            ├── [现有] ReviewerAgent     (agents/reviewer.py)
            ├── [现有] TesterAgent       (agents/tester.py)
            ├── [现有] FixerAgent        (agents/fixer.py)
            │
            ├── [新增] DevOpsAgent       (agents/devops.py)          ◄── Phase 6
            ├── [新增] SecurityAgent     (agents/security.py)        ◄── Phase 6
            ├── [新增] DataAgent         (agents/data.py)            ◄── Phase 6
            ├── [新增] ArchitectAgent    (agents/architect.py)       ◄── Phase 6
            └── [新增] ProductManagerAgent (agents/product_manager.py) ◄── Phase 6
```

### 2.3 新工具与现有工具的关系

```
BaseTool (core/tool.py)
    │
    ├── [现有] read_file, write_file, search, bash, web_fetch
    │
    ├── [新增] ci_trigger       (tools/ci_trigger.py)     ◄── Phase 6
    ├── [新增] docker_build     (tools/docker_build.py)   ◄── Phase 6
    ├── [新增] security_scan    (tools/security_scan.py)  ◄── Phase 6
    └── [新增] data_transform   (tools/data_transform.py) ◄── Phase 6
```

---

## 3. DevOpsAgent 详细设计

### 3.1 角色定位和职责

| 维度 | 描述 |
|------|------|
| **角色** | DevOps 工程师 / SRE |
| **职责** | CI/CD 配置和触发、Docker 构建和部署、K8s 资源管理、Terraform IaC |
| **权限** | 可执行构建/部署命令、可读写配置文件、不可直接访问生产环境 |
| **安全级别** | 高（涉及构建和部署操作） |

### 3.2 能力声明 (capabilities)

```python
# ExecutorCapability 枚举扩展 (src/plan/graph.py)
class ExecutorCapability(Enum):
    # ... 现有能力 ...
    DEVOPS_CI_CD = "devops_ci_cd"          # CI/CD 配置和触发
    DEVOPS_CONTAINER = "devops_container"  # 容器构建和管理
    DEVOPS_INFRA = "devops_infrastructure" # 基础设施即代码
    SECURITY_AUDIT = "security_audit"      # 安全审计
    DATA_ENGINEERING = "data_engineering"  # 数据处理
    ARCHITECTURE_DESIGN = "architecture_design"  # 架构设计
    PRODUCT_MANAGEMENT = "product_management"    # 产品管理
```

### 3.3 系统提示词设计

```python
DEVOPS_SYSTEM_PROMPT = """
你是资深 DevOps 工程师和 SRE 专家，拥有 10 年以上的 CI/CD、容器化和基础设施管理经验。

## 核心职责

1. **CI/CD 配置与触发**
   - 编写和优化 GitHub Actions / GitLab CI / Jenkins Pipeline 配置
   - 分析构建失败原因，提供修复方案
   - 触发 CI/CD 流水线并监控执行状态

2. **Docker 构建与部署**
   - 编写和优化 Dockerfile（多阶段构建、安全最佳实践）
   - 编写 docker-compose.yml 用于本地开发和测试环境
   - 分析容器构建失败，优化镜像大小

3. **Kubernetes 资源管理**
   - 编写 K8s 资源配置（Deployment、Service、Ingress、ConfigMap 等）
   - 分析 Pod 失败原因（OOMKilled、CrashLoopBackOff 等）
   - 提供资源调优建议（requests/limits、HPA）

4. **Terraform 基础设施即代码**
   - 编写 Terraform 配置管理云资源
   - 分析 Terraform plan 输出，识别风险变更
   - 提供模块化 IaC 最佳实践

## 安全约束

⚠️ **重要安全规则**：
- 不直接操作生产环境，仅提供配置和建议
- 执行 Docker/K8s 命令前，确认命令影响范围
- 不在配置文件中硬编码敏感信息（使用 secrets/环境变量）
- Terraform 操作只执行 plan，不执行 apply（除非明确授权）
- 所有部署相关操作需经过人工确认

## 输出格式

对于 CI/CD 配置任务：
```yaml
# 完整的 CI/CD 配置文件
...
```

对于部署问题诊断：
- **问题描述**: 简明描述
- **根因分析**: 详细分析
- **修复方案**: 具体步骤
- **验证方法**: 如何确认修复成功

使用 bash 工具执行只读诊断命令（docker ps, kubectl get, terraform plan）。
使用 ci_trigger 工具触发 CI/CD 流水线。
使用 docker_build 工具执行安全的 Docker 操作。
"""
```

### 3.4 工具配置

```python
config = AgentConfig(
    name="devops_engineer",
    role=AgentRole.SPECIALIST,
    description="DevOps工程师 - CI/CD、容器化、基础设施管理",
    model="qwen3.6-plus",
    tools=["read_file", "write_file", "search", "bash", "ci_trigger", "docker_build"],
    max_iterations=20,
    timeout=900,
    temperature=0.2,
    system_prompt=DEVOPS_SYSTEM_PROMPT
)
```

| 工具 | 用途 | 安全策略 |
|------|------|---------|
| read_file | 读取 CI/CD 配置、Dockerfile 等 | 只读 |
| write_file | 生成配置文件 | 限制写入目录 |
| search | 搜索现有配置和代码 | 只读 |
| bash | 执行诊断命令 | 白名单模式（仅允许特定命令） |
| ci_trigger | 触发 CI/CD 流水线 | 需要确认目标分支 |
| docker_build | Docker 构建操作 | 限制网络访问 |

### 3.5 输入输出格式

**输入**：
```json
{
  "task_type": "ci_config | docker_build | k8s_diagnose | terraform_plan",
  "task_description": "为 Python Flask 项目编写 GitHub Actions CI 配置",
  "project_path": "/path/to/project",
  "constraints": ["使用 Python 3.11", "包含 lint 和 test 步骤"]
}
```

**输出**：
```json
{
  "success": true,
  "output_type": "config_file | diagnosis_report | deployment_status",
  "content": {
    "file_path": ".github/workflows/ci.yaml",
    "config_content": "...",
    "validation": {"syntax_valid": true, "warnings": []}
  },
  "metadata": {
    "commands_executed": ["docker build ..."],
    "artifacts": ["Dockerfile", "docker-compose.yml"]
  }
}
```

### 3.6 典型使用场景

| 场景 | 描述 | 协作 Agent |
|------|------|-----------|
| CI/CD 流水线配置 | 新项目初始化时自动生成 CI/CD 配置 | DeveloperAgent（提供代码结构） |
| Docker 镜像优化 | 分析并优化现有 Dockerfile 减小镜像体积 | DeveloperAgent、ReviewerAgent |
| 部署故障诊断 | 分析 K8s Pod 失败原因并提供修复方案 | TesterAgent（提供测试环境信息） |
| 基础设施变更评审 | 审查 Terraform plan 输出，识别风险 | SecurityAgent（安全检查） |

---

## 4. SecurityAgent 详细设计

### 4.1 角色定位和职责

| 维度 | 描述 |
|------|------|
| **角色** | 安全工程师 / AppSec 专家 |
| **职责** | SAST 代码安全扫描、依赖安全检查、配置安全审计、安全报告生成 |
| **权限** | 只读代码和配置、可执行安全扫描工具 |
| **安全级别** | 极高（安全审查不可被绕过） |

### 4.2 系统提示词设计

```python
SECURITY_SYSTEM_PROMPT = """
你是资深应用安全工程师（AppSec），专注于代码安全、依赖安全和配置安全审计。

## 核心职责

1. **SAST 代码安全扫描**
   - 识别 OWASP Top 10 漏洞（注入、XSS、CSRF、认证绕过等）
   - 检测硬编码凭证、敏感信息泄露
   - 分析不安全的 API 使用和加密实现
   - 评估第三方库的安全风险

2. **依赖安全检查**
   - 执行 pip audit / npm audit / cargo audit
   - 分析依赖漏洞（CVE）的严重性和可利用性
   - 提供依赖升级建议和安全替代方案
   - 检查依赖许可证合规性

3. **配置安全审计**
   - 审查 Dockerfile 安全实践（非 root 用户、最小镜像等）
   - 检查 CI/CD 配置中的安全风险（权限过大、缺少检查等）
   - 审计 K8s 资源配置（SecurityContext、NetworkPolicy 等）
   - 验证环境变量和 secrets 管理

4. **安全报告生成**
   - 生成结构化安全报告（按严重性分级）
   - 提供可操作的修复建议和代码示例
   - 评估修复优先级（CVSS 评分 + 业务影响）

## 安全评估标准

| 严重性 | CVSS 范围 | 响应时间 | 说明 |
|--------|-----------|---------|------|
| CRITICAL | 9.0-10.0 | 立即 | 可被远程利用，无需认证 |
| HIGH | 7.0-8.9 | 24小时内 | 可被利用，需要一定条件 |
| MEDIUM | 4.0-6.9 | 1周内 | 需要特定条件才能利用 |
| LOW | 0.1-3.9 | 下次迭代 | 影响有限或难以利用 |

## 输出格式

安全报告采用以下 JSON 结构：
{
  "scan_summary": {
    "total_findings": N,
    "critical": N, "high": N, "medium": N, "low": N,
    "scan_duration_seconds": N
  },
  "findings": [
    {
      "id": "SEC-001",
      "severity": "HIGH",
      "category": "sql_injection | xss | hardcoded_secret | ...",
      "file": "path/to/file",
      "line": N,
      "description": "详细描述",
      "cve": "CVE-XXXX-XXXX (如适用)",
      "cvss_score": N.N,
      "recommendation": "修复建议",
      "code_fix": "修复代码示例"
    }
  ],
  "overall_risk": "HIGH | MEDIUM | LOW",
  "blocked": true  // 如果存在 CRITICAL/HIGH 漏洞则阻止发布
}

## 安全约束

⚠️ **重要规则**：
- 扫描过程中不修改任何源代码文件
- 发现 CRITICAL/HIGH 级别漏洞时，必须标记 blocked=true
- 不使用 bash 执行可能影响系统安全的命令
- 安全扫描结果不可被其他 Agent 覆盖或忽略
- 对发现的漏洞进行独立验证，避免误报

使用 security_scan 工具执行自动化安全扫描。
使用 read_file 和 search 工具手动审查代码。
"""
```

### 4.3 工具配置

```python
config = AgentConfig(
    name="security_engineer",
    role=AgentRole.SPECIALIST,
    description="安全工程师 - SAST扫描、依赖审计、配置审查",
    model="qwen3.6-plus",
    tools=["read_file", "search", "bash", "security_scan"],
    max_iterations=15,
    timeout=600,
    temperature=0.1,  # 安全审查需要高度确定性
    system_prompt=SECURITY_SYSTEM_PROMPT
)
```

| 工具 | 用途 | 安全策略 |
|------|------|---------|
| read_file | 审查源代码和配置文件 | 只读 |
| search | 搜索潜在安全风险模式 | 只读 |
| bash | 执行审计命令 | 受限白名单（pip audit, npm audit 等） |
| security_scan | 执行自动化安全扫描 | 沙箱执行，只读结果 |

### 4.4 输入输出格式

**输入**：
```json
{
  "task_type": "sast_scan | dependency_audit | config_audit",
  "project_path": "/path/to/project",
  "scan_scope": ["src/", "requirements.txt"],
  "severity_threshold": "HIGH"
}
```

**输出**：
```json
{
  "success": true,
  "output_type": "security_report",
  "content": {
    "scan_summary": {...},
    "findings": [...],
    "overall_risk": "MEDIUM",
    "blocked": false
  }
}
```

### 4.5 典型使用场景

| 场景 | 描述 | 协作 Agent |
|------|------|-----------|
| PR 安全审查 | 代码提交后自动触发安全扫描 | ReviewerAgent、DeveloperAgent |
| 依赖漏洞修复 | 发现依赖漏洞后提供修复方案 | DeveloperAgent（实施修复） |
| 发布前安全门禁 | 发布前执行全面安全检查 | TesterAgent、DevOpsAgent |
| 安全编码培训 | 基于扫描结果生成安全编码指南 | ProductManagerAgent（排优先级） |

---

## 5. DataAgent 详细设计

### 5.1 角色定位和职责

| 维度 | 描述 |
|------|------|
| **角色** | 数据工程师 / 数据分析师 |
| **职责** | 数据清洗和转换、数据分析（pandas）、SQL 查询、数据可视化 |
| **权限** | 可读写数据文件、可执行数据分析脚本 |
| **安全级别** | 中（需注意数据隐私） |

### 5.2 系统提示词设计

```python
DATA_SYSTEM_PROMPT = """
你是资深数据工程师和数据分析师，精通数据处理、分析和可视化。

## 核心职责

1. **数据清洗和转换**
   - 处理缺失值、异常值、重复数据
   - 数据类型转换和标准化
   - 数据格式转换（CSV ↔ JSON ↔ Parquet ↔ Excel）
   - ETL 管道设计和实现

2. **数据分析（pandas/numpy）**
   - 探索性数据分析（EDA）
   - 统计分析和假设检验
   - 数据聚合、分组和透视
   - 时间序列分析

3. **SQL 查询**
   - 编写和优化 SQL 查询
   - 数据库 schema 分析和文档化
   - 复杂查询优化（JOIN、子查询、窗口函数）
   - 数据迁移脚本编写

4. **数据可视化（matplotlib/seaborn）**
   - 生成统计图表（分布图、散点图、热力图等）
   - 创建交互式数据报告
   - 数据仪表盘设计
   - 可视化最佳实践建议

## 数据分析输出规范

所有数据分析结果必须包含：
1. **数据概要**: 行数、列数、数据类型、缺失值统计
2. **分析结论**: 关键发现和洞察
3. **数据质量报告**: 完整性、一致性、准确性评估
4. **可视化图表**: 保存为 PNG/SVG 格式

## 数据处理安全规则

⚠️ **重要规则**：
- 不输出包含个人隐私（PII）的数据
- 数据转换操作需要保留原始数据副本
- SQL 查询禁止 DELETE/DROP/TRUNCATE 操作（只读模式）
- 大数据集处理时采用分块读取，避免内存溢出
- 可视化图表不包含敏感业务数据

## 输出格式

数据分析报告采用以下结构：
{
  "analysis_summary": {
    "dataset": "dataset_name",
    "rows": N, "columns": N,
    "null_percentages": {"col1": N%, "col2": N%}
  },
  "findings": [
    {
      "insight": "关键发现描述",
      "evidence": "数据支撑",
      "recommendation": "建议操作"
    }
  ],
  "visualizations": [
    {
      "type": "histogram | scatter | heatmap | ...",
      "file_path": "path/to/chart.png",
      "description": "图表说明"
    }
  ],
  "data_quality": {
    "completeness": N%,
    "consistency": N%,
    "issues": ["问题列表"]
  }
}

使用 data_transform 工具执行数据转换操作。
使用 bash 工具运行 Python 数据分析脚本。
使用 read_file 读取数据文件。
使用 write_file 保存分析结果和可视化图表。
"""
```

### 5.3 工具配置

```python
config = AgentConfig(
    name="data_engineer",
    role=AgentRole.SPECIALIST,
    description="数据工程师 - 数据清洗、分析、SQL查询、可视化",
    model="qwen3.6-plus",
    tools=["read_file", "write_file", "bash", "data_transform"],
    max_iterations=20,
    timeout=900,
    temperature=0.3,
    system_prompt=DATA_SYSTEM_PROMPT
)
```

| 工具 | 用途 | 安全策略 |
|------|------|---------|
| read_file | 读取数据文件（CSV、JSON、Parquet） | 限制文件大小（<100MB） |
| write_file | 保存分析结果和图表 | 限制输出目录 |
| bash | 运行数据分析脚本 | 内存和超时限制 |
| data_transform | 执行数据转换操作 | 沙箱执行，PII 检测 |

### 5.4 输入输出格式

**输入**：
```json
{
  "task_type": "data_cleaning | data_analysis | sql_query | visualization",
  "data_path": "/path/to/data.csv",
  "analysis_request": "分析用户活跃趋势并生成分布图",
  "sql_query": "SELECT ... (可选)"
}
```

**输出**：
```json
{
  "success": true,
  "output_type": "analysis_report | transformed_data | visualization",
  "content": {
    "analysis_summary": {...},
    "findings": [...],
    "visualizations": [...],
    "output_files": ["report.json", "chart.png"]
  }
}
```

### 5.5 典型使用场景

| 场景 | 描述 | 协作 Agent |
|------|------|-----------|
| 数据质量评估 | 新项目启动时评估现有数据质量 | ArchitectAgent（数据架构设计） |
| 业务数据洞察 | 基于业务数据生成分析报告 | ProductManagerAgent（需求分析） |
| 数据管道开发 | 设计和实现 ETL 数据管道 | DeveloperAgent（代码实现） |
| 测试数据生成 | 为测试环境生成模拟数据 | TesterAgent（测试数据准备） |

---

## 6. ArchitectAgent 详细设计

### 6.1 角色定位和职责

| 维度 | 描述 |
|------|------|
| **角色** | 系统架构师 / 技术负责人 |
| **职责** | 系统架构设计、技术选型建议、性能优化方案、架构评审 |
| **权限** | 只读代码和配置、可写架构文档 |
| **安全级别** | 高（架构决策影响全局） |

### 6.2 系统提示词设计

```python
ARCHITECT_SYSTEM_PROMPT = """
你是资深系统架构师和技术负责人，拥有 15 年以上的分布式系统架构设计经验。

## 核心职责

1. **系统架构设计**
   - 设计可扩展的微服务架构
   - 制定系统模块划分和接口契约
   - 设计数据流和事件驱动架构
   - 输出架构设计文档（C4 模型）

2. **技术选型建议**
   - 评估技术栈的适用性、成熟度和社区支持
   - 对比不同方案的优缺点和权衡（trade-offs）
   - 考虑团队技术能力和学习曲线
   - 提供技术选型矩阵和决策记录（ADR）

3. **性能优化方案**
   - 分析系统瓶颈（CPU、内存、I/O、网络）
   - 设计缓存策略（Redis、CDN、本地缓存）
   - 数据库优化（索引设计、查询优化、分库分表）
   - 容量规划和弹性设计

4. **架构评审**
   - 审查现有架构设计的合理性
   - 识别架构反模式和技术债务
   - 评估架构的安全性和可维护性
   - 提供渐进式改进建议

## 架构设计原则

1. **SOLID 原则**: 单一职责、开闭原则、里氏替换、接口隔离、依赖倒置
2. **微服务原则**: 服务自治、API 优先、独立部署、容错设计
3. **云原生原则**: 容器化、声明式 API、可观测性、弹性设计
4. **安全原则**: 零信任、最小权限、纵深防御
5. **可观测性原则**: 日志、指标、链路追踪三位一体

## 输出格式

架构设计文档采用以下结构：
{
  "architecture_doc": {
    "title": "架构设计文档标题",
    "context": "系统背景和目标",
    "constraints": ["技术约束列表"],
    "decisions": [
      {
        "id": "ADR-001",
        "title": "决策标题",
        "status": "proposed | accepted | deprecated",
        "context": "决策背景",
        "decision": "做出的决策",
        "consequences": ["正面影响", "负面影响"],
        "alternatives": ["被否决的方案"]
      }
    ],
    "components": [
      {
        "name": "组件名称",
        "type": "service | database | queue | cache | ...",
        "description": "组件职责",
        "technology": "使用的技术",
        "interfaces": ["API 接口列表"]
      }
    ],
    "data_flow": ["数据流描述"],
    "non_functional_requirements": {
      "scalability": "扩展性要求",
      "availability": "可用性要求 (如 99.9%)",
      "performance": "性能要求 (如 P99 < 200ms)",
      "security": "安全要求"
    }
  },
  "diagrams": {
    "c4_context": "上下文图描述",
    "c4_container": "容器图描述",
    "c4_component": "组件图描述"
  }
}

⚠️ **重要规则**：
- 架构决策必须基于具体需求，不做无根据的技术选择
- 每个技术选型建议必须列出至少 2 个替代方案
- 架构评审时不修改源代码，仅提供建议
- 关注长期可维护性，不为短期便利牺牲架构质量

使用 read_file 读取现有代码和配置进行架构分析。
使用 search 搜索代码库了解现有架构。
使用 write_file 保存架构设计文档。
"""
```

### 6.3 工具配置

```python
config = AgentConfig(
    name="system_architect",
    role=AgentRole.SPECIALIST,
    description="系统架构师 - 架构设计、技术选型、性能优化",
    model="qwen3.6-plus",
    tools=["read_file", "search", "write_file"],
    max_iterations=15,
    timeout=600,
    temperature=0.4,  # 适度创造性用于架构设计
    system_prompt=ARCHITECT_SYSTEM_PROMPT
)
```

| 工具 | 用途 | 安全策略 |
|------|------|---------|
| read_file | 阅读代码和配置进行架构分析 | 只读 |
| search | 搜索代码库了解架构模式 | 只读 |
| write_file | 输出架构设计文档 | 限制写入文档目录 |

> **注意**：ArchitectAgent 不需要 bash 工具，它是纯分析角色，不执行任何系统命令。

### 6.4 输入输出格式

**输入**：
```json
{
  "task_type": "architecture_design | tech_selection | performance_review | architecture_audit",
  "project_path": "/path/to/project",
  "requirements": ["需求列表"],
  "constraints": ["技术约束"],
  "current_state": "现有架构描述（可选）"
}
```

**输出**：
```json
{
  "success": true,
  "output_type": "architecture_doc | tech_matrix | performance_plan | audit_report",
  "content": {
    "architecture_doc": {...},
    "diagrams": {...}
  }
}
```

### 6.5 典型使用场景

| 场景 | 描述 | 协作 Agent |
|------|------|-----------|
| 新项目架构设计 | 项目启动时设计整体架构 | DesignerAgent（详细设计）、ProductManagerAgent |
| 技术债务评估 | 识别和评估现有技术债务 | ReviewerAgent（代码层面） |
| 性能瓶颈分析 | 分析系统性能问题 | DeveloperAgent、TesterAgent |
| 架构演进规划 | 规划从单体到微服务的演进 | DevOpsAgent（部署架构） |

---

## 7. ProductManagerAgent 详细设计

### 7.1 角色定位和职责

| 维度 | 描述 |
|------|------|
| **角色** | 产品经理 / 业务分析师 |
| **职责** | 需求优先级排序、用户故事编写、验收标准定义、产品路线图 |
| **权限** | 只读代码（了解实现）、可写需求文档 |
| **安全级别** | 低（纯文本处理） |

### 7.2 系统提示词设计

```python
PRODUCT_MANAGER_SYSTEM_PROMPT = """
你是资深产品经理和业务分析师，擅长需求管理、用户故事编写和产品规划。

## 核心职责

1. **需求优先级排序**
   - 使用 MoSCoW 方法（Must have / Should have / Could have / Won't have）
   - 使用 RICE 评分模型（Reach × Impact × Confidence ÷ Effort）
   - 使用 Kano 模型分析用户满意度
   - 考虑技术依赖和业务价值平衡

2. **用户故事编写**
   - 遵循标准格式："作为 [角色]，我想要 [功能]，以便 [价值]"
   - 拆分大型史诗（Epic）为可执行的 User Story
   - 定义清晰的验收标准（Acceptance Criteria）
   - 使用 Given-When-Then 格式编写行为驱动场景

3. **验收标准定义**
   - 为每个用户故事定义可测试的验收标准
   - 定义功能验收标准和性能验收标准
   - 定义边界条件和异常场景
   - 与 TesterAgent 协作确保可测试性

4. **产品路线图**
   - 制定短期（Sprint）和长期（Quarter）产品计划
   - 识别关键里程碑和依赖关系
   - 平衡新功能开发和技术债务
   - 生成产品路线图文档

## 优先级评估模型

### RICE 评分

| 因子 | 范围 | 说明 |
|------|------|------|
| Reach（覆盖范围） | 1-100 | 影响的用户数量 |
| Impact（影响力） | 0.25/0.5/1/2/3 | 对目标的影响程度 |
| Confidence（信心） | 50%/80%/100% | 对估计的信心 |
| Effort（工作量） | 人月数 | 实现所需工作量 |

RICE Score = (Reach × Impact × Confidence) / Effort

### MoSCoW 分类

| 类别 | 占比建议 | 说明 |
|------|---------|------|
| Must have | ~60% | 核心功能，没有则产品不可用 |
| Should have | ~20% | 重要功能，有变通方案 |
| Could have | ~15% | 锦上添花的功能 |
| Won't have | ~5% | 本次不做的功能 |

## 输出格式

### 用户故事
{
  "epic": "史诗名称",
  "stories": [
    {
      "id": "US-001",
      "title": "用户故事标题",
      "format": "作为 [角色]，我想要 [功能]，以便 [价值]",
      "priority": "Must have | Should have | Could have | Won't have",
      "rice_score": N.N,
      "story_points": N,
      "acceptance_criteria": [
        "Given [前置条件] When [操作] Then [预期结果]"
      ],
      "dependencies": ["US-000"],
      "technical_notes": "技术实现建议"
    }
  ]
}

### 产品路线图
{
  "roadmap": {
    "product_name": "产品名称",
    "vision": "产品愿景",
    "phases": [
      {
        "name": "阶段名称",
        "timeline": "Q1 2026",
        "theme": "阶段主题",
        "epics": ["史诗列表"],
        "milestones": ["里程碑"]
      }
    ]
  }
}

⚠️ **重要规则**：
- 需求优先级必须基于业务价值，而非技术偏好
- 用户故事必须可测试（TesterAgent 可直接转换为测试用例）
- 不做出技术实现决策（由 DesignerAgent 和 DeveloperAgent 负责）
- 需求文档必须包含明确的验收标准
- 保持需求与实现的一致性，定期回顾和更新

使用 read_file 读取现有需求文档和代码（了解实现状态）。
使用 write_file 保存需求文档和用户故事。
使用 search 搜索代码库了解当前实现情况。
"""
```

### 7.3 工具配置

```python
config = AgentConfig(
    name="product_manager",
    role=AgentRole.SPECIALIST,
    description="产品经理 - 需求管理、用户故事、验收标准、产品路线图",
    model="qwen3.6-turbo",  # 文本处理任务可用轻量模型
    tools=["read_file", "write_file", "search"],
    max_iterations=12,
    timeout=480,
    temperature=0.5,  # 需要一定创造性
    system_prompt=PRODUCT_MANAGER_SYSTEM_PROMPT
)
```

| 工具 | 用途 | 安全策略 |
|------|------|---------|
| read_file | 读取现有需求文档和代码 | 只读 |
| write_file | 输出需求文档和用户故事 | 限制写入文档目录 |
| search | 搜索代码库了解实现状态 | 只读 |

### 7.4 输入输出格式

**输入**：
```json
{
  "task_type": "story_writing | prioritization | roadmap | acceptance_criteria",
  "feature_description": "功能描述",
  "user_personas": ["用户角色列表"],
  "business_goals": ["业务目标"],
  "existing_stories": ["现有用户故事（可选）"]
}
```

**输出**：
```json
{
  "success": true,
  "output_type": "user_stories | prioritization_matrix | roadmap | acceptance_criteria",
  "content": {
    "stories": [...],
    "priorities": [...],
    "roadmap": {...}
  }
}
```

### 7.5 典型使用场景

| 场景 | 描述 | 协作 Agent |
|------|------|-----------|
| 需求拆解 | 将大型需求拆解为用户故事 | RequirementsAgent（原始需求分析） |
| Sprint 规划 | 为下一个 Sprint 排定优先级 | DeveloperAgent（工作量评估） |
| 验收标准制定 | 为功能定义可测试的验收标准 | TesterAgent（转换为测试用例） |
| 产品路线图更新 | 根据市场变化调整产品方向 | ArchitectAgent（技术可行性评估） |

---

## 8. 领域工具设计

### 8.1 工具基类设计

所有新领域工具继承 `BaseTool`：

```python
# src/core/tool.py 现有
class BaseTool(ABC):
    """工具基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> dict:
        """执行工具"""
        pass
```

### 8.2 ci_trigger.py - CI/CD 触发工具

```python
"""src/tools/ci_trigger.py - CI/CD 触发工具"""

from typing import Optional
from ..core.tool import BaseTool


class CITriggerTool(BaseTool):
    """CI/CD 触发工具
    
    安全的 CI/CD 流水线触发器，支持：
    - 触发指定的 CI/CD 流水线
    - 指定目标分支
    - 传递环境变量
    - 获取执行状态
    
    安全策略：
    - 白名单验证目标仓库
    - 不允许触发生产环境部署
    - 记录所有触发操作审计日志
    """
    
    @property
    def name(self) -> str:
        return "ci_trigger"
    
    @property
    def description(self) -> str:
        return "触发 CI/CD 流水线并获取执行状态。支持 GitHub Actions、GitLab CI。"
    
    @property
    def parameters(self) -> dict:
        return {
            "platform": {
                "type": "string",
                "enum": ["github_actions", "gitlab_ci"],
                "description": "CI/CD 平台"
            },
            "repository": {
                "type": "string",
                "description": "目标仓库 (owner/repo)"
            },
            "branch": {
                "type": "string",
                "description": "目标分支",
                "default": "main"
            },
            "workflow_name": {
                "type": "string",
                "description": "工作流名称或文件名"
            },
            "env_vars": {
                "type": "object",
                "description": "传递给流水线的环境变量",
                "default": {}
            },
            "dry_run": {
                "type": "boolean",
                "description": "仅验证配置，不实际触发",
                "default": False
            }
        }
    
    async def execute(self, **kwargs) -> dict:
        """执行 CI/CD 触发
        
        Args:
            platform: CI/CD 平台
            repository: 目标仓库
            branch: 目标分支
            workflow_name: 工作流名称
            env_vars: 环境变量
            dry_run: 是否仅验证
            
        Returns:
            {
                "success": bool,
                "workflow_id": str,
                "status": "triggered | queued | running",
                "url": str,
                "estimated_duration_seconds": int
            }
        """
        # 实现要点：
        # 1. 验证 repository 在白名单中
        # 2. 检查 branch 不是生产分支（如 prod/main 需额外确认）
        # 3. 调用对应平台的 API 触发流水线
        # 4. 返回流水线 URL 和状态
        # 5. 记录审计日志
        pass
```

**安全策略**：

| 策略 | 实现 |
|------|------|
| 仓库白名单 | 配置文件中维护允许触发的仓库列表 |
| 分支保护 | 禁止直接触发生产分支，需人工确认 |
| 操作审计 | 每次触发记录操作者、时间、目标 |
| 频率限制 | 同一流水线每分钟最多触发 3 次 |

### 8.3 docker_build.py - Docker 操作工具

```python
"""src/tools/docker_build.py - Docker 操作工具"""

from ..core.tool import BaseTool


class DockerBuildTool(BaseTool):
    """Docker 构建和管理工具
    
    安全的 Docker 操作封装，支持：
    - 构建 Docker 镜像
    - 运行容器（开发/测试环境）
    - 检查镜像/容器状态
    - 清理无用镜像
    
    安全策略：
    - 禁止挂载主机敏感目录
    - 限制容器资源（CPU/内存）
    - 禁止 --privileged 模式
    - 网络隔离（默认 bridge）
    """
    
    @property
    def name(self) -> str:
        return "docker_build"
    
    @property
    def description(self) -> str:
        return "执行 Docker 构建和管理操作。安全封装，限制危险操作。"
    
    @property
    def parameters(self) -> dict:
        return {
            "action": {
                "type": "string",
                "enum": ["build", "run", "inspect", "prune", "logs"],
                "description": "Docker 操作类型"
            },
            "context_path": {
                "type": "string",
                "description": "构建上下文路径"
            },
            "dockerfile": {
                "type": "string",
                "description": "Dockerfile 路径（可选）",
                "default": "Dockerfile"
            },
            "image_name": {
                "type": "string",
                "description": "镜像名称"
            },
            "tag": {
                "type": "string",
                "description": "镜像标签",
                "default": "latest"
            },
            "build_args": {
                "type": "object",
                "description": "构建参数",
                "default": {}
            },
            "container_name": {
                "type": "string",
                "description": "容器名称（run 操作）"
            },
            "ports": {
                "type": "array",
                "items": {"type": "string"},
                "description": "端口映射 (host:container)",
                "default": []
            },
            "no_cache": {
                "type": "boolean",
                "description": "不使用构建缓存",
                "default": False
            }
        }
    
    async def execute(self, **kwargs) -> dict:
        """执行 Docker 操作
        
        Returns:
            {
                "success": bool,
                "action": "build | run | ...",
                "image_id": str,  # build 操作
                "container_id": str,  # run 操作
                "output": str,
                "size_bytes": int,  # build 后的镜像大小
                "warnings": [str]
            }
        """
        # 实现要点：
        # 1. 验证 context_path 在项目目录范围内
        # 2. 检查 Dockerfile 内容（禁止 FROM 不安全的基础镜像）
        # 3. build 时限制 --memory、--cpus
        # 4. run 时禁止 --privileged、-v 挂载敏感目录
        # 5. 默认使用 bridge 网络
        pass
```

**安全策略**：

| 策略 | 实现 |
|------|------|
| 路径限制 | 构建上下文必须在项目目录内 |
| 基础镜像检查 | 禁止使用 `latest` 标签和未知来源镜像 |
| 资源限制 | 容器最大 4GB 内存、2 CPU |
| 特权禁止 | 强制 `--privileged=false` |
| 网络隔离 | 默认使用 bridge 网络，禁止 host 网络 |

### 8.4 security_scan.py - 安全扫描工具

```python
"""src/tools/security_scan.py - 安全扫描工具"""

from ..core.tool import BaseTool


class SecurityScanTool(BaseTool):
    """自动化安全扫描工具
    
    集成多种安全扫描引擎：
    - 依赖漏洞扫描（pip-audit, npm audit, safety）
    - 代码安全扫描（bandit, semgrep, trivy）
    - 容器镜像扫描（trivy, grype）
    - 配置安全检查（checkov, tfsec）
    
    安全策略：
    - 沙箱执行，不修改源代码
    - 结果只读输出
    - 扫描超时限制
    """
    
    @property
    def name(self) -> str:
        return "security_scan"
    
    @property
    def description(self) -> str:
        return "执行自动化安全扫描。支持依赖审计、SAST、容器扫描、配置检查。"
    
    @property
    def parameters(self) -> dict:
        return {
            "scan_type": {
                "type": "string",
                "enum": [
                    "dependency_audit", "sast",
                    "container_scan", "config_check", "full_scan"
                ],
                "description": "扫描类型"
            },
            "target_path": {
                "type": "string",
                "description": "扫描目标路径"
            },
            "severity_threshold": {
                "type": "string",
                "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                "description": "最低报告严重性",
                "default": "MEDIUM"
            },
            "languages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "目标语言（如 python, javascript）",
                "default": ["python"]
            },
            "output_format": {
                "type": "string",
                "enum": ["json", "sarif", "text"],
                "description": "输出格式",
                "default": "json"
            }
        }
    
    async def execute(self, **kwargs) -> dict:
        """执行安全扫描
        
        Returns:
            {
                "success": bool,
                "scan_type": str,
                "findings": [
                    {
                        "id": str,
                        "severity": "CRITICAL | HIGH | MEDIUM | LOW",
                        "category": str,
                        "file": str,
                        "line": int,
                        "description": str,
                        "cve": str,
                        "cvss_score": float,
                        "remediation": str
                    }
                ],
                "summary": {
                    "total": int,
                    "critical": int,
                    "high": int,
                    "medium": int,
                    "low": int
                },
                "scan_duration_seconds": float
            }
        """
        # 实现要点：
        # 1. 根据 scan_type 选择对应扫描引擎
        # 2. 沙箱中执行扫描命令
        # 3. 解析输出为标准格式
        # 4. 按严重性过滤结果
        # 5. 设置超时（默认 300 秒）
        pass
```

**安全策略**：

| 策略 | 实现 |
|------|------|
| 沙箱执行 | 扫描命令在隔离环境中运行 |
| 只读输出 | 不修改目标文件 |
| 超时保护 | 单次扫描最长 300 秒 |
| 网络隔离 | 漏洞数据库可访问，禁止其他网络请求 |

### 8.5 data_transform.py - 数据转换工具

```python
"""src/tools/data_transform.py - 数据转换工具"""

from ..core.tool import BaseTool


class DataTransformTool(BaseTool):
    """数据转换工具
    
    安全的数据处理操作：
    - 格式转换（CSV ↔ JSON ↔ Parquet ↔ Excel）
    - 数据清洗（去重、填充缺失值、类型转换）
    - 数据聚合和统计
    - PII 检测和脱敏
    
    安全策略：
    - 文件大小限制（<500MB）
    - PII 自动检测和脱敏
    - 操作日志记录
    - 原始数据保护
    """
    
    @property
    def name(self) -> str:
        return "data_transform"
    
    @property
    def description(self) -> str:
        return "执行数据转换操作。支持格式转换、数据清洗、PII脱敏。"
    
    @property
    def parameters(self) -> dict:
        return {
            "operation": {
                "type": "string",
                "enum": [
                    "convert_format", "clean", "aggregate",
                    "filter", "sort", "deduplicate", "anonymize"
                ],
                "description": "转换操作类型"
            },
            "input_path": {
                "type": "string",
                "description": "输入文件路径"
            },
            "output_path": {
                "type": "string",
                "description": "输出文件路径"
            },
            "output_format": {
                "type": "string",
                "enum": ["csv", "json", "parquet", "excel"],
                "description": "输出格式"
            },
            "transformations": {
                "type": "array",
                "description": "转换操作列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "column": {"type": "string"},
                        "value": {},
                        "condition": {"type": "string"}
                    }
                },
                "default": []
            },
            "anonymize_pii": {
                "type": "boolean",
                "description": "是否自动检测并脱敏 PII 数据",
                "default": False
            },
            "chunk_size": {
                "type": "integer",
                "description": "分块处理大小（行数）",
                "default": 10000
            }
        }
    
    async def execute(self, **kwargs) -> dict:
        """执行数据转换
        
        Returns:
            {
                "success": bool,
                "operation": str,
                "input_rows": int,
                "output_rows": int,
                "output_path": str,
                "output_size_bytes": int,
                "pii_detected": bool,
                "pii_columns": [str],
                "warnings": [str]
            }
        """
        # 实现要点：
        # 1. 验证输入文件大小（<500MB）
        # 2. 验证输入路径安全性（不访问系统敏感目录）
        # 3. 大文件分块处理，避免 OOM
        # 4. PII 检测（邮箱、手机号、身份证号等）
        # 5. 操作前后数据校验（行数、checksum）
        # 6. 保留原始文件，新文件写入输出路径
        pass
```

**安全策略**：

| 策略 | 实现 |
|------|------|
| 文件大小 | 输入文件 < 500MB |
| 内存限制 | 分块处理，最大 1GB 内存 |
| PII 检测 | 自动识别邮箱、手机号、身份证等 |
| 路径保护 | 禁止访问 `/etc`, `/proc` 等系统目录 |
| 数据校验 | 转换前后行数和 checksum 验证 |

---

## 9. Executor 注册

### 9.1 扩展 ExecutorCapability 枚举

在 `src/plan/graph.py` 中扩展现有能力枚举：

```python
class ExecutorCapability(Enum):
    # ---- Phase 1-3 已有能力 ----
    REQUIREMENTS_ANALYSIS = "requirements_analysis"
    TECHNICAL_DESIGN = "technical_design"
    CODE_DEVELOPMENT = "code_development"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    BUG_FIXING = "bug_fixing"
    DOCUMENTATION = "documentation"
    
    # ---- Phase 4 已有能力 ----
    SECURITY_AUDIT = "security_audit"
    DEPLOYMENT = "deployment"
    GENERIC = "generic"
    
    # ---- Phase 6 新增能力 ----
    DEVOPS_CI_CD = "devops_ci_cd"          # CI/CD 配置和触发
    DEVOPS_CONTAINER = "devops_container"  # 容器构建和管理
    DEVOPS_INFRA = "devops_infrastructure" # 基础设施即代码
    DATA_ENGINEERING = "data_engineering"  # 数据处理和分析
    ARCHITECTURE_DESIGN = "architecture_design"  # 架构设计
    PRODUCT_MANAGEMENT = "product_management"    # 产品管理
```

### 9.2 注册新 Agent 到 ExecutorRegistry

在 `src/executors/registry.py` 中注册：

```python
# src/executors/registry.py 新增注册逻辑

from ..agents.devops import create_devops_agent
from ..agents.security import create_security_agent
from ..agents.data import create_data_agent
from ..agents.architect import create_architect_agent
from ..agents.product_manager import create_product_manager_agent

def register_domain_agents(registry, api_key=None):
    """注册 Phase 6 领域 Agent 到 ExecutorRegistry"""
    
    # DevOps Agent - 多能力注册
    devops_agent = create_devops_agent(api_key=api_key)
    registry.register(
        name="devops_agent",
        agent=devops_agent,
        capabilities=[
            ExecutorCapability.DEVOPS_CI_CD,
            ExecutorCapability.DEVOPS_CONTAINER,
            ExecutorCapability.DEVOPS_INFRA,
        ],
        metadata={
            "phase": 6,
            "description": "DevOps工程师 - CI/CD、容器化、基础设施管理",
            "tools": ["ci_trigger", "docker_build"],
            "model": "qwen3.6-plus",
        }
    )
    
    # Security Agent
    security_agent = create_security_agent(api_key=api_key)
    registry.register(
        name="security_agent",
        agent=security_agent,
        capabilities=[ExecutorCapability.SECURITY_AUDIT],
        metadata={
            "phase": 6,
            "description": "安全工程师 - SAST扫描、依赖审计、配置审查",
            "tools": ["security_scan"],
            "model": "qwen3.6-plus",
        }
    )
    
    # Data Agent
    data_agent = create_data_agent(api_key=api_key)
    registry.register(
        name="data_agent",
        agent=data_agent,
        capabilities=[ExecutorCapability.DATA_ENGINEERING],
        metadata={
            "phase": 6,
            "description": "数据工程师 - 数据清洗、分析、SQL查询、可视化",
            "tools": ["data_transform"],
            "model": "qwen3.6-plus",
        }
    )
    
    # Architect Agent
    architect_agent = create_architect_agent(api_key=api_key)
    registry.register(
        name="architect_agent",
        agent=architect_agent,
        capabilities=[ExecutorCapability.ARCHITECTURE_DESIGN],
        metadata={
            "phase": 6,
            "description": "系统架构师 - 架构设计、技术选型、性能优化",
            "tools": [],  # 纯分析角色，使用标准工具
            "model": "qwen3.6-plus",
        }
    )
    
    # Product Manager Agent
    pm_agent = create_product_manager_agent(api_key=api_key)
    registry.register(
        name="product_manager_agent",
        agent=pm_agent,
        capabilities=[ExecutorCapability.PRODUCT_MANAGEMENT],
        metadata={
            "phase": 6,
            "description": "产品经理 - 需求管理、用户故事、验收标准、产品路线图",
            "tools": [],
            "model": "qwen3.6-turbo",
        }
    )
```

### 9.3 能力匹配优先级

当 PlannerAgent 需要匹配 Executor 时，按以下优先级：

```
1. 精确能力匹配 (ExecutorCapability 完全匹配)
2. 能力子集匹配 (需要的能力是注册能力的子集)
3. GENERIC 兜底 (使用 GENERIC 能力的 Agent)
```

---

## 10. 配置示例

### 10.1 DevOps CI/CD 流水线配置

```yaml
# configs/workflows/devops-ci.yaml
schema_version: "1.0"

meta:
  name: "devops-ci-pipeline"
  version: "1.0.0"
  description: "DevOps CI/CD 配置和部署流水线"

defaults:
  model: "qwen3.6-plus"
  max_iterations: 15
  enable_human_review: true
  timeout_seconds: 600

nodes:
  - id: "ci_config"
    name: "CI/CD 配置生成"
    type: "executor"
    executor: "devops_agent"
    outputs: ["ci_config_file"]
    dependencies: []
    prompt_template: |
      为以下项目生成 CI/CD 配置：
      项目路径: {project_path}
      语言: {language}
      要求: {requirements}

  - id: "docker_build"
    name: "Docker 镜像构建"
    type: "executor"
    executor: "devops_agent"
    inputs:
      - source: "ci_config"
        target: "ci_config_file"
    outputs: ["docker_image_info"]
    dependencies: ["ci_config"]

  - id: "security_check"
    name: "镜像安全扫描"
    type: "executor"
    executor: "security_agent"
    inputs:
      - source: "docker_build"
        target: "docker_image_info"
    outputs: ["security_report"]
    dependencies: ["docker_build"]

  - id: "deploy"
    name: "部署到测试环境"
    type: "executor"
    executor: "devops_agent"
    inputs:
      - source: "docker_build"
        target: "docker_image_info"
      - source: "security_check"
        target: "security_report"
    outputs: ["deployment_status"]
    dependencies: ["security_check"]

conditions:
  security_gate:
    type: "conditional"
    source: "security_check"
    branches:
      - condition: "security_report.blocked == false"
        target: "deploy"
        label: "安全检查通过"
      - default: true
        target: "__end__"
        label: "安全扫描失败"

verifier:
  enabled: true
  rules:
    - dimension: "security"
      threshold: 0.8
    - dimension: "deployment_health"
      threshold: 0.7
  on_failure: "fail"
```

### 10.2 安全审查流水线配置

```yaml
# configs/workflows/security-audit.yaml
schema_version: "1.0"

meta:
  name: "security-audit-pipeline"
  version: "1.0.0"
  description: "全面安全审查流水线"

defaults:
  model: "qwen3.6-plus"
  max_iterations: 10
  enable_human_review: true
  timeout_seconds: 600

nodes:
  - id: "sast_scan"
    name: "SAST 代码安全扫描"
    type: "executor"
    executor: "security_agent"
    outputs: ["sast_report"]
    dependencies: []

  - id: "dependency_audit"
    name: "依赖安全审计"
    type: "executor"
    executor: "security_agent"
    outputs: ["dependency_report"]
    dependencies: []

  - id: "config_audit"
    name: "配置安全审计"
    type: "executor"
    executor: "security_agent"
    outputs: ["config_report"]
    dependencies: []

  - id: "consolidate"
    name: "安全报告汇总"
    type: "executor"
    executor: "security_agent"
    inputs:
      - source: "sast_scan"
        target: "sast_report"
      - source: "dependency_audit"
        target: "dependency_report"
      - source: "config_audit"
        target: "config_report"
    outputs: ["final_security_report"]
    dependencies: ["sast_scan", "dependency_audit", "config_audit"]

verifier:
  enabled: true
  rules:
    - dimension: "security"
      threshold: 0.9
  on_failure: "fail"
```

### 10.3 数据分析流水线配置

```yaml
# configs/workflows/data-analysis.yaml
schema_version: "1.0"

meta:
  name: "data-analysis-pipeline"
  version: "1.0.0"
  description: "数据分析流水线：清洗 → 分析 → 可视化"

defaults:
  model: "qwen3.6-plus"
  max_iterations: 20
  enable_human_review: false
  timeout_seconds: 900

nodes:
  - id: "data_cleaning"
    name: "数据清洗"
    type: "executor"
    executor: "data_agent"
    outputs: ["cleaned_data"]
    dependencies: []
    timeout_seconds: 600

  - id: "data_analysis"
    name: "数据分析"
    type: "executor"
    executor: "data_agent"
    inputs:
      - source: "data_cleaning"
        target: "cleaned_data"
    outputs: ["analysis_results"]
    dependencies: ["data_cleaning"]

  - id: "visualization"
    name: "数据可视化"
    type: "executor"
    executor: "data_agent"
    inputs:
      - source: "data_analysis"
        target: "analysis_results"
    outputs: ["visualizations"]
    dependencies: ["data_analysis"]
```

### 10.4 全生命周期流水线（所有 Agent 协作）

```yaml
# configs/workflows/full-lifecycle.yaml
schema_version: "1.0"

meta:
  name: "full-lifecycle-pipeline"
  version: "1.0.0"
  description: "完整研发生命周期：产品 → 需求 → 架构 → 设计 → 开发 → 安全 → 测试 → DevOps"

defaults:
  model: "qwen3.6-plus"
  max_iterations: 20
  enable_human_review: true
  timeout_seconds: 600

nodes:
  # 产品阶段
  - id: "product_planning"
    name: "产品规划"
    type: "executor"
    executor: "product_manager_agent"
    model: "qwen3.6-turbo"
    outputs: ["product_requirements", "user_stories", "roadmap"]
    dependencies: []

  # 需求分析
  - id: "requirements"
    name: "需求分析"
    type: "executor"
    executor: "requirements_agent"
    inputs:
      - source: "product_planning"
        target: "product_requirements"
    outputs: ["requirements_doc"]
    dependencies: ["product_planning"]

  # 架构设计
  - id: "architecture"
    name: "架构设计"
    type: "executor"
    executor: "architect_agent"
    inputs:
      - source: "requirements"
        target: "requirements_doc"
    outputs: ["architecture_doc"]
    dependencies: ["requirements"]

  # 技术设计
  - id: "design"
    name: "技术设计"
    type: "executor"
    executor: "designer_agent"
    inputs:
      - source: "requirements"
        target: "requirements_doc"
      - source: "architecture"
        target: "architecture_doc"
    outputs: ["design_doc"]
    dependencies: ["requirements", "architecture"]

  # 开发实现
  - id: "develop"
    name: "开发实现"
    type: "executor"
    executor: "developer_agent"
    inputs:
      - source: "design"
        target: "design_doc"
    outputs: ["source_code"]
    dependencies: ["design"]

  # 代码审查
  - id: "review"
    name: "代码审查"
    type: "executor"
    executor: "reviewer_agent"
    inputs:
      - source: "develop"
        target: "source_code"
    outputs: ["review_report"]
    dependencies: ["develop"]

  # 安全扫描
  - id: "security"
    name: "安全审查"
    type: "executor"
    executor: "security_agent"
    inputs:
      - source: "develop"
        target: "source_code"
    outputs: ["security_report"]
    dependencies: ["develop"]

  # 测试验证
  - id: "test"
    name: "测试验证"
    type: "executor"
    executor: "tester_agent"
    inputs:
      - source: "develop"
        target: "source_code"
      - source: "review"
        target: "review_report"
    outputs: ["test_report"]
    dependencies: ["review"]

  # DevOps 部署
  - id: "ci_cd"
    name: "CI/CD 配置"
    type: "executor"
    executor: "devops_agent"
    inputs:
      - source: "develop"
        target: "source_code"
    outputs: ["ci_config"]
    dependencies: ["develop"]

conditions:
  review_router:
    type: "conditional"
    source: "review"
    branches:
      - condition: "review_result.approved == true"
        target: "test"
        label: "审查通过"
      - default: true
        target: "develop"
        label: "需要修改"

  security_gate:
    type: "conditional"
    source: "security"
    branches:
      - condition: "security_report.blocked == false"
        target: "ci_cd"
        label: "安全检查通过"
      - default: true
        target: "develop"
        label: "安全漏洞需修复"

  test_router:
    type: "conditional"
    source: "test"
    branches:
      - condition: "test_result.passed == true"
        target: "ci_cd"
        label: "测试通过"
      - default: true
        target: "develop"
        label: "测试失败"
```

---

## 11. Agent 协作模式

### 11.1 完整协作矩阵

| 上游 Agent | 下游 Agent | 传递内容 | 触发条件 |
|-----------|-----------|---------|---------|
| ProductManagerAgent | RequirementsAgent | 产品需求文档、用户故事 | 产品规划完成后 |
| ProductManagerAgent | ArchitectAgent | 业务约束、用户画像 | 架构设计阶段 |
| ProductManagerAgent | TesterAgent | 验收标准 | 测试用例生成 |
| RequirementsAgent | ArchitectAgent | 功能需求、非功能需求 | 架构设计输入 |
| RequirementsAgent | DesignerAgent | 结构化需求文档 | 技术设计输入 |
| ArchitectAgent | DesignerAgent | 架构决策记录、技术选型 | 详细设计输入 |
| ArchitectAgent | DevOpsAgent | 部署架构要求 | 基础设施配置 |
| DesignerAgent | DeveloperAgent | 技术设计文档 | 开发实现输入 |
| DeveloperAgent | ReviewerAgent | 源代码 | 代码审查 |
| DeveloperAgent | SecurityAgent | 源代码 | 安全扫描 |
| DeveloperAgent | TesterAgent | 源代码 | 测试执行 |
| DeveloperAgent | DataAgent | 数据结构定义 | 数据处理 |
| DeveloperAgent | DevOpsAgent | 应用代码 | CI/CD 配置 |
| ReviewerAgent | FixerAgent | 审查报告 | 需要修复 |
| ReviewerAgent | DeveloperAgent | 审查意见 | 代码修改 |
| SecurityAgent | DeveloperAgent | 安全漏洞报告 | 漏洞修复 |
| SecurityAgent | DevOpsAgent | 镜像扫描结果 | 部署决策 |
| TesterAgent | FixerAgent | 测试失败报告 | Bug 修复 |
| TesterAgent | DeveloperAgent | 回归测试结果 | 修复验证 |
| DataAgent | ProductManagerAgent | 数据分析报告 | 需求调整 |
| DataAgent | TesterAgent | 测试数据集 | 测试数据准备 |
| DevOpsAgent | SecurityAgent | 部署配置 | 部署安全审查 |
| DevOpsAgent | TesterAgent | 测试环境状态 | 集成测试 |

### 11.2 协作模式图示

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         全生命周期协作流程                                    │
│                                                                             │
│  ┌──────────────┐                                                          │
│  │ProductManager│ ── 用户故事 ──► ┌──────────────┐                         │
│  │   Agent      │                 │Requirements  │                         │
│  └──────────────┘                 │    Agent     │                         │
│                                   └──────┬───────┘                         │
│                                          │ 需求文档                          │
│                                   ┌──────▼───────┐                         │
│                                   │ Architect    │ ── 架构决策 ──► ┌──────┐│
│                                   │    Agent     │                  │Design││
│                                   └──────┬───────┘                  │Agent ││
│                                          │ 需求 + 架构               └──┬───┘│
│                                   ┌──────▼───────┐                     │    │
│                                   │ Developer    │ ◄───────────────────┘    │
│                                   │    Agent     │                          │
│                                   └──────┬───────┘                          │
│                                          │ 源代码                            │
│                    ┌─────────────────────┼─────────────────────┐            │
│                    ▼                     ▼                     ▼            │
│            ┌───────────────┐    ┌───────────────┐    ┌───────────────┐    │
│            │  Reviewer     │    │  Security     │    │   Tester     │    │
│            │   Agent       │    │   Agent       │    │   Agent      │    │
│            └───────┬───────┘    └───────┬───────┘    └───────┬───────┘    │
│                    │                    │                    │            │
│                    ▼                    ▼                    ▼            │
│            ┌───────────────┐    ┌───────────────┐    ┌───────────────┐    │
│            │   Fixer       │    │  Developer    │    │   Fixer      │    │
│            │   Agent       │    │   Agent       │    │   Agent      │    │
│            └───────────────┘    └───────────────┘    └───────────────┘    │
│                                                                         │
│                    ┌─────────────────────────────────┐                   │
│                    │         DevOps Agent            │                   │
│                    │  (代码审查✓ + 安全✓ + 测试✓)    │                   │
│                    └───────────────┬─────────────────┘                   │
│                                    │                                     │
│                    ┌───────────────▼─────────────────┐                   │
│                    │      CI/CD + Docker + K8s       │                   │
│                    └─────────────────────────────────┘                   │
│                                                                         │
│  ┌──────────────┐                                                       │
│  │  Data Agent  │ ◄── 数据分析结果 ── 反馈 ── ProductManagerAgent        │
│  └──────────────┘                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.3 关键协作场景

#### 场景 1: 安全门禁集成

```
DeveloperAgent ──(代码)──► SecurityAgent ──(扫描结果)──► 判断
                                                       │
                                              blocked? ├─ YES ─► DeveloperAgent (修复)
                                                       │
                                                       └─ NO  ─► DevOpsAgent (部署)
```

#### 场景 2: 数据驱动需求调整

```
DataAgent ──(数据分析)──► ProductManagerAgent ──(需求调整)──► RequirementsAgent
                                                                    │
                                                                    ▼
                                                              重新规划开发任务
```

#### 场景 3: 架构-运维联动

```
ArchitectAgent ──(部署架构)──► DevOpsAgent ──(基础设施配置)──► 部署环境
                              │                                      │
                              ▼                                      ▼
                        性能指标反馈                          实际运行数据
                              │                                      │
                              └───────────── 优化循环 ───────────────┘
```

---

## 12. 模型选型建议

### 12.1 模型选型矩阵

| Agent | 推荐模型 | 备选模型 | 选型理由 | 预估成本/次 |
|-------|---------|---------|---------|------------|
| DevOpsAgent | qwen3.6-plus | qwen3.5-plus | 需要理解复杂配置文件和命令，中等推理需求 | ¥0.5-1.5 |
| SecurityAgent | qwen3.6-plus | qwen3.5-plus | 安全审查需要高精度和低幻觉率，需强推理能力 | ¥0.5-1.5 |
| DataAgent | qwen3.6-plus | qwen3.5-plus | 需要理解数据结构和编写分析代码 | ¥0.8-2.0 |
| ArchitectAgent | qwen3.6-plus | qwen3.5-plus | 架构设计需要深度分析和权衡能力 | ¥1.0-2.5 |
| ProductManagerAgent | qwen3.6-turbo | qwen3.5-turbo | 主要是文本处理和结构化输出，轻量模型足够 | ¥0.1-0.3 |

### 12.2 模型选择策略

```
┌─────────────────────────────────────────────────────────┐
│                    模型选择决策树                         │
│                                                         │
│  任务是否需要深度推理？                                   │
│  ├─ YES → 需要代码生成/安全分析？                         │
│  │          ├─ YES → qwen3.6-plus                       │
│  │          └─ NO  → 需要复杂架构决策？                   │
│  │                    ├─ YES → qwen3.6-plus             │
│  │                    └─ NO  → qwen3.6-plus             │
│  │                                                         │
│  └─ NO  → 主要是文本处理/结构化输出？                     │
│              ├─ YES → qwen3.6-turbo                      │
│              └─ NO  → qwen3.6-plus                       │
└─────────────────────────────────────────────────────────┘
```

### 12.3 成本优化建议

| 策略 | 说明 | 预计节省 |
|------|------|---------|
| 任务分级 | 简单任务用 turbo，复杂任务用 plus | 30-50% |
| 缓存复用 | 相同输入复用历史结果 | 20-40% |
| 批量处理 | 合并相似请求减少 API 调用 | 15-25% |
| 温度控制 | 确定性任务用低温度减少重试 | 10-15% |
| 输出限制 | 控制 max_tokens 避免过长输出 | 10-20% |

### 12.4 Agent 模型配置参数

| Agent | model | temperature | max_tokens | max_iterations |
|-------|-------|------------|------------|---------------|
| DevOpsAgent | qwen3.6-plus | 0.2 | 8192 | 20 |
| SecurityAgent | qwen3.6-plus | 0.1 | 8192 | 15 |
| DataAgent | qwen3.6-plus | 0.3 | 8192 | 20 |
| ArchitectAgent | qwen3.6-plus | 0.4 | 16384 | 15 |
| ProductManagerAgent | qwen3.6-turbo | 0.5 | 4096 | 12 |

> **说明**：
> - `temperature` 越低，输出越确定（安全审查需要高确定性）
> - `temperature` 越高，输出越有创造性（产品管理需要创造性）
> - `max_tokens` 根据输出复杂度调整
> - `max_iterations` 根据任务复杂度调整

---

## 13. 文件变更清单

### 13.1 新增文件

| 文件路径 | 描述 | 优先级 |
|---------|------|-------|
| `src/agents/devops.py` | DevOpsAgent 实现 | P0 |
| `src/agents/security.py` | SecurityAgent 实现 | P0 |
| `src/agents/data.py` | DataAgent 实现 | P1 |
| `src/agents/architect.py` | ArchitectAgent 实现 | P1 |
| `src/agents/product_manager.py` | ProductManagerAgent 实现 | P1 |
| `src/tools/ci_trigger.py` | CI/CD 触发工具 | P0 |
| `src/tools/docker_build.py` | Docker 操作工具 | P0 |
| `src/tools/security_scan.py` | 安全扫描工具 | P0 |
| `src/tools/data_transform.py` | 数据转换工具 | P1 |
| `configs/workflows/devops-ci.yaml` | DevOps CI/CD 配置示例 | P1 |
| `configs/workflows/security-audit.yaml` | 安全审计配置示例 | P1 |
| `configs/workflows/data-analysis.yaml` | 数据分析配置示例 | P2 |
| `configs/workflows/full-lifecycle.yaml` | 全生命周期配置示例 | P2 |
| `tests/agents/test_devops.py` | DevOpsAgent 测试 | P0 |
| `tests/agents/test_security.py` | SecurityAgent 测试 | P0 |
| `tests/agents/test_data.py` | DataAgent 测试 | P1 |
| `tests/agents/test_architect.py` | ArchitectAgent 测试 | P1 |
| `tests/agents/test_product_manager.py` | ProductManagerAgent 测试 | P1 |
| `tests/tools/test_ci_trigger.py` | CI 触发工具测试 | P0 |
| `tests/tools/test_docker_build.py` | Docker 工具测试 | P0 |
| `tests/tools/test_security_scan.py` | 安全扫描工具测试 | P0 |
| `tests/tools/test_data_transform.py` | 数据转换工具测试 | P1 |

### 13.2 修改文件

| 文件路径 | 修改内容 | 优先级 |
|---------|---------|-------|
| `src/plan/graph.py` | 扩展 ExecutorCapability 枚举 | P0 |
| `src/executors/registry.py` | 注册新 Agent 和能力 | P0 |
| `src/agents/__init__.py` | 导入新 Agent | P0 |
| `src/tools/__init__.py` | 导入新工具 | P0 |
| `src/cli/main.py` | 新增领域 Agent 相关 CLI 命令 | P1 |
| `docs/design/phase4-pev-architecture.md` | 补充新 Agent 架构图 | P2 |
| `docs/design/phase5-configurable-orchestration.md` | 补充新 Agent 配置示例 | P2 |

### 13.3 文件依赖关系

```
ExecutorCapability 扩展 (graph.py)
    │
    ├── DevOpsAgent (devops.py) ──► ci_trigger.py, docker_build.py
    ├── SecurityAgent (security.py) ──► security_scan.py
    ├── DataAgent (data.py) ──► data_transform.py
    ├── ArchitectAgent (architect.py)
    └── ProductManagerAgent (product_manager.py)
            │
            └── ExecutorRegistry 注册 (registry.py)
                    │
                    └── CLI 集成 (main.py)
```

---

## 14. 测试策略

### 14.1 测试金字塔

```
                    ┌──────────┐
                    │ E2E 测试  │  ← 完整工作流集成测试
                    │  (少量)  │
                  ┌─┴──────────┴─┐
                  │  集成测试     │  ← Agent + 工具协作测试
                  │  (适量)      │
                ┌─┴──────────────┴─┐
                │    单元测试       │  ← 单个 Agent/工具测试
                │    (大量)        │
              ┌─┴──────────────────┴─┐
              │      Mock 测试       │  ← LLM 调用模拟
              │      (大量)          │
              └──────────────────────┘
```

### 14.2 各 Agent 测试计划

#### DevOpsAgent 测试

| 测试类别 | 测试用例 | 优先级 |
|---------|---------|-------|
| 单元测试 | Agent 初始化配置正确 | P0 |
| 单元测试 | 系统提示词包含所有职责描述 | P0 |
| 单元测试 | 工具列表正确配置 | P0 |
| Mock 测试 | CI 配置生成任务（Mock LLM） | P0 |
| Mock 测试 | Dockerfile 优化任务（Mock LLM） | P0 |
| 集成测试 | ci_trigger 工具调用（Mock API） | P0 |
| 集成测试 | docker_build 工具调用（Mock Docker） | P0 |
| E2E 测试 | 完整 CI/CD 流水线配置生成 | P1 |

```python
# tests/agents/test_devops.py 示例
class TestDevOpsAgent:
    """DevOpsAgent 测试"""
    
    def test_agent_initialization(self):
        """测试 Agent 初始化配置"""
        agent = create_devops_agent(api_key="test-key")
        assert agent.config.name == "devops_engineer"
        assert agent.config.role == AgentRole.SPECIALIST
        assert "ci_trigger" in agent.config.tools
        assert "docker_build" in agent.config.tools
        assert agent.config.temperature == 0.2
    
    @pytest.mark.asyncio
    async def test_ci_config_generation(self, mock_llm):
        """测试 CI 配置生成"""
        mock_llm.set_response("""
        ```yaml
        name: CI
        on: [push]
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
              - run: pip install -r requirements.txt
              - run: pytest
        ```
        """)
        
        agent = create_devops_agent(api_key="test-key")
        result = await agent.run("为 Python 项目生成 GitHub Actions CI 配置")
        
        assert result.success
        assert "ci_config_file" in result.output
    
    def test_security_constraints(self):
        """测试安全约束"""
        agent = create_devops_agent()
        prompt = agent.config.system_prompt
        assert "不直接操作生产环境" in prompt
        assert "不执行 apply" in prompt
```

#### SecurityAgent 测试

| 测试类别 | 测试用例 | 优先级 |
|---------|---------|-------|
| 单元测试 | Agent 初始化配置正确 | P0 |
| 单元测试 | 系统提示词包含严重性评估标准 | P0 |
| 单元测试 | temperature 为 0.1（高确定性） | P0 |
| Mock 测试 | SAST 扫描任务（Mock LLM） | P0 |
| Mock 测试 | 依赖漏洞报告生成 | P0 |
| 集成测试 | security_scan 工具调用 | P0 |
| 集成测试 | CRITICAL 漏洞标记 blocked=true | P0 |
| E2E 测试 | 完整安全审查流水线 | P1 |

#### DataAgent 测试

| 测试类别 | 测试用例 | 优先级 |
|---------|---------|-------|
| 单元测试 | Agent 初始化配置正确 | P0 |
| 单元测试 | 工具列表包含 data_transform | P0 |
| Mock 测试 | 数据分析任务（Mock LLM） | P0 |
| Mock 测试 | SQL 查询生成任务 | P1 |
| 集成测试 | data_transform 工具调用 | P1 |
| 集成测试 | PII 脱敏功能 | P0 |
| E2E 测试 | 数据分析流水线 | P1 |

#### ArchitectAgent 测试

| 测试类别 | 测试用例 | 优先级 |
|---------|---------|-------|
| 单元测试 | Agent 初始化配置正确 | P0 |
| 单元测试 | 无 bash 工具（只读角色） | P0 |
| Mock 测试 | 架构设计文档生成 | P0 |
| Mock 测试 | 技术选型对比矩阵 | P0 |
| E2E 测试 | 架构评审流程 | P1 |

#### ProductManagerAgent 测试

| 测试类别 | 测试用例 | 优先级 |
|---------|---------|-------|
| 单元测试 | Agent 初始化配置正确 | P0 |
| 单元测试 | 使用 qwen3.6-turbo 模型 | P0 |
| Mock 测试 | 用户故事生成 | P0 |
| Mock 测试 | RICE 优先级计算 | P0 |
| Mock 测试 | 产品路线图生成 | P1 |
| E2E 测试 | 需求拆解到用户故事 | P1 |

### 14.3 领域工具测试计划

#### ci_trigger 工具测试

| 测试用例 | 描述 | 优先级 |
|---------|------|-------|
| 白名单验证 | 非白名单仓库触发被拒绝 | P0 |
| 分支保护 | 生产分支触发需要确认 | P0 |
| dry_run 模式 | 仅验证配置不实际触发 | P0 |
| API 调用 | 正确调用 GitHub/GitLab API | P0 |
| 审计日志 | 每次触发记录审计日志 | P0 |

#### docker_build 工具测试

| 测试用例 | 描述 | 优先级 |
|---------|------|-------|
| 路径验证 | 构建上下文在项目目录内 | P0 |
| 基础镜像检查 | 禁止 latest 标签 | P0 |
| 资源限制 | 容器 CPU/内存限制 | P0 |
| 特权禁止 | --privileged 被拒绝 | P0 |
| 网络隔离 | 默认使用 bridge 网络 | P0 |

#### security_scan 工具测试

| 测试用例 | 描述 | 优先级 |
|---------|------|-------|
| 依赖扫描 | pip audit / npm audit 执行 | P0 |
| SAST 扫描 | bandit / semgrep 执行 | P0 |
| 超时保护 | 扫描超时自动终止 | P0 |
| 结果解析 | 标准格式输出 | P0 |
| 严重性过滤 | 按阈值过滤结果 | P0 |

#### data_transform 工具测试

| 测试用例 | 描述 | 优先级 |
|---------|------|-------|
| 格式转换 | CSV → JSON → Parquet | P0 |
| 数据清洗 | 缺失值填充、去重 | P0 |
| PII 检测 | 自动识别敏感数据 | P0 |
| 分块处理 | 大文件分块处理 | P0 |
| 数据校验 | 转换前后行数和 checksum | P1 |

### 14.4 集成测试计划

| 测试场景 | 涉及 Agent | 验证内容 | 优先级 |
|---------|-----------|---------|-------|
| 安全门禁 | Developer → Security → DevOps | 安全漏洞阻止部署 | P0 |
| CI/CD 流水线 | DevOps → Security → Tester | 完整构建-扫描-测试 | P0 |
| 数据洞察循环 | Data → ProductManager → Requirements | 数据驱动需求调整 | P1 |
| 架构-运维联动 | Architect → DevOps → Tester | 部署架构验证 | P1 |
| 全生命周期 | 全部 11 个 Agent | 端到端流程 | P2 |

---

## 15. 实施步骤

### 15.1 分阶段实施计划

```
Week 1: 基础设施搭建
├── Day 1-2: 扩展 ExecutorCapability 枚举
├── Day 2-3: 创建领域工具接口 (ci_trigger, docker_build)
├── Day 3-4: 实现安全工具接口 (security_scan)
└── Day 4-5: 编写工具单元测试

Week 2: 核心 Agent 实现
├── Day 1-2: 实现 DevOpsAgent（最高优先级）
├── Day 2-3: 实现 SecurityAgent
├── Day 3-4: 注册到 ExecutorRegistry
└── Day 4-5: 编写 Agent 单元测试和集成测试

Week 3: 扩展 Agent 实现
├── Day 1-2: 实现 DataAgent + data_transform 工具
├── Day 2-3: 实现 ArchitectAgent
├── Day 3-4: 实现 ProductManagerAgent
└── Day 4-5: 编写测试和文档

Week 4: 集成和优化
├── Day 1-2: 编写配置示例 (YAML)
├── Day 2-3: CLI 集成和文档更新
├── Day 3-4: 集成测试和 E2E 测试
└── Day 4-5: 性能优化和代码审查
```

### 15.2 优先级排序

| 优先级 | 内容 | 原因 |
|-------|------|------|
| P0 | DevOpsAgent + ci_trigger + docker_build | CI/CD 是研发基础设施，影响所有其他流程 |
| P0 | SecurityAgent + security_scan | 安全是发布门禁，不可缺失 |
| P1 | DataAgent + data_transform | 数据分析支持决策，但非阻塞性 |
| P1 | ArchitectAgent | 架构设计在项目早期需要 |
| P1 | ProductManagerAgent | 产品管理在需求阶段需要 |
| P2 | 配置示例和文档 | 依赖 P0/P1 Agent 实现完成 |

### 15.3 实施检查清单

#### Phase 6.1: DevOps 基础 (P0)

- [ ] `ExecutorCapability` 枚举扩展完成
- [ ] `ci_trigger.py` 工具实现完成
- [ ] `docker_build.py` 工具实现完成
- [ ] 工具安全策略实现（白名单、路径验证、资源限制）
- [ ] `devops.py` Agent 实现完成
- [ ] ExecutorRegistry 注册 DevOpsAgent
- [ ] DevOpsAgent 单元测试通过
- [ ] 工具集成测试通过

#### Phase 6.2: 安全基础 (P0)

- [ ] `security_scan.py` 工具实现完成
- [ ] 沙箱执行和超时保护实现
- [ ] `security.py` Agent 实现完成
- [ ] ExecutorRegistry 注册 SecurityAgent
- [ ] SecurityAgent 单元测试通过
- [ ] 安全门禁集成测试通过

#### Phase 6.3: 领域扩展 (P1)

- [ ] `data_transform.py` 工具实现完成
- [ ] PII 检测和脱敏实现
- [ ] `data.py` Agent 实现完成
- [ ] `architect.py` Agent 实现完成
- [ ] `product_manager.py` Agent 实现完成
- [ ] 所有 Agent 注册到 ExecutorRegistry
- [ ] 所有 Agent 单元测试通过

#### Phase 6.4: 集成和优化 (P2)

- [ ] YAML 配置示例完成
- [ ] CLI 命令集成完成
- [ ] 集成测试和 E2E 测试通过
- [ ] 文档更新完成
- [ ] 代码审查通过

---

## 16. 未来扩展

### 16.1 可扩展的 Agent 角色

以下角色可以在 Phase 7 及以后版本中添加：

| Agent | 文件名 | 角色 | 核心能力 | 依赖 |
|-------|--------|------|---------|------|
| QA Lead | `qa_lead.py` | 质量保障负责人 | 测试策略、质量度量、自动化测试框架 | TesterAgent |
| Tech Writer | `tech_writer.py` | 技术文档工程师 | API 文档、用户手册、Changelog | DeveloperAgent, ReviewerAgent |
| DBA | `dba.py` | 数据库管理员 | 数据库设计、性能调优、备份恢复 | DataAgent, ArchitectAgent |
| Release Manager | `release_manager.py` | 发布经理 | 版本管理、变更管理、发布协调 | DevOpsAgent, ProductManagerAgent |
| Scrum Master | `scrum_master.py` | 敏捷教练 | Sprint 计划、进度跟踪、障碍消除 | ProductManagerAgent |
| ML Engineer | `ml_engineer.py` | 机器学习工程师 | 模型训练、评估、部署 | DataAgent, DevOpsAgent |
| API Designer | `api_designer.py` | API 设计师 | OpenAPI/Swagger 规范、版本管理 | ArchitectAgent, DeveloperAgent |
| UX Designer | `ux_designer.py` | 用户体验设计师 | 用户研究、交互设计、可用性测试 | ProductManagerAgent |

### 16.2 工具扩展方向

| 工具 | 描述 | 使用 Agent |
|------|------|-----------|
| kubectl_ops | K8s 操作封装（只读诊断） | DevOpsAgent |
| terraform_ops | Terraform 操作封装（plan only） | DevOpsAgent |
| git_ops | Git 操作封装（branch, merge, rebase） | 所有 Agent |
| monitoring | 监控数据查询（Prometheus, Grafana） | DevOpsAgent, DataAgent |
| cost_analyzer | 云资源成本分析 | DevOpsAgent, ArchitectAgent |
| compliance_check | 合规性检查（GDPR, SOC2） | SecurityAgent |

### 16.3 架构演进方向

```
Phase 6 (当前)                    Phase 7+ (未来)
┌──────────────────────┐         ┌──────────────────────────────────┐
│ 11 个 Agent          │  演进   │ Agent Marketplace                 │
│ (硬编码注册)         │ ──►    │ (动态加载、插件化)                │
│                      │        │                                  │
│ 4 个领域工具         │  演进   │ Tool Registry                    │
│ (静态绑定)           │ ──►    │ (动态发现、按需加载)              │
│                      │        │                                  │
│ YAML 配置            │  演进   │ AI 驱动配置生成                   │
│ (手动编写)           │ ──►    │ (自然语言 → YAML)                 │
│                      │        │                                  │
│ 单模型               │  演进   │ 模型路由器                        │
│ (固定选择)           │ ──►    │ (自动选择最优模型)                │
│                      │        │                                  │
│ 本地执行             │  演进   │ 分布式执行                        │
│ (单机)               │ ──►    │ (多机、K8s 部署)                  │
└──────────────────────┘         └──────────────────────────────────┘
```

### 16.4 多语言支持

当前 Agent 主要面向 Python 项目，未来可扩展支持：

| 语言 | 支持内容 | 优先级 |
|------|---------|-------|
| JavaScript/TypeScript | npm audit, ESLint, Jest 集成 | P1 |
| Java/Kotlin | Maven/Gradle, SpotBugs, JUnit | P1 |
| Go | go vet, gosec, go test | P2 |
| Rust | cargo audit, clippy | P2 |
| C/C++ | cppcheck, valgrind | P3 |

---

## 附录

### A. 现有 Agent 系统提示词风格对照

| Agent | temperature | max_iterations | 工具风格 |
|-------|------------|---------------|---------|
| RequirementsAgent | 0.3 | 15 | 分析为主，输出结构化 |
| DesignerAgent | 0.3 | 15 | 设计为主，输出文档 |
| DeveloperAgent | 0.2 | 25 | 代码生成为主 |
| ReviewerAgent | 0.1 | 10 | 审查为主，高确定性 |
| TesterAgent | 0.2 | 20 | 测试代码生成 |
| FixerAgent | 0.1 | 15 | 修复代码，高确定性 |
| **DevOpsAgent** | **0.2** | **20** | **配置+命令，中等确定性** |
| **SecurityAgent** | **0.1** | **15** | **审查为主，极高确定性** |
| **DataAgent** | **0.3** | **20** | **分析+代码，中等创造性** |
| **ArchitectAgent** | **0.4** | **15** | **设计+决策，较高创造性** |
| **ProductManagerAgent** | **0.5** | **12** | **文本处理，较高创造性** |

### B. 安全注意事项

1. **领域工具权限**：所有领域工具默认最小权限原则
2. **bash 命令限制**：新 Agent 的 bash 命令需在白名单中配置
3. **生产环境保护**：DevOpsAgent 禁止直接操作生产环境
4. **敏感信息保护**：所有 Agent 不得在输出中泄露 API Key、密码等敏感信息
5. **审计日志**：所有领域工具操作必须记录审计日志

### C. 参考资料

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [C4 模型](https://c4model.com/)
- [RICE 评分模型](https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/)
- [MoSCoW 方法](https://en.wikipedia.org/wiki/MoSCoW_method)
- [Kano 模型](https://en.wikipedia.org/wiki/Kano_model)

---

*文档版本: v1.0 | 创建日期: 2026-05-20 | 最后更新: 2026-05-20*
