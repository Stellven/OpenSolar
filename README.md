# Solar v2.0: Multi-Agent Development Framework

> 五阶段流程 | 并行优先 | 快速失败 | 会话恢复 | 多模式切换

## 🚀 快速启动

| 说 | 启动模式 | 描述 |
|-----|----------|------|
| "我要开发" | 🛠️ Solar | 10个Agent + 五阶段流程 |
| "我要办公" | 📋 Clawbot | 邮件/日程/文档/任务处理 |
| "我要研究" | 🔬 Research | 技术调研 + 可行性分析 |

```
/mode dev      # 开发模式
/mode office   # 办公模式
/mode research # 研究模式
```

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| **五阶段流程** | 研究→设计→实现→验证→收尾，自动调度 |
| **10个专业Agent** | Researcher/Architect/Coder/Tester 等 |
| **@Agent 直达** | `@Researcher xxx` 直接调用指定 Agent |
| **会话恢复** | `/save` `/restore` 崩溃后快速恢复 |
| **多模式切换** | 开发/办公/研究模式一键切换 |
| **Gate 检查** | 阶段门禁，失败自动重试 |
| **Token 优化** | 会话恢复节省 90%+ tokens |

## 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                      用户: "我要开发" / @Agent                       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Coordinator (模式识别 + 复杂度分析)                │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
   ┌─────────┐           ┌───────────┐           ┌───────────┐
   │ 🛠️ Solar │           │📋 Clawbot │           │🔬 Research│
   │ 开发模式 │           │  办公模式  │           │  研究模式  │
   └────┬────┘           └───────────┘           └───────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  P1 研究 → P2 设计 → P3 实现 → P4 验证 → P5 收尾                     │
│  Researcher  Architect   Coder    Tester//   Ops→PM                 │
│              +Guard      +Guard   Reviewer   →Secretary             │
│                                   //Docs                            │
└─────────────────────────────────────────────────────────────────────┘
```

## 🛠️ 开发模式 (Solar)

### 五阶段流程

| 阶段 | Agent | 触发条件 | 产出 |
|------|-------|----------|------|
| P1 研究 | Researcher | 新技术/不确定方案 | 可行性报告 |
| P2 设计 | Architect + Guard | 中等/复杂任务 | 架构方案 |
| P3 实现 | Coder + Guard | 需要写代码 | 代码实现 |
| P4 验证 | Tester // Reviewer // Docs | 代码完成 | 测试+审查+文档 |
| P5 收尾 | Ops → PM → Secretary | 验证通过 | 部署+验收+记录 |

`//` = 并行 | `→` = 串行

### 10 个 Agent

| 层级 | Agent | 模型 | 职责 |
|------|-------|------|------|
| 决策 | Researcher | Opus | 前沿技术调研、可行性分析 |
| 决策 | Architect | Opus | 架构设计、技术评审 |
| 决策 | PM | Opus | 产品竞争力、功能验收 |
| 决策 | Secretary | Sonnet | 记录整理、Agent 评估 |
| 执行 | Coder | Sonnet | 代码实现、重构 |
| 执行 | Tester | Sonnet | 测试编写、执行 |
| 执行 | Reviewer | Sonnet | 代码审查、安全检查 |
| 支撑 | Docs | Sonnet | 文档生成、更新 |
| 支撑 | Ops | Sonnet | 构建、部署、基准测试 |
| 支撑 | Guard | Haiku | 规范检查、质量门禁 |

### @Agent 直达

```
@Solar      → 完整流程      @Coder    → 代码实现
@Researcher → 技术调研      @Tester   → 测试
@Architect  → 架构设计      @Reviewer → 代码审查
@PM         → 产品验收      @Docs     → 文档
```

示例: `@Researcher 调研 SIMD 向量化优化技术`

### Gate 检查点

