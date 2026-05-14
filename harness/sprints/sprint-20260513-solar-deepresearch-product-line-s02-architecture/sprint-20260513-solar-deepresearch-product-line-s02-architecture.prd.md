# PRD — 架构设计与接口契约 (S02 architecture)

> epic_id: `epic-20260513-solar-deepresearch-product-line`
> sprint_id: `sprint-20260513-solar-deepresearch-product-line-s02-architecture`
> slice: `architecture`
> priority: `P0`
> Author: Solar PM
> Date: 2026-05-13
> Depends on: S01_requirements (passed at 01:50Z 2026-05-14)
> Knowledge Context: solar-harness context inject used

---

## 0. 切片定位 (Slice Framing)

S02 是 DeepResearch Product Line 的**架构契约切片** —— S01 已经把"做什么"压成可验收 PRD + 需求矩阵 + DoD + Stop Rules, S02 必须把"怎么做"压成可被 S03 builder 直接落地的架构契约: **模块分层、Schema 不变量、存储布局、标准 DAG 模板**。

S02 **不写**实现代码 (那是 S03 core-runtime), **不**做接入层 (那是 S04 orchestration-ui), **不**做验证/release (那是 S05)。本切片是**架构 spec only**: 4 份规格文档 (.md/.json), 0 行可执行 `.py/.sh/.ts/.js`。

## 1. Context / 背景

S01 已交付:
- `deepresearch.prd.md` — 用户价值/目标报告类型/失败边界
- `deepresearch.requirements_matrix.json` — 把 Source Mesh/Evidence Ledger/Claim Ledger/ReportAST/Factuality/Long Report Compiler 映射到子 sprint
- `deepresearch.dod.md` — 什么叫"可用"
- `deepresearch.stop_rules.md` — 5 条红线

但 S01 没有钉死**接口契约**:
- 8 个数据模型 (SourceConnector / SourceHit / SourceDocument / EvidenceItem / Claim / ClaimEvidenceLink / CitationSpan / ReportAST) 的字段名、类型、必填、不变量
- `harness/lib/research/` 子模块的边界 (谁负责写 schema / 谁负责读 / 谁负责 hash)
- SQLite 7 张表 vs JSONL artifact 的职责切分
- R0-R11 DAG 模板的节点 ID/依赖/write_scope 规则

如果不先压住接口契约, S03 builder 边写边设计会出三大灾难:
1. **Schema 漂移**: builder A 用 `span_text`, builder B 用 `text_span`, builder C 用 `quote`; claim_id 哈希算法不一致
2. **存储双写**: evidence 既在 SQLite `evidence_items` 表又在 `<sid>.evidence.jsonl`, 还不一致, 监护人看哪个都不对
3. **DAG 模板返工**: S04 接 capability plane 时发现 R3_fetch_extract 节点 write_scope 跟 R4_claim_mining 重叠, 整个产品线返工

## 2. Problem Statement / 用户问题

**S03 builder 视角的疼点**:
- 拿到 S01 PRD 后, 字段级 schema 不写在哪份文档里, 只能问 PM 或自己拍 → 出现 8 个模型 30+ 字段的命名分歧
- SQLite/JSONL 边界不清, 同一个 evidence 写两遍是常见 anti-pattern
- DAG 模板没先过 graph_scheduler validate, builder 等到 S04 集成才发现 task_graph 非法

**S04 builder 视角的疼点**:
- 没 DAG 模板, 没法实现 `solar-harness research run --expand-template`
- 没 schema 钉死, status UI 显示的 `evidence_count` 跟 `claim.evidence_ids` 数量对不上

**评估者 / 监护人视角的疼点**:
- 没接口契约 → 后续每个节点 eval 都要争吵"这个字段名对不对" → 评审颗粒度 ≈ 字段级
- 没存储边界 → audit 时无法判断 evidence 是不是真的归一了 (vs 多份残留)

**根因**: DeepResearch 涉及 8 个数据模型 + 7 张存储表 + 12 个 DAG 节点, 必须先有"法律级" architecture spec, 否则下游所有 sprint 都在猜接口。

