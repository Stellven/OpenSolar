# PRD: ThunderOMLX Anthropic Cache Usage Observability

## Summary
修复 ThunderOMLX AnthropicProxy 响应 usage 可观测性：当前服务端日志已经确认 `Cache HIT cached_tokens=256`，但 `/v1/messages` Anthropic 兼容响应里的 `usage.cache_read_input_tokens` 仍为 0 或缺失。目标是让 pane4/API 层直接看到缓存命中 token，而不必 grep 服务端日志。

## Background
- Sprint `sprint-20260521-thunderomlx-anthropic-cache-hit-no-garbled` 已通过：
  - `cloud.anthropic_prefix_cache_enabled=true`
  - ThunderOMLX 8002 PID 51527 健康
  - 日志出现 `Cache HIT ... cached_tokens=256`
  - 顺序和并发压测 `bad_chars=false`
- 剩余缺口：Anthropic response JSON usage 没有透出 cache hit，影响监控、pane 观测和自动调参。

## Goals
1. 定位 AnthropicProxy/Responses API 的 usage 转换路径。
2. 将内部 `output.cached_tokens` 映射到 Anthropic response usage：
   - `cache_read_input_tokens`
   - 如本地 schema 支持，同时保留 `cached_tokens` 或兼容字段。
3. 覆盖非流式和流式 usage 输出（若流式支持 usage chunk）。
4. 增加回归测试，证明 cache hit 时 JSON usage 不再为 0。
5. 不改变缓存策略、模型、服务端口或安全特性。

## Non-Goals
- 不重新调参 cache。
- 不启用 Partial Block Cache / Full Skip / Approximate Skip。
- 不删除 cache。
- 不更换模型。
- 不打印 API key/token。

## Acceptance
- 重复 AnthropicProxy 长 prompt 请求在日志出现 cache hit 时，响应 usage 也出现 `cache_read_input_tokens > 0`。
- pane4 等价中文请求仍 HTTP 200、bad_chars=false。
- 单元或 smoke 测试覆盖 cached_tokens 转换。
- 最终报告写入 `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-anthropic-cache-usage-observability.md`。

