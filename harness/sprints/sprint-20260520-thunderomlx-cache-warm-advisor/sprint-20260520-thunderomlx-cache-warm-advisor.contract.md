# Contract: ThunderOMLX P0 Cache Warm + Advisor Metrics

## Sprint

- sprint_id: `sprint-20260520-thunderomlx-cache-warm-advisor`
- priority: P0
- lane: reliability/performance
- target_host: `lisihao@100.122.223.55`
- target_repo: `/Users/lisihao/ThunderOMLX`
- harness_runtime: `/Users/lisihao/.solar/harness`

## Scope

Implement a safe P0 cache performance loop for Mac mini ThunderOMLX:

1. Productize the existing four-pane prewarm workflow.
2. Run prewarm automatically after ThunderOMLX service startup or restart, after `/health` is ready.
3. Record cache advisor metrics in local reports without automatically mutating runtime parameters.
4. Preserve all safety disables that fixed乱码/empty replies.

## Hard Safety Rules

- Do not re-enable partial block cache restore or partial block storage.
- Do not re-enable full skip or approximate skip.
- Do not enable KVTC on the main pane path.
- Do not enable semantic response cache for coding builder requests.
- Do not write cache/offload data to `/Volumes/toshiba`.
- Do not print or persist API keys/tokens.
- Do not delete task directories, cache directories, model files, or user work.

## Expected Files / Ownership

Worker may modify or create only files directly needed for the integration, such as:

- `/Users/lisihao/.solar/harness/scripts/thunderomlx_prewarm_four_pane.py`
- `/Users/lisihao/.solar/harness/scripts/*thunderomlx*`
- `/Users/lisihao/ThunderOMLX/src/omlx/server.py` or startup-adjacent code, if the integration belongs in service startup.
- `/Users/lisihao/ThunderOMLX/src/omlx/cache_tuning_advisor.py` or existing advisor/metrics routes, only for read/report wiring.
- `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-*.md`
- sprint handoff/evidence files under `/Users/lisihao/.solar/harness/sprints/`

If another file is required, document why before changing it.

## Required Evidence

Final handoff must include:

- Exact files changed.
- Exact commands run.
- Current ThunderOMLX process command.
- Health response from `http://127.0.0.1:8002/health`.
- Four-pane prewarm report path.
- Table with pane, prompt_hash, cached_tokens, verify_s, bad_chars.
- Confirmation that unsafe cache features remain disabled.
- Git diff summary and commit SHA if a commit is made.

## Definition of Done

- Automatic prewarm path works after service startup/restart.
- Manual fallback command still works.
- Metrics report is generated in `~/.solar/harness/monitor-reports/`.
- API smoke with lowercase model id succeeds.
- No乱码, no `content=null`, no `bad_chars`.
- Relevant tests or smoke checks were actually run.

Knowledge Context: solar-harness context inject used