## 3. User Goals / 用户目标

| # | 目标 | 衡量 |
|---|------|------|
| G1 | Schema 是法律 | 8 个数据模型字段全钉死 (字段名/类型/必填/不变量), `deepresearch.schemas.md` 通过 PM+评估者双签 |
| G2 | 模块边界单一来源 | `harness/lib/research/` 各子模块的"读/写哪些 schema"由 `deepresearch.architecture.md` 唯一回答 |
| G3 | SQLite/JSONL 职责互斥 | `deepresearch.storage.md` 给每个 evidence/claim 字段明确"在 SQLite / 在 JSONL / 在两边" 的归属, 无双写 |
| G4 | DAG 模板可机器校验 | `deepresearch.dag-template.json` 跑 `solar-harness graph-scheduler validate` exit 0, R0-R11 节点 write_scope 0 冲突 |
| G5 | 复用现有基础设施 | 4 份产物明确写"复用 DAG scheduler / dispatch / evaluator / capability plane / Mirage / context inject", 不发明新框架 |
| G6 | S03/S04 启动可行 | handoff.md 直接列出"S03 schemas.py 输入"、"S04 capability plane 输入"两个接口表 |

## 4. User Stories / 用户故事

- **US1**: 作为 S03 schemas.py builder, 我希望打开 `deepresearch.schemas.md` 就能逐字段照着实现 (含 type hints + 不变量 + ID 算法), **以便** 0 字段歧义。
- **US2**: 作为 S03 storage.py builder, 我希望 `deepresearch.storage.md` 给我 SQLite 7 张表的完整 DDL + JSONL 每行的 schema + 索引策略, **以便** 知道哪条数据走 SQLite 哪条走 JSONL。
- **US3**: 作为 S04 capability plane builder, 我希望 `deepresearch.dag-template.json` 是 machine-readable JSON, 我能直接调 `graph_scheduler validate` 不需要手抄, **以便** 不重复造 DAG schema 解析。
- **US4**: 作为 S04 status UI builder, 我希望 `deepresearch.architecture.md` 告诉我"哪些字段进 status panel"、"哪些字段 evidence-private 不暴露", **以便** UI 不泄漏内部 hash。
- **US5**: 作为评估者, 我希望 4 份产物的字段命名互相一致 (e.g. `evidence_id` 不能在 schemas.md 叫 `eid` 在 storage.md 叫 `evidence.id`), **以便** 不用字段级 grep audit。
- **US6**: 作为监护人, 我希望 S02 不写实现代码, **以便** 这个 sprint 1 天内能 closeout, 不变成 8 个数据模型的实现 marathon。

## 5. Functional Requirements / 功能需求

### FR-1 模块分层与 CLI 边界 (对应 A1)
- 在 `deepresearch.architecture.md` 写明 `harness/lib/research/` 8 个子模块 (schemas / ids / hashing / storage / sources / extractors / evidence / graph / report / eval / cli) 各自的责任
- 每个子模块声明: 读哪些 schema, 写哪些 schema, 调用哪些子模块, 不调用哪些子模块
- CLI 边界: `solar-harness research <subcmd>` 的 12 条子命令 (run/plan/search/extract/mine/graph/outline/write/check/compile/export/status) 每条命令的 read/write scope
- 复用策略: DAG scheduler / dispatch / evaluator / capability plane / Mirage / context inject 各自怎么接入 (现有 API 字段映射)

### FR-2 数据模型 schema 钉死 (对应 A2)
- 在 `deepresearch.schemas.md` 给出 8 个数据模型完整字段:
  - `SourceConnector`: 接口形态 (search / fetch / extract 三方法签名 + return type)
  - `SourceHit`: query/url/title/snippet/score/source_kind/fetched_at
  - `SourceDocument`: hit_ref/raw_bytes/normalized_text/extraction_meta
  - `EvidenceItem`: id/hash/span_text/source_doc_ref/page/quote_kind/authority_score/freshness
  - `Claim`: id/hash/statement/scope/confidence/created_by_node
  - `ClaimEvidenceLink`: claim_id/evidence_id/support_kind/strength
  - `CitationSpan`: in_report_path/character_range/evidence_id/verified
  - `ReportAST`: Report/Chapter/Section/Subsection/ClaimBlock/EvidenceBlock/FigureBlock/TableBlock/Bibliography 八层节点的字段
