# Design — DeepResearch Professor-Grade Survey Quality Hardening · S03 Core-Runtime

Sprint: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s03-core-runtime`
Epic: `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build`
Slice: `core-runtime` (Planner pass — design for builder implementations)
Author: Solar Planner
Date: 2026-05-17
Knowledge Context: solar-harness context inject used（命中 S01 outcomes/boundary/handoff + S02 5 arch spec + quality-gap-lockdown + handoff）

## 1. Problem Framing

S01 锁了 5 outcome 边界，S02 锁了 5 schema + 4 gate registration interface + e2e artifact layout + 6 QG lockdown + 6 builder boundary items。S03 必须**实现**：

| S02 锁定 | S03 实现单元 |
|---------|------------|
| `SourceQualityDistribution` schema | `survey/schemas.py` 扩展 + `survey/gates/source_quality_distribution.py` |
| `ArgumentDensityProfile` schema | `survey/schemas.py` 扩展 + `survey/gates/argument_density.py` (5 维度检测) |
| `ContradictionMatrix` + `ClaimEvidenceLink` | `survey/schemas.py` 扩展 + `survey/gates/controversy_matrix.py` (含 decorative 检测) |
| `EliminationRecord` + `exploration_run()` | `survey/explorer/` 新包（exploration_run + score_direction + log_writer）|
| `GateReport` aggregation | `survey/gates/compile_gate_report.py` + survey-continue runner 集成 |
| 4 gate plugin registration | `survey/gates/__init__.py` + `gates/_registry.py` decorator |
| QG-3/QG-5 global consistency | `survey/gates/global_consistency_pass.py`（跨章节 claim_id + 术语漂移）|

实现必须：纯函数（gate / 计分 / 矩阵构建）+ 单测覆盖（floor ≥ 60 assertions across nodes）+ 不改 frozen 5 module + 不改 6 frozen file + 引入 plugin 注册不改 `survey/__init__.py` 已有导出。

## 2. Slice Boundaries

- **做**：实现 5 个 schema 扩展 + 4 个 gate 纯函数 + 1 个 explorer 包 + 1 个 aggregator + plugin registry + global consistency pass + 单测（核心场景 + 边界 + 失败路径）
- **不做**：survey-eval / survey-review / survey-compile CLI 输出渲染（S04）；e2e runtime 真跑（S05）；阈值数值最终调（S05 fixture 验证后定）；ReportAST schema 改动；frozen module 改动
- **不允许**：mock 数据库 / mock LLM（gate 都是 deterministic 纯函数，无外部依赖）；动 frozen 接口；声称 S04/S05 已就绪；忽略 6 builder boundary（必须用 planner-locked constants）

## 3. Planner-Locked Non-Builder Decisions (S03 builder 必须用这些常量)

S02 handoff §4 列出 6 个 builder 不能自决的项，本 design 在此**逐条锁定 default 值**，builder 必须以 constants 形式实现到 `gates/config_defaults.py`：

| Decision | Planner-Locked Default | Rationale |
|---------|----------------------|-----------|
| SourceTaxonomy 词典 | `["paper", "code", "official", "benchmark", "web", "blog", "wiki"]`；前 4 计入 high-authority 池，后 3 不入 | 与 S02 source-quality-arch §4 一致；后续可由 config override |
| 5 维度 detector | `mechanism_comparison`: 关键词集 `["versus", "对比", "compare", "vs."]` + 句式（"X 优于 Y" 模式）；`method_taxonomy`: 关键词 `["category", "taxonomy", "类型", "分类"]` + 段落含 `>= 2` 子类型枚举；`evaluation_protocol`: 关键词 `["benchmark", "evaluation", "metric", "评测"]`；`failure_negative_evidence`: 关键词 `["fail", "negative", "反例", "limitation"]`；`engineering_implication`: 关键词 `["implication", "deploy", "production", "engineering"]` | 默认 detector 必须 deterministic，不调 LLM；S04/S05 可调整词典但 S03 不引入运行时配置 |
| Claim 粒度 | dual indexing：`claim_id = "{chapter_id}.{section_id}.{seq}"`；chapter-level claim 单独标记 `chapter.{id}.summary`| 满足 S02 contradiction-matrix-arch §3 ClaimEvidenceLink schema 要求 |
| Direction scoring weights | uniform baseline `{"source_coverage": 1.0, "novelty": 1.0, "feasibility": 1.0, "evidence_density": 1.0}`；4 维度同权 | S03 不引入策略偏好；S04/S05 可通过 config override |
| Direction initial selection protocol | `llm_propose_n_3`: 起始 3 个候选方向（由 SurveyQuestion 经 explorer.propose_directions 产出，使用现有 survey/planner.py 的 candidate-generation 接口 + 去重） | 与 S02 exploration-arch §9 一致 |
| E2E test sample | defer to S05；S03 单测使用 hand-crafted fixture（每 gate 3-5 fixture cases）| E2E 真样本由 S05 prepare/strict-test 节点选 |

这些 default 值由 builder 写入 `survey/gates/config_defaults.py` + `survey/explorer/config_defaults.py`，构成"S03 行为基线"。

## 4. Non-Goals

- 不实现 survey-eval / survey-review / survey-compile CLI 输出渲染（S04 责任）
- 不跑 e2e survey-continue runtime（S05 责任）
- 不调阈值数值（gate 输出 raw metric + verdict 留 S05 fixture-driven 调阈）
- 不动 frozen 5 module（source_authority / literature_mapping / controversy / chapter_review / chief_editor）
- 不动 frozen 6 file（coordinator.sh / autopilot.sh / dispatcher.sh / phase-state-machine.sh / solar-harness.sh / survey/__init__.py 已有导出）
- 不引入新的外部依赖（如 spacy / sentence-transformers）；用现有 stdlib + 已存 deps

## 5. Architecture Layout (Files Built by S03)

```text
harness/lib/research/survey/
├── schemas.py                         [N1: APPEND 5 dataclass]
├── gates/
│   ├── __init__.py                    [N2: NEW; plugin registry + 4 gate slot]
│   ├── _registry.py                   [N2: NEW; @register_gate decorator + GateRegistry]
│   ├── config_defaults.py             [N2: NEW; planner-locked constants §3]
│   ├── source_quality_distribution.py [N3: NEW; build_source_quality_distribution + StuffingAlert]
│   ├── argument_density.py            [N4: NEW; measure_argument_density + 5 dim detectors]
│   ├── controversy_matrix.py          [N5: NEW; build_contradiction_matrix + decorative detector]
│   ├── compile_gate_report.py         [N7: NEW; aggregator + GateReport assembler]
│   └── global_consistency_pass.py     [N7: NEW; QG-3 claim_id reuse + QG-5 terminology drift]
├── explorer/                          [N6: NEW package]
│   ├── __init__.py                    [N6]
│   ├── config_defaults.py             [N6]
│   ├── exploration_run.py             [N6; main entry exploration_run()]
│   ├── score_direction.py             [N6; pure scoring fn]
│   └── log_writer.py                  [N6; JSONL incremental writer]
└── runner_hook.py                     [N7: NEW; survey-continue wiring hook (callable from existing runner)]

