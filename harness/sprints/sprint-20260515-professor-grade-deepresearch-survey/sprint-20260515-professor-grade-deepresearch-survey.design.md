# Design — Survey-Native DeepResearch Runtime

## Architecture

```text
Existing DeepResearch Core
  sources.jsonl / evidence.jsonl / claims.jsonl / claim_evidence.jsonl
        │
        ▼
harness/lib/research/survey/
  planner.py            -> SurveyPlan + SourceMatrix
  evidence_pack.py      -> per-section EvidencePack
  report_ast.py         -> 8-12 chapter / 30-40 section SurveyReportAST
  section_compiler.py   -> section artifact compiler
  evaluator.py          -> section/chapter/global survey scorecard
        │
        ▼
reports/<sid>/
  survey_plan.json
  survey_report_ast.json
  sections/chXX/secYY/
    section.spec.json
    evidence_pack.json
    claim_budget.json
    draft.md
    review.json
    final.md
  chapters/chXX/
    synthesis.md
    review.json
  final.md
  survey_eval.json
```

## Package Boundary

All survey-specific code lives under:

`harness/lib/research/survey/`

The existing `harness/lib/research/cli.py` may add thin command adapters only. It must not absorb survey logic.

## Data Model

- `SurveyRun`: run metadata, target chars, profile, status.
- `SurveyQuestion`: question tree node.
- `SourceMatrix`: required source types by question/section.
- `SurveyReportAST`: chapters, sections, target chars, dependencies.
- `SectionSpec`: section title, target chars, required claims, required evidence types.
- `EvidencePack`: evidence IDs, source diversity, contradictions, risk flags.
- `SectionReview`: factuality, citation, repetition, terminology, coherence verdict.
- `SurveyScorecard`: aggregate quality gate.

## Evaluation Philosophy

Existing `eval-artifacts` checks whether a small report is supported. Survey evaluator checks whether a large report is survey-grade:

- section-level evidence sufficiency,
- chapter-level synthesis quality,
- cross-section contradictions,
- taxonomy depth,
- source diversity,
- historical/evolution coverage,
- limitations/open problems,
- roadmap usefulness.

## Human-In-The-Loop Search

The source matrix can emit handoff Markdown chunks per chapter/section. User can paste the Markdown into Gemini/GPT/browser search, then import returned source blocks back into Solar.

This is not fallback; it is an explicit acquisition mode:

`survey-plan -> handoff-search batches -> import-search -> evidence-pack`

