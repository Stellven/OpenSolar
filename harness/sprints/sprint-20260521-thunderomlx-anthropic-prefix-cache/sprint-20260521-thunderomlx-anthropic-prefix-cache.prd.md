# PRD: ThunderOMLX AnthropicProxy Prefix Cache Repair

## Summary
修复 Mac mini ThunderOMLX 中 AnthropicProxy 路径绕过 Block Prefix Cache 的问题，让第二个四分屏第四 pane 这类 Claude/Anthropic 兼容请求能够复用稳定 system prompt/persona 前缀缓存，降低 prefill 开销。

## Background
- 当前 ThunderOMLX 8002 服务使用 Qwen3.6-35b-a3b、RAID0 SSD cache、8GB RAM hot cache。
- 原生 OpenAI/Qwen 请求路径已能看到前缀缓存收益，热命中吞吐约为冷请求的 4.5x。
- 审计报告显示 AnthropicProxy 路径日志存在 `Prefix cache disabled for request ... using full prefill`，导致 pane4 兼容路由的重复长 prompt 缓存命中率接近 0%。
- 这不是乱码根因，但会显著增加第二个四分屏第四 pane 的首 token 延迟和重复 prefill 成本。

## Goals
1. 定位 AnthropicProxy 禁用 prefix cache 的代码条件和调用链。
2. 在不启用 unsafe cache 特性的前提下，让 AnthropicProxy 安全复用已有 Block Prefix Cache。
3. 对 pane4 等价 Anthropic 请求做 before/after 验证，记录 cached_tokens、prefill time、bad_chars。
4. 生成中文报告，明确收益、风险、回滚方式和仍未解决问题。

## Non-Goals
- 不重新启用 Partial Block Cache。
- 不启用 Full Skip / Approximate Skip。
- 不改模型、量化、上下文窗口或 hot cache 大小。
- 不打印 API key、token、请求正文中的敏感内容。
- 不把临时 workaround 当作最终修复。

## Acceptance
- AnthropicProxy 路径不再无条件输出 `Prefix cache disabled ... using full prefill`。
- 重复 Anthropic/Claude 兼容请求能看到 prefix cache 命中证据，或报告明确说明代码层阻塞。
- pane4 等价 smoke 通过：中文输出正常、bad_chars=false、HTTP 200。
- unsafe cache features 保持 disabled。
- 产出最终报告：`/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-anthropic-prefix-cache-repair.md`。

