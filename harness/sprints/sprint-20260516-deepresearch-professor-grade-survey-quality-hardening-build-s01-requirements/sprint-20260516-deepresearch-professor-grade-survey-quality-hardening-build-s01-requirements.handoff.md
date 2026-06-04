# Handoff — sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s01-requirements / N3

Sprint: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s01-requirements`
Node: N3 (join)
Date: 2026-05-17
Knowledge Context: solar-harness context inject used

## Summary

Join node: synthesized N1 (outcomes.md) and N2 (non-builder-boundary.md) into sprint-level handoff with 5 outcome × 4 slice entry matrix, governance boundary summary, known unclosed items, and blocking declarations. Patched parent traceability.json `children[0].outcomes_ready=true`.

evaluator_can_review: true

---

## 1. Outcome × Slice Entry Matrix

5 outcomes × 4 slices = 20 entry points. Each cell identifies what the slice consumes from the outcome and which prior sprint interface it depends on.

### O1 — Source Quality Distribution Gate

| Slice | Deliverable / Entry Point | Prior Interface Dependency |
|-------|--------------------------|---------------------------|
| S02_architecture | Define `SourceQualityDistribution` schema + plugin registration interface + data flow boundary with `source_authority.py` | `source_authority.py: check_source_authority()` (frozen) |
| S03_core-runtime | Implement `build_source_quality_distribution()` pure function + unit tests + distribution → verdict mapping | `evidence_pack.py: EvidencePack schema` (frozen) |
| S04_orchestration-ui | `survey-eval --strict` output shows distribution vector + anti-pattern flags | `evaluator.py: SurveyScorecard` (frozen) |
| S05_verification-release | e2e fixture with controlled distribution (strong/weak) → strict eval verifies distribution difference reflected in verdict | `survey_eval.json` artifact schema (frozen) |

### O2 — Argument Density Per-Section Gate

| Slice | Deliverable / Entry Point | Prior Interface Dependency |
|-------|--------------------------|---------------------------|
| S02_architecture | Define `ArgumentDensityProfile` schema + applicability mapping interface + data flow with `SectionReview` | `chapter_review.py: compile_survey()` (frozen) |
| S03_core-runtime | Implement `measure_argument_density()` pure function + marker-based detection + unit tests | `section_compiler.py: section artifact layout` (frozen) |
| S04_orchestration-ui | `survey-review` output shows density profile per section | `writing_loop.py: review.json schema` (frozen) |
| S05_verification-release | e2e fixture with high/low density sections → strict eval verifies low density sections flagged | `SectionReview` schema (frozen) |

### O3 — Controversy & Negative Evidence Matrix

| Slice | Deliverable / Entry Point | Prior Interface Dependency |
|-------|--------------------------|---------------------------|
| S02_architecture | Define `ContradictionMatrix` schema + data flow from `EvidencePack` + `claim_evidence.jsonl` + chapter synthesis reference interface | `controversy.py: contradiction_slots` (frozen) |
| S03_core-runtime | Implement `build_contradiction_matrix()` + `check_synthesis_references()` + contradiction_slots filling path | `evidence_pack.py: contradiction_slots` (frozen) |
| S04_orchestration-ui | `survey-compile` output includes matrix as report appendix | `report_ast.py: SurveyReportAST` (frozen) |
| S05_verification-release | e2e fixture with controlled contradiction data → verify matrix build + synthesis reference detection | `claim_evidence.jsonl` schema (frozen) |

### O4 — Multi-Direction Exploration with Elimination Log

| Slice | Deliverable / Entry Point | Prior Interface Dependency |
|-------|--------------------------|---------------------------|
| S02_architecture | Define `EliminationRecord` schema + `exploration_run()` interface + data flow from `source_matrix` / `handoff-search` | `literature_mapping.py: SourceMatrix` (frozen) |
| S03_core-runtime | Implement `run_exploration()` + `write_elimination_log()` + direction scoring + unit tests | `handoff-search` / `import-search` CLI (frozen) |
| S04_orchestration-ui | `survey-plan` output includes direction list + `survey-eval` output shows elimination summary | `planner.py: survey_source_matrix.json` (frozen) |
| S05_verification-release | e2e fixture with 3 controlled directions (1 eliminated) → verify log structure + eval check | `sources.jsonl` schema (frozen) |

### O5 — E2E Runtime Evidence (survey-continue)

| Slice | Deliverable / Entry Point | Prior Interface Dependency |
|-------|--------------------------|---------------------------|
| S02_architecture | Define `GateReport` schema + 4 gate plugin registration interface + e2e runner artifact layout | All 5 frozen interfaces above |
| S03_core-runtime | Implement 4 gate pure functions + `compile_gate_report()` aggregation + unit tests | O1-O4 gate functions (new, S03 builds) |
| S04_orchestration-ui | `survey-eval --strict` output shows 4 gate individual verdicts + gate_report | `evaluator.py: evaluate_survey()` (frozen) |
| S05_verification-release | e2e runner implementation + fixture preparation + strict test suite + regression tests | Full survey pipeline (S02 + S03 + S04 delivered) |

---

## 2. Governance Boundary Summary

From N2 `non-builder-boundary.md`:

- **不动文件** (6 files): `coordinator.sh` / `autopilot.sh` / `dispatcher.sh` / `phase-state-machine.sh` / `solar-harness.sh` / `survey/__init__.py` (existing exports only)
- **不动接口** (5 modules): `source_authority.py` / `literature_mapping.py` / `controversy.py` / `chapter_review.py` / `chief_editor.py` — public API + artifact schemas frozen
- **Plugin registration**: new gates register via `survey/gates/__init__.py`; explorer via `survey/explorer/__init__.py`
- **非 Builder 决策项** (4 categories): threshold values / scoring rubric / counter-evidence corpus selection / exploration direction initialization

---

## 3. Known Unclosed Items

前置 sprint 自评 6 个质量缺口中，以下项在 S01 outcomes 中已覆盖但需要 S02-S05 逐步闭环：

| # | 质量缺口 | S01 覆盖 Outcome | 闭环依赖 |
|---|---------|-----------------|---------|
| QG-1 | 文献综述方法学 | O1 + O4 | S02 需定义 literature review methodology 评估标准 |
| QG-2 | 分类法原创性 | O2 (`method_taxonomy` dimension) | S02 需决定是否要求 novel taxonomy |
| QG-3 | 跨章节一致性 | O3 (matrix cross-chapter view) | S03 需实现 cross-chapter claim linking |
| QG-4 | 反证覆盖 | O2 + O3 | S02 需定义 contradiction corpus 选源规则 |
| QG-5 | 术语稳定性 | O2 + O5 | S02 需定义 terminology consistency metric |
| QG-6 | 贡献边界 | O2 (`engineering_implication`) | S02 需定义 contribution boundary 判定规则 |

**所有 6 个缺口已在 outcomes.md 中显式引用，不会遗漏。** 但闭环需要 S02 architecture spec 锁定标准 + S03 实现 + S05 验证。

---

## 4. Blocking Declarations

```
s02_can_start: true
s03_blocked_until: s02_passed
s04_blocked_until: s02_passed
s05_blocked_until: [s03_passed, s04_passed]
```

S02 可以在 S01 evaluator 通过后立即启动。S03/S04 等 S02 architecture spec 完成后才能开始。S05 等 S03 和 S04 都通过后才能启动 e2e 验证。

---

## 5. Not Claimed

- epic NOT complete
- S02-S05 NOT ready
- Only S01 requirements slice deliverables (outcomes.md + non-builder-boundary.md + this handoff) are produced

---

## Changed Files

| File | Action | Description |
|------|--------|-------------|
| `sprints/…s01-requirements.handoff.md` | created | Sprint-level handoff with 20-row entry matrix + governance summary + blocking declarations |
| `sprints/epic-…traceability.json` | patched | `children[0].outcomes_ready=true` added |

## Verification Evidence

```bash
# Entry matrix row count (s0[2-5] identifiers)
grep -cE 'S0[2-5]_' sprints/…s01-requirements.handoff.md
# Expected: ≥ 20