tests/research/survey/gates/
├── test_source_quality_distribution.py [N3]
├── test_argument_density.py            [N4]
├── test_controversy_matrix.py          [N5]
├── test_compile_gate_report.py         [N7]
└── test_global_consistency_pass.py     [N7]

tests/research/survey/explorer/
├── test_exploration_run.py             [N6]
├── test_score_direction.py             [N6]
└── test_log_writer.py                  [N6]

tests/research/survey/
└── test_schemas.py                     [N1; dataclass + to_dict round-trip]
```

每个新文件需在 module docstring 顶部声明 source spec（如 `# S03 N3 implementation per S02 source-quality-arch.md`）。

## 6. DAG Topology

```text
Layer 1 (foundation):    N1 schemas ∥ N2 gates_registry
                                       │
Layer 2 (gates + explorer): N3 source_quality ∥ N4 argument_density ∥ N5 controversy_matrix ∥ N6 explorer
                                       │
Layer 3 (aggregator):    N7 compile_gate_report + global_consistency_pass + runner_hook
                                       │
Layer 4 (join):          N8 handoff + parent traceability patch (children[2].core_runtime_ready=true)
```

8 节点 4 层；L2 4-way parallel；schema 单源（N1）防冲突。

## 7. Deliverables

| # | Deliverable | Owner Node | 核心内容 |
|---|-------------|-----------|---------|
| D1 | schemas.py 扩展 + test_schemas.py | N1 | `SourceQualityDistribution` / `ArgumentDensityProfile` / `ContradictionMatrix` / `ClaimEvidenceLink` / `EliminationRecord` / `ExplorationDirection` / `ExplorationRunResult` / `GateReport` 8 个 dataclass + `to_dict` 兼容 + ≥ 8 个 round-trip 测试 |
| D2 | gates/__init__.py + _registry.py + config_defaults.py | N2 | `@register_gate(name)` decorator + `GateRegistry.get(name)` + 4 个 placeholder 注册槽 + planner-locked constants §3（SourceTaxonomy / 5 dim detectors / Claim 粒度 / scoring weights / direction protocol）+ ≥ 6 registry 测试 |
| D3 | source_quality_distribution.py + 测试 | N3 | `build_source_quality_distribution(evidence_pack: EvidencePack) -> SourceQualityDistribution` 纯函数 + `detect_stuffing_alerts(evidence_pack) -> list[StuffingAlert]` + 注册为 `@register_gate("source_quality")` + ≥ 10 个测试（高/低 distribution / stuffing / 边界 / 类型缺失）|
| D4 | argument_density.py + 测试 | N4 | `measure_argument_density(section: SectionReview) -> ArgumentDensityProfile` + `map_dimension_applicability(section_spec, profile)` + 5 个独立 detector 函数 + 注册为 `@register_gate("argument_density")` + ≥ 12 测试（每维度 ≥ 2 + 边界）|
| D5 | controversy_matrix.py + 测试 | N5 | `build_contradiction_matrix(evidence_pack, claim_evidence_rows) -> ContradictionMatrix` + `check_synthesis_references(report_ast, matrix) -> list[MissingRef]` + `detect_decorative_matrix(matrix) -> bool` + 注册为 `@register_gate("controversy")` + ≥ 10 测试 |
| D6 | explorer/ 包 + 测试 | N6 | `exploration_run(question: SurveyQuestion, candidates: list[ExplorationDirection]) -> ExplorationRunResult` + `score_direction(direction, sources) -> float` (uniform weights §3) + `LogWriter.append(record)` JSONL incremental + ≥ 12 测试（含 3 方向消除 1 弱方向 e2e fixture）|
| D7 | compile_gate_report.py + global_consistency_pass.py + runner_hook.py + 测试 | N7 | `compile_gate_report(evidence_pack, sections, claim_rows) -> GateReport` 调 4 gate plugin + `global_consistency_pass(report_ast) -> ConsistencyReport`（QG-3 claim_id reuse + QG-5 terminology drift）+ `runner_hook.attach_to_survey_continue(runner)` 无侵入式 hook + ≥ 10 测试 |
| D8 | handoff.md + parent traceability patch | N8 (join) | 实现完成清单 + S04/S05 切入 + s04_can_start: true + s05_blocked_until: [s04_passed]（注意 S04 也依赖 S03，二者均完成才能 S05）+ `children[2].core_runtime_ready=true` 单字段 patch |