- 每个字段标注: 类型 / 必填 / 不变量 / 何时计算
- ID/hash 算法: `evidence_id = sha256(span_text + source_doc_ref + page)`, 类似规则全部写死

### FR-3 存储层职责互斥 (对应 A3)
- 在 `deepresearch.storage.md` 给出 SQLite 7 张表 (`research_runs / research_sources / evidence_items / claims / claim_evidence / report_sections / section_checks`) 完整 DDL
- JSONL artifact 布局: `<sid>.sources.jsonl / evidence.jsonl / claims.jsonl / contradictions.jsonl` 每行 schema
- 互斥规则: 每个字段明确"主存储=SQLite 还是 JSONL", 另一个最多是 derived view
- 索引策略: SQLite FTS5 / 物理索引列表
- hash/span verify 算法: 写 evidence 时怎么算 hash, 读时怎么 verify span_text 仍在 source_doc 里
- 向后兼容: 字段加列 / 改列 / 删列三种场景的迁移规则

### FR-4 DAG 模板可机器校验 (对应 A4)
- 在 `deepresearch.dag-template.json` 给出 R0-R11 12 节点完整定义 (节点 ID / 角色 / 输入 / 输出 / write_scope / 依赖)
- 节点 ID 命名规则: `R{0..11}_{snake_case}` (e.g. `R0_scope_rewrite`, `R3_fetch_extract`)
- write_scope 隔离: section 级写权限走 `sections/chXX/secYY.*` 前缀, R3/R4 不能跟 R7 共写 `sections/`
- 通过 `solar-harness graph-scheduler validate <path>` exit 0
- 模板字段必须复用 `~/.solar/harness/schemas/task-graph.schema.json`, 不引入新 schema

### FR-5 失败恢复 + 观测 (对应 A5)
- `deepresearch.architecture.md` 写明每个 R 节点失败时的恢复策略 (重试 / 跳过 / 降级 / 阻塞)
- 观测点: 哪些字段送 status UI, 哪些字段进 events.jsonl, 哪些字段是私密 (不暴露)
- 不重复 S04 设计 (S04 实现 status UI), 只画接口契约

### FR-6 handoff 接口表 (对应 A6)
- `<sid>.handoff.md` 必须含两节:
  - **给 S03 的接口**: 列出 S03 schemas.py / storage.py / sources/ / evidence/ 各模块的输入文件 (来自 S02 4 份产物的哪几节)
  - **给 S04 的接口**: 列出 S04 autopilot intent / DAG 模板 / status UI 各组件的输入文件 (来自 S02 哪几节)
- 含已知 risk 表 (字段命名争议未解 / 未来扩展点 / 假设)

## 6. Acceptance Criteria / 验收标准

| ID | 验收 | 验证命令 |
|----|------|----------|
| A1 | architecture.md 覆盖 control/data plane + 状态 + 失败恢复 + 观测 | grep `module=`/`api=`/`recovery=`/`observe=` 四类标签, 各 ≥3 条 |
| A2 | schemas.md 8 个数据模型字段齐 | grep `^### ` 模型名出现 8 次, 每个模型字段表行数 ≥ 模型字段数 |
| A3 | storage.md SQLite 7 表 DDL + JSONL 互斥 | grep `CREATE TABLE` 出现 7 次, 字段归属表 (SQLite / JSONL / both) 完整 |
| A4 | dag-template.json 通过 validate | `solar-harness graph-scheduler validate deepresearch.dag-template.json` exit 0 + R0-R11 12 节点 + write_scope 0 冲突 |
| A5 | handoff.md 给 S03/S04 接口表齐 | grep `给 S03 的接口` / `给 S04 的接口` 各 1 次, 接口字段表 ≥10 条 |
| A6 | 字段命名跨 4 份产物一致 | 4 份产物 grep `evidence_id / claim_id / span_text / source_doc_ref` 命名 0 漂移 |
| A7 | 0 行可执行代码 | `find sprints/$sid.* -name '*.py' -o -name '*.sh'` 返回空 |