# Blocking declarations present
grep 's02_can_start' handoff.md
grep 's03_blocked_until' handoff.md
grep 's05_blocked_until' handoff.md

# No "epic complete" claims
grep -cE 'epic.*(complete|done|passed)' handoff.md
# Expected: 0

# Traceability patch verification
python3 -c "
import json
t = json.load(open('sprints/epic-…traceability.json'))
assert t['schema_version'] == 'solar.epic.traceability.v1'
assert len(t['children']) == 5
assert t['children'][0]['outcomes_ready'] == True
print('traceability patch OK')
"
```

## Capability / KB Usage Evidence

- **harness-knowledge**: `solar-harness context inject` used at dispatch start
- **harness-graph**: Task graph read for N3 join gate verification; traceability.json patched per plan spec
- Not used: harness-intent, harness-skills, harness-ATLAS, harness-autopilot, gstack

## Scope Compliance

- `sprints/…s01-requirements.handoff.md` — within write scope
- `sprints/epic-…traceability.json` — within write scope (only `children[0].outcomes_ready` patched)
- No files outside write scope were modified

## Known Risks

1. **N2 non-builder-boundary.md 的不动接口清单准确性**：N2 列出的 5 个模块路径基于前置 sprint handoff，如果实际文件名有偏差，S03 builder 可能误改。
2. **Traceability children[0] index assumption**：patch 假设 children[0] 是 S01。如果 traceability.json 被 epic manager 重排，索引会错。

## Not Done

- S02-S05 deliverables (downstream sprints, not S01 scope)
- Evaluator review of N1/N2/N3 (awaiting evaluator)
