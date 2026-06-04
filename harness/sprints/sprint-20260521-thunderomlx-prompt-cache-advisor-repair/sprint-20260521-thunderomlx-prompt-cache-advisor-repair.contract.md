# Contract: ThunderOMLX Prompt Cache API and Advisor Repair

## Runtime Target
- Host: Mac mini `lisihao@100.122.223.55`
- Repo: `/Users/lisihao/ThunderOMLX`
- Harness: `/Users/lisihao/.solar/harness`
- Service: `http://127.0.0.1:8002`
- Model: `Qwen3.6-35b-a3b`

## Required Safety Constraints
- Keep cache writes on `/Volumes/RAID0-Main/omlx-cache/ssd-qwen36`.
- Keep `--hot-cache-max-size 8GB`.
- Keep `--initial-cache-blocks 256` unless a measured change clearly wins; if tested and not retained, restore 256.
- Keep partial block cache, full skip, and approximate skip disabled.
- Do not expose API keys or auth tokens in logs, handoffs, or reports.
- Do not delete existing cache directories.

## Required Work
1. Reproduce and document:
   - Prompt Cache API `save` 422 on pane4 system prompt and/or long knowledge extraction prompt.
   - Advisor duplicate `libomp.dylib` failure.
2. Fix Prompt Cache API capture path:
   - Prefer deterministic block lookup based on the request that just prefills the prompt.
   - Avoid timing-only assumptions around async SSD writer flush.
   - Add a regression script/report under harness monitor reports.
3. Confirm inference reuse contract:
   - If loaded named prompt cache is intended to affect chat/completions, add the minimal request field and integration test.
   - If it is not currently wired, document exact missing integration and do not claim latency improvement.
4. Fix Cache Advisor:
   - Resolve duplicate OpenMP initialization at import/dependency boundary, or isolate advisor into a subprocess/env that avoids loading two OpenMP runtimes.
   - Do not use `KMP_DUPLICATE_LIB_OK=TRUE` as the accepted fix.
5. Validate:
   - API smoke: uppercase/lowercase model names.
   - Chinese output and `bad_chars=false`.
   - four-pane prewarm thresholds.
   - no unsafe feature was re-enabled.

## Deliverables
- Code changes in `/Users/lisihao/ThunderOMLX` and/or harness scripts as needed.
- Handoff files:
  - `sprint-20260521-thunderomlx-prompt-cache-advisor-repair.N1-audit.md`
  - `sprint-20260521-thunderomlx-prompt-cache-advisor-repair.N2-handoff.md`
  - `sprint-20260521-thunderomlx-prompt-cache-advisor-repair.N3-handoff.md`
  - `sprint-20260521-thunderomlx-prompt-cache-advisor-repair.N4-handoff.md`
- Reports under `/Users/lisihao/.solar/harness/monitor-reports/`.

