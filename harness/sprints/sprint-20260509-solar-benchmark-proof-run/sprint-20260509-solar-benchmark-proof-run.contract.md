# Sprint Contract — Solar Benchmark Proof Run

sprint_id: sprint-20260509-solar-benchmark-proof-run
status: active
phase: planning_complete
handoff_to: builder_main
priority: P0
lane: verification

## Intent

Prove the benchmark claims using the real Solar builder pane, not only Codex-local shell execution.

## Required Work

1. Run `bash solar-harness.sh integrations benchmark --threshold 90`.
2. Run `bash solar-harness.sh integrations platform-benchmark --threshold 80`.
3. Run `bash solar-harness.sh verify-integrations`.
4. Write a handoff to:
   `/Users/sihaoli/.solar/harness/sprints/sprint-20260509-solar-benchmark-proof-run.handoff.md`

## Handoff Must Include

- The exact commands run.
- PASS/FAIL summary for all three commands.
- Paths to generated benchmark reports and evidence directories.
- A short statement separating “local benchmark proof” from “full heavy end-to-end proof”.

## Stop Rules

- Do not modify product code.
- Do not run full 24GB migration export/import.
- Do not run destructive commands.
- If any command fails, write the failure output into the handoff and stop.