每条 acceptance 必须有可复现验证证据 (命令 + 输出 + 时间戳), 不接受 "刚跑过缓存通过"。

## 7. Non-Goals / 非目标

- **不**写任何可执行代码 (.py/.sh/.ts/.js) — 全部 .md + .json
- **不**实现 connector (OpenAlex/Brave/Tavily/Jina 等) — 只设计 schema, 不发请求
- **不**冻结 LLM 模型路由 — 每个 R 节点用什么模型由 S03 builder 决定, S02 只定 input/output schema
- **不**写 SKILL.md / agent — 那是 S04 的事
- **不**重写 `~/.solar/harness/schemas/task-graph.schema.json` — 只产出 DAG 模板实例
- **不**替换 Mirage / context inject / evaluator / capability plane — 现有基础设施完全复用
- **不**做 schema migration script — S03 实现时再做, 本切片只写迁移**策略**
- **不**展开 epic 全部 12 子能力实现 — 只压字段级契约

## 8. Constraints / 约束

- **C1 (依赖)**: 本切片建立在 S01 PRD 已 passed 之上 (✅ 2026-05-14T01:50Z), 不重新讨论用户价值层
- **C2 (单一来源)**: 字段命名在 4 份产物中 0 漂移 — 任何重命名必须 4 份同步, 评审用 grep diff
- **C3 (互斥存储)**: 同一字段不能既是 SQLite 主存储又是 JSONL 主存储 — 必须明确归属
- **C4 (machine-readable DAG)**: `deepresearch.dag-template.json` 必须是合法 JSON, 不能含 `// comment` / trailing comma
- **C5 (复用 task_graph schema)**: 不引入新 DAG schema, 复用现有 `task-graph.schema.json`
- **C6 (向后兼容)**: schema 新增字段不能破坏现有 `solar-harness research / graph-scheduler` 命令签名 (虽然现在还没实现, 接口契约要为兼容性预留)
- **C7 (Stop Rules 继承)**: 父 epic 5 条 Stop Rules 继续生效
- **C8 (0 代码)**: 任何代码逻辑只能用伪码 / DDL / JSON 表达, 不能写实际 .py/.sh

## 9. Risks / 风险

| # | 风险 | 触发条件 | 缓解 |
|---|------|----------|------|
| R1 | Schema 设计过早冻结, S03 实现时发现字段不够用 | S03 builder 提"我需要加个 retry_count 字段" | schemas.md 留 `extension_fields[]` 数组, 允许 S03 加 namespaced 字段 (e.g. `_solar_internal.*`) 不破坏契约 |
| R2 | SQLite/JSONL 边界划得太死, 后续无法演化 | 实际数据量 100x 后想把 evidence 从 JSONL 挪到 SQLite | storage.md 加 "迁移路径" 节, 每个字段标"可迁移目标存储" |
| R3 | DAG 模板 graph_scheduler validate 失败 | `validate` 报 write_scope 冲突 | N4 builder 在写 dag-template.json 时同步跑 validate, 失败就改, 不交付未通过 validate 的版本 |
| R4 | 字段命名跨 4 份产物漂移 | builder A 写 schemas.md 用 `span_text`, builder B 写 storage.md 用 `text_span` | N5 集成节点强制 grep diff 4 份产物字段名, 漂移则 fail; evaluator 复跑 |
| R5 | "Schema 是法律" 被监护人感知为过度工程 | 监护人觉得"这就是写 markdown 嘛, 1 小时该搞完" | PRD User Stories US6 + Non-Goals 已显式约束 1 天 closeout, 不变成 8 模型实现 marathon |
| R6 | 复用现有基础设施承诺空头 | architecture.md 写"复用 evaluator", 但实际 evaluator API 不能消费 evidence_id | N1 architecture.md 在每个复用点附 "API 字段映射" 表, 强制对齐现有 API |
| R7 | 0 代码红线被建设者违反 | builder 写了 schemas.py 而不是 schemas.md | contract Stop Rule + evaluator 用 find 命令校验; 违反触发 ATLAS structured repair |
| R8 | 节点 R0-R11 命名跟 S04 PRD 假设不一致 | S04 PRD 写 `R0_scope_rewrite`, S02 改成 `R0_rewrite_scope` | S02 dag-template.json 引用 epic.md 的 12 节点命名作为单一来源, 不能改名 |

