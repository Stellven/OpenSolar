# Contract: ThunderOMLX AnthropicProxy Prefix Cache Repair

## Scope
远端目标：`lisihao@100.122.223.55`

主要路径：
- ThunderOMLX repo: `/Users/lisihao/ThunderOMLX`
- ThunderOMLX log: `/Users/lisihao/.solar/harness/logs/thunderomlx-8002.log`
- Runtime settings: `/Users/lisihao/.omlx/settings.json`
- Pane env: `/Users/lisihao/.solar/harness/run/pane-env/_8.json`
- Final report: `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-anthropic-prefix-cache-repair.md`

## Safety Rules
- 禁止打印 API key、Anthropic token、Claude OAuth token。
- 禁止启用 Partial Block Cache、Full Skip、Approximate Skip。
- 禁止删除 cache 目录。
- 禁止 kill 进程，除非 contract 后续人工确认。
- 禁止把 `KMP_DUPLICATE_LIB_OK=TRUE` 作为修复。
- 允许改 ThunderOMLX 源码并运行局部测试。
- 允许在必要时给出“需重启服务生效”的说明；默认不要擅自重启。

## Required Evidence
- before/after 日志证据，至少包含是否出现 prefix cache disabled、cache hit/cached_tokens/prefill 指标。
- pane4 等价请求验证，必须经过 AnthropicProxy 路径。
- bad_chars 检查结果。
- unsafe cache feature 状态。
- 回滚说明和修改文件列表。

## Definition of Done (Planner — Quantified)
- [ ] D1: server.py 中 AnthropicProxy 路径的 disable_prefix_cache 不再无条件硬编码 True，改为读取 settings 开关
- [ ] D2: settings_v2.py 新增 anthropic_prefix_cache_enabled 字段，默认 False（安全 fallback）
- [ ] D3: 单元测试 >= 8 条覆盖开关逻辑（默认/opt-in/None fallback），pytest 全通过
- [ ] D4: Pane4 等价 Anthropic 请求 HTTP 200 + bad_chars=false + 中文输出正常
- [ ] D5: 最终中文报告写入 monitor-reports/thunderomlx-anthropic-prefix-cache-repair.md，含 before/after 对比和回滚说明