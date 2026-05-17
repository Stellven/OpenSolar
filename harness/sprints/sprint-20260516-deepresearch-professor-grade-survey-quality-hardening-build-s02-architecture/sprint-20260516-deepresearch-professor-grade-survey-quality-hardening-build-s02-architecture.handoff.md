# Handoff — DeepResearch Professor-Grade Survey Quality Hardening · S02 Architecture

Sprint: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s02-architecture`
Epic: `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build`
Node: `N6` (join)
Author: Lab Builder (Solar Harness — lab-builder-4)
Date: 2026-05-17
Knowledge Context: solar-harness context inject used

```
s03_can_start: true
s04_can_start: true
s05_blocked_until: [s03_passed, s04_passed]
```

---

## 1. Arch Spec × Slice Entry Matrix

5 arch specs (D1-D5) × 2 slices (S03/S04) = 10 entry rows. Each cell: which slice deliverable, which frozen interface it depends on.

### O1 — Source Quality Distribution Gate (`source-quality-arch.md`)

| Slice | Entry Point / Deliverable | Frozen Interface Dependency |
|-------|--------------------------|---------------------------|
| s03_source_quality_impl | Implement `build_source_quality_distribution()` pure function in `survey/gates/source_quality_distribution.py`; register via `survey/gates/__init__.py` plugin registry; implement `StuffingAlert` detection heuristics; unit tests per AC1.1-AC1.4 | `source_authority.check_source_authority()` (frozen); `EvidencePack.source_types` / `EvidencePack.source_ids` (frozen schema); `SourceMatrix.required_source_types` (frozen) |
| s04_source_quality_ui | Surface `SourceQualityDistribution.canonical_coverage` and `stuffing_alerts` in `survey-eval --strict` output; include distribution vector in CLI report | `evaluator.py: SurveyScorecard` (frozen); `survey-eval` CLI entry point |

### O2 — Argument Density Per-Section Gate (`argument-density-arch.md`)

| Slice | Entry Point / Deliverable | Frozen Interface Dependency |
|-------|--------------------------|---------------------------|
| s03_argument_density_impl | Implement `measure_argument_density()` + `map_dimension_applicability()` in `survey/gates/argument_density.py`; implement 5 dimension presence detectors; implement `ArgumentDensityProfile` schema in `survey/schemas.py` extension; unit tests per AC2.1-AC2.4 | `SectionReview` schema (frozen); `chapter_review.compile_survey()` (frozen — consumed, not modified); `SectionSpec.section_id` (frozen) |
| s04_argument_density_ui | Surface per-section density profile in `survey-review` output; show `low_density_sections` list; section-level density summary in CLI | `writing_loop.py: review.json` artifact schema (frozen) |

### O3 — Controversy & Negative Evidence Matrix (`contradiction-matrix-arch.md`)

| Slice | Entry Point / Deliverable | Frozen Interface Dependency |
|-------|--------------------------|---------------------------|
| s03_contradiction_matrix_impl | Implement `build_contradiction_matrix()` + `check_synthesis_references()` in `survey/gates/controversy_matrix.py`; implement `ContradictionMatrix` + `ClaimEvidenceLink` schemas; implement decorative matrix detection; unit tests per AC3.1-AC3.4 | `EvidencePack.contradiction_slots` (frozen schema); `controversy.py` (frozen — consumed, not modified); `claim_evidence.jsonl` schema (frozen artifact format) |
| s04_contradiction_matrix_ui | Include `controversy_matrix.json` artifact in `survey-compile` output; surface decorative matrix warning in CLI; UI decorative warning alert | `report_ast.py: SurveyReportAST` (frozen); `survey-compile` CLI |

### O4 — Multi-Direction Exploration with Elimination Log (`exploration-arch.md`)

| Slice | Entry Point / Deliverable | Frozen Interface Dependency |
|-------|--------------------------|---------------------------|
| s03_exploration_impl | Implement `exploration_run()` + `score_direction()` + `log_writer.py` in `survey/explorer/` (new package); implement `ExplorationDirection`, `EliminationRecord`, `ExplorationRunResult` schemas; write `elimination_log.jsonl` incrementally; unit tests per AC4.1-AC4.4 | `SourceMatrix` dataclass (frozen — `literature_mapping.py`); `survey_source_matrix.json` artifact layout (frozen — `planner.py`); `handoff-search` / `import-search` CLI contract (frozen); `source_authority.check_source_authority()` (frozen — direction scorer) |
| s04_exploration_ui | Integrate `exploration_run()` call in survey planner phase; surface `directions_eliminated_count` / `directions_selected_count` in `survey-plan` CLI output; persist `elimination_log.jsonl` path in survey run artifact index | `planner.py: survey_source_matrix.json` artifact layout (frozen) |

### O5 — E2E Runtime Evidence (`gate-report-arch.md`)

| Slice | Entry Point / Deliverable | Frozen Interface Dependency |
|-------|--------------------------|---------------------------|
| s03_gate_report_impl | Implement `compile_gate_report()` aggregation function that runs all 4 gate plugins and assembles `GateReport`; implement `GateReport` schema in `survey/schemas.py` extension; wire 4 gate plugins (O1-O4) into survey-continue runner hook; unit tests per AC5.1-AC5.5 partial (E2E deferred to S05) | `evaluate_survey()` (frozen — `evaluator.py`); `SurveyScorecard` (frozen schema — referenced, not duplicated); O1-O4 gate functions (new, built in S03) |
| s04_gate_report_ui | Surface `gate_report.json` in `survey-eval --strict` CLI output with 4 gate individual verdicts; include `artifact_paths` in structured CLI output | `evaluator.py: evaluate_survey()` (frozen — consumed, not modified) |

---

## 2. Frozen Interface Non-Modification Summary

All 5 frozen modules and 6 frozen files from S01 governance boundary remain untouched by S02 architecture specs:

**5 Frozen Modules (public API frozen):**
- `source_authority.py: check_source_authority()`
- `literature_mapping.py: SourceMatrix` dataclass
- `controversy.py: contradiction_slots` pipeline
- `chapter_review.py: compile_survey()`
- `chief_editor.py` (all public API)

**6 Frozen Files (no modification):**
- `coordinator.sh`
- `autopilot.sh`
- `dispatcher.sh`
- `phase-state-machine.sh`
- `solar-harness.sh`
- `survey/__init__.py` (existing exports only; new sub-packages added, existing exports frozen)

---

## 3. Quality Gap Lockdown Summary

From `quality-gap-lockdown.md`:

| QG | 标准锁定（无数值）| S03 实现入口 |
|----|----------------|------------|
| QG-1 文献综述方法学 | 检索可追溯 + 来源类型覆盖 + 综合对比覆盖 + 筛选文档质量 | O4 explorer + O1/O2 gates |
| QG-2 分类法原创性 | 分类框架显式性 + 基线 diff + 跨 section 标签一致性 | O2 argument_density gate |
| QG-3 跨章节一致性 | Claim ID 复用一致性 + 矛盾检测 + density 章节平衡 | O3 gate + global consistency pass |
| QG-4 反证覆盖 | Claim 级矩阵 + 非装饰性 + 来源多样性 | O3 controversy_matrix gate |
| QG-5 术语稳定性 | 首次定义优先 + 别名映射 + 跨章节漂移检测 | O5 E2E global consistency pass |
| QG-6 贡献边界 | 声明范围 + 排除范围 + 探索边界一致性 + 来源可溯性 | O4 + O5 report structure checker |

---

## 4. Known Unclosed Items (S03 Builder 需关注)

以下项在 S02 arch spec 中被标为"builder boundary"，S03 builder 在实现前必须等待 planner 决定（不得自行拍板）：

| Item | 涉及 Spec | Builder 不能自决的原因 |
|------|---------|---------------------|
| 来源类型分类法词典（SourceTaxonomy） | source-quality-arch.md §4 | 分类规则是方法学决策；builder 自定义会导致不可重复 |
| 5 维度操作定义 rubric（O2） | argument-density-arch.md | 维度定义模糊 → LLM 检测不稳定 |
| Claim 粒度定义（O3） | contradiction-matrix-arch.md | 粒度影响 matrix 规模和可读性 |
| 探索方向初选协议（O4） | exploration-arch.md §9 | 初选规则决定探索空间；builder 自选可能同质化 |
| Scoring dimension 权重（O4） | exploration-arch.md §9 | 权重是策略决策，需外部可配置 |
| E2E 测试样本（O5） | gate-report-arch.md | 样本选择影响 gate 暴露真实质量问题的能力 |

---

## 5. Not Claimed

- epic NOT complete — S03/S04/S05 均未实现
- S03/S04 implementation NOT ready — 所有 arch spec 为 "spec only"，不含实现代码
- schema NOT implemented — `survey/schemas.py` 尚未扩展新 dataclass
- 本 handoff 仅覆盖 S02 architecture slice 的 N6 join 交付物

---

## 6. Changed Files (This Sprint S02)

| File | 操作 | 节点 |
|------|------|------|
| `sprints/…s02-architecture.source-quality-arch.md` | CREATE | N1 |
| `sprints/…s02-architecture.argument-density-arch.md` | CREATE | N2 |
| `sprints/…s02-architecture.contradiction-matrix-arch.md` | CREATE | N3 |
| `sprints/…s02-architecture.exploration-arch.md` | CREATE | N4 |
| `sprints/…s02-architecture.gate-report-arch.md` | CREATE | N5 |
| `sprints/…s02-architecture.quality-gap-lockdown.md` | CREATE | N6 |
| `sprints/…s02-architecture.handoff.md` | CREATE | N6 |
| `sprints/epic-…traceability.json` | PATCH | N6 (`children[1].architecture_ready=true` only) |
