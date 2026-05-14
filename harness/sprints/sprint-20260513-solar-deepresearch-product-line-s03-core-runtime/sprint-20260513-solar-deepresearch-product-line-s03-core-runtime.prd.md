# PRD: Solar DeepResearch S03 Core Runtime

## Context / 背景
S03 是 Solar DeepResearch 产品线的核心运行时切片，承接 S02 架构输出，为后续 orchestration-ui 和 verification-release 提供可执行地基。现有详细需求、目标架构、SQLite MVP 表、CLI 目标、运行产物和验收策略保留在本文末尾的原始详细材料中。

## Problem / 用户问题
当前 DeepResearch 产品线已经完成架构规划，但核心运行时、Source Mesh、报告生成流水线和可验证的数据模型仍未落地。若 S03 不先通过，S04 调度 UI 会缺少真实 runtime API 和状态表，容易出现只调度、不执行、不可验收的假前进。

## Goals / 目标
- 落地可被 harness 调度和测试的 DeepResearch core runtime。
- 提供 Source Mesh、任务状态、证据记录、长报告分段生成和 CLI 入口的最小闭环。
- 为 S04 orchestration-ui 和 S05 verification-release 提供稳定契约、数据表和测试锚点。

## User Stories / 用户故事
- 作为研究任务发起者，我可以提交一个 DeepResearch 主题并看到任务进入可追踪的运行状态。
- 作为 Builder/Verifier，我可以读取 runtime 产物、状态表和日志，判断每个阶段是否真实执行。
- 作为后续 UI 开发者，我可以依赖明确的 CLI/API/SQLite 契约，而不是解析临时文件。

## Requirements / 需求
- 实现核心 runtime 模块、数据表和 CLI 命令，支持任务创建、source mesh 采集/记录、分段报告状态和错误落盘。
- 所有关键路径必须有结构化状态，能被 coordinator/evaluator 自动验证。
- Runtime 必须与现有 Solar harness 约定兼容，不引入不可控后台常驻依赖。
- 对十万字报告策略采用可恢复、分段、可审计的生成模型，避免一次性长上下文堆叠。

## Acceptance Criteria / 验收标准
- S03 task_graph 中核心节点可以由 Builder 执行并产出 handoff。
- validate.sh PRD 校验通过，后续 Planner/Builder 不再因标题 schema 反复回退。
- 本切片交付的 CLI/API/SQLite 契约能支撑 S04 prerequisite 检查。
- 运行失败时必须有明确错误状态和日志，不能静默卡住。

## Non-Goals / 非目标
- 不在 S03 内完成完整 orchestration-ui。
- 不在 S03 内承诺生产级大规模并发和成本优化。
- 不绕过 S04/S05 的独立验收边界。

## Constraints / 约束
- S04 必须等待 S03 passed 后才能放行 Builder 节点。
- 必须优先使用本地 harness 现有脚本、status.json、task_graph 和日志机制。
- 任何自动推进都必须保持可审计历史，不能吞掉失败原因。

## Risks / 风险
- PRD/plan/schema 标题漂移会导致 coordinator 重复派 PM，浪费 pane 和 token。
- 若 graph scheduler 忽略外部 prerequisite，S04 会在 S03 未完成时误派 Builder。
- 长报告链路如果没有分段状态，容易出现生成中断后不可恢复。

## Open Questions / 开放问题
- S03 MVP 的 SQLite 表是否需要同时写入 Solar DB 主库，还是先使用 harness scoped DB。
- Source Mesh 第一阶段是否只支持本地/网页检索，还是立即接入多 provider。
- 十万字报告的默认分段大小和 evaluator 抽检策略需要在 S05 最终确定。

## Planner Handoff / 架构交接
- Planner/Builder 以本文末尾原始详细材料为实现细节来源，但必须保持本节 schema headings 不变。
- 优先交付 core runtime、状态表、CLI 和最小回归测试。
- Builder 在提交 handoff 前需证明 S04 prerequisite 可以读取 S03 passed 状态。
- 若发现上游依赖未满足，必须阻塞而不是绕过。

## Detailed Source Material / 原始详细材料

epic_id: `epic-20260513-solar-deepresearch-product-line`
sprint_id: `sprint-20260513-solar-deepresearch-product-line-s03-core-runtime`
slice: `core-runtime`

## 用户原始需求

# Solar DeepResearch Product Line Requirements

## 来源

用户提交了一份 Solar-Harness 后续增加 Deep Research 能力的设计文档，核心判断是：Solar-Harness 已经具备 AI-native 研发控制面的雏形，不应重写框架，也不应把 LangGraph 等外部框架硬塞为核心；应该在现有 Harness 上新增 DeepResearch 产品线，把深度研究变成专门的 DAG 工作流、证据系统和报告编译系统。

