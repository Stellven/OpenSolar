# PRD: ThunderOMLX P0 Cache Warm + Advisor Metrics

## 背景

Mac mini 上 ThunderOMLX 当前服务运行在 `127.0.0.1:8002`，模型目录为
`/Volumes/toshiba/models/Qwen3.6-35b-a3b`，SSD cache 和 KV offload 已迁移到
`/Volumes/RAID0-Main/omlx-cache/`，hot cache 已提升到 `8GB`。

已验证四分屏 system prompt 手动预热有效：

| pane | prompt_chars | cached_tokens | verify_s | bad_chars |
|---:|---:|---:|---:|---|
| 0 | 3369 | 1280 | 0.602 | false |
| 1 | 3369 | 1280 | 0.600 | false |
| 2 | 3369 | 1280 | 0.601 | false |
| 3 | 3830 | 1536 | 0.568 | false |

当前缺口：预热仍是手动脚本，Cache Tuning Advisor/metrics 未形成启动后的证据闭环。

## 目标

1. 将四分屏 system prompt 预热接入 Mac mini 的 ThunderOMLX / solar-harness 启动流程。
2. 在不自动改参数的前提下，记录 cache hit、cached_tokens、TTFT、bad_chars、unsafe feature guard 状态。
3. 保持当前安全配置：Paged SSD Cache + 8GB RAM Hot Cache + RAID0 KV offload。
4. 明确禁止重新启用 Partial Block Cache、Full Skip、Approximate Skip 主路径。

## 非目标

- 不启用 KVTC 主路径。
- 不启用 Semantic Cache 作为 coding builder 默认响应缓存。
- 不重写 ThunderOMLX 核心调度器。
- 不删除现有缓存目录或诊断文件。
- 不打印或持久化 API token。

## 用户价值

- ThunderOMLX 重启后，四分屏 Builder 的长 system prompt 首轮开销降低。
- 有可审计报告证明缓存命中是否有效，而不是只看服务进程状态。
- 后续调参以数据为准，避免再次引入乱码/空回复风险。

## 验收标准

- 重启 ThunderOMLX 后自动执行四分屏预热，生成 report。
- report 至少包含 pane、prompt_hash、prompt_chars、warm_s、verify_s、cached_tokens、bad_chars。
- `cached_tokens` 对 lab builder prompt 至少达到 1280，对 ThunderOMLX pane 至少达到 1536，除非 prompt 变化并在报告中说明。
- `bad_chars=false`，API HTTP 200，模型名小写 `qwen3.6-35b-a3b` 可用。
- 启动命令仍包含 `--hot-cache-max-size 8GB` 和 RAID0 SSD cache 路径。
- 日志或报告明确显示 partial block cache / full skip / approximate skip 没有重新启用。

Knowledge Context: solar-harness context inject used