| Gate | 位置 | 失败处理 |
|------|------|----------|
| G1 | P2 设计后 | 重新设计 (最多2次) |
| G2 | P4 验证后 | 返回P3修改 (最多3次) |
| G3 | P5 收尾后 | 迭代改进 |

### 复杂度路由

| 复杂度 | 判断标准 | Token | 流程 |
|--------|----------|-------|------|
| 简单 | <50行, 单文件 | 5K | 直接做 |
| 中等 | 50-500行, 2-5文件 | 30K | P2→P3→P4 |
| 复杂 | >500行, 跨模块 | 100K | P1→P2→P3→P4→P5 |

## 📋 办公模式 (Clawbot)

| 能力 | 描述 |
|------|------|
| 📧 邮件处理 | 起草、回复、摘要 |
| 📅 日程管理 | 会议安排、提醒 |
| 📝 文档处理 | 会议纪要、报告撰写 |
| ✅ 任务管理 | 待办清单、优先级 |
| 🔍 信息检索 | 搜索、汇总、对比 |

## 💾 会话恢复

解决 Claude Code 崩溃/重启后状态丢失问题。

```
┌────────────────────────────────────────┐
│  正常工作 ──→ /save ──→ .solar/session.md
│                                        │
│  崩溃/重启                              │
│                                        │
│  /restore ──→ 只读 session.md (~500 tokens)
│           ⚠️ 不重新读取所有源文件        │
└────────────────────────────────────────┘
```

| 场景 | 传统方式 | Solar |
|------|----------|-------|
| 恢复会话 | 10K-50K tokens | ~500 tokens |
| 时间 | 30s-2min | <5s |

## 14 个 Skill

| Skill | 用途 |
|-------|------|
| `/mode` | 🔀 切换工作模式 (dev/office/research) |
| `/agent` | 🎯 列出/激活 Agent |
| `/save` | 💾 保存会话状态 |
| `/restore` | 🔄 快速恢复会话 |
| `/commit` | Git 提交 |
| `/pr` | 创建 PR |
| `/review` | 代码审查 |
| `/test` | 运行测试 |
| `/build` | 构建项目 |
| `/benchmark` | 性能测试 |
| `/docs` | 生成文档 |
| `/webapp-testing` | 🎭 Playwright UI 测试 |
| `/mcp-builder` | 🔧 创建 MCP 服务器 |
| `/skill-creator` | ✨ 交互式创建 Skill |

## 安装

```bash
git clone https://github.com/lisihao/Solar.git
cd Solar && ./install.sh
```

或手动:
```bash
cp -r Solar/agents ~/.claude/
cp -r Solar/skills ~/.claude/
cp -r Solar/hooks ~/.claude/
cp Solar/CLAUDE.md ~/.claude/
```

## 与业界对比

| 维度 | Solar | AutoGen | CrewAI | MetaGPT |
|------|-------|---------|--------|---------|
| 多模式切换 | ✅ | ❌ | ❌ | ❌ |
| 五阶段流程 | ✅ | ❌ | ❌ | 部分 |
| @Agent 直达 | ✅ | ❌ | ❌ | ❌ |
| 会话恢复 | ✅ | ❌ | ❌ | ❌ |
| 并行执行 | ✅ | 部分 | ❌ | ✅ |
| Gate 检查 | ✅ | ❌ | ❌ | ❌ |
| Token 优化 | ✅ | ❌ | ❌ | ❌ |
| 技术研究 Agent | ✅ | ❌ | ❌ | ❌ |

## 文档

- [工作流程设计](docs/WORKFLOW_DESIGN.md)
- [Clawbot 办公助手](frameworks/clawbot.md)

## 许可证

MIT

## 致谢

- [Anthropic](https://www.anthropic.com/) - Claude Code
- [OpenAI Swarm](https://github.com/openai/swarm) - 轻量级编排启发
- [CrewAI](https://github.com/joaomdmoura/crewAI) - 角色设计启发
- [MetaGPT](https://github.com/geekan/MetaGPT) - 多角色协作启发
