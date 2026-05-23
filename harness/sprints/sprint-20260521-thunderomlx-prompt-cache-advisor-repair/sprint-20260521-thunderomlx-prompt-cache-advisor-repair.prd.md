# PRD: ThunderOMLX Prompt Cache API and Cache Advisor Repair

## Summary
Repair the remaining safe cache optimization blockers for ThunderOMLX + Qwen3.6 on the Mac mini. The current stable runtime already uses RAID0 paged SSD cache, 8GB RAM hot cache, four-pane prewarm, and `initial_cache_blocks=256`. This sprint must not re-enable partial block cache, full skip, or approximate skip.

## Problem
Two optimization paths were tested and blocked:

- Prompt Cache API exists at `/v1/cache/prompt/save|load|list|delete`, but `save` returns HTTP 422 for both pane4 system prompt and long knowledge-extraction prompt because KV cache capture cannot find persisted SSD blocks.
- `thunderomlx_cache_advisor_report.py` fails with duplicate `libomp.dylib` initialization, so the cache advisor cannot be used as a safe automatic reporting lane.

## Goals
- Make Prompt Cache API save/load work for stable long prompts without enabling unsafe cache skip features.
- Determine whether loaded named prompt caches can be consumed by `chat/completions`; if not, implement the minimal explicit request contract or document the gap with tests.
- Fix or isolate Cache Advisor so it runs without `KMP_DUPLICATE_LIB_OK=TRUE`.
- Preserve current stable pane4 behavior: `base_url_host=127.0.0.1:8002`, `bad_chars=false`, and four-pane prewarm cached token thresholds.

## Non-Goals
- Do not re-enable partial block cache.
- Do not re-enable full skip or approximate skip.
- Do not move cache writes to Toshiba.
- Do not print or persist auth tokens.
- Do not change the model from `Qwen3.6-35b-a3b`.

## Acceptance
- Prompt Cache API regression test demonstrates save/list/load for a long knowledge-extraction prompt.
- The implementation explains and verifies how a loaded named prompt cache is reused by inference, or clearly marks it unsupported with a follow-up contract.
- Cache Advisor report runs successfully without duplicate OpenMP runtime workaround.
- API smoke passes for uppercase and lowercase model names.
- Chinese output has `bad_chars=false`.
- Four-pane prewarm still reports pane0-2 `cached_tokens >= 1280` and pane4 `cached_tokens >= 1536`.
- Current safe cache config remains: RAID0 SSD cache, 8GB hot cache, `initial_cache_blocks=256`, unsafe skip features disabled.

## Evidence Inputs
- `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-four-pane-prewarm-20260521T013326Z.json`
- `/Users/lisihao/.solar/harness/scripts/thunderomlx_start_8002.sh`
- `/Users/lisihao/ThunderOMLX/src/omlx/server.py`
- `/Users/lisihao/ThunderOMLX/src/omlx/cache/prompt_cache_manager.py`
- `/Users/lisihao/.solar/harness/scripts/thunderomlx_cache_advisor_report.py`

