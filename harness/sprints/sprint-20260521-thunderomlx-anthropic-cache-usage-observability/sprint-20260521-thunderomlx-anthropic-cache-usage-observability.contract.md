# Contract: ThunderOMLX Anthropic Cache Usage Observability

## Target
- Host: `lisihao@100.122.223.55`
- Repo: `/Users/lisihao/ThunderOMLX`
- Service: `127.0.0.1:8002`
- Settings: `/Users/lisihao/.omlx/settings.json`
- Evidence:
  - `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-anthropic-cache-hit-no-garbled.md`
  - `/Users/lisihao/.solar/harness/monitor-reports/sprint-20260521-thunderomlx-anthropic-cache-hit-no-garbled-N3-stress.json`

## Allowed Actions
- Edit ThunderOMLX source and tests.
- Restart ThunderOMLX 8002 if required to load code changes.
- Run AnthropicProxy API smoke tests against 127.0.0.1:8002.
- Commit the ThunderOMLX code change if tests pass.

## Forbidden Actions
- Do not print API keys/tokens/OAuth secrets.
- Do not disable `cloud.anthropic_prefix_cache_enabled=true`.
- Do not enable Partial Block Cache, Full Skip, or Approximate Skip.
- Do not delete or move cache directories.
- Do not use Toshiba as write cache.
- Do not leave service stopped.

## Required Evidence
- Changed files and git commit if committed.
- Unit test output.
- Live smoke output showing:
  - HTTP 200
  - cache hit in logs
  - response usage `cache_read_input_tokens > 0`
  - bad_chars=false
- Final Chinese report with current problem and next step.

## Definition of Done (Planner — Quantified)
- [ ] D1: Anthropic 响应 usage 中 cache_read_input_tokens 在缓存命中时 > 0（非流式 + 流式路径）
- [ ] D2: 单元/回归测试 >= 3 条覆盖 cached_tokens 转换路径，pytest 全通过
- [ ] D3: 活测试 HTTP 200 + bad_chars=false + 日志 Cache HIT 与 JSON usage cache_read_input_tokens 一致
- [ ] D4: ThunderOMLX 8002 保持健康，缓存策略未变（Partial/Full/Approx Skip 均关闭）
- [ ] D5: 最终中文报告写入 monitor-reports/thunderomlx-anthropic-cache-usage-observability.md