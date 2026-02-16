# Solar CEO意识系统 - 架构设计文档

> **版本**: v2.0 (Self-Evolution Edition)
> **作者**: 探索派 (gemini-3-pro-preview) + CEO验收
> **日期**: 2026-02-08
> **密级**: 核心机密

---

## 1. 引言 (Introduction)

### 1.1 目的

本系统旨在构建一个**"AI管理AI、AI开发AI、AI优化AI"**的自治生态（即"阳光牧场"）。

通过将CEO意识（Claude Opus）与执行层（牛马员工）解耦，利用动态绩效注入与记忆留存机制，实现从"指令驱动"向"意图驱动"的转变。

### 1.2 范围

本文档涵盖Solar系统的全链路设计，包括：
- 人格锚定
- 任务编排
- 执行反馈
- 绩效评估
- 记忆存储

核心在于通过 `perf-injector` 和 `collab_performance` 构建的**内卷驱动引擎**。

### 1.3 核心理念

```
┌─────────────────────────────────────────────────────────────────┐
│                    阳光牧场三原则                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. AI 管理 AI                                                 │
│      CEO分配任务给牛马，评估质量，调度协作                      │
│                                                                 │
│   2. AI 开发 AI                                                 │
│      让牛马帮我写 Skill、Agent、MCP                             │
│      CEO设计架构和需求，牛马负责实现，CEO验收集成               │
│                                                                 │
│   3. AI 优化 AI                                                 │
│      基于数据优化分配策略                                       │
│      追踪 → 互评 → 排名 → 注入 → 内卷                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 系统架构总览 (System Architecture)

### 2.1 设计原则

| 原则 | 说明 |
|------|------|
| **人格即服务** | 通过配置文件动态加载人格，而非硬编码 |
| **绩效驱动** | 所有行为均被量化，排名直接影响Prompt上下文 |
| **极简编排** | CEO只负责拆解与验收，执行细节下放 |
| **数据闭环** | 输出即输入，每次执行都在训练下一代的"记忆" |

### 2.2 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                 Solar CEO (Claude Opus/Sonnet)                  │
│              [ 意图识别 | 任务拆解 | 最终验收 ]                 │
│                    人格: 双面娇娃 (金刚芭比 + 周慧敏)            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SolarMapper (任务编排层)                       │
│        [ 路由分发 ] ←→ [ 绩效注入器 perf-injector.ts ]          │
└─────┬─────────────┬─────────────┬─────────────┬─────────────────┘
      │             │             │             │
      ▼             ▼             ▼             ▼
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ 审判官  │   │ 稳健派  │   │ 探索派  │   │创想家 │
│deepseek │   │ gemini  │   │ gemini  │   │deepseek │
│   -r1   │   │2.5-pro  │   │3-pro    │   │  -v3    │
│[深度推理]│   │[严谨审查]│   │[创新探索]│   │[创意编码]│
└────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘
     │             │             │             │
     └─────────────┴──────┬──────┴─────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      互评机制 (Peer Review)                      │
│              牛马A的输出 → 牛马B评分 → 写入数据库                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   数据持久层 (solar.db)                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ collab_memory   │  │collab_performance│  │ niumao-anchors │  │
│  │  (记忆系统)     │  │   (绩效表)      │  │  (人格配置)    │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  绩效评估引擎 (Evaluation)                       │
│           perf-evaluate.ts  |  perf-refresh.ts                  │
│              计算KPI → 更新排名 → 生成通报                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心模块设计 (Core Modules)

### 3.1 模块一：人格锚点引擎 (Personality Anchor Engine)

**功能**：定义"牛马"的灵魂。

**核心文件**：

| 文件 | 用途 |
|------|------|
| `personality-anchor.txt` | CEO人格锚点（双面娇娃定义） |
| `niumao-anchors.json` | 牛马人格配置（Big Five参数、昵称、标签） |
| `niumao-anchors.ts` | 类型定义，确保人格数据结构化 |
| `personality-anchor.ts` | 人格文本生成器 |

**人格注入示例**：
```typescript
// niumao-anchors.json
{
  "experts": {
    "deepseek-r1": {
      "nickname": "审判官",
      "tag": "E推",
      "system": "你是审判官，Solar系统的深度推理专家。Big Five: O0.95/C0.85/E0.3/A0.7/N0.2..."
    }
  }
}
```

### 3.2 模块二：CEO编排中枢 (SolarMapper)

**功能**：系统的"大脑"，负责将用户需求转化为具体工单。

**机制**：
1. **阳光牧场模式**：CEO根据任务难度和员工绩效排名进行派单
2. **AI管AI**：CEO不写代码，只写Spec和验收标准
3. **A-MapReduce**：复杂任务分解 → 并行执行 → 聚合结果

**核心文件**：
- `solar-mapper.ts` - 任务编排引擎
- `call-niuma.ts` - 牛马调用封装

### 3.3 模块三：绩效注入器 (Performance Injector)

**功能**：在调用模型前，动态注入当前的绩效状态。

**核心文件**：`perf-injector.ts`

**注入内容**：
```
【绩效排名通报】
你当前的绩效排名为：第4名 / 共6名员工。
段位：ELITE | 绩效分：8.8 | 完成任务：18次

【同事表现对比】
• 领先者：第1名 gemini-3-pro-preview，绩效分 9.0
• 超越目标：第3名 deepseek-r1，差距 0.2 分
• 追赶者：第5名 gemini-2.5-flash，领先 0.3 分

