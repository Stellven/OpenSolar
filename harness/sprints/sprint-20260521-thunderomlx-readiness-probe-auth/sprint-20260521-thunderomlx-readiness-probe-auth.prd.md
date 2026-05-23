# PRD: ThunderOMLX authenticated readiness probe

## Summary
Fix ThunderOMLX 8002 readiness and monitor probes so authenticated services are not marked unhealthy just because unauthenticated `GET /v1/models` returns `401`.

## Problem
ThunderOMLX is configured with API-key enforcement. During the cache usage observability sprint, an unauthenticated readiness loop repeatedly called `/v1/models` and timed out even though `/v1/messages` was healthy and cache hits were working. This creates false alarms and can trigger unnecessary restarts or stale-task diagnosis.

## Goals
- Replace unauthenticated readiness checks with one of:
  - an authenticated `/v1/models` probe using the local configured API key without printing it, or
  - a dedicated non-secret health endpoint if ThunderOMLX already exposes one.
- Update scripts or monitor helpers used by Mac mini solar-harness/ThunderOMLX operations.
- Preserve current runtime constraints:
  - model: `Qwen3.6-35b-a3b`
  - service: `127.0.0.1:8002`
  - SSD cache: `/Volumes/RAID0-Main/omlx-cache/ssd-qwen36`
  - hot cache: `8GB`
  - `anthropic_prefix_cache_enabled=true`
  - Partial Block Cache, Full Skip, and Approximate Skip remain disabled.
- Add focused tests or smoke checks proving:
  - unauthenticated `401` is treated as "auth required / service alive", not "port unhealthy";
  - authenticated probe returns ok;
  - `/v1/messages` still reports `usage.cache_read_input_tokens > 0` on a repeated-prefix request;
  - Chinese output has `bad_chars=false`.

## Non-Goals
- Do not rework the cache algorithm.
- Do not change API keys or print secrets.
- Do not delete cache directories.
- Do not enable unsafe cache features.
- Do not change the model or route pane4 away from ThunderOMLX.

## Acceptance
- Final report exists at `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-readiness-probe-auth.md`.
- Task graph all nodes passed and parent-check ready is true.
- Probe behavior is documented with command evidence, sanitized for keys/tokens.
- ThunderOMLX 8002 is healthy after the change.
- Repeated-prefix live smoke shows `cache_read_input_tokens > 0` and `bad_chars=false`.