## 8. Acceptance Contract (Sprint-level)

| # | Acceptance | 验证 |
|---|------------|------|
| A1 | 8 个 dataclass 全部新增到 `schemas.py` + `to_dict` 兼容 + round-trip 测试通过 | pytest + grep |
| A2 | gates/ 注册表能 `GateRegistry.get(name)` 4 个名字（source_quality / argument_density / controversy / aggregator）取到对应函数 | pytest |
| A3 | 4 gate 纯函数被独立 import 时不触发外部 IO / 网络 / LLM 调用 | grep `requests\|urllib\|httpx\|openai\|anthropic\|fetch_url` == 0 |
| A4 | 5 维度 detector 全部 deterministic（同输入同输出，无 random / 无 datetime.now / 无 time.time）| grep `random\.\|datetime\.now\|time\.time` == 0 in detectors |
| A5 | explorer 单测含 3 方向 fixture（其中 1 个会被消除）+ elimination_log.jsonl 含 kill_reason 段落 | pytest + jq |
| A6 | compile_gate_report 集成测试：fixture 输入 → 4 gate 全部触发 → GateReport 4 verdict 字段齐 | pytest |
| A7 | global_consistency_pass 检测 claim_id 漂移与术语漂移各 ≥ 2 fixture 测试 | pytest |
| A8 | 单测总数（pytest collect）≥ 60；全部 pass | pytest -q --collect-only \| wc + pytest |
| A9 | frozen 5 module 未被修改 | git diff source_authority.py literature_mapping.py controversy.py chapter_review.py chief_editor.py == empty |
| A10 | 6 frozen file 未被修改 | git diff coordinator.sh autopilot.sh dispatcher.sh phase-state-machine.sh solar-harness.sh survey/__init__.py == empty |
| A11 | 父 `epic-…traceability.json` 仅 `children[2].core_runtime_ready=true` 被 patch；schema_version + children 顺序 + 长度不变 | jq |
| A12 | handoff.md 不声称 "epic 完成" / "S04-S05 已就绪" / "e2e 已验证" | grep == 0 |
| A13 | gates / explorer 文件全部 docstring 顶部声明 source spec 引用 | grep `S02|s02-architecture` ≥ 7 (one per source file) |
| A14 | runner_hook 是 attach 式调用（不修改现有 runner 文件源；只暴露 hook 函数）| grep + diff |
| A15 | 所有 gate / explorer 内部使用 `config_defaults` 常量（不硬编码 inline 阈值/词典）| grep `from .config_defaults import` / `from .config_defaults import` 出现次数 ≥ 4 |