## 10. Open Questions / 开放问题 (给 Planner / 架构师)

1. **evidence_id 哈希算法**: `sha256(span_text + source_doc_ref + page)` 还是 `sha256(span_text + source_url)` 还是 `sha256(span_text + canonical_doc_id)` ? — 影响跨 source 同一引语的去重粒度。
2. **span_text 字段名最终拍**: `span_text / text_span / quote / quoted_text`? 4 候选选哪个? 建议 `span_text` (跟 epic.md `span_text` 一致)。
3. **claim 与 evidence 的多对多关系**: `ClaimEvidenceLink` 表的 `support_kind` 枚举值列表? (supports / contradicts / partial / methodology_match / sample_size_match...)
4. **SQLite 唯一约束**: `evidence_items` 的 unique 是 (id) 还是 (hash) 还是 (source_doc_ref, span_text, page)?
5. **JSONL append-only 限制**: 是否允许 mutating update (e.g. evidence verified 后更新 verified=true)? 建议 append-only + 用 last-write-wins, 但需要架构师确认。
6. **DAG 模板节点 ID 命名规则**: `R{0..11}_{snake_case}` 还是允许 `R0a` / `R3.1` 子节点? 影响 graph_scheduler validate 严格度。
7. **section 级 write_scope 切分**: `sections/ch{NN}/sec{NN}.*` 还是 `sections/{chapter_id}/{section_id}.*`? 影响 S04 模板展开命令的复杂度。
8. **ReportAST 8 节点字段**: 是否需要 `FigureBlock.image_blob_ref` 字段 (指向 Mirage VFS 中的图)? S03 reportast 实现时要不要内嵌 base64?
9. **接口契约的版本号**: schemas.md 是否标 `schema_version: deepresearch.schemas.v1`? 影响后续向后兼容判定。
10. **freshness_score 计算**: 是 `evidence.fetched_at - now()` 单一维度, 还是要考虑 `source.published_at`? 影响 EvidenceItem 字段 + Factuality evaluator 算法 (S05 范围)。

## 11. 架构交接 / Planner Handoff

Planner 把本切片拆成 **5 个 builder slice (N1-N5)**, N1-N4 完全并行, N5 集成 (跟现有 design.md 完全一致):

1. **N1 — `deepresearch.architecture.md`** (FR-1 + FR-5)
   - 模块分层 / CLI 边界 / capability plane 接入 / DAG/evaluator/Mirage 复用策略 / 失败恢复 + 观测
   - 出口: grep `module=`/`api=`/`recovery=`/`observe=` 四类标签各 ≥3 条
   - write_scope: 仅 `<sid>.deepresearch.architecture.md`

2. **N2 — `deepresearch.schemas.md`** (FR-2)
   - 8 个数据模型字段 + 类型 + 不变量 + ID/hash 算法 + 兼容策略
   - 出口: grep 模型名 8 次, 字段表行数 ≥ 字段数, evidence_id/claim_id 哈希算法显式写出
   - write_scope: 仅 `<sid>.deepresearch.schemas.md`

3. **N3 — `deepresearch.storage.md`** (FR-3)
   - SQLite 7 表 DDL + JSONL 布局 + 索引 + hash/span verify + 向后兼容
   - 出口: `CREATE TABLE` 7 次, 字段归属表完整, 0 双写字段
   - write_scope: 仅 `<sid>.deepresearch.storage.md`

