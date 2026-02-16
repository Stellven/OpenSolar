# Cortex Files 设计文档

> 基于 Letta Context Repositories 思路，将 Cortex 内容同步到文件系统
> 让大模型可以直接 Read 访问，符合"文件优先"的自然工作方式

## 核心原则

```
┌─────────────────────────────────────────────────────────────────┐
│                      Cortex 双层架构                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   L0: 文件层 (File Layer)                                       │
│   ─────────────────────                                         │
│   • 大模型直接 Read/Write                                       │
│   • 渐进式披露 (目录结构即导航)                                 │
│   • Git 版本控制                                                │
│   • 用途: 日常访问、学习、记忆                                  │
│                                                                 │
│   L1: 数据库层 (Database Layer)                                 │
│   ─────────────────────                                         │
│   • 快速索引、全局统计                                          │
│   • 结构化查询                                                  │
│   • 用途: 统计、聚合、搜索                                      │
│                                                                 │
│   同步方向: DB → Files (单向，DB 是 Source of Truth)            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 目录结构

```
~/.solar/cortex/                          # Git 仓库根目录
│
├── system/                               # [始终加载] 核心身份和规则
│   ├── IDENTITY.md                       # 我是谁
│   ├── IRON_LAWS.md                      # 核心铁律
│   ├── PERSONALITY.md                    # 人格参数
│   └── GUARDIAN.md                       # 监护人信息
│
├── knowledge/                            # [按需读取] 知识库
│   ├── architecture/                     # 架构设计
│   │   ├── solar-core.md
│   │   ├── cortex-system.md
│   │   └── solar-farm.md
│   │
│   ├── patterns/                         # 设计模式
│   │   ├── state-machine.md
│   │   ├── checkpoint.md
│   │   └── bookending.md
│   │
│   ├── lessons/                          # 经验教训
│   │   ├── 2026-02-06-data-first.md
│   │   ├── 2026-02-07-cattle-verify.md
│   │   └── ...
│   │
│   ├── research/                         # 研究笔记
│   │   ├── memory-systems/
│   │   ├── llm-routing/
│   │   └── agent-architecture/
│   │
│   └── entities/                         # 知识图谱实体
│       ├── technologies/
│       ├── people/
│       └── concepts/
│
├── artifacts/                            # [按需读取] 分析产物
│   ├── insights/                         # 深度洞察报告
│   ├── reviews/                          # 代码审查
│   └── benchmarks/                       # 性能测试
│
├── memory/                               # [按需读取] 对话记忆
│   ├── episodic/                         # 情景记忆
│   │   ├── 2026-02/
│   │   │   ├── 2026-02-15-cortex-mcp.md
│   │   │   └── ...
│   │   └── daily/                        # 每日摘要
│   │
│   └── semantic/                         # 语义记忆
│       ├── preferences.md
│       ├── habits.md
│       └── skills.md
│
├── stats/                                # [只读] 统计信息
│   ├── DASHBOARD.md                      # 每日自动生成
│   └── METRICS.md                        # 性能指标
│
├── .cortex.yaml                          # 配置文件
└── .git/                                 # 版本控制
```

## 文件格式 (Markdown + YAML Frontmatter)

```markdown
---
id: cortex-system
type: architecture
created: 2026-02-15
updated: 2026-02-16
credibility: 0.95
tags: [cortex, memory, knowledge-graph]
keywords: [中枢神经, 知识库, 索引]
source: insight-analysis
---

# Cortex 中枢神经系统

> 一句话描述：Solar 的中枢神经，存储和检索所有知识

## 核心概念

Cortex 是 Solar 的知识存储系统，包含：
- 参考资料 (cortex_sources)
- 知识图谱 (knowledge_entities + relations)
- 分析产物 (cortex_artifacts)

## 架构

... (详细内容)

