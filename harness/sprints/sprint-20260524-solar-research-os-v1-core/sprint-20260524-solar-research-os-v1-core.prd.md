---
title: "PRD: Solar Research OS v1 Core"
sprint_id: sprint-20260524-solar-research-os-v1-core
priority: P0
lane: strategy
handoff_to: planner
status: drafting
phase: spec
created_at: 2026-05-24T20:30:00Z
---

# PRD: Solar Research OS v1 Core

**Source**: codex-pm-router (requirement_ir `req-b9d450e48cf6`)
**Priority**: P0
**Lane**: strategy
**Handoff To**: planner

Knowledge Context: solar-harness context inject used

## 背景 / Context

Solar-Harness 已经拥有 DAG scheduler、physical operators、APO/optimizer、evidence ledger、quality gate 和 status-server。但这些能力目前是面向 **sprint/builder 工作流**设计的，缺少一个面向 **研究编译** 的上层产品。

当前现状：
- 研究类需求（技术趋势分析、论文/产品/峰会调研、跨领域技术洞察）没有结构化的执行路径
- 没有证据驱动的 claim graph → 报告中关键判断无法追溯
- 没有统一的 SourceConnectorRegistry → 每次研究都从零开始接数据源
- 没有 Report Compiler → 报告由 LLM 自由生成，不是从结构化 evidence/claim/figure/section packet 编译

本 sprint 要在现有 harness 基础上构建 **Solar Research OS v1 Core**——一个证据驱动的研究编译器，不是另一个 deep research report writer。

## 用户问题 / Problem

1. **无结构化研究路径**: 用户发起研究请求后，系统没有 claim-level verifiable 的执行链，只能靠 LLM 自由生成 → 报告不可追溯、不可验证
2. **citation 不可信**: 没有从 evidence ledger 渲染 citation 的机制 → model-generated citation 无法避免
3. **反证缺失**: 没有 contradiction-first 搜索 → 报告只会支持假设，不会主动找反例
4. **图表空缺**: 没有 FigureSpec / architecture diagram / figure grounding → 报告无图
5. **产物漂移**: PRD / contract / DAG 多份产物互相漂移 → 用 Requirement IR 做唯一事实源编译

## 用户目标 / Goals

1. **Claim-level verifiable report**: 报告中的每个关键判断都可追溯到 evidence → claim graph → source/span
2. **Contradiction-first research**: 每个 high-impact claim 必须主动搜索反证和反面观点
3. **Report Compiler with section contracts**: 报告从结构化 evidence/claim/figure packet 编译，不是 LLM 自由生成
4. **Final closeout gate as SSOT**: 研究完成的唯一标准是 closeout gate 通过，不是 LLM 说"写完了"
5. **SourceConnectorRegistry**: 统一 provider 访问，支持 web/arxiv/GitHub/HF/YouTube 等数据源
6. **FigureSpec minimum viable path**: 技术架构图、技术栈分析图的最小可行路径
7. **Delta-friendly artifacts**: 产物设计支持后续 Living Report / delta research 扩展

## 用户故事 / User Stories

- **As 研究发起者 (PM/Architect)**, I want 输入一个研究意图后系统自动生成 Research Contract → Logical Plan → Physical Operator Plan → Evidence Ledger → Report, so that 我不需要手动编排每一步。
- **As 报告审阅者 (Evaluator)**, I want 报告中每个 claim 都有 evidence ledger 链接和 confidence score, so that 我能验证报告可信度而不只是看文字流畅度。
- **As 平台开发者 (Builder)**, I want Research OS 的各个模块有明确的 section contracts 和 operator seams, so that 后续能扩展到 Research Lab / Living Report / Domain Packs。
- **As 研究者**, I want contradiction-first 搜索自动覆盖我的核心假设的反面证据, so that 报告不会变成 confirmation bias 的放大器。
- **As Solar 维护者**, I want 所有研究产物都是 delta-friendly 的, so that 后续增量研究不需要从头开始。

## 功能需求 / Requirements

### Phase 拆分

| Phase | 内容 | 依赖 |
|---|---|---|
| **P0 止血** | Requirement IR 做唯一事实源，消除产物漂移 | 无 |
| **P1 核心编译链** | Research Intent → Contract → Plan → Evidence Ledger → Claim Graph → Report Compiler → Closeout Gate | P0 |
| **P2 图表与趋势** | FigureSpec / architecture diagram / figure grounding / 趋势分析模块 | P1 |
| **P3 Lab/Memory seams** | 为 Research Lab / Living Report / Domain Packs 预留 contracts/schema/operator seams | P1 |

### R1: Research Intent & Contract Compiler
- 接收研究意图字符串 → 编译为 Research Contract (JSON)
- Research Contract 包含: hypothesis, scope, time_window (默认 183 天回看), evidence_policy, required_gates
- Research Contract 是 Requirement IR 的编译产物，不是独立文件

