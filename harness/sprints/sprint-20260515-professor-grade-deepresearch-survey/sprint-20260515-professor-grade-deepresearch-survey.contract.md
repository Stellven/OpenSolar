---
sprint_id: sprint-20260515-professor-grade-deepresearch-survey
title: Solar DeepResearch Professor-Grade Survey Pipeline
priority: P0
lane: research-runtime
owner: solar-harness
created_at: 2026-05-15T19:27:12Z
status: active
phase: planning_complete
handoff_to: builder_main
target_role: builder_main
package_boundary: harness/lib/research/survey
bypass_pm: true
---

# P0 合约: Solar DeepResearch Professor-Grade Survey Pipeline

## 1. Intent

把 Solar DeepResearch 从“带证据门禁的技术简报/中篇报告生成器”升级为能支撑 5-10 万字教授级专业 survey 的研究生产线。

当前系统不能支撑教授级 survey 的原因已经确认：

- `report_ast.json` 只有 `1 chapter / 5 sections`，不是 survey 级结构。
- 现有 `final.md` 虽可通过 citation/factuality gate，但内容组织仍偏 technical brief。
- 现有 evaluator 主要验证 citations、source types、section density，不能评审文献综述方法学、分类法原创性、跨章节一致性、反证覆盖、术语稳定性、贡献边界。
- 现有 ReportAST 缺少 chapter/section spec、evidence pack、claim budget、revision loop、reviewer verdict、global consistency pass。

目标不是继续补长 prompt，而是实现 survey-native pipeline：

```text
research brief
  -> survey question tree
  -> literature/source matrix
  -> source ingestion
  -> evidence ledger
  -> claim ledger
  -> taxonomy synthesis
  -> report ast 8-12 chapters / 30-40 sections
  -> section specs + evidence packs
  -> section drafting
  -> section factuality review
  -> chapter synthesis
  -> global consistency review
  -> final survey compile
  -> professor-grade scorecard
```

## 2. Non-Negotiables

- Package-first architecture: all new code must live under `harness/lib/research/survey/` or `harness/tests/research_survey/`.
- Do not rewrite main coordinator, core graph scheduler, or existing DeepResearch CLI loop except for a thin plug-in command.
- No fake completion: a 5-section report must never be labelled professor-grade survey.
- No one-shot 100k output. Output must be 30-40 section artifacts with per-section evidence packs.
- No unsupported key claims. Any section final must fail if key claim lacks `claim_id -> evidence_id -> source_id`.
- Human-in-the-loop source acquisition must remain first-class to avoid paid API dependency.
- Online exploration must support multi-direction source plans and fast elimination: paper/code/benchmark/official_doc/contradiction/negative-results/review/survey/dataset.
- All generated PRD/design/plan/evidence docs must be written to Markdown and exportable into `/Users/sihaoli/Knowledge/_raw/solar-harness`.

## 3. Target Quality Bar

Professor-grade survey means:

- 5-10 万中文字符 or configured target size.
- 8-12 chapters, 30-40 sections.
- Each section has a `section.spec.json`, `evidence_pack.json`, `claim_budget.json`, `draft.md`, `review.json`, `final.md`.
- Each chapter has a chapter synthesis and chapter review.
- Final report includes taxonomy, historical evolution, competing schools, architecture tradeoffs, evaluation methodology, limitations, open problems, and roadmap.
- Factuality evaluator checks citation span support, contradiction coverage, source authority, source diversity, repetition, terminology drift, cross-section conflict, and unsupported claim rate.

## 4. Deliverables

### D1 — Survey Package Skeleton

Files:

- `harness/lib/research/survey/__init__.py`
- `harness/lib/research/survey/schemas.py`
- `harness/lib/research/survey/planner.py`
- `harness/lib/research/survey/evidence_pack.py`
- `harness/lib/research/survey/report_ast.py`
- `harness/lib/research/survey/section_compiler.py`
- `harness/lib/research/survey/evaluator.py`
- `harness/tests/research_survey/`

Acceptance:

- Package imports without side effects.
- Schemas include SurveyRun, SurveyQuestion, SourceMatrix, SurveyReportAST, ChapterSpec, SectionSpec, EvidencePack, SectionReview, SurveyScorecard.
- All schemas have `schema_version`.

### D2 — Survey Planner

Acceptance:

- Converts brief into question tree + chapter plan.
- Produces 8-12 chapters and 30-40 sections for target `50000-100000`.
- Generates source matrix per section with required source types and min counts.
- Supports `target_chars`, `audience`, `domain`, `time_range`, `source_policy`, `contradiction_policy`.

### D3 — Evidence Pack Builder

Acceptance:

- Builds per-section evidence packs from existing `sources.jsonl`, `evidence.jsonl`, `claims.jsonl`.
- Each pack has min evidence count, min source diversity, claim/evidence links, contradiction slots.
- Empty or weak packs block drafting.

### D4 — Section Compiler

Acceptance:

- Writes one section at a time from SectionSpec + EvidencePack + ClaimLedger.
- Does not write unsupported claims.
- Writes deterministic section artifacts under `reports/<sid>/sections/<chapter>/<section>/`.
- Supports revision loop inputs from evaluator.

### D5 — Survey Evaluator

Acceptance:

- Adds professor-grade scorecard:
  - unsupported_claim_rate
  - citation_span_accuracy
  - contradiction_coverage
  - source_diversity_score
  - taxonomy_depth_score
  - section_repetition_rate
  - terminology_consistency_score
  - cross_section_conflict_count
  - chapter_coherence_score
  - survey_readiness_verdict
- Strict mode fails unless `survey_readiness_verdict=PASS`.

### D6 — CLI Integration

Acceptance:

- Adds thin commands without rewriting existing CLI:
  - `solar-harness research survey-plan`
  - `solar-harness research survey-pack`
  - `solar-harness research survey-write-section`
  - `solar-harness research survey-review`
  - `solar-harness research survey-compile`
  - `solar-harness research survey-eval`
- Existing `research run`, `handoff-search`, `import-search`, `source-audit`, `eval-artifacts` stay compatible.

### D7 — End-to-End Smoke

Acceptance:

- Fake/local fixture run creates 8 chapters and at least 30 section specs.
- At least 3 sections go through pack -> draft -> review -> final.
- Final survey compile produces an index with all chapters/sections.
- Strict survey eval fails on weak packs and passes on controlled strong fixture.
- No network or paid API required for tests.

## 5. Required Verification

```bash
python3 -m pytest -q /Users/sihaoli/.solar/harness/tests/research_survey
python3 -m pytest -q /Users/sihaoli/.solar/harness/tests/research_unit/test_cli.py /Users/sihaoli/.solar/harness/tests/research_unit/test_evaluator.py
python3 -m py_compile /Users/sihaoli/.solar/harness/lib/research/survey/*.py
solar-harness research survey-plan --brief "隐空间推理技术架构和演进方向" --target-chars 50000 --output-dir /tmp/solar-survey-smoke
solar-harness research survey-eval --output-dir /tmp/solar-survey-smoke --strict --json
```

## 6. Stop Rules

- If implementation tries to make the existing 5-section brief template pass as professor-grade survey, fail.
- If new code mutates coordinator/autopilot/main scheduler directly, fail.
- If a section can be finalized without evidence pack and claim links, fail.
- If tests rely on paid online APIs, fail.
