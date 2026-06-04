# Plan — sprint-20260531-p0-ai-influence-youtube-报告流质量增强-report-ir-逐章写作-deep-w-s01-requirements

## 概述

本计划负责 S01 Requirements 阶段的需求拆解。从用户原始 P0 大需求中提取 8 个核心需求组（RG1-RG8），并围绕 Report IR Schema、Chapter Jobs 状态机、Evidence Pack、Verifier 规则、Repair Loop 流程、加权 Quality Score 评分以及 Operator Proof 校验机制进行详细规约与多层追踪，为后续 S02 架构设计提供标准规约文件。

## DAG 设计

```
N1 (原始大需求分析
   + 提取 8 个 RG)
        │
    ┌───┴───┐
    ▼       ▼
N2 (细化数据  N3 (细化 Verifier
   规约/结构)   & Quality 评分)
    │       │
    └───┬───┘
        ▼
N4 (边界, 风险 
   & 文件影响清单)
        │
        ▼
N5 (汇总产物 + 
   Traceability)
```

## 节点详情

### N1: 原始大需求分析 + 提取核心 RG
- **goal**: 分析原始大需求，提取核心 RG (至少 8 个 RG)，覆盖 5 个阶段 (S01-S05) 的所有核心功能。
- **write_scope**: `sprints/s01-req-N1-rg-extraction.md`
- **gate**: G_RG_EXTRACTED
- **acceptance**: 
  - 至少提取 8 个核心需求组 (RG)
  - 覆盖 PRD 所有核心实现目标与验收要求

### N2: 细化数据规约与数据结构规范
- **goal**: 细化 Report IR、Chapter Job 和 Per-Chapter Evidence Pack 数据规据与数据结构规范。
- **write_scope**: `sprints/s01-req-N2-data-specifications.md`
- **gate**: G_DATA_SPECIFICATIONS_DEFINED
- **acceptance**: 
  - 明确定义 `report-ir.json` 所需的 9 个全局属性及章节 10 个属性字段
  - 明确 `chapter_job` 的 7 种状态和支持的 9 种 chapter_type 及其默认 Deep Writer 规则
  - 明确 Evidence Pack 字段及 T0-T3 级别数据准入规则

### N3: 细化 Verifier 与 Quality 评分逻辑
- **goal**: 细化 Verifier (Chapter & Global)、Repair Loop 以及 Quality Score 评分量化逻辑与触发条件。
- **write_scope**: `sprints/s01-req-N3-verifier-quality-spec.md`
- **gate**: G_VERIFIER_SPECIFICATIONS_DEFINED
- **acceptance**:
  - 明确 Chapter Verifier 的 8 项检查标准及 `claim-verification` 的输出字段
  - 细化 Repair Loop 5 大场景的修复手段与退出规则 (最多 3 轮)
  - 给出 Quality Score 9 项权重分布公式、等级评定 (A/B/C/D) 和处理决策

### N4: 制定边界与风险缓解矩阵
- **goal**: 制定非目标边界（>= 6 条）、风险缓解矩阵（>= 6 条，含等级和缓解）以及文件影响清单（>= 8 个文件）。
- **write_scope**: `sprints/s01-req-N4-boundaries-risks.md`
- **gate**: G_BOUNDARIES_DEFINED
- **acceptance**: 
  - 非目标边界定义明确，至少 6 条
  - 风险缓解矩阵覆盖到位，至少 6 条
  - 文件影响清单覆盖 YouTube 报告流相关核心脚本与工具文件，至少 8 个文件

### N5: 汇总产物与 Traceability Map
- **goal**: 汇总 N1-N4 产物，生成 handoff.md 并建立 Parent Epic 到子 Sprint 的 Traceability Map。
- **write_scope**: `sprints/s01-req-N5-handoff.md`
- **gate**: G_REQUIREMENTS_READY
- **acceptance**: 
  - 产出完整的多层追踪矩阵 (Epic -> Child Sprints -> RGs)
  - handoff.md 包含完整 8 个 RG 及量化验收
  - 汇总核心规约、验证矩阵、非目标与未闭环项，为 S02 架构阶段提供清晰输入

## 先验知识

- `sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收` (PASSED): YouTube 报告流已具备基础规划和单次写完链路。
- `tools/chatgpt_report_operator.py` 已有基础 operator 接口可供后续扩展。
