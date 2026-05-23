# PRD — ThunderOMLX 知识抽取缓存基准

## 背景

当前已经证明 Mac mini 上的 ThunderOMLX 可以通过无头 multi-task tmux worker 完成知识抽取，并在同一批文档复跑时出现高前缀 KV cache 命中。单次冷/热对比不足以作为稳定性能结论，需要用小样本矩阵验证缓存命中率口径、延迟收益、乱码风险和热缓存路径。

## 目标

在 Mac mini 上用 ThunderOMLX/Qwen3.6 执行知识抽取缓存基准：

- 3 种文档长度：short、medium、large。
- 每种长度 3 次冷跑 + 3 次热跑。
- 记录 wall latency、input/output tokens、cache_read_input_tokens、cache_creation_input_tokens、cache_hit_ratio、bad_chars。
- 输出 p50/p95、热跑平均 cache hit、p50 speedup。

## 非目标

- 不重启 ThunderOMLX。
- 不删除 cache。
- 不启用 Partial Block Cache、Full Skip、Approximate Skip。
- 不暴露 API key/token。
- 不用 Claude/Gemini 执行粗活。

## 验收

- `thunderomlx-benchmark` profile 为 `backend=command` 且 `model=thunderomlx`。
- 报告存在：`/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-knowledge-cache-benchmark.md`。
- JSON 结果存在：`/Users/lisihao/.solar/harness/run/thunderomlx-knowledge-cache-benchmark/results.json`。
- 每档长度至少 6 行结果，合计至少 18 行。
- 所有行 `bad_chars=false`。
- 热跑行必须记录 `cache_read_input_tokens` 与 `cache_hit_ratio`。
- 报告必须明确说明：cache_hit_ratio 是前缀 KV block 命中率，不等同于端到端成本节省率。