## 产品目标

把 Solar-Harness 从“AI-native 研发控制面”升级为“AI-native 研究生产操作系统”，支持多源检索、证据账本、claim 账本、研究图谱、结构化长报告 AST、分章节写作、事实审稿和最终报告编译。

## 当前地基

Solar-Harness 已具备以下可复用能力：

- DAG scheduler：非法 DAG fail fast、依赖 passed 后才能 ready、write_scope 冲突不会并发、parent 不能提前 passed。
- graph node dispatcher：按 node 生成 dispatch 文件、绑定 pane lease、限制 builder 只做当前 node、handoff 后进入 reviewing。
- evaluator 闭环：已有工程验收、write_scope、handoff、session log-native evaluation 基础。
- Capability Plane：已有 capability inference、skills inventory、doctor、readiness、certify、inject、scorecard。
- Unified Knowledge：已有 Mirage、QMD、Obsidian、Solar DB、RAGFlow optional 的统一上下文。
- Mirage VFS：已有安全 mount、redaction、path escape 防护和事件记录。
- 多 pane runtime：PM / Planner / Builder / Evaluator + Builder Lab，可承载研究团队角色。

## 核心缺口

### Source Mesh

DeepResearch 需要外部来源网格，并统一成 `Search -> Fetch -> Extract -> Normalize -> Cite`：

- Web Search
- Academic Search
- Preprint Search
- DOI Metadata
- Patent Search
- Code Repository Search
- Standards Search
- Dataset / Benchmark Search
- Company / Product / Release Notes Search
- Internal Mirage / QMD / Obsidian / Solar DB

### Evidence Ledger

需要一等公民级证据账本：

- `EvidenceItem`
- `Claim`
- `ClaimEvidenceLink`
- `CitationSpan`
- `Contradiction`
- `EvidencePack`

硬规则：

- 没有 `evidence_id` 的关键 claim 不能进入正文。
- 没有 `span_text` 的 evidence 不能支撑正文。
- citation span 不匹配正文 claim，factuality evaluator 必须 fail。

### ReportAST

十万字报告不能靠一次长 prompt 生成，必须有结构化 AST：

- `Report`
- `Chapter`
- `Section`
- `Subsection`
- `ClaimBlock`
- `EvidenceBlock`
- `FigureBlock`
- `TableBlock`
- `Bibliography`

### Factuality Evaluator

DeepResearch 需要事实审稿 gates：

- `unsupported_claim_rate`
- `citation_span_accuracy`
- `source_authority_score`
- `freshness_score`
- `contradiction_coverage`
- `section_repetition_rate`
- `cross_section_consistency`

### Source Intent Classifier

现有 capability inference 适合工程 dispatch，但研究规划需要判断问题需要哪些来源：

- 论文还是标准？
- GitHub issue 还是 official changelog？
- patent 还是 benchmark？
- 最新资料还是历史脉络？
- 是否需要反向证据？

## 目标架构

新增一级能力模块：

```text
harness/lib/research/
  schemas.py
  ids.py
  hashing.py
  storage.py
  sources/
  extractors/
  evidence/
  graph/
  report/
  eval/
  cli.py

skills/solar-deep-research/
agents/researcher/
agents/evidence-miner/
agents/fact-checker/
agents/chief-editor/
```

## 运行产物

每个 DeepResearch sprint 至少产出：

```text
<sid>.research_brief.md
<sid>.research_plan.json
<sid>.source_matrix.json
<sid>.sources.jsonl
<sid>.evidence.jsonl
<sid>.claims.jsonl
<sid>.contradictions.jsonl
<sid>.report_ast.json
<sid>.sections/
<sid>.chapters/
<sid>.final.md
<sid>.final.bibliography.json
<sid>.research_eval.json
```

## DeepResearch DAG 模板

推荐节点：

- `R0_scope_rewrite`
- `R1_source_matrix`
- `R2_external_search`
- `R3_fetch_extract`
- `R4_claim_mining`
- `R5_contradiction_hunt`
- `R6_report_ast`
- `R7_section_writing_batch`
- `R8_section_fact_check`
- `R9_chapter_compile`
- `R10_global_consistency`
- `R11_final_export`

## 十万字报告策略

不要一次性输出十万字。应生成 30-40 个 section artifact：

```text
sections/ch01/sec01.spec.json
sections/ch01/sec01.evidence_pack.json
sections/ch01/sec01.claims.json
sections/ch01/sec01.draft.md
sections/ch01/sec01.factcheck.json
sections/ch01/sec01.final.md
```

每节 2000-4000 字，每节证据包 20-80 条 evidence，每节 claim 20-60 条。

## Source Mesh 分层