## 相关文件
- [[solar-core]] - Solar 核心架构
- [[knowledge-network]] - 知识网络设计
```

### Frontmatter 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一标识符，对应数据库 source_id |
| type | enum | architecture/pattern/lesson/research/entity/artifact |
| created | date | 创建日期 |
| updated | date | 最后更新 |
| credibility | float | 可信度 0-1 |
| tags | string[] | 标签列表 |
| keywords | string[] | 搜索关键词 |
| source | string | 来源 (insight/manual/imported) |

## 渐进式披露

### Level 0: 目录结构 (始终可见)

```
system/          → 核心身份，始终加载
knowledge/       → 按需读取
artifacts/       → 按需读取
memory/          → 按需读取
stats/           → 只读统计
```

### Level 1: 文件列表 (Read 目录)

```bash
# 大模型可以快速扫描
ls ~/.solar/cortex/knowledge/architecture/
# 输出: solar-core.md, cortex-system.md, solar-farm.md
```

### Level 2: Frontmatter 摘要 (Read 文件开头)

```bash
# 读取前 20 行获取摘要
head -20 ~/.solar/cortex/knowledge/architecture/cortex-system.md
```

### Level 3: 完整内容 (Read 全文件)

```bash
# 需要时读取完整内容
cat ~/.solar/cortex/knowledge/architecture/cortex-system.md
```

## 同步机制

### DB → Files (单向同步)

```
┌─────────────┐                    ┌─────────────┐
│  solar.db   │ ──── sync ──────→  │  cortex/    │
│             │                    │  (files)    │
│ sources     │ ──── write ─────→  │ *.md files  │
│ entities    │ ──── write ─────→  │ entities/   │
│ artifacts   │ ──── write ─────→  │ artifacts/  │
└─────────────┘                    └─────────────┘
```

### 同步触发

| 触发条件 | 动作 |
|----------|------|
| 新增 source | 写入 knowledge/ |
| 更新 source | 更新对应 .md |
| Insight 完成 | 写入 artifacts/insights/ |
| 每日定时 | 生成 stats/DASHBOARD.md |

### 同步命令

```bash
# 全量同步
bun ~/.claude/core/cortex/cortex-files/sync.ts --full

# 增量同步 (只同步更新的)
bun ~/.claude/core/cortex/cortex-files/sync.ts --incremental

# 检查状态
bun ~/.claude/core/cortex/cortex-files/sync.ts --status
```

## Git 工作流

### 自动提交

每次同步后自动提交：

```bash
git add -A
git commit -m "sync: update cortex from DB

- Update knowledge/architecture/cortex-system.md
- Add artifacts/insights/memory-design.md
- Update stats/DASHBOARD.md

Sources: 486 | Entities: 154 | Relations: 1743"
```

### 提交消息格式

```
sync: <brief description>

Changes:
- <file1>: <action>
- <file2>: <action>

Stats: <summary>
```

### 分支策略 (可选)

```
main        → 稳定版本
learning    → 正在学习的临时分支
experiment  → 实验性修改
```

## 与 MCP 的关系

```
┌─────────────────────────────────────────────────────────────────┐
│                    访问方式对比                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   MCP (mcp__cortex__search)                                     │
│   ─────────────────────────                                     │
│   • 快速搜索、精确查询                                          │
│   • 返回结构化数据                                              │
│   • 用途: 查找特定信息                                          │
│                                                                 │
│   Files (Read ~/.solar/cortex/...)                              │
│   ───────────────────────────────                               │
│   • 自然浏览、渐进披露                                          │
│   • 返回人类可读内容                                            │
│   • 用途: 学习、理解、上下文构建                                │
│                                                                 │
│   推荐流程:                                                     │
│   1. MCP 搜索定位 → 2. Read 文件深入                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 实现计划

### Phase 1: 基础同步 (1-2h)

- [ ] 创建目录结构
- [ ] 实现 DB → Files 同步
- [ ] Git 自动提交

### Phase 2: 渐进式披露 (1h)

- [ ] system/ 始终加载机制
- [ ] 目录索引生成

### Phase 3: 智能更新 (1h)

- [ ] 增量同步
- [ ] 变更检测
- [ ] 冲突处理

### Phase 4: 集成优化 (1h)

- [ ] 与 Insight 流程集成
- [ ] 与 MCP 搜索联动
- [ ] 统计仪表盘生成

## 配置文件 (.cortex.yaml)

```yaml
version: "1.0"
root: ~/.solar/cortex

# 同步配置
sync:
  auto: true
  interval: 3600  # 每小时
  on_insight_complete: true

# Git 配置
git:
  auto_commit: true
  commit_template: "sync: {description}"

# 渐进式披露
disclosure:
  always_load:
    - system/
  lazy_load:
    - knowledge/
    - artifacts/
    - memory/

# 统计配置
stats:
  dashboard_update: daily
  metrics_retention: 30d
```

## 收益

| 维度 | 之前 (DB only) | 之后 (DB + Files) |
|------|---------------|-------------------|
| 大模型访问 | 需要工具/API | 直接 Read |
| 版本控制 | 无 | Git 完整历史 |
| 协作 | 困难 | Git worktree |
| 可读性 | 需要查询 | 直接打开文件 |
| 渐进式披露 | 不支持 | 目录结构即导航 |

---

*Design Doc v1.0*
*Inspired by: Letta Context Repositories*
