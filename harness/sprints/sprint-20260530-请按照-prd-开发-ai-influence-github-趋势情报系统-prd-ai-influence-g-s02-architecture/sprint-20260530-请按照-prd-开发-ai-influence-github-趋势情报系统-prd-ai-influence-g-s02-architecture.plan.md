# Plan — s02-architecture: GitHub 趋势情报系统架构设计

## 概述

本 sprint 是 epic 第二切片 (s02-architecture)，基于 S01 的 10 个需求组 (RG1-RG10)，为 GitHub 趋势情报系统设计 5 层 Intelligence Pipeline 架构、4 个核心数据模型、评分引擎、归因模型和 Token 经济学处理管道。

## 架构设计范围

PRD 12 章节映射到以下架构模块：

| PRD 章节 | 架构模块 | 层级 |
|----------|----------|------|
| §4 数据源矩阵 | 5 数据源接口契约 | L1 Source |
| §5 发现机制 | 4 路发现器设计 | L2 Discovery |
| §3.3 Token 经济学 | 本地/云端处理管道 | L3 Processing |
| §6 数据模型 | 4 核心 schema | L4 Storage |
| §7 评分算法 | Heat Score + 3 Detector | L5 Analysis |
| §8 归因模型 | 5 维归因引擎 | L5 Analysis |
| §9 策划生成 | Planning Brief 生成器 | L5 Output |
| §10 报告层级 | 5 层报告结构 | L5 Output |
| §11 告警机制 | Critical/High 告警 | L5 Output |

## DAG 设计

```
N1 (系统架构总览 + 5 层分层)
    │
    ├──────────────┐
    ▼              ▼
N2 (数据源接口   N3 (4 核心
 契约: 5 源      Schema 设计)
 + 发现器接口)
    │              │
    ├──────┬───────┤
    ▼      ▼       
N4 (评分/归因   N5 (Token 经济
 引擎架构)      + 处理管道
                + 报告架构)
    │         │
    └────┬────┘
         ▼
N6 (Architecture Handoff)
```

- **N1**: 独立（总览 + 分层）
- **N2 ∥ N3**: 并行（接口契约 vs schema 设计）
- **N4 ∥ N5**: 并行（分析引擎 vs 处理管道）
- **N6**: join N4 + N5

## 节点详情

### N1: 系统架构总览
- **目标**: 设计 5 层 Intelligence Pipeline 架构图，定义层间接口边界
- **gate**: G_SYSTEM_LAYERED
- **acceptance**: 5 层架构图、层间数据流定义、每层职责边界

### N2: 数据源接口契约 + 发现器接口
- **目标**: 为 5 个数据源 + 4 路发现器定义接口签名、频率、错误处理
- **gate**: G_INTERFACES_DEFINED
- **acceptance**: 每个数据源有 API contract、rate limit 策略、错误处理

### N3: 4 核心 Schema 设计
- **目标**: 设计 Repo Master / Snapshot / Evidence Atom / Analysis Card 的字段和约束
- **gate**: G_SCHEMAS_DESIGNED
- **acceptance**: 4 个 schema 定义完成、Snapshot 不可覆盖约束、字段类型

### N4: 评分/归因引擎架构
- **目标**: Heat Score 6 因子权重 + 3 Detector 阈值 + 5 维归因模型
- **gate**: G_ENGINE_DESIGNED
- **acceptance**: 评分公式、检测器条件、归因维度、Evidence 关联

### N5: Token 经济学 + 处理管道 + 报告架构
- **目标**: 本地(Qwen) → 云端路由、5 层报告结构、策划 Brief、告警规则
- **gate**: G_PIPELINE_DESIGNED
- **acceptance**: Token 路由图、报告 5 层结构、告警条件、策划 Brief 模板

### N6: Architecture Handoff
- **目标**: 汇总全部架构文档 + handoff
- **gate**: G_ARCHITECTURE_READY
- **acceptance**: handoff 含 5 层架构 + 接口 + schema + 引擎 + 管道 + 下游需求

## 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| GitHub API rate limit | 中 | 接口设计含分级频率 + conditional request |
| 本地 LLM 压缩质量 | 中 | S03 PoC 验证 |
| 4 个 schema 之间关联复杂 | 中 | N3 明确外键关系 + 生命周期 |
| 评分权重需持续调优 | 低 | 设计为可配置参数 |