公网与网页层：

- Brave Search
- Exa
- Tavily
- Jina Reader

学术与技术层：

- OpenAlex
- Semantic Scholar
- arXiv
- Crossref
- Papers With Code

工程与产业层：

- GitHub
- Hugging Face
- Lens / USPTO
- IETF / W3C / NIST / IEEE / ISO
- Official docs / changelogs / release notes

## CLI 目标

```bash
solar-harness research run --brief "..." --target-chars 100000 --depth max
solar-harness research plan --sid <sid>
solar-harness research search --sid <sid>
solar-harness research extract --sid <sid>
solar-harness research mine --sid <sid>
solar-harness research graph --sid <sid>
solar-harness research outline --sid <sid>
solar-harness research write --sid <sid> --section <id>
solar-harness research check --sid <sid>
solar-harness research compile --sid <sid>
solar-harness research export --sid <sid> --format md|docx|pdf
solar-harness research status --sid <sid> --json
```

## SQLite MVP 表

先用 SQLite，不急着上重型数据库：

- `research_runs`
- `research_sources`
- `evidence_items`
- `claims`
- `claim_evidence`
- `report_sections`
- `section_checks`

## 阶段策略

### Phase 1: Evidence Kernel

先做 `schemas.py`、`storage.py`、`evidence/ledger.py`、`evidence/citation_span.py`，目标是 `research init/add-source/extract/ledger` 可用。

### Phase 2: Source Mesh

先接 `internal_mirage`、`github`、`arxiv`、`crossref`、`semantic_scholar`、`openalex`、`jina/html extractor`。

### Phase 3: Claim Miner

新增 `claims.jsonl`、claim-evidence links、support checker、contradiction task。

### Phase 4: ReportAST + Section Compiler

新增 `report_ast.json`、`sections/`、`chapters/`、`final.md`。

### Phase 5: DeepResearch Skill / Agent

新增 `skills/solar-deep-research/SKILL.md` 和 researcher/evidence-miner/fact-checker/chief-editor agents，接入 capability plane。

## 验收标准

- P0：Evidence Ledger 能写入、读取、hash、span verify。
- P0：DeepResearch CLI 有 `init/add-source/extract/ledger/status`。
- P0：SourceConnector schema 和最小 internal/file/html connector 可用。
- P0：Claim Ledger 能拒绝 unsupported key claim。
- P1：ReportAST 能把 section artifacts 编译成 final markdown 和 bibliography。
- P1：Factuality evaluator 输出 unsupported claim rate 和 citation span accuracy。
- P1：DAG 模板能被 graph_scheduler validate，并能按 write_scope 并行 dispatch。
- P2：skills/agents 注册到 capability plane，并出 activation-proof。

## Stop Rules

- 不允许把 DeepResearch 做成一个单 prompt。
- 不允许没有 evidence span 的 claim 进入 final report。
- 不允许 parent sprint 在 evidence / claims / fact-check gates 未过前 passed。
- 不允许 Source Mesh connector 失败时静默降级为模型自说自话。
- 不允许十万字报告写入单个 builder 节点。

## 本切片目标

实现核心库、状态机、schema、持久化和向后兼容适配层。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260513-solar-deepresearch-product-line.epic.md`、`epic-20260513-solar-deepresearch-product-line.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 核心 API 有单测覆盖
- 旧路径兼容，不破坏现有 wake/dispatch/status
- 状态变更可由元数据或事件重建

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260513-solar-deepresearch-product-line-s03-core-runtime.design.md`
- `sprint-20260513-solar-deepresearch-product-line-s03-core-runtime.plan.md`
- `sprint-20260513-solar-deepresearch-product-line-s03-core-runtime.task_graph.json`
- `sprint-20260513-solar-deepresearch-product-line-s03-core-runtime.handoff.md`
- `sprint-20260513-solar-deepresearch-product-line-s03-core-runtime.eval.md` 或 `sprint-20260513-solar-deepresearch-product-line-s03-core-runtime.eval.json`

## DeepResearch 专用补充

本切片实现最小可运行 research kernel。优先级：

- P0: `harness/lib/research/schemas.py`、`ids.py`、`hashing.py`、`storage.py`。
- P0: `harness/lib/research/evidence/ledger.py` 和 `citation_span.py`，支持 write/read/hash/span verify。
- P0: `harness/lib/research/sources/base.py`、`internal_mirage.py`、`extractors/markdown.py` 或 `html.py` 的最小 connector。
- P0: `solar-harness research init/add-source/extract/ledger/status` CLI。
- P1: `claims.jsonl`、`claim_evidence` links、unsupported claim checker。

验收时必须用真实 fixture 写入 source/evidence/claim，并证明 unsupported key claim 被拒绝。