### R2: Logical Research Plan → APO-scored Physical Operator Plan
- Logical Plan 定义研究 DAG 的抽象节点 (Ingest → Extract Claims → Contradiction Scan → Synthesis → Review → Closeout)
- APO (Automatic Plan Optimizer) 将 logical operators 映射到 physical operators (ResearchScout, Critic, Verifier, ResearchSynthesizer, ArtifactCurator)
- Physical Plan 包含: 依赖关系、cost estimate、risk score、parallelizability

### R3: Evidence Ledger & Claim Graph
- Evidence Ledger: 每个 evidence 记录 source_id, span, confidence, extraction_method, timestamp
- Claim Graph: claims 之间的 support/contradict/extend 关系
- 每个 high-impact claim 必须有 contradiction-first 搜索覆盖
- citation 必须从 ledger 渲染，禁止 model-generated citation

### R4: Report Compiler with Section Contracts
- 报告从结构化 packets 编译: evidence_packet, claim_packet, figure_packet, section_packet
- Section contracts 定义每个 section 的必需字段和验证规则
- 默认输出 2-5 万字，包含: 技术架构图、技术栈分析、技术趋势分析、跨领域技术洞察、论文/产品/峰会/关键人物分析
- 报告不是 LLM 自由生成，是 deterministic render from packets

### R5: Final Closeout Gate
- 单一 source of truth 判定研究是否完成
- Gate 检查: evidence ledger 完整性、claim graph 覆盖率、citation 可追溯性、contradiction coverage
- Gate 失败 → 进入 Repair DAG，不是直接结束
- 默认开启，不允许 opt-out

### R6: SourceConnectorRegistry
- 统一 provider 访问接口: discover(query), fetch(source_id), extract(source_id)
- v1 支持: web search, arxiv, GitHub repos/issues, HuggingFace models/datasets, YouTube transcripts
- 每个 connector 注册到 registry，支持 capability 声明 (full_text, metadata, structured_data)

### R7: FigureSpec & Architecture Diagram MVP
- FigureSpec schema: type, data_source, rendering_hint, grounding_spans
- v1 支持技术架构图 (component diagram) 和技术栈分析图 (stack comparison)
- figure grounding: 每个图元素必须引用 source evidence
- 渲染暂用 Mermaid/plantuml text output，后续 phase 加 visual rendering

### R8: Delta-friendly Artifacts
- 所有产物 (evidence_ledger, claim_graph, report_sections) 带版本号和 source_hash
- 后续 Living Report 可基于 delta 做增量更新
- Schema 预留 seams: stale_flag, invalidated_by, updated_from

### R9: Operator Seams for Future Phases
- 为 Research Lab 预留: benchmark_runner, repo_analyzer operator slots
- 为 Living Report 预留: delta_research, stale_claim_invalidator operator slots
- 为 Domain Packs 预留: domain_config, prompt_template_registry schema slots
- 为 Speaker/Conference Signal Intelligence 预留: signal_connector, trust_engine schema slots

## 验收标准 / Acceptance Criteria

| # | 标准 | 验证方式 |
|---|---|---|
| AC1 | Research Intent 输入 → Research Contract 输出，格式符合 Requirement IR schema | schema validation |
| AC2 | Evidence Ledger 每条记录包含 source_id + span + confidence + extraction_method | ledger dump 检查 |
| AC3 | Claim Graph 支持 support/contradict/extend 三种边 | graph structure 检查 |
| AC4 | Report 中所有 citation 从 ledger 渲染，无 model-generated citation | report grep for uncited claims |
| AC5 | 每个 high-impact claim 有 contradiction-first 搜索结果 | claim graph 中 contradiction 边存在 |
| AC6 | Final Closeout Gate 检查 evidence 完整性 + claim 覆盖率 + citation 可追溯性 | gate output JSON |
| AC7 | SourceConnectorRegistry 至少注册 3 个 connector (web, arxiv, github) | registry list 命令 |
| AC8 | FigureSpec schema 定义并至少产出 1 个架构图 | figure_spec.json + rendered output |
| AC9 | 所有产物带 version + source_hash，支持 delta-friendly | artifact metadata 检查 |
| AC10 | Gate 失败 → Repair DAG 自动触发，不是直接结束 | failure injection test |

## 非目标 / Non-Goals

- **不做 Full Research Console UI** — 后续 phase
- **不做 Global cross-run research memory network** — 后续 phase
- **不做 Marketplace for domain research packs** — 后续 phase
- **不做 Full human expert workflow** — 后续 phase
- **不做 Full empirical lab / benchmark reproduction framework** — 后续 phase
- **不把论文总结直接当作实现结论** — 必须有 evidence chain
- **不在缺证据时进入生产实现** — closeout gate 阻断

