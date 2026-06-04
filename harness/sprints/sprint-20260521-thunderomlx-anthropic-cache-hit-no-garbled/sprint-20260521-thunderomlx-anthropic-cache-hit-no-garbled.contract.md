# Contract: ThunderOMLX AnthropicProxy Cache Hit Without Garbled Output

## Target
- Host: `lisihao@100.122.223.55`
- ThunderOMLX repo: `/Users/lisihao/ThunderOMLX`
- Service: `127.0.0.1:8002`
- Model: `/Volumes/toshiba/models/Qwen3.6-35b-a3b`
- SSD cache: `/Volumes/RAID0-Main/omlx-cache/ssd-qwen36`
- Hot cache: `8GB`
- Pane4 env truth source: `/Users/lisihao/.solar/harness/run/pane-env/_8.json`

## Allowed Actions
- Edit ThunderOMLX source in `/Users/lisihao/ThunderOMLX`.
- Edit `/Users/lisihao/.omlx/settings.json` to set `cloud.anthropic_prefix_cache_enabled=true`.
- Restart ThunderOMLX 8002 using the existing RAID0 cache and 8GB hot cache launch shape.
- Run local unit/smoke/performance tests.
- Add regression scripts/reports under `/Users/lisihao/.solar/harness/monitor-reports/`.

## Forbidden Actions
- Do not print API keys, tokens, OAuth credentials, or full sensitive request bodies.
- Do not enable Partial Block Cache.
- Do not enable Full Skip or Approximate Skip.
- Do not delete cache directories.
- Do not use Toshiba as write cache.
- Do not leave ThunderOMLX stopped.
- Do not pass by disabling AnthropicProxy prefix cache again.

## Required Evidence
- Exact runtime command or launch evidence after restart.
- `/v1/models` or equivalent service health.
- Before/after metrics:
  - latency
  - `cache_read_input_tokens` / `cached_tokens` or cache-hit log
  - `bad_chars`
  - output language sanity
- Concurrency/overlap test result covering at least Chinese, English, code, and mixed-language prompts.
- Changed files and rollback instructions.

## Definition of Done
- Graph all nodes passed.
- Final report exists.
- Final report includes `当前问题` and `下一步`.

