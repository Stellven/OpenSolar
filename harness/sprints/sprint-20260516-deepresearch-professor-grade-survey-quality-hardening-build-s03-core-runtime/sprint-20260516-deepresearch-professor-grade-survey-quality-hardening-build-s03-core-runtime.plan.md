# Plan — DeepResearch Professor-Grade Survey Quality Hardening · S03 Core-Runtime

Sprint: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s03-core-runtime`
Epic: `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build`
Slice: `core-runtime`
Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-graph, harness-contracts, harness-skills

## 1. DAG (8 nodes, 4 layers)

```text
L1: N1 schemas ∥ N2 gates_registry
                  │
L2: N3 source_quality ∥ N4 argument_density ∥ N5 controversy_matrix ∥ N6 explorer
                  │
L3: N7 compile_gate_report + global_consistency_pass + runner_hook
                  │
L4: N8 handoff + parent traceability patch
```

Layers: `[[N1, N2], [N3, N4, N5, N6], [N7], [N8]]`

## 2. Node-by-Node Execution

| Node | Goal | Owns | Depends | Gate |
|------|------|------|---------|------|
| N1 | APPEND 8 dataclass 到 schemas.py + to_dict round-trip | `survey/schemas.py` (APPEND), `tests/research/survey/test_schemas.py` | — | G1 |
| N2 | 建 gates/ 包：__init__.py + _registry.py（@register_gate decorator + GateRegistry）+ config_defaults.py（planner-locked constants）+ registry 测试 | `gates/__init__.py`, `gates/_registry.py`, `gates/config_defaults.py`, `tests/.../test_registry.py` | — | G2 |
| N3 | 实现 source_quality_distribution（含 StuffingAlert detector）+ 注册 + 测试 | `gates/source_quality_distribution.py` + test | N1, N2 | G3 |
| N4 | 实现 argument_density（5 维度 detector + applicability mapping）+ 注册 + 测试 | `gates/argument_density.py` + test | N1, N2 | G4 |
| N5 | 实现 controversy_matrix（含 decorative detection + synthesis ref check）+ 注册 + 测试 | `gates/controversy_matrix.py` + test | N1, N2 | G5 |
| N6 | 建 explorer/ 包：exploration_run + score_direction + log_writer + config_defaults + 测试 | `explorer/__init__.py`, `explorer/config_defaults.py`, `explorer/exploration_run.py`, `explorer/score_direction.py`, `explorer/log_writer.py` + tests | N1 | G6 |
| N7 | compile_gate_report aggregator + global_consistency_pass (QG-3/QG-5) + runner_hook attach + 测试 | `gates/compile_gate_report.py`, `gates/global_consistency_pass.py`, `runner_hook.py` + tests | N3, N4, N5, N6 | G7 |
| N8 | handoff.md + parent traceability patch (children[2].core_runtime_ready=true) | `sprints/…s03.handoff.md`, `epic-…traceability.json` | N7 | G8 |

## 3. Parallelism & Layer Ready

- L1 N1∥N2：两个独立 foundation，写不同文件
- L2 N3∥N4∥N5∥N6：4-way parallel；schema 单源 N1，registry 单源 N2，避免文件冲突
- L3 N7：单 builder pane，aggregator 需读取 N3-N6 出口
- L4 N8：单 builder pane，join

如 builder pane 资源 ≥ 4，L2 可一次性 4-way 派发；否则按 batch 拆。

## 4. Dispatch Batches

| Batch | Nodes | Trigger |
|-------|-------|---------|
| B1 | N1, N2 | status=active 后派发（S02 已 passed 满足 blocks_until） |
| B2 | N3, N4 | N1.G1.passed AND N2.G2.passed |
| B3 | N5, N6 | N1.G1.passed AND N2.G2.passed AND（B2 至少 1 个 dispatched，避免 pane 抢资源）|
| B4 | N7 | N3..N6 全部 passed |
| B5 | N8 | N7 passed |

scheduler `layers ready` 命令会自动报告每层 ready 节点；如 pane 充裕，B2+B3 可合并。

## 5. Per-Node Acceptance

### N1 schemas extension
- APPEND 8 dataclass：`SourceQualityDistribution`, `StuffingAlert`, `ArgumentDensityProfile`, `ContradictionMatrix`, `ClaimEvidenceLink`, `EliminationRecord`, `ExplorationDirection`, `ExplorationRunResult`, `GateReport`（含 nested `GateVerdict`）—— 实际计数 ≥ 8 顶层 dataclass
- 每 dataclass 字段名与 S02 arch spec 表格一致（不重命名）
- `to_dict(dc)` 兼容所有新 dataclass（用现有 `to_dict` helper）
- 测试 ≥ 8：每 dataclass 1 个 round-trip + 边界（空字段 / 嵌套）
- 不改既有 12 个 dataclass（git diff 显示 schemas.py 只有 + 行，无 - 行）

### N2 gates registry
- `gates/__init__.py` 导出 `GateRegistry, register_gate`
- `gates/_registry.py`：`@register_gate(name)` decorator + `GateRegistry.get(name) / .list() / .clear()`
- `gates/config_defaults.py` 含 planner-locked constants（design.md §3 全部）
- 4 placeholder slot 名称：`source_quality / argument_density / controversy / aggregator`
- 测试 ≥ 6：register / get / list / overwrite 防止 / clear / 不存在 name 取出抛错

### N3 source_quality_distribution
- `build_source_quality_distribution(evidence_pack: EvidencePack) -> SourceQualityDistribution`
- `detect_stuffing_alerts(evidence_pack) -> list[StuffingAlert]`
- `@register_gate("source_quality")` 装饰
- 使用 `config_defaults.SOURCE_TAXONOMY`（不硬编码）
- 测试 ≥ 10：高 canonical / 低 canonical / paper-only / web-stuffing / 类型缺失 / 边界 0 source / mixed / typed taxonomy / stuffing pattern 1 / stuffing pattern 2

### N4 argument_density
- `measure_argument_density(section: SectionReview) -> ArgumentDensityProfile`
- `map_dimension_applicability(section_spec: SectionSpec, profile: ArgumentDensityProfile)`
- 5 个独立 detector：`detect_mechanism_comparison / detect_method_taxonomy / detect_evaluation_protocol / detect_failure_negative_evidence / detect_engineering_implication`
- 使用 `config_defaults.DIMENSION_DETECTORS`（不内联词典）
- `@register_gate("argument_density")` 装饰
- 测试 ≥ 12：每维度 2（present / absent）+ applicability case ≥ 2

### N5 controversy_matrix
- `build_contradiction_matrix(evidence_pack, claim_evidence_rows) -> ContradictionMatrix`
- `check_synthesis_references(report_ast, matrix) -> list[MissingRef]`
- `detect_decorative_matrix(matrix) -> bool`（判断 matrix 是否仅出现在 appendix 而 chapter synthesis 未引用 matrix 行）
- 使用 `config_defaults.CLAIM_GRANULARITY`（dual indexing）
- `@register_gate("controversy")` 装饰
- 测试 ≥ 10：正常 matrix / 装饰性 matrix / 无 claim_id / synthesis miss / 完整 ref / 边界

### N6 explorer
- 新建 `survey/explorer/` 包；`__init__.py` 导出 `exploration_run, score_direction`
- `exploration_run(question, candidates) -> ExplorationRunResult`：调 score_direction + write log + return result
- `score_direction(direction, sources) -> float`：使用 `config_defaults.DIRECTION_SCORE_WEIGHTS`（uniform）
- `log_writer.LogWriter(path).append(record: EliminationRecord)`：JSONL incremental
- `explorer/config_defaults.py`：DIRECTION_SCORE_WEIGHTS + DIRECTION_INITIAL_PROTOCOL + ELIMINATION_THRESHOLD（留 None 由 S05 定）
- 测试 ≥ 12：3 方向 fixture（含 1 被消除）+ score deterministic + log writer atomic + 重启 resume + 边界 0 候选 + 边界 1 候选 + kill_reason 必含

### N7 aggregator + global pass + runner_hook
- `compile_gate_report(evidence_pack, sections, claim_rows, report_ast) -> GateReport`：调 4 gate plugin + assemble + partial_verdicts 段
- `global_consistency_pass(report_ast) -> ConsistencyReport`：QG-3 claim_id reuse + QG-5 terminology drift
- `runner_hook.attach_to_survey_continue(runner)`：attach 式 hook（不改 runner 源）
- 测试 ≥ 10：4 gate 全到 / 1 gate missing / claim_id 漂移 / 术语漂移 / hook attach idempotent / hook 不动 runner state / aggregator partial

### N8 handoff + parent patch
- handoff.md 含：实现完成清单（D1-D7 各一行 + 测试数）+ S04 切入清单（5 gate × CLI 输出字段）+ S05 切入清单（e2e fixture 准备 + verdict 链）+ 已知未闭环项（阈值/词典/真样本）+ 测试统计 + `s04_can_start: true` + `s05_blocked_until: [s04_passed]`
- handoff.md 不声称 epic 完成 / S04/S05 已就绪 / e2e 已验证
- 父 traceability 仅 `children[2].core_runtime_ready=true` patch；schema_version + 顺序 + 长度不变

## 6. Routing Policy

- 所有节点 `preferred_model=sonnet`（Python 实现 + pytest；GLM 1210 风险）
- 禁止 builder webfetch / web search / 安装新 deps（pyproject 不变）
- 上游证据源（read_scope）：S01 三件套 + S02 5 arch spec + S02 lockdown + S02 handoff + 现有 `survey/schemas.py / evidence_pack.py / evaluator.py / chapter_review.py / planner.py`

## 7. Stop Rules

- 修改 frozen 5 module（source_authority / literature_mapping / controversy / chapter_review / chief_editor）→ fail
- 修改 6 frozen file（coordinator/autopilot/dispatcher/phase-state-machine/solar-harness/survey/__init__.py）→ fail
- detector / gate 含 `requests/urllib/httpx/openai/anthropic` → fail（纯函数禁外部 IO）
- detector 含 `random./datetime.now()/time.time()` → fail（必须 deterministic）
- 任何测试用 `@mock.patch` / `MagicMock` → fail
- 单测总数 < 60 → fail
- 节点硬编码 inline 阈值/词典（应来自 config_defaults）→ fail
- N7 runner_hook 修改 survey-continue / solar-harness 主入口源 → fail
- handoff 声称 "S04+ 已就绪" / "e2e 完成" → fail

## 8. Exit Criteria (Sprint passed)

- N1-N8 8 节点 evaluator verdict 全部 PASS
- D1-D8 8 deliverable 齐备
- 单测总数 ≥ 60 且全部 pass（`pytest -q tests/research/survey/`）
- frozen 5 module + 6 file `git diff` 为空
- 父 `epic-…traceability.json` `children[2].core_runtime_ready=true`（结构未变）
- A1-A15 acceptance 全过

## 9. Evaluator Entry Points

- 看 design.md §8 Acceptance Contract（15 条）
- pytest 全跑：`pytest -q tests/research/survey/ --collect-only` 计数 ≥ 60；`pytest -q tests/research/survey/` 全 pass
- frozen 检查：`git diff source_authority.py literature_mapping.py controversy.py chapter_review.py chief_editor.py` 为空；`git diff coordinator.sh autopilot.sh dispatcher.sh phase-state-machine.sh solar-harness.sh harness/lib/research/survey/__init__.py` 为空
- 纯函数检查：`grep -rE 'import (requests|urllib|httpx|openai|anthropic)' harness/lib/research/survey/gates/ harness/lib/research/survey/explorer/` == 0
- Deterministic 检查：`grep -rE 'random\.|datetime\.now|time\.time' harness/lib/research/survey/gates/ harness/lib/research/survey/explorer/` == 0
- Mock 检查：`grep -rE '@mock\.patch|MagicMock' tests/research/survey/` == 0
- Config 检查：`grep -rE 'from \.config_defaults import|from \.\.gates\.config_defaults' harness/lib/research/survey/` 次数 ≥ 4
- 父 traceability：jq `.children[2].core_runtime_ready == true` + `.schema_version == "solar.epic.traceability.v1"` + `len(.children) == 5`

## 10. Out of Scope

- survey-eval / survey-review / survey-compile CLI 输出渲染（S04）
- e2e runtime 真跑（S05）
- 阈值数值最终调（S05 fixture-driven）
- 词典扩充（S05 / 后续 sprint）
- 给 frozen 5 module 加新功能
- 改动 `survey/__init__.py` 已有导出

## 11. Current Status

- status: drafting → active（本次 planner pass 完成后翻）
- phase: prd_ready → planning_complete
- handoff_to: planner → builder_parallel
- target_role: planner → builder_main
- artifacts: design.md ✓ / plan.md ✓ / task_graph.json ✓
