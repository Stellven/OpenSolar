# Contract — ThunderOMLX 知识抽取缓存基准

## 输入

- Mac mini ThunderOMLX 服务：`http://127.0.0.1:8002`
- 本地映射模型：`Qwen3.6-35b-a3b`
- Anthropic proxy model 名：`claude-3-5-sonnet-latest`
- 源文档：
  - `/Users/lisihao/.solar/harness/run/knowledge-extract-smoke/input/01-multi-task-screen.prd.md`
  - `/Users/lisihao/.solar/harness/run/knowledge-extract-smoke/input/02-multi-task-screen.design.md`
  - `/Users/lisihao/.solar/harness/run/knowledge-extract-smoke/input/03-code-as-harness.contract.md`

## 执行约束

- 必须使用 `preferred_profile=thunderomlx-benchmark`。
- 该 profile 必须是 command backend，不允许走 Claude/Gemini。
- 不得重启 ThunderOMLX。
- 不得删除 cache 目录。
- 不得启用已禁用的不安全缓存特性：Partial Block Cache、Full Skip、Approximate Skip。
- 不得打印 secrets、API keys、tokens。

## 输出

- Markdown 报告：`/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-knowledge-cache-benchmark.md`
- JSON 结果：`/Users/lisihao/.solar/harness/run/thunderomlx-knowledge-cache-benchmark/results.json`
- Handoff：`/Users/lisihao/.solar/harness/sprints/sprint-20260521-thunderomlx-knowledge-cache-benchmark.N1-handoff.md`

## 指标口径

- `cache_hit_ratio = cache_read_input_tokens / input_tokens`
- 该指标只表示前缀 KV block 命中比例。
- 性能收益必须同时看 wall latency、p50/p95、output_tokens、bad_chars。
- 若热跑 `cache_hit_ratio` 高但 wall latency 不降，必须在报告中标为 `warn` 并解释可能原因。