## 9. Stop Rules

- 任何节点修改 frozen 5 module 任一文件 → fail
- 任何节点修改 6 frozen file 任一 → fail
- 节点内任意 .py 含 `import requests` / `urllib` / `httpx` / `openai` / `anthropic` → fail（gate 必须纯函数）
- 节点内任意 detector 含 `random.` / `datetime.now()` / `time.time()` → fail（必须 deterministic）
- 节点内使用 `@mock.patch` / `MagicMock` → fail（gate 纯函数，无需 mock）
- 单测 floor 不达标（A8：60 assertions）→ fail
- N8 之前父 traceability 被改 → graph_scheduler 阻断
- 任何节点声称 "S04+ 已就绪" / "e2e 验证完成" → fail
- N3-N6 任一硬编码 inline 阈值数值（应来自 config_defaults）→ fail
- N7 runner_hook 修改 `solar-harness` 主二进制或 `survey-continue` 入口源 → fail

## 10. Parallelism & Write Scope

- **N1**: `harness/lib/research/survey/schemas.py` (APPEND), `tests/research/survey/test_schemas.py`
- **N2**: `harness/lib/research/survey/gates/__init__.py`, `gates/_registry.py`, `gates/config_defaults.py`, `tests/research/survey/gates/test_registry.py`
- **N3**: `harness/lib/research/survey/gates/source_quality_distribution.py`, `tests/research/survey/gates/test_source_quality_distribution.py`
- **N4**: `harness/lib/research/survey/gates/argument_density.py`, `tests/research/survey/gates/test_argument_density.py`
- **N5**: `harness/lib/research/survey/gates/controversy_matrix.py`, `tests/research/survey/gates/test_controversy_matrix.py`
- **N6**: `harness/lib/research/survey/explorer/__init__.py`, `explorer/config_defaults.py`, `explorer/exploration_run.py`, `explorer/score_direction.py`, `explorer/log_writer.py`, `tests/research/survey/explorer/test_exploration_run.py`, `test_score_direction.py`, `test_log_writer.py`
- **N7**: `harness/lib/research/survey/gates/compile_gate_report.py`, `gates/global_consistency_pass.py`, `harness/lib/research/survey/runner_hook.py`, `tests/research/survey/gates/test_compile_gate_report.py`, `test_global_consistency_pass.py`, `tests/research/survey/test_runner_hook.py`
- **N8**: `sprints/…s03-core-runtime.handoff.md`, `sprints/epic-…traceability.json` (`children[2].core_runtime_ready` only)

