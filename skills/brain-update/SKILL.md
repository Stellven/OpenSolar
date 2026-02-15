# /brain-update - 大脑信息更新

> 更新多大脑调度系统的模型信息、价格和评价

## 用法

```bash
/brain-update                # 完整更新（搜索+分析+存储）
/brain-update price          # 只更新价格
/brain-update benchmark      # 只更新评测信息
/brain-update list           # 查看当前大脑配置
/brain-update compare        # 对比各大脑性价比
```

## 执行流程

### 1. 搜索最新信息

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   WebSearch: "LLM API pricing 2026 Claude GPT Gemini DeepSeek"              │
│   WebSearch: "LLM benchmark comparison 2026 strengths weaknesses"           │
│                                                                             │
│   信息来源:                                                                 │
│   • pricepertoken.com - 价格对比                                            │
│   • artificialanalysis.ai - 性能排行                                        │
│   • lmcouncil.ai - 基准测试                                                 │
│   • 官方定价页面                                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2. 更新大脑档案

```sql
-- 大脑档案表
CREATE TABLE IF NOT EXISTS sys_brain_profiles (
    brain_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,           -- anthropic, openai, google, deepseek
    model_name TEXT NOT NULL,         -- claude-opus-4-5, gpt-5.2, etc.
    display_name TEXT,                -- 显示名称

    -- 定价 (per 1M tokens)
    input_price_per_m REAL,           -- 输入价格
    output_price_per_m REAL,          -- 输出价格
    cached_input_price REAL,          -- 缓存输入价格

    -- 能力评估
    reasoning_score INTEGER,          -- 推理能力 1-100
    coding_score INTEGER,             -- 编码能力 1-100
    chinese_score INTEGER,            -- 中文能力 1-100
    multimodal_score INTEGER,         -- 多模态能力 1-100
    speed_score INTEGER,              -- 速度 1-100

    -- 特长和短板
    strengths TEXT,                   -- JSON: ["深度推理", "复杂任务"]
    weaknesses TEXT,                  -- JSON: ["成本高", "速度慢"]

    -- 适用场景
    best_for TEXT,                    -- JSON: ["架构设计", "难题攻关"]

    -- 上下文窗口
    context_window INTEGER,           -- tokens
    max_output INTEGER,               -- tokens

    -- 元信息
    last_updated TEXT,
    data_source TEXT,                 -- 数据来源 URL
    notes TEXT
);
```

### 3. 更新调度规则

```sql
-- 调度规则表
CREATE TABLE IF NOT EXISTS sys_brain_routing (
    rule_id INTEGER PRIMARY KEY,
    condition TEXT NOT NULL,          -- 条件描述
    condition_type TEXT,              -- complexity, task_type, budget, language
    recommended_brain TEXT,           -- 推荐的大脑
    fallback_brain TEXT,              -- 备选大脑
    reason TEXT,                      -- 推荐理由
    priority INTEGER DEFAULT 5
);
```

## 当前大脑档案 (2026-01)

| 大脑 | 输入$/M | 输出$/M | 推理 | 编码 | 中文 | 适用场景 |
|------|---------|---------|------|------|------|----------|
| Claude Opus 4.5 | $15 | $75 | 95 | 98 | 90 | 架构设计、复杂编码 |
| Claude Sonnet 4.5 | $3 | $15 | 88 | 92 | 88 | 日常开发、平衡之选 |
| Claude Haiku 4.5 | $1 | $5 | 75 | 80 | 82 | 简单任务、快速响应 |
| GPT-5.2 Pro | $12 | $60 | 98 | 90 | 85 | 硬推理、逻辑难题 |
| GPT-4o | $2.5 | $10 | 82 | 85 | 80 | 多模态、图像理解 |
| GPT-4o Mini | $0.15 | $0.6 | 70 | 75 | 75 | 极低成本简单任务 |
| Gemini 3 Pro | $1.25 | $5 | 90 | 88 | 82 | 研究引用、长上下文 |
| Gemini 3 Flash | $0.075 | $0.3 | 78 | 80 | 78 | 高速低成本 |
| DeepSeek V3.2 | $0.28 | $0.42 | 85 | 88 | 95 | 中文任务、科学推理 |
| DeepSeek R1 | $0.55 | $2.19 | 92 | 90 | 95 | 数学推理、性价比王 |

## 调度规则

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  任务类型              │  首选大脑          │  备选              │  理由    │
├────────────────────────┼───────────────────┼───────────────────┼──────────┤
│  架构设计/复杂推理     │  Claude Opus 4.5  │  GPT-5.2 Pro      │  最强推理│
│  日常编码              │  Claude Sonnet    │  DeepSeek V3.2    │  平衡    │
│  简单问答              │  Claude Haiku     │  Gemini Flash     │  低成本  │
│  中文任务              │  DeepSeek R1      │  Claude Sonnet    │  中文强  │
│  数学/科学推理         │  DeepSeek R1      │  GPT-5.2          │  性价比  │
│  图像理解              │  GPT-4o           │  Gemini 3 Pro     │  多模态  │
│  长文档分析            │  Gemini 3 Pro     │  Claude Opus      │  长上下文│
│  预算紧张              │  DeepSeek V3.2    │  Gemini Flash     │  最便宜  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 输出格式

```
╭═══════════════════════════════════════════════════════════════════════════════╮
│                    🧠 BRAIN UPDATE                                             │
╞═══════════════════════════════════════════════════════════════════════════════╡
│                                                                               │
│  更新时间    2026-01-31                                                       │
│  数据来源    pricepertoken.com, artificialanalysis.ai                         │
│                                                                               │
│  价格变化:                                                                    │
│  ─────────────────────────────────────────────────────────────────────────    │
│  • DeepSeek V3.2: $0.55 → $0.28/M input (↓49%)                               │
│  • Gemini Flash: $0.10 → $0.075/M input (↓25%)                               │
│                                                                               │
│  新模型:                                                                      │
│  ─────────────────────────────────────────────────────────────────────────    │
│  • GPT-5.2 Reasoning (推理增强版)                                            │
│  • Gemini 3 Deep Think (深度思考)                                            │
│                                                                               │
│  调度规则更新: 3 条                                                           │
│                                                                               │
╰═══════════════════════════════════════════════════════════════════════════════╯
```

## Hook 触发条件

在以下情况自动提醒更新:

```yaml
triggers:
  # 定期提醒
  weekly_reminder:
    schedule: "每周日 20:00"
    action: "提醒执行 /brain-update"

  # 会话开始检查
  session_start:
    condition: "距上次更新超过 14 天"
    action: "建议执行 /brain-update"

  # 新闻触发
  news_trigger:
    keywords: ["新模型发布", "价格调整", "LLM 更新"]
    action: "主动搜索并建议更新"
```

## 经济分析

执行 `/brain-update compare` 会生成性价比分析:

```
性价比排行 (能力/价格):
1. DeepSeek V3.2   ████████████████████ 性价比之王
2. Gemini Flash    ████████████████     高速低价
3. DeepSeek R1     ███████████████      推理性价比
4. Claude Haiku    ████████████         轻量首选
5. Gemini Pro      ███████████          平衡之选
6. Claude Sonnet   ██████████           质量优先
7. GPT-4o          █████████            多模态
8. Claude Opus     ██████               顶级能力
9. GPT-5.2 Pro     █████                最强推理
```

---

*Brain Update Skill*
*保持大脑信息与时俱进*
*Solar*