4. **N4 — `deepresearch.dag-template.json`** (FR-4)
   - R0-R11 12 节点完整 task_graph (依赖 / write_scope / 角色)
   - 出口: `graph_scheduler validate` exit 0 + R0-R11 12 节点 + write_scope 0 冲突
   - write_scope: 仅 `<sid>.deepresearch.dag-template.json`

5. **N5 — 集成 + handoff** (FR-6)
   - 校验 4 份产物字段命名 0 漂移 (grep diff `evidence_id / claim_id / span_text / source_doc_ref`)
   - 产出 handoff.md 含给 S03/S04 接口表 + 已知 risk
   - 出口: handoff.md grep `给 S03 的接口` / `给 S04 的接口` 各 1 次, 接口字段表 ≥10 条
   - write_scope: `<sid>.handoff.md` + read-only 4 份 N1-N4 产物
   - 依赖: N1 ∧ N2 ∧ N3 ∧ N4 全 passed

**并行性**: N1/N2/N3/N4 write_scope 互不重叠, 可由 4 个 builder pane 并发派工; N5 是 join gate。

**评审颗粒度**: 每个 N 必须独立 evaluator review, 不允许 contract-patrol 直接标 passed (吸取 sprint-20260513-tool-plane-sandbox followup F4 教训)。

**跨切片共用约束**:
- 4 份产物字段命名必须 0 漂移, N5 集成时强制 grep 校验, 漂移则全部回炉
- DAG 模板必须真的过 `graph_scheduler validate`, 不接受"我看着对了"
- 0 代码红线: 任何 .py/.sh 出现立即触发 ATLAS repair

---

## 附录 A — Epic 上下文 (参考材料, 不在本切片实现范围)

> 以下内容来自 `epic-20260513-solar-deepresearch-product-line.epic.md`, 仅作为背景参考。S02 不实现这些内容; 它们是 S03/S04/S05 的范围。

### A.1 DeepResearch 核心缺口 (S02 只设计 schema, 不实现)

- **Source Mesh**: Web/Academic/Preprint/DOI/Patent/Code Repo/Standards/Dataset/Company/Internal connector
- **Evidence Ledger**: `EvidenceItem / Claim / ClaimEvidenceLink / CitationSpan / Contradiction / EvidencePack` 一等公民
- **ReportAST**: `Report / Chapter / Section / Subsection / ClaimBlock / EvidenceBlock / FigureBlock / TableBlock / Bibliography`
- **Factuality Evaluator**: 7 指标 (unsupported_claim_rate / citation_span_accuracy / source_authority_score / freshness_score / contradiction_coverage / section_repetition_rate / cross_section_consistency)
- **Source Intent Classifier**: 判断需求需要哪类源

### A.2 DAG 模板节点清单 (epic-level, S02 写成 JSON)

`R0_scope_rewrite / R1_source_matrix / R2_external_search / R3_fetch_extract / R4_claim_mining / R5_contradiction_hunt / R6_report_ast / R7_section_writing_batch / R8_section_fact_check / R9_chapter_compile / R10_global_consistency / R11_final_export`

S02 范围: 把 12 节点写进 `deepresearch.dag-template.json`, 让 graph_scheduler validate 过。不实现每个节点的具体逻辑 (那是 S03)。

### A.3 SQLite MVP 表 (epic-level, S02 写完整 DDL)

`research_runs / research_sources / evidence_items / claims / claim_evidence / report_sections / section_checks`

S02 范围: 给完整 DDL + 索引策略 + 字段归属表 (SQLite / JSONL / both)。

### A.4 Epic Stop Rules (继承)

- 不允许把 DeepResearch 做成单 prompt
- 不允许没有 evidence span 的 claim 进入 final report
- 不允许 parent sprint 在 evidence/claims/fact-check gates 未过前 passed
- 不允许 Source Mesh connector 失败时静默降级为模型自说自话
- 不允许十万字报告写入单个 builder 节点

---

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-intent, harness-skills, harness-graph