write_scope 完全互斥；schema 单源（N1）；plugin registry 单源（N2）。

## 11. Model Routing

- 所有节点 `preferred_model=sonnet`（Python 纯函数 + dataclass + pytest；GLM 1210 风险持续）
- 禁止 builder webfetch / web search
- 上游证据源（必须 read_scope）：S01 handoff / S02 5 arch spec / S02 quality-gap-lockdown / S02 handoff / 现有 `survey/schemas.py` / 现有 `survey/evidence_pack.py` / 现有 `survey/evaluator.py`

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| N1 schemas.py 改动破坏现有 dataclass | A1 强制 round-trip 测试 + N1 只 APPEND 不改既有定义；evaluator 检查 `git diff schemas.py` 只有 + 行 |
| 4 gate plugin 注册冲突（同时写 __init__.py）| N2 owns the only write to `gates/__init__.py`；N3-N5 不写 __init__.py 只写各自 gate 文件 + decorator 用法 |
| detector 不 deterministic 导致测试 flaky | A4 stop rule + grep ban `random / datetime.now / time.time`；fixture 用 frozen text |
| explorer 网络依赖（handoff-search CLI）| N6 实现把 handoff-search 视作 pure data source（test 用 fixture jsonl）；不在 gate 主路径 spawn 子进程 |
| compile_gate_report 调 4 gate 时部分缺失/异常 | A6 集成测试覆盖部分 gate 缺失场景；GateReport.partial_verdicts 字段表达降级 |
| 单测数量不足 | A8 floor 60；每 gate plan §6 列具体 case 数（10/12/10/12/10）总 = 54；schemas 8 + registry 6 = 14；总 ≈ 68 |
| runner_hook 侵入 survey-continue 主链 | A14 强制 attach 式；test 验证 hook 是 attach (`runner.add_hook(...)`) 而非 `if survey_continue: ...` inline |
| Builder inline 硬编码而不用 config_defaults | A15 grep `from .config_defaults import` ≥ 4 |

## 13. Knowledge Context Usage

- `solar-harness context inject` 已执行
- S01 handoff + outcomes + boundary（mirage 命中）
- S02 5 arch spec + quality-gap-lockdown + handoff（builder 必须 read_scope）
- 现有 `survey/schemas.py` 12 个 frozen dataclass（不动；只 APPEND 新 dataclass）
- 现有 `survey/evidence_pack.py` `build_evidence_packs()`（consumed in N3/N5 入口）

## 14. Handoff Plan (N8)

N8 必须含：

- 实现完成清单（8 dataclass / 4 gate / 1 explorer 包 / 1 aggregator / 1 global pass / 1 runner_hook + 测试统计）
- S04 切入清单（每 gate 一行：CLI 输出该 gate 哪个字段 + UI 警告条件）
- S05 切入清单（e2e fixture 怎么准备 + 期望验收 metric / verdict 链）
- 已知未闭环项（阈值数值最终调 / 词典扩充 / E2E 真样本选择留 S05）
- 测试统计（assertion 总数 + pass/fail）
- 不动 frozen 接口声明（重申 S01/S02 governance）
- `s04_can_start: true` + `s05_blocked_until: [s04_passed]`
- 不声称 epic 已完成 / S04/S05 已就绪 / e2e 已验证