## 约束 / Constraints

- **Requirement IR 是唯一事实源**: PRD / contract / DAG 都是 IR 的编译视图，不允许手工修改编译产物后声称 IR 未更新
- **所有研究节点必须携带 evidence_policy / citation_required / unsupported_claim_guard**
- **P1 核心编译链必须在现有 harness 代码基础上落点**: `lib/research`, `graph_node_dispatcher`, `status-server/research_routes`, `operator_runtime`, `schemas/draft`, `graph_scheduler_research`
- **研究模式默认开启 evidence ledger 和 review gate**，不允许 opt-in 弱化
- **不允许 raw request 直派 builder**: 必须走 product-brief → planner handoff
- **时间窗口**: 默认 183 天回看 (相对 task.started_at)
- **source/document/span/evidence 是事实源，模型不是事实源**

## 风险 / Risks

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | PRD/contract/DAG 产物漂移 | 多源不一致导致执行混乱 | Requirement IR 做唯一事实源，所有视图从 IR 编译 |
| R2 | 原始需求直接派给 Builder | 执行发散，返工浪费 | 强制 product-brief / planner handoff |
| R3 | 研究结论缺证据链就进入实现 | 不可信的结论进入生产 | Research mode 强制 evidence ledger + review gate |
| R4 | contradiction-first 搜索覆盖不足 | 报告偏向 confirmation bias | 每个 high-impact claim 必须有 contradiction 边，gate 检查 |
| R5 | SourceConnectorRegistry 扩展成本高 | v1 connector 数量不足 | 先做 3 个核心 connector (web/arxiv/github)，后续增量加 |
| R6 | Report Compiler 复杂度超出 v1 范围 | sprint 超时 | section contracts 做最小集，后续 phase 扩展 |
| R7 | FigureSpec 渲染路径依赖外部工具 | 环境不一致 | v1 用 text-based (Mermaid)，不依赖 visual rendering engine |

## 开放问题 / Open Questions

| # | 问题 | 决策需要谁 | 处理方式 |
|---|---|---|---|
| Q1 | Research Contract 的 schema 版本策略? | Planner | 列入 P0，planner 在 design.md 中定义 |
| Q2 | Evidence Ledger 存储用 SQLite 还是 JSONL? | Planner | 列入 P1 design，给出 trade-off |
| Q3 | Claim Graph 的图存储选型 (edge list vs property graph)? | Planner | 列入 P1 design |
| Q4 | Report Compiler 的 section contracts 最小集包含哪些 section? | PM + Planner | 本 PRD 给出默认集，planner 可调整 |
| Q5 | Closeout Gate 的量化阈值 (evidence 覆盖率、claim 覆盖率)? | 昊哥 | 列入 handoff 未闭环项 |
| Q6 | 与现有 harness DAG scheduler 的集成点是 operator 级别还是 node 级别? | Planner | 列入 P1 design |
| Q7 | SourceConnectorRegistry 是否复用现有 knowledge_ingest_dispatcher 的 adapter 模式? | Planner | 需要调研与 sprint-20260524-141723 的交叉 |

## 架构交接 / Planner Handoff

**Handoff target**: `planner`

**Planner 必须做的**:

1. 读取本 PRD + requirement_ir.json + Contracts.yaml + task_graph.json
2. 基于 P0-P3 phase 拆分产出 design.md，包含:
   - 核心编译链架构 (Research Intent → Contract → Plan → Evidence → Claim → Report → Gate)
   - 各模块的接口契约和 schema
   - 与现有 harness (DAG scheduler, operators, status-server) 的集成点
   - Evidence Ledger / Claim Graph 的存储选型
3. 产出 plan.md 和 task_graph.json，节点围绕现有 harness 代码落点
4. 研究类节点必须显式携带 evidence_policy / citation_required / unsupported_claim_guard
5. task_graph 不要只停留在高层口号，要能切出明确实现节点

**Planner 不得做的**:

- 不得跳过 evidence ledger 直接设计 Report Compiler
- 不得在 design.md 中省略 contradiction-first 机制
- 不得在 v1 scope 中包含 Full Research Console UI / Memory Network / Marketplace
- 不得修改 Requirement IR schema (只能扩展 research variant)

**下游影响**:

- P0 (止血): Requirement IR 编译管线 — 影响所有后续产物生成
- P1 (核心编译链): lib/research, graph_node_dispatcher, status-server/research_routes
- P2 (图表): FigureSpec schema + Mermaid renderer
- P3 (seams): schema 预留，不改 runtime
- 交叉: SourceConnectorRegistry 与 knowledge_ingest_dispatcher (sprint-20260524-141723) 可能有 adapter 模式复用
