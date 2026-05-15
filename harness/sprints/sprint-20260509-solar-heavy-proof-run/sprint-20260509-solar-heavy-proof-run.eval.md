# Eval — sprint-20260509-solar-heavy-proof-run

Sprint: `sprint-20260509-solar-heavy-proof-run`
Evaluator: Solar pane attempted evaluation; Codex controller fallback finalized due evaluator write-stage stall.

## Verdict

`PASS`

## Verification Commands

```bash
cd /Users/lisihao/.solar/harness
bash solar-harness.sh integrations heavy-proof --threshold 100
cat reports/heavy-proof-benchmark-latest.json
file reports/heavy-proof-evidence/latest/runtime/browser-use-screenshot.png
```

## Results

```text
┌────┬────────────────────────────────────────┬────────┬──────────────────────────────────────────────┐
│ #  │ Acceptance                             │ 状态   │ Evidence                                     │
├────┼────────────────────────────────────────┼────────┼──────────────────────────────────────────────┤
│ 1  │ Heavy proof command exit 0             │ ok     │ latest JSON ok=true                          │
│ 2  │ Score 100 / passed 4 / total 4         │ ok     │ score=100 passed=4 total=4                  │
│ 3  │ MemPalace true semantic search         │ ok     │ total_docs=108 hits=3                       │
│ 4  │ Apple Notes isolated wiki dispatch     │ ok     │ exported=1 wiki_dispatches=1                │
│ 5  │ Accepted artifact wiki dispatch        │ ok     │ bytes=40835 dispatch_exists=True            │
│ 6  │ Browser-use screenshot proof           │ ok     │ PNG 1280x720, marker_found=True             │
│ 7  │ No real Knowledge vault pollution      │ ok     │ dispatch path is temp /var/folders vault     │
└────┴────────────────────────────────────────┴────────┴──────────────────────────────────────────────┘
```

## Evidence Paths

- `/Users/lisihao/.solar/harness/reports/heavy-proof-benchmark-latest.json`
- `/Users/lisihao/.solar/harness/reports/heavy-proof-benchmark-latest.md`
- `/Users/lisihao/.solar/harness/reports/heavy-proof-evidence/latest/commands`
- `/Users/lisihao/.solar/harness/reports/heavy-proof-evidence/latest/runtime`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260509-solar-heavy-proof-run.handoff.md`

## Important Findings

- The benchmark is real runtime proof, not just file existence: MemPalace loaded embeddings and queried live Chroma; Browser-use produced an actual PNG screenshot.
- Browser-use MCP was actually broken and was repaired during this run.
- Solar builder/evaluator panes can execute the work, but both stalled around artifact write stages. This is a control-plane/hook issue, not a runtime proof failure.
- `heavy-proof --threshold 101` is a bad falsification method for this heavy test because it reruns expensive runtime probes and overwrites `latest`; the controller restored `latest` with threshold 100 after observing this.

## Final Judgment

PASS with one operational follow-up: fix write-stage discipline so panes read `~/.solar/STATE.md` before handoff/eval writes and do not rely on controller fallback.
