# Plan — s01-requirements: AI Influence 算子固化需求拆解

## 概述

本 sprint 是 epic 的第一个切片 (s01-requirements)，目标是将"5 条 AI Influence 算子固化 + 其余降级"需求拆解为 8+ 个 requirement groups，定义边界/非目标，生成 traceability map，为 S02-S05 提供结构化输入。

## PRD 需求域分析

PRD 描述了 6 大目标，涉及 9 个具体文件（5 条 primary 主线 + 4 条 executor/helper）：

```
Operator Inventory (9 files)
─────────────────────────────────────────────────────────
Line    Role        File
─────────────────────────────────────────────────────────
X       PRIMARY     scripts/ai_influence_daily.py
X       EXECUTOR    tools/playwright_twitter_scraper.py
GitHub  PRIMARY     scripts/github_trends_pipeline.py
GitHub  CONTROL     (旧 github_intelligence, 短期对照)
HF      PRIMARY     scripts/tech_hotspot_radar.py
HF      HELPER      scripts/run_tech_hotspot_radar.sh
Gemini  PRIMARY     tools/gemini_deep_research_operator.py
Gemini  EXECUTOR    scripts/browser_agent_gemini_deep_research_wrapper.py
YouTube PRIMARY     scripts/youtube_influence_digest.py
YouTube EXECUTOR    scripts/browser_agent_youtube_transcript_wrapper.py
```

## Requirement Groups

| RG | 名称 | PRD 来源 | 优先级 |
|----|------|----------|--------|
| RG1 | Operator Registration (主入口固化) | 目标 1 | P0 |
| RG2 | Responsibility Boundaries (职责边界) | 目标 2 | P0 |
| RG3 | Primary/Fallback Configuration (默认/回退配置) | 目标 4 | P0 |
| RG4 | Unified Output Schema (统一产物口径) | 目标 5 | P0 |
| RG5 | Status Page Integration (/ai-influence 页面) | 目标 3 | P1 |
| RG6 | GitHub Dual-Run Comparison (新旧双跑对照) | 目标 2, 3 | P1 |
| RG7 | Non-Goals & Constraints (非目标/约束) | 目标 6 | P0 |
| RG8 | Smoke Testing & Validation (冒烟测试) | 验收标准 | P1 |

## RG → Epic Slice 映射

```
RG → Epic Slice
──────────────────────────────────────────
RG1 Operator Registration    → S02 architecture (配置定义)
RG2 Responsibility Boundaries→ S02 architecture + S03 core-runtime
RG3 Primary/Fallback Config  → S02 architecture + S03 core-runtime
RG4 Unified Output Schema   → S03 core-runtime
RG5 Status Page Integration  → S04 orchestration-ui
RG6 GitHub Dual-Run          → S03 core-runtime + S04 orchestration-ui
RG7 Non-Goals & Constraints  → S02 architecture (约束文档)
RG8 Smoke Testing            → S05 verification-release
```

## DAG 设计

```
N1 (PRD 分析 + Operator Inventory)
    │
    ├──────────┐
    ▼          ▼
N2 (RG 提取    N3 (非目标/约束
 + 验收标准     + 边界定义)
 + 风险边界)
    │          │
    └────┬─────┘
         ▼
N4 (Traceability Map
 + 跨切片依赖)
         │
         ▼
N5 (Handoff + 覆盖度审计)
```

- **N1**: 独立，读取 PRD + epic context，列出 9 个 operator 及当前状态
- **N2 ∥ N3**: 并行（write_scope 不重叠）
- **N4**: join gate，等 N2 + N3 都 passed
- **N5**: 依赖 N4

## 节点详情

### N1: PRD 分析 + Operator Inventory
- **目标**: 读取 PRD 6 大目标，列出 9 个文件角色，验证文件存在性
- **write_scope**: N1-handoff.md
- **gate**: G_OPERATORS_INVENTORIED
- **acceptance**: >= 9 个文件在 inventory 表中、每个标注角色 (primary/executor/fallback/helper/control)

### N2: Requirement Group 提取 + 验收标准
- **目标**: 提取 >= 8 个 RG，每个有优先级和 >= 2 条验收标准
- **depends**: N1
- **write_scope**: N2-handoff.md
- **gate**: G_RG_EXTRACTED
- **acceptance**: >= 8 RG 编号、每个有 P0/P1/P2 + >= 2 条验收标准 + 风险等级

### N3: 非目标/约束/边界定义
- **目标**: 非目标 >= 5 条 + 约束矩阵 + 首批交付边界
- **depends**: N1
- **write_scope**: N3-handoff.md
- **gate**: G_BOUNDARIES_DEFINED
- **acceptance**: 非目标 >= 5 条、约束覆盖唯一宿主/no-duplicate-entry/fallback 规则

### N4: Traceability Map + 跨切片依赖
- **目标**: RG → S02-S05 映射 + >= 3 个跨切片依赖
- **depends**: N2, N3
- **write_scope**: N4-handoff.md
- **gate**: G_TRACEABILITY_MAPPED
- **acceptance**: 所有 RG 映射到至少一个 slice、>= 3 跨切片依赖、100% 覆盖

### N5: Handoff + 覆盖度审计
- **目标**: 汇总全部产出，覆盖度审计，编写最终 handoff.md
- **depends**: N4
- **write_scope**: handoff.md
- **gate**: G_HANDOFF_READY
- **acceptance**: handoff 含 inventory + RG + 验收 + 非目标 + traceability + 未闭环项

## 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 9 个文件部分可能已不存在/已重构 | 中 | N1 先做 inventory 验证文件存在性 |
| 旧 github_intelligence 退役时机不明确 | 中 | 定义对照期限和退役条件 |
| 产物格式各算子差异大 | 中 | RG4 定义最小公共 schema |
| /ai-influence 页面现有状态未知 | 低 | S04 再探查，S01 只定义需求 |

## 验证命令

```bash
# 检查 operator inventory 完整性
grep -c "PRIMARY\|EXECUTOR\|FALLBACK\|HELPER\|CONTROL" "$DIR/$SID.N1-handoff.md"

# 检查 RG 数量
grep -c "^RG[0-9]" "$DIR/$SID.N2-handoff.md"

# 检查 handoff 存在
ls -la "$DIR/$SID.handoff.md"
```
