# Plan — Professor-Grade Survey Pipeline

## P0 Mainline

Build survey-native package and gates without modifying the main harness architecture.

## Steps

1. Implement schemas and package skeleton.
2. Implement survey planner with 8-12 chapter / 30-40 section AST.
3. Implement evidence pack builder from existing ledger artifacts.
4. Implement section compiler and section artifact layout.
5. Implement survey evaluator and strict scorecard.
6. Add CLI adapter commands.
7. Add e2e fixture and regression tests.
8. Export final raw evidence note to Knowledge `_raw`.

## Acceptance

- `pytest tests/research_survey` passes.
- Existing research unit tests still pass.
- `survey-plan --target-chars 50000` creates >= 8 chapters and >= 30 sections.
- Weak evidence pack blocks section finalization.
- Strict survey eval distinguishes `brief_passed` from `survey_passed`.

## Risks

- If source quality is poor, survey writing must stop rather than hallucinate.
- If evaluator is too weak, it will rubber-stamp garbage.
- If CLI absorbs survey logic, package architecture will rot.

