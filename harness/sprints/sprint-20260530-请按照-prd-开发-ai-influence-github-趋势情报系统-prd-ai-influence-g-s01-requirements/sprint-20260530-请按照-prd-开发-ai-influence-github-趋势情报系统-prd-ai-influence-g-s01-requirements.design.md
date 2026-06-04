# Design — s01-requirements: AI Influence GitHub 趋势情报系统 需求拆解

## 设计目标

将 PRD 12 章节（4000+ 字）结构化拆解为可验收的需求组 (Requirement Groups)，生成追踪矩阵和交付边界定义，作为后续 4 个切片（S02-S05）的结构化输入。

## 方法论

### 需求提取方法
- **逐章节扫描**: PRD §1-§12 每章提取一个或多个 requirement group
- **功能域分组**: 按职责域（而非 PRD 章节号）聚合为 8-12 个 RG
- **优先级标注**: 每个 RG 内子需求按 PRD §12 验收标准分为 P0/P1/P2

### 功能域拓扑

```
数据层 (Source)     → RG1 Discovery / RG2 Data Sources
处理层 (Process)    → RG6 Local Preprocess (ThunderOMLX+Qwen)
存储层 (Storage)    → RG3 Schema (Repo Master/Snapshot/Evidence/Card)
分析层 (Analysis)   → RG4 Scoring / RG5 Attribution
输出层 (Output)     → RG7 Planning Brief / RG8 Report / RG9 Alerting
```

### Requirement Group → Epic Slice 映射策略

| RG | 主切片 | 辅助切片 | 说明 |
|----|--------|----------|------|
| RG1 Discovery | S03 core-runtime | - | 采集器实现 |
| RG2 Data Sources | S02 architecture | S03 | 接口契约先行 |
| RG3 Schema | S02 architecture | S03 | 设计后实现 |
| RG4 Scoring | S03 core-runtime | - | 算法实现 |
| RG5 Attribution | S03 core-runtime | - | 归因引擎 |
| RG6 Local Preprocess | S03 core-runtime | - | ThunderOMLX 集成 |
| RG7 Planning Brief | S04 orchestration-ui | - | 自动化生成 |
| RG8 Report | S04 orchestration-ui | - | Markdown 生成器 |
| RG9 Alerting | S04 orchestration-ui | - | 告警管道 |

### 验收标准设计原则
1. 每个 RG 至少 2 条可量化验收标准
2. P0 验收标准必须可直接转化为测试用例
3. 风险边界覆盖 API rate limit、Token 预算、数据保留、安全

### 非目标定义原则
- 明确源自 PRD §2 反模式和 §12 P2 延后项
- 至少 5 条非目标
- 每条非目标标注"为什么不做"的理由

## DAG 架构

5 节点 DAG，2 个并行批次：

```
Batch 1: N1 (PRD 分析)
Batch 2: N2 || N3 (验收标准 || 边界定义)
Batch 3: N4 (Traceability Map, join N2+N3)
Batch 4: N5 (Handoff 汇总)
```

关键约束:
- N2 和 N3 的 write_scope 不重叠，可并行
- N4 是 join gate，必须等 N2+N3 都 passed
- N5 汇总全部产出，是唯一的最终 gate

## 跨切片依赖预判

1. RG3 Schema 设计 (S02) → RG4 Scoring 实现 (S03): 必须先定义数据结构
2. RG2 Data Sources 接口 (S02) → RG1 Discovery 采集器 (S03): API 契约先行
3. RG6 Local Preprocess (S03) → RG7 Planning Brief (S04): Evidence Atom 格式确定后才能生成策划单
4. RG4 Scoring (S03) + RG5 Attribution (S03) → RG8 Report (S04): 分析结果驱动报告内容

## 风险矩阵

| 风险 | 等级 | 缓解 |
|------|------|------|
| PRD §3.3 Token 经济学未给具体数值 | 中 | S02 architecture 设计时补全 budget |
| ThunderOMLX + Qwen3.6 本地清洗能力未验证 | 中 | S03 需先做 PoC |
| GH Archive/BigQuery 数据规模不确定 | 低 | P2 延后项，不阻塞 P0 |
| 跨源社媒 API 合规性/限流 | 中 | S02 需纳入 rate limit 设计 |