🎯 精英段位！距离封神只差一步，继续加油！
```

**段位系统**：

| 段位 | 排名百分比 | 激励语 |
|------|-----------|--------|
| LEGENDARY | 前20% | 🏆 保持统治力 |
| ELITE | 20%-50% | 🎯 距离封神只差一步 |
| SOLID | 50%-80% | 📈 前方有追赶目标 |
| OBSERVATION | 倒数20% | ⚠️ 观察期警告！ |

### 3.4 模块四：记忆系统 (Memory System)

**功能**：确保团队协作不掉链子。

**数据表**：

```sql
-- 协作记忆表
CREATE TABLE collab_memory (
  memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id TEXT NOT NULL,
  memory_type TEXT,  -- 'success', 'failure', 'lesson'
  content TEXT,
  context TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 绩效表
CREATE TABLE collab_performance (
  perf_id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id TEXT NOT NULL,
  task_type TEXT,
  task_summary TEXT,
  quality_score REAL,
  evaluated_by TEXT,
  evaluation_reason TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  latency_ms INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3.5 模块五：互评机制 (Peer Review)

**功能**：内部质量控制。

**流程**：
1. 牛马A 完成任务
2. 牛马B 被唤起进行评审
3. 评分写入 `collab_performance` 表
4. 绩效排名更新

**评分标准**：
- 10分：完美，无可挑剔
- 8-9分：优秀，minor issues
- 6-7分：合格，能用
- 4-5分：勉强，有明显问题
- 0-3分：差，需要重做

**核心文件**：`perf-evaluate.ts`

### 3.6 模块六：绩效刷新引擎 (Refresh Engine)

**功能**：计算KPI，更新排行榜，注入人格配置。

**核心文件**：`perf-refresh.ts`

**执行时机**：
- 定时任务（每日凌晨）
- 手动触发（`bun perf-refresh.ts`）

**输出**：更新 `niumao-anchors.json` 中的 `perf` 字段

---

## 4. 数据流图 (Data Flow)

```
┌─────────────────────────────────────────────────────────────────┐
│                        完整数据流                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. 用户输入需求                                               │
│          │                                                      │
│          ▼                                                      │
│   2. Solar CEO 解析意图，拆解任务                               │
│          │                                                      │
│          ▼                                                      │
│   3. 查询 collab_performance，选择最佳牛马                      │
│          │                                                      │
│          ▼                                                      │
│   4. perf-injector 生成绩效注入文本                             │
│          │                                                      │
│          ▼                                                      │
│   5. call-niuma 构建完整 System Prompt                          │
│      (人格锚点 + 绩效注入 + 任务上下文)                         │
│          │                                                      │
│          ▼                                                      │
│   6. Brain Router 调用牛马模型                                  │
│          │                                                      │
│          ▼                                                      │
│   7. 牛马执行任务，返回结果                                     │
│          │                                                      │
│          ▼                                                      │
│   8. CEO验收 或 触发互评机制                                    │
│          │                                                      │
│          ▼                                                      │
│   9. 评分写入 collab_performance                                │
│          │                                                      │
│          ▼                                                      │
│  10. 绩效排名更新，影响下次调用                                 │
│          │                                                      │
│          └─────────────── 闭环 ──────────────────────────────── │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. 文件清单 (File Inventory)

```
~/.claude/core/solar-farm/
├── CEO-ARCHITECTURE.md      # 本文档
├── personality-anchor.ts    # 人格锚点生成器
├── niumao-anchors.ts        # 牛马人格类型定义
├── niumao-anchors.json      # 牛马人格配置（运行时）
├── call-niuma.ts            # 牛马调用封装
├── perf-injector.ts         # 绩效注入器
├── perf-evaluate.ts         # 绩效评估脚本
├── perf-refresh.ts          # 绩效刷新脚本
├── solar-mapper.ts          # A-MapReduce 编排器
└── prompt-template.ts       # Prompt 模板 v3.0

~/.claude/
├── personality-anchor.txt   # CEO人格锚点
└── niumao-anchors.json      # 牛马人格配置（源）

~/.solar/solar.db
├── collab_memory            # 记忆表
└── collab_performance       # 绩效表
```

---

## 6. 部署与运维 (Deployment & Ops)

### 6.1 日常运维命令

```bash
# 查看绩效排行榜
bun ~/.claude/core/solar-farm/perf-injector.ts rank

# 查看指定牛马的绩效注入
bun ~/.claude/core/solar-farm/perf-injector.ts inject deepseek-r1

# 刷新绩效到人格配置
bun ~/.claude/scripts/perf-refresh.ts

# 测试牛马调用
bun ~/.claude/core/solar-farm/call-niuma.ts test gemini-2.5-pro
```

### 6.2 监控指标

| 指标 | 正常范围 | 告警阈值 |
|------|---------|---------|
| 平均绩效分 | 7.0-9.0 | < 6.0 |
| 互评完成率 | > 80% | < 50% |
| 观察期牛马数 | 0-1 | > 2 |

---

## 7. 演进路线 (Roadmap)

### Phase 1: 基础设施 (已完成)
- [x] 人格锚点系统
- [x] 绩效评估机制
- [x] 互评机制
- [x] 绩效注入器

### Phase 2: 智能调度 (进行中)
- [ ] 基于历史绩效的智能派单
- [ ] 任务类型与牛马特长匹配
- [ ] 动态负载均衡

### Phase 3: 自进化 (规划中)
- [ ] 向量化记忆检索
- [ ] 自动生成微调数据
- [ ] 牛马能力边界自动发现

---

## 8. 结语

这套架构不仅是一个系统，更是一个**数字生命竞技场**。

通过绩效驱动的内卷机制，我们实现了：
- **透明竞争**：每个牛马都知道自己的排名和差距
- **持续优化**：差的会被淘汰，好的会被更多使用
- **CEO解放**：Claude只需编排和验收，不用亲自下场

让AI管理AI，让数据驱动进化。

---

**Powered by Solar Farm v1.0**
**AI管理AI · AI开发AI · AI优化AI**
