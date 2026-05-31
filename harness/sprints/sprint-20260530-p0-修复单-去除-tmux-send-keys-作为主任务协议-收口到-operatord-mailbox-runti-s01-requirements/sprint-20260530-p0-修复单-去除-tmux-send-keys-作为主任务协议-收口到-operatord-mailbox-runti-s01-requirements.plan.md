# Plan — s01-requirements: 去除 tmux send-keys 主协议需求拆解

## 概述

从修复单（6 个问题 + 4 个修复范围 S1-S4）提取 13 个需求组（RG1-RG13），定义 task envelope schema 和 mailbox 协议草案，建立追踪矩阵。

## DAG 设计

```
N1 (PRD 分析 +
 RG 提取 13 条)
        │
    ┌───┴───┐
    ▼       ▼
N2 (验收标准  N3 (非目标 + 风险
 + envelope   + 文件影响)
 schema 草案)
    │       │
    └───┬───┘
        ▼
N4 (Traceability
 Map: RG→Slice)
        │
        ▼
N5 (Handoff)
```

## 节点详情

### N1: PRD 分析 + RG 提取
- **gate**: G_RG_EXTRACTED
- **acceptance**: >= 13 RG，覆盖 envelope/mailbox/coordinator/dispatcher/operatord/send-keys/compat/verification

### N2: 验收标准 + Envelope Schema
- **gate**: G_ACCEPTANCE_DEFINED
- **acceptance**: 13 RG 量化验收，task_envelope.v1 schema 草案

### N3: 非目标 + 风险 + 文件影响
- **gate**: G_BOUNDARIES_DEFINED
- **acceptance**: 非目标 >= 6，风险 >= 6，文件 >= 8

### N4: Traceability Map
- **gate**: G_TRACEABILITY_MAPPED
- **acceptance**: 13 RG 全映射，S03 承接最多

### N5: Handoff
- **gate**: G_REQUIREMENTS_READY
- **acceptance**: 完整 RG + schema + S02 需求

## 先验知识

- sprint-20260522-operatord-daemon-submit-production (PASSED): operatord daemon 提交机制已有基础
- sprint-20260521-physical-operator-registry (PASSED): physical operator 注册表已建立
- agent-actors.json 已有 mailbox 配置但 pane_mailbox.py 不存在
