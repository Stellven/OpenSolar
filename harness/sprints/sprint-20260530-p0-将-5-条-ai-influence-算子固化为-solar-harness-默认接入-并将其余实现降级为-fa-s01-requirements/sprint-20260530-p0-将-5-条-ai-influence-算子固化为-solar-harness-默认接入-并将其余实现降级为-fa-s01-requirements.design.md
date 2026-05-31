# Design — s01-requirements: AI Influence 算子固化需求拆解

## 设计目标

将"5 条 AI Influence 算子固化 + 其余降级"需求拆解为可验收的需求组，生成 operator inventory、职责边界定义、primary/fallback 关系表和追踪矩阵。

## Operator Inventory 拓扑

```
┌─────────────────────────────────────────────────────────────────┐
│                    solar-harness (唯一执行宿主)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ① X / Social 主线                                              │
│  ├─ PRIMARY:  ai_influence_daily.py          (最终日报)          │
│  └─ EXECUTOR: playwright_twitter_scraper.py  (无头抓取)          │
│                                                                 │
│  ② GitHub 主线                                                   │
│  ├─ PRIMARY:  github_trends_pipeline.py      (新默认)            │
│  └─ CONTROL:  github_intelligence (旧版)     (短期对照)          │
│                                                                 │
│  ③ HF Papers 主线                                                │
│  ├─ PRIMARY:  tech_hotspot_radar.py          (最终分析)          │
│  └─ HELPER:   run_tech_hotspot_radar.sh      (调度辅助)          │
│                                                                 │
│  ④ Gemini Deep Research 主线                                     │
│  ├─ PRIMARY:  gemini_deep_research_operator.py (正式入口)        │
│  └─ EXECUTOR: browser_agent_gemini_deep_research_wrapper.py      │
│                                                                 │
│  ⑤ YouTube 主线                                                  │
│  ├─ PRIMARY:  youtube_influence_digest.py     (最终报告)         │
│  └─ EXECUTOR: browser_agent_youtube_transcript_wrapper.py        │
│                                                                 │
│  ── 统一输出层 ──                                                │
│  report + raw + metadata/status + log/diagnostic                │
│                                                                 │
│  ── /ai-influence 状态页 ──                                      │
│  6 区块: X/Social | GitHub New | GitHub Legacy | HF | YT | Gemini│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 需求域分析

PRD 包含 6 大目标：

| # | 目标 | 核心关注 |
|---|------|----------|
| 1 | 固化默认主入口 | 9 个文件的角色明确化 |
| 2 | 职责边界 | primary vs executor/fallback 不重叠 |
| 3 | 状态页统一 | /ai-influence 6 区块 |
| 4 | Primary/Fallback 机制 | 配置层明确关系 |
| 5 | 统一产物口径 | report+raw+metadata+log |
| 6 | 禁止新重复 | 唯一宿主 solar-harness |

## Requirement Group → Epic Slice 映射

| RG | 主切片 | 辅助切片 | 说明 |
|----|--------|----------|------|
| RG1 Operator Registration | S02 architecture | - | 配置层定义 primary/executor/fallback |
| RG2 Responsibility Boundaries | S02 architecture | S03 | 角色边界 + 代码级 guard |
| RG3 Primary/Fallback Config | S02 architecture | S03 | 配置 schema + 路由实现 |
| RG4 Unified Output Schema | S03 core-runtime | - | 产物格式标准化 |
| RG5 Status Page Integration | S04 orchestration-ui | - | /ai-influence 6 区块 |
| RG6 GitHub Dual-Run | S03 core-runtime | S04 | 新旧并行 + 对比展示 |
| RG7 Non-Goals & Constraints | S02 architecture | - | 约束文档 |
| RG8 Smoke Testing | S05 verification | - | 冒烟测试验证 |

## 跨切片依赖

1. RG1 operator registration (S02) → RG4 output schema (S03): 先知道哪些算子，再标准化输出
2. RG3 primary/fallback config (S02) → RG5 status page (S04): 页面需要知道谁是 primary
3. RG2 role boundaries (S02) → RG4 output schema (S03): 角色边界决定每个算子输出什么
4. RG6 GitHub dual-run (S03+S04) → RG8 smoke tests (S05): 双跑就绪才能测试

## 风险矩阵

| 风险 | 等级 | 缓解 |
|------|------|------|
| 旧 github_intelligence 退役时机不明确 | 中 | 写明对照期限和退役条件 |
| 9 个文件部分可能已不存在或已重构 | 中 | N1 先做 inventory 验证 |
| /ai-influence 页面现有实现未知 | 低 | S04 阶段再探查 |
| 产物格式各算子差异大 | 中 | RG4 定义最小公共 schema |
