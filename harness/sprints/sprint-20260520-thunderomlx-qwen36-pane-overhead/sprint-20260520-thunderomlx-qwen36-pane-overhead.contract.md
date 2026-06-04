# Contract: ThunderOMLX + Qwen3.6 Pane Overhead Analysis

## Sprint

- sprint_id: `sprint-20260520-thunderomlx-qwen36-pane-overhead`
- priority: P0
- lane: performance/reliability
- target_host: `lisihao@100.122.223.55`
- target_repo: `/Users/lisihao/ThunderOMLX`
- target_harness: `/Users/lisihao/.solar/harness`
- target_pane: `solar-harness-lab:0.3`

## Mission

Analyze the end-to-end overhead of the real ThunderOMLX + Qwen3.6 pane path and identify optimizations. The known delta is:

- bare API: about `1.0s` total with `1536 cached_tokens`
- real pane: about `8.3s` end-to-end

The task is to explain the delta with measurements and implement only safe, reversible optimizations if clearly justified.

## Hard Safety Rules

- Do not print, persist, or expose API tokens.
- Do not re-enable partial block cache, full skip, or approximate skip.
- Do not enable KVTC on the main pane path.
- Do not clear cache directories.
- Do not kill long-running user panes.
- Do not alter unrelated dirty files in ThunderOMLX.
- If changing launch flags or prompt flags, make a backup and provide rollback.

## Required Measurements

Measure and report:

- bare API timing: TTFT, total_time, cached_tokens, prompt_tokens, output_tokens.
- pane timing: tmux send time to assistant line visible.
- Claude CLI / wrapper overhead: infer by comparing pane e2e vs API timing using same prompt/query where possible.
- thinking/render overhead: detect time spent before final `⏺` output and whether hidden/visible thinking contributes.
- hook overhead: inspect Claude settings hooks and relevant harness hook logs.
- cache evidence: latest ThunderOMLX log cache hits and unsafe feature guard lines.

## Allowed Optimizations

Allowed if justified by measurement:

- Reduce unnecessary visible thinking/render overhead for the ThunderOMLX pane.
- Use a shorter performance/interactive system prompt for pane4 if it preserves required Solar-Harness policy.
- Add a lightweight pane smoke/perf command that bypasses UI overhead for diagnosis.
- Tune harness hook frequency or logging if it is measured to be material and safe.
- Add reporting scripts under `~/.solar/harness/scripts/`.

## Forbidden Optimizations

- Any optimization that weakens the Solar Runtime Context Policy.
- Any optimization that bypasses safety/permission boundaries for general use.
- Any optimization based only on subjective observation without before/after evidence.

## Required Artifacts

- `~/.solar/harness/sprints/sprint-20260520-thunderomlx-qwen36-pane-overhead.N*-handoff.md`
- `~/.solar/harness/monitor-reports/thunderomlx-pane4-overhead-*.json`
- `~/.solar/harness/monitor-reports/thunderomlx-pane4-overhead-*.md`

## Definition of Done

- Root-cause table for the 8.3s pane latency is produced.
- Top 3 optimization candidates are ranked.
- Any implemented change has before/after evidence.
- No乱码, no content-null, no token leakage.
- Unsafe cache features remain disabled.

Knowledge Context: solar-harness context inject used
