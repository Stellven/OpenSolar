# Contract — Solar Heavy Runtime Proof Run

bypass_pm: true

## Task

Run the heavy integration proof from a real Solar builder pane.

```bash
cd /Users/lisihao/.solar/harness
bash solar-harness.sh integrations heavy-proof --threshold 100
```

## Acceptance

- The command exits 0.
- The report `/Users/lisihao/.solar/harness/reports/heavy-proof-benchmark-latest.json` contains:
  - `ok: true`
  - `score: 100`
  - `passed: 4`
  - `total: 4`
- The evidence directory `/Users/lisihao/.solar/harness/reports/heavy-proof-evidence/latest` contains raw stdout/stderr and runtime artifacts.
- The handoff file `/Users/lisihao/.solar/harness/sprints/sprint-20260509-solar-heavy-proof-run.handoff.md` summarizes results honestly.

## Stop Rules

- If any proof fails, do not claim success. Capture stderr and explain the blocker.
- Do not write mock data into `/Users/lisihao/Knowledge`; the benchmark uses isolated temporary vaults for mock writes.
