# Solar: AI Native Operating System

> Token In → Token Out | 从计算本质重构的智能操作系统

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Agents](https://img.shields.io/badge/Agents-13-green.svg)](docs/agents.md)
[![Skills](https://img.shields.io/badge/Skills-18-blue.svg)](docs/skills.md)

## Why AI Native?

**传统方案**: 在现有 OS 上叠加 AI 功能 (AI-Powered)
**Solar**: 从计算本质为 AI 重新设计 (AI-Native)

| 维度 | 传统 OS + AI | Solar (AI Native) |
|------|-------------|-------------------|
| 交互入口 | GUI/CLI | **语义意图** |
| AI 角色 | 附加特性 | **内核一等公民** |
| Token 效率 | 低（大量冗余） | **高（最短路径）** |
| 执行模式 | 多层翻译 | **结构化 Action** |
| 记忆系统 | 文件路径 | **语义索引** |

```
┌─────────────────────────────────────────────────────────────────┐
│                      AI Native OS 架构                          │
├─────────────────────────────────────────────────────────────────┤
│  Intent Layer      │ 自然语言 / @Agent / /Skill                │
│  ─────────────────────────────────────────────────────────────  │
│  Semantic Parser   │ sys_agents + sys_skills + 路由规则        │
│  ─────────────────────────────────────────────────────────────  │
│  Execution Engine  │ 13 Agents + 五阶段流程 + Gate 检查        │
│  ─────────────────────────────────────────────────────────────  │
│  Self-Evolution    │ 互评系统 + 书记员 + 自动优化              │
│  ─────────────────────────────────────────────────────────────  │
│  UI Runtime        │ TVS ZenWhite 设计系统                     │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

| 说 | 启动模式 | 描述 |
|-----|----------|------|
| "我要开发" | Solar Dev | 13个Agent + 五阶段流程 |
| "我要办公" | Clawbot | 邮件/日程/文档/任务处理 |
| "我要研究" | Research | 技术调研 + 可行性分析 |

```bash
# 安装
git clone https://github.com/anthropics/solar.git
cd solar && ./install.sh

# 使用
@Coder 优化这个函数    # 直达 Agent
/commit               # 调用 Skill
```

## Core Features

### Token First 原则

```
传统方式 (50+ tokens):
  用户: "检查磁盘"
  LLM: #!/bin/bash
       df -h | grep -E "^/dev" | awk '{print $1,$5}'
       # 检查使用率...

AI Native (8 tokens):
  用户: "检查磁盘"
  LLM: { "skill": "check_disk", "path": "/" }
```

**减少 85%+ Token 消耗**，同时提升安全性。

### 13 个专业 Agent

| 层级 | Agent | 职责 |
|------|-------|------|
| 决策 | Researcher / Architect / PM / Reporter | 调研、设计、验收、报告 |
| 执行 | Coder / Tester / Reviewer | 编码、测试、审查 |
| 支撑 | Docs / Ops / Guard / Secretary | 文档、部署、守护、记录 |
| 工具 | BenchmarkReporter / SkillMarket | 测试报告、技能市场 |

### 五阶段流程

```
P1 研究 → P2 设计 → P3 实现 → P4 验证 → P5 收尾
    │         │         │         │         │
    ▼         ▼         ▼         ▼         ▼
Researcher  Architect  Coder   Tester//   Ops→PM
  +Guard      +Guard           Reviewer   →Secretary
```

`//` = 并行 | `→` = 串行 | Gate 检查确保质量

### 自我演进系统

```
┌─────────────────────────────────────────────────────────────────┐
│                    Self-Evolution System                         │
├─────────────────────────────────────────────────────────────────┤
│  数据采集    │ Agent执行/Skill调用/阶段转换 → 自动记录          │
│  互评系统    │ 25条规则: Reviewer评Coder, PM评Tester...         │
│  书记员      │ 会议纪要 + 性能评估 + 优化建议                    │
│  持续优化    │ 基于历史数据自动调优参数                          │
└─────────────────────────────────────────────────────────────────┘
```

### 18 个 Skill

| 类别 | Skill |
|------|-------|
| 开发 | `/commit` `/pr` `/review` `/test` `/build` `/benchmark` |
| 文档 | `/docs` `/report` `/changelog` |
| 系统 | `/status` `/stats` `/save` `/restore` |
| 工具 | `/webapp-testing` `/mcp-builder` `/skill-creator` |

## Agent 宣告

每个 Agent 执行前必须输出宣告（Thinking Out Loud）:

```
┌─ 💻 Coder ──────────────────────────────────────┐
│ Task: 优化 Hash Join 性能                        │
│ Plan:                                           │
│   1. 分析当前瓶颈                                │
│   2. 实现 SIMD 加速                              │
│   3. 验证性能提升                                │
└─────────────────────────────────────────────────┘
```

## Session Recovery

```
┌─────────────────────────────────────────────────┐
│  传统方式: 恢复会话 10K-50K tokens              │
│  Solar:    /restore   ~500 tokens (节省 90%+)  │
└─────────────────────────────────────────────────┘
```

## Architecture

```
                    ┌─────────────────┐
                    │   User Intent   │
                    │  自然语言输入    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │  Solar   │  │ Clawbot  │  │ Research │
        │ Dev Mode │  │  Office  │  │   Mode   │
        └────┬─────┘  └──────────┘  └──────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  Execution Engine                                        │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐               │
│  │ P1  │→│ P2  │→│ P3  │→│ P4  │→│ P5  │               │
│  │研究 │ │设计 │ │实现 │ │验证 │ │收尾 │               │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘               │
│     │       │       │       │       │                   │
│  Researcher Architect Coder  Tester  Ops               │
│            +Guard   +Guard  //Review  →PM              │
│                             //Docs    →Secretary       │
└─────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  Self-Evolution Layer                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ sys_*    │  │ evo_*    │  │ 书记员   │              │
│  │ 资源注册 │  │ 执行追踪 │  │ 汇总优化 │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  TVS UI Runtime                                          │
│  ZenWhite 设计系统 | 9种视觉风格 | Agent 宣告卡片        │
└─────────────────────────────────────────────────────────┘
```

## Metadata System

67 张系统表支撑智能路由与自我演进:

| 类别 | 表 | 用途 |
|------|-----|------|
| 资源注册 | sys_agents, sys_skills, sys_hooks | 资源自省 |
| 路由规则 | sys_routing_model/agent/tool | 智能选择 |
| 执行追踪 | evo_agent_executions, evo_tool_calls | 数据采集 |
| 互评系统 | evo_review_rules, evo_votes | 质量评估 |
| 学习信号 | evo_learning_signals | 持续优化 |

## vs 业界方案

| 维度 | Solar | AutoGen | CrewAI | MetaGPT |
|------|-------|---------|--------|---------|
| AI Native 架构 | **Token First** | AI 叠加 | AI 叠加 | AI 叠加 |
| 五阶段流程 | **P1→P5 Gate** | 无 | 无 | 部分 |
| 自我演进 | **互评+书记员** | 无 | 无 | 无 |
| 会话恢复 | **90%+ Token 节省** | 无 | 无 | 无 |
| @Agent 直达 | **语义路由** | 无 | 无 | 无 |
| 多模式切换 | **Dev/Office/Research** | 单模式 | 单模式 | 单模式 |

## Documentation

- [AI Native OS Architecture](docs/AI_NATIVE_OS_ARCHITECTURE.md) - 架构设计原理
- [Workflow Design](docs/WORKFLOW_DESIGN.md) - 工作流程设计
- [Metadata System](core/nerve/README.md) - 元数据系统

## Installation

```bash
git clone https://github.com/anthropics/solar.git
cd solar && ./install.sh
```

或手动:
```bash
cp -r Solar/agents ~/.claude/
cp -r Solar/skills ~/.claude/
cp -r Solar/hooks ~/.claude/
cp Solar/CLAUDE.md ~/.claude/
```

## License

MIT

---

**Solar** — AI Native Operating System | Token In → Token Out
