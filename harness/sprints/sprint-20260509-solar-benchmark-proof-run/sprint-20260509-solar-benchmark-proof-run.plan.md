# Plan — Solar Benchmark Proof Run

## Single Slice

Builder runs:

```bash
cd /Users/lisihao/.solar/harness
bash solar-harness.sh integrations benchmark --threshold 90
bash solar-harness.sh integrations platform-benchmark --threshold 80
bash solar-harness.sh verify-integrations
```

Then writes:

```text
/Users/lisihao/.solar/harness/sprints/sprint-20260509-solar-benchmark-proof-run.handoff.md
```

## Evidence

- tmux pane output from `solar-harness:0.2`
- events file:
  `/Users/lisihao/.solar/harness/sprints/sprint-20260509-solar-benchmark-proof-run.events.jsonl`
- benchmark evidence directories:
  `/Users/lisihao/.solar/harness/reports/capability-fusion-evidence/latest`
  `/Users/lisihao/.solar/harness/reports/platform-workflow-evidence/latest`

## Gate

PASS only if the handoff exists and reports all commands as successful.
