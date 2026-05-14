# PRD: 需求拆解与追踪矩阵

epic_id: `epic-20260513-solar-deepresearch-product-line`
sprint_id: `sprint-20260513-solar-deepresearch-product-line-s01-requirements`
slice: `requirements`

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

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260513-solar-deepresearch-product-line.epic.md`、`epic-20260513-solar-deepresearch-product-line.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 每个 outcome 都有验收标准和风险边界
- 明确哪些工作不能直接派 builder
- 生成父 epic 到子 sprint 的 traceability map

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260513-solar-deepresearch-product-line-s01-requirements.design.md`
- `sprint-20260513-solar-deepresearch-product-line-s01-requirements.plan.md`
- `sprint-20260513-solar-deepresearch-product-line-s01-requirements.task_graph.json`
- `sprint-20260513-solar-deepresearch-product-line-s01-requirements.handoff.md`
- `sprint-20260513-solar-deepresearch-product-line-s01-requirements.eval.md` 或 `sprint-20260513-solar-deepresearch-product-line-s01-requirements.eval.json`

## DeepResearch 专用补充

本切片不是写代码，而是把 DeepResearch 产品线拆成可执行规格。必须输出：

- `deepresearch.prd.md`：定义用户价值、目标报告类型、目标字数、研究深度、输出格式、失败边界。
- `deepresearch.requirements_matrix.json`：把 Source Mesh、Evidence Ledger、Claim Ledger、ReportAST、Factuality Evaluator、Long Report Compiler 映射到后续子 sprint。
- `deepresearch.dod.md`：明确什么叫“可用”，不能只证明 CLI 存在；必须证明 evidence/claim/citation/report gates 有效。
- `deepresearch.stop_rules.md`：禁止单 prompt 生成长报告，禁止 unsupported key claim 进入 final report，禁止 source connector 失败后模型自说自话。
