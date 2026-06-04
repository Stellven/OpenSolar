# Design — S05 verification-release

Sprint: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s05-verification-release`
Parent epic: `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build`
Slice: `verification-release`

## Goal

Prove the professor-grade DeepResearch survey hardening is usable end-to-end through reproducible tests, negative controls, activation proof, release evidence, and traceability without closing the parent epic prematurely.

## Inputs Read

- `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build.epic.md`
- `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build.task_graph.json`
- `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build.traceability.json`
- `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s03-core-runtime.handoff.md`
- `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s04-orchestration-ui.handoff.md`
- Current S05 PRD and contract

## Architecture Boundary

This sprint is verification only. It may add tests, fixtures, reports, release evidence, handoff/eval artifacts, and raw knowledge archival. It must not rewrite frozen survey modules, core harness loops, coordinator, dispatcher, autopilot, or `survey-continue` entrypoints.

## Verification Strategy

| Track | Purpose | Evidence |
| --- | --- | --- |
| E2E gate chain | Prove source quality, argument density, controversy matrix, exploration log, and gate report propagate in one deterministic fixture | pytest fixture, expected report, CLI view assertion |
| Negative controls | Prove low-quality web stuffing, weak argument density, decorative contradiction matrix, and missing exploration evidence are rejected or degraded visibly | fail/warn assertions |
| Activation proof | Prove S03 runtime gates and S04 CLI/status registry are importable and observable in the harness runtime | pytest + activation proof report |
| Release evidence | Aggregate reproducible commands, no-rewrite scans, raw knowledge archive, and open loops | release evidence markdown/json |
| Join gate | Patch only S05 traceability, write final handoff/eval, and let graph verdict decide sprint passed | handoff/eval + traceability flag |

## Determinism Requirements

- No live network access in tests.
- No wall-clock, UUID, random, or external LLM dependency in verification logic.
- No `@mock.patch` or `MagicMock` as substitute for real package-local functions.
- Fixtures must be local JSON/text artifacts.
- Any degradation must be visible through `partial_verdicts`, verdict table, or release evidence.

## Stop Rules

- If `.task_graph.json` is missing or invalid, do not dispatch builders.
- If any required gate test is missing, do not mark S05 passed.
- If parent epic is marked complete before S05 passes, fail the join node.
- If traceability update touches children other than S05, fail the join node.
- If frozen files are modified, fail release evidence.

## Frozen Scope

Frozen survey modules:

- `lib/research/survey/source_authority.py`
- `lib/research/survey/literature_mapping.py`
- `lib/research/survey/controversy.py`
- `lib/research/survey/chapter_review.py`
- `lib/research/survey/chief_editor.py`

Frozen harness runtime files:

- coordinator
- autopilot
- dispatcher
- phase-state-machine
- `solar-harness`
- `lib/research/survey/__init__.py`

## Exit Criteria

- S05 graph validates.
- N1-N4 verification nodes pass with evaluator evidence.
- N5 join passes after traceability patch `children[4].verification_release_ready=true`.
- Final handoff/eval/report exists.
- Raw knowledge archive exists or the blocker is explicitly recorded.
