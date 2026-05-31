# Plan — s01-requirements: AI Influence GitHub 趋势情报系统 需求拆解

## 概述

本 sprint 是 epic 的第一个切片（s01-requirements），目标是将大 PRD（12 章节、4000+ 字）拆解为可验收的需求组、追踪矩阵和边界定义，为后续 s02-architecture → s03-core-runtime → s04-orchestration-ui → s05-verification-release 提供结构化输入。

## PRD 需求域分析

PRD 包含以下核心功能域：

```
┌─────────────────────────────────────────────────────┐
│                PRD 功能域拓扑                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  [RG1] 项目发现机制 (Discovery)                       │
│  ├─ Topic Discovery (关键词扫描 Top 200)             │
│  ├─ Trending Discovery (Daily/Weekly/Monthly)        │
│  ├─ Tracked Repo Monitoring (动态频次 15m~6h)        │
│  └─ Cross-source Mention (YouTube/X 逆向发现)        │
│                                                     │
│  [RG2] 数据源接入 (Data Sources)                      │
│  ├─ GitHub REST/GraphQL                              │
│  ├─ GitHub Events API                                │
│  ├─ GH Archive / BigQuery                            │
│  └─ X / YouTube 社媒                                 │
│                                                     │
│  [RG3] 数据模型 (Schema)                              │
│  ├─ Repo Master (长生命周期)                          │
│  ├─ Repo Snapshot (不可覆盖快照)                      │
│  ├─ Repo Evidence Atom (本地模型压缩)                 │
│  └─ Project Analysis Card (最终卡片)                  │
│                                                     │
│  [RG4] 评分引擎 (Scoring)                             │
│  ├─ Heat Score (6 因子加权)                           │
│  └─ 3 个 Detector (Sudden Hot / Early Potential /     │
│     Foundation Infra)                                │
│                                                     │
│  [RG5] 归因模型 (Attribution)                         │
│  └─ 5 维归因 (Big-name / Release / Tech /             │
│     Ecosystem / Demo)                                │
│                                                     │
│  [RG6] 本地预处理 (Token 经济学)                      │
│  ├─ ThunderOMLX + Qwen3.6 清洗                       │
│  └─ Evidence Atom 压缩                               │
│                                                     │
│  [RG7] 项目策划生成 (Planning Brief)                  │
│  └─ S/A-tier 项目自动策划单                           │
│                                                     │
│  [RG8] 报告生成 (Report)                              │
│  └─ 5 层报告结构                                     │
│                                                     │
│  [RG9] 告警机制 (Alerting)                            │
│  └─ Critical / High 双级告警                          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 需求组到 Epic 切片的映射

```
RG → Epic Slice 映射
─────────────────────────────────────────────────────
RG1 Discovery      → S03 core-runtime (采集器实现)
RG2 Data Sources    → S02 architecture (接口契约)
                    → S03 core-runtime (适配器)
RG3 Schema          → S02 architecture (设计)
                    → S03 core-runtime (实现)
RG4 Scoring         → S03 core-runtime (算法实现)
RG5 Attribution     → S03 core-runtime (归因引擎)
RG6 Local Preprocess→ S03 core-runtime (ThunderOMLX 集成)
RG7 Planning Brief  → S04 orchestration-ui (自动化)
RG8 Report          → S04 orchestration-ui (生成器)
RG9 Alerting        → S04 orchestration-ui (告警管道)
```

## DAG 设计

```
N1 (PRD 分析 + 需求组提取)
    │
    ├──────────┐
    ▼          ▼
N2 (验收标准   N3 (边界/非目标
 + 风险边界)    + 约束矩阵)
    │          │
    └────┬─────┘
         ▼
N4 (Traceability Map
 + 跨切片依赖)
         │
         ▼
N5 (Handoff + 覆盖度审计)
```

- **N1**: 独立（只读 PRD + epic）
- **N2 ∥ N3**: 并行（N2 写验收标准，N3 写边界；不同 write_scope）
- **N4**: join N2 + N3
- **N5**: 依赖 N4

## 节点详情

### N1: PRD 全文分析 + 需求组提取
- **目标**: 读取 PRD 12 章节，提取 >= 8 个 requirement groups，标注优先级 P0/P1/P2
- **write_scope**: handoff + 分析报告
- **gate**: `G_PRD_ANALYZED`

### N2: 验收标准与风险边界定义
- **目标**: 每个 requirement group 给出可量化验收标准 + 风险边界
- **write_scope**: requirements matrix 文档
- **gate**: `G_ACCEPTANCE_DEFINED`

### N3: 非目标/约束/边界定义
- **目标**: 明确首批不做的内容 >= 5 条，约束矩阵（安全/性能/Token 预算）
- **write_scope**: boundaries 文档
- **gate**: `G_BOUNDARIES_DEFINED`

### N4: Traceability Map + 跨切片依赖分析
- **目标**: 将 requirement groups 映射到 S02-S05，识别 >= 3 个跨切片依赖
- **write_scope**: traceability 更新
- **gate**: `G_TRACEABILITY_MAPPED`

### N5: Handoff 编写 + 覆盖度审计
- **目标**: 最终 handoff，验证每个 outcome 都有验收+gate，上下游清晰
- **write_scope**: handoff.md
- **gate**: `G_HANDOFF_READY`

## 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| PRD 过大导致需求组遗漏 | 中 | N1 逐章节提取，N5 覆盖度审计兜底 |
| 跨切片依赖识别不充分 | 中 | N4 交叉检查 epic task_graph 和 traceability |
| P0/P1/P2 优先级划分争议 | 低 | 遵循 PRD 验收标准（§12）的 P0/P1/P2 定义 |
| 需求组粒度过粗或过细 | 中 | 目标 8-12 组，每组可独立验收 |

## 验证命令

```bash
# 检查 traceability 更新
python3 -c "import json; t=json.load(open('$SDIR/epic-*.traceability.json')); print(len(t['children']), 'child sprints')"

# 检查 handoff 存在
ls -la "$SDIR/${SID}.handoff.md"
```
