# Plan — s02-architecture: AI Influence 算子固化架构设计

## 概述

本 sprint 是 epic 第二切片 (s02-architecture)，基于 S01 的需求矩阵，为 5 条 AI Influence 主线（9 个 operator 文件）产出架构设计。涵盖 control plane (operator registry + routing)、data plane (unified output schema)、presentation plane (/ai-influence status page) 三层。

## 架构设计范围

```
3 层架构
──────────────────────────────────────────
Control Plane:
  - Operator Registry (operator_registry.json)
  - Router/Dispatcher (primary/fallback/executor 路由)
  - Role enforcement (禁止 executor 产出最终报告)

Data Plane:
  - Unified Output Schema (report + raw + metadata + log)
  - metadata.json 最小公共 schema
  - GitHub dual-run 数据隔离

Presentation Plane:
  - /ai-influence 页面数据模型 (6 cards)
  - GitHub New/Legacy 对照视图
```

## 5 条主线 × 角色矩阵

| 主线 | Primary | Executor | Fallback/Control | 产物目录 |
|------|---------|----------|-------------------|----------|
| X/Social | ai_influence_daily.py | playwright_twitter_scraper.py | - | reports/x-social/ |
| GitHub | github_trends_pipeline.py | - | github_intelligence (control) | reports/github/ |
| HF Papers | tech_hotspot_radar.py | run_tech_hotspot_radar.sh (helper) | - | reports/hf-papers/ |
| Gemini | gemini_deep_research_operator.py | browser_agent_gemini_deep_research_wrapper.py | - | reports/gemini/ |
| YouTube | youtube_influence_digest.py | browser_agent_youtube_transcript_wrapper.py | - | reports/youtube/ |

## DAG 设计

```
N1 (现状审计: 9 文件接口/输出/依赖)
    │
    ├──────────────┐
    ▼              ▼
N2 (系统分层     N3 (接口契约
 + Registry       + 统一 Output
 设计)            Schema)
    │              │
    ├──────┬───────┤
    ▼      ▼       
N4 (状态页   N5 (兼容策略
 数据模型     + 迁移方案)
 + GitHub
 对照设计)
    │         │
    └────┬────┘
         ▼
N6 (Architecture Handoff)
```

- **N1**: 独立（审计 9 个文件现状）
- **N2 ∥ N3**: 并行（N2 写 registry/routing 设计，N3 写接口契约/output schema）
- **N4 ∥ N5**: 并行（N4 写状态页数据模型，N5 写兼容迁移策略）
- **N6**: join N4 + N5

## 节点详情

### N1: 现状审计
- **目标**: 审计 9 个 operator 文件，记录: 文件存在性、当前接口签名、输出格式、上下游依赖
- **gate**: G_STATE_AUDITED
- **acceptance**: 9 个文件的审计表完成、每个标注现状接口和输出格式

### N2: 系统分层 + Registry 设计
- **目标**: 设计 control plane operator_registry.json schema + routing 逻辑
- **gate**: G_REGISTRY_DESIGNED
- **acceptance**: registry schema 可表达 5 条主线的 primary/executor/fallback 关系、routing 规则明确

### N3: 接口契约 + 统一 Output Schema
- **目标**: 定义 4 类统一产物格式 (report + raw + metadata + log) + metadata.json 最小 schema
- **gate**: G_OUTPUT_SCHEMA_DESIGNED
- **acceptance**: metadata.json schema 定义完成、所有 5 条主线可适配

### N4: 状态页数据模型 + GitHub 对照设计
- **目标**: 设计 /ai-influence 6 card 数据模型 + GitHub New/Legacy 对照视图
- **gate**: G_STATUS_PAGE_DESIGNED
- **acceptance**: 6 card 数据模型完成、GitHub 对照视图字段定义

### N5: 兼容策略 + 迁移方案
- **目标**: 文档化旧接口保留期、退役条件、回滚策略、breaking changes
- **gate**: G_MIGRATION_PLANNED
- **acceptance**: GitHub legacy 退役条件明确、executor 内化方案、回滚策略

### N6: Architecture Handoff
- **目标**: 汇总全部设计文档，编写 handoff.md
- **gate**: G_ARCHITECTURE_READY
- **acceptance**: handoff 含 3 层架构 + registry schema + output schema + 状态页模型 + 迁移方案

## 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 9 个 operator 文件接口差异大 | 中 | N1 先审计，N3 设计适配层 |
| 旧 github_intelligence 退役时机争议 | 中 | N5 定义明确退役条件和时间窗 |
| 状态页现有实现未知 | 低 | N4 只定义数据模型，S04 再实现 |
| 统一 output schema 可能过于约束 | 低 | 设计为最小公共 + 扩展字段 |

## 验证命令

```bash
# 检查架构文档存在
ls -la "$DIR/$SID.design.md" "$DIR/$SID.plan.md"
# 检查 handoff
ls -la "$DIR/$SID.handoff.md"
```
