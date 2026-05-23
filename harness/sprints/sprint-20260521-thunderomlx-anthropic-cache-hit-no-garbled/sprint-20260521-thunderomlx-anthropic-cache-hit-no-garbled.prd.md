# PRD: ThunderOMLX AnthropicProxy Cache Hit Without Garbled Output

## Summary
把 AnthropicProxy 前缀缓存从“可配置 opt-in”推进到“真实性能收益可用”：受控开启 `anthropic_prefix_cache_enabled=true`，重启 Mac mini ThunderOMLX 8002 服务，验证 pane4/Claude Code 等价路径能够读取 prefix cache，同时不再出现中文乱码、多语言 token 流污染或坏字符。

## Background
- 上一 sprint 已完成代码修复：
  - `src/omlx/settings_v2.py` 增加 `cloud.anthropic_prefix_cache_enabled: bool = False`
  - `src/omlx/server.py` 将 AnthropicProxy 的 `disable_prefix_cache=True` 硬编码改为读取 settings
  - 单元测试 `tests/test_anthropic_prefix_cache.py` 8/8 pass
- 当前默认仍为 disabled，因此性能收益尚未释放。
- 历史注释说明：该路径曾因 Claude Code haiku/sonnet 重叠请求导致 corrupted multilingual token streams，被临时禁用 prefix cache。

## Goals
1. 受控开启 AnthropicProxy prefix cache，并重启 ThunderOMLX 8002 服务。
2. 用 pane4 等价请求验证 `cache_read_input_tokens > 0`。
3. 构造中文、英文、代码、混合语言、并发/重叠请求用例，验证 `bad_chars=false`、无乱码、多语言 token 流不串线。
4. 如果启用后复现乱码，定位根因并修复，不能只关闭开关逃避。
5. 输出最终中文报告，给出 before/after 性能、cache hit、乱码检测和回滚路径。

## Non-Goals
- 不启用 Partial Block Cache。
- 不启用 Full Skip / Approximate Skip。
- 不更换模型。
- 不使用 Toshiba 盘做写缓存。
- 不打印 API key、token、Claude OAuth 凭据。

## Acceptance
- ThunderOMLX 8002 服务恢复健康，模型仍为 `Qwen3.6-35b-a3b`。
- `~/.omlx/settings.json` 或等效配置中 `cloud.anthropic_prefix_cache_enabled=true` 生效。
- 重复长 system prompt 的 AnthropicProxy 请求至少一次出现 `cache_read_input_tokens > 0` 或日志证明 blocks loaded from cache。
- pane4 等价中文请求 HTTP 200，`bad_chars=false`。
- 并发/重叠请求不出现 corrupted multilingual token streams。
- 如发现乱码，必须提交根因和修复；最终不得以“禁用 cache”作为通过条件。
- 最终报告：`/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-anthropic-cache-hit-no-garbled.md`。

