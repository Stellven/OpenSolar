# PRD: ThunderOMLX Prompt Cache API and Cache Advisor Repair

## Summary
Repair the remaining safe cache optimization blockers for ThunderOMLX + Qwen3.6 on the Mac mini. The current stable runtime already uses RAID0 paged SSD cache, 8GB RAM hot cache, four-pane prewarm, and `initial_cache_blocks=256`. This sprint must not re-enable partial block cache, full skip, or approximate skip.

## Problem
Two optimization paths were tested and blocked:

- Prompt Cache API exists at `/v1/cache/prompt/save|load|list|delete`, but `save` returns HTTP 422 for both pane4 system prompt and long knowledge-extraction prompt because KV cache capture cannot find persisted SSD blocks.
- `thunderomlx_cache_advisor_report.py` fails with duplicate `libomp.dylib` initialization, so the cache advisor cannot be used as a safe automatic reporting lane.

## Goals
- Make Prompt Cache API save/load work for stable long prompts without enabling unsafe cache skip features.
- Determine whether loaded named prompt caches can be consumed by `chat/completions`; if not, implement the minimal explicit request contract or document the gap with tests.
- Fix or isolate Cache Advisor so it runs without `KMP_DUPLICATE_LIB_OK=TRUE`.
- Preserve current stable pane4 behavior: `base_url_host=127.0.0.1:8002`, `bad_chars=false`, and four-pane prewarm cached token thresholds.

## Non-Goals
- Do not re-enable partial block cache.
- Do not re-enable full skip or approximate skip.
- Do not move cache writes to Toshiba.
- Do not print or persist auth tokens.
- Do not change the model from `Qwen3.6-35b-a3b`.

## Acceptance
- Prompt Cache API regression test demonstrates save/list/load for a long knowledge-extraction prompt.
- The implementation explains and verifies how a loaded named prompt cache is reused by inference, or clearly marks it unsupported with a follow-up contract.
- Cache Advisor report runs successfully without duplicate OpenMP runtime workaround.
- API smoke passes for uppercase and lowercase model names.
- Chinese output has `bad_chars=false`.
- Four-pane prewarm still reports pane0-2 `cached_tokens >= 1280` and pane4 `cached_tokens >= 1536`.
- Current safe cache config remains: RAID0 SSD cache, 8GB hot cache, `initial_cache_blocks=256`, unsafe skip features disabled.

## Evidence Inputs
- `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-four-pane-prewarm-20260521T013326Z.json`
- `/Users/lisihao/.solar/harness/scripts/thunderomlx_start_8002.sh`
- `/Users/lisihao/ThunderOMLX/src/omlx/server.py`
- `/Users/lisihao/ThunderOMLX/src/omlx/cache/prompt_cache_manager.py`
- `/Users/lisihao/.solar/harness/scripts/thunderomlx_cache_advisor_report.py`

## 背景 / Context
Mac mini 上 ThunderOMLX + Qwen3.6 的稳定运行时已使用 RAID0 paged SSD cache、8GB RAM hot cache、四 pane prewarm、`initial_cache_blocks=256`。在此基础上，仍有两条**安全**的 cache 优化路径被阻塞，需修复——但本 sprint 绝不可重新启用 partial block cache / full skip / approximate skip。

被阻塞的两条路径：
- Prompt Cache API（`/v1/cache/prompt/save|load|list|delete`）存在，但 `save` 对 pane4 system prompt 与长 knowledge-extraction prompt 都返回 HTTP 422，因为 KV cache capture 找不到持久化的 SSD blocks。
- `thunderomlx_cache_advisor_report.py` 因 `libomp.dylib` 重复初始化失败，导致 cache advisor 无法作为安全的自动报告通道使用。

## 用户故事 / User Stories
- 作为 Mac mini 运维者，我希望对稳定的长 prompt 能成功 save/load 命名 prompt cache，而无需开启不安全的 skip 特性。
- 作为运维者，我希望 Cache Advisor 报告能直接运行，不依赖 `KMP_DUPLICATE_LIB_OK=TRUE` 这类 OpenMP workaround。
- 作为审计者，我需要回归测试与 smoke 证据，证明改动后 pane4 行为与四 pane prewarm 阈值仍然稳定、中文输出无乱码。

## 功能需求 / Requirements
- 让 Prompt Cache API 的 save/load 对稳定长 prompt 工作，且不启用任何不安全 cache skip 特性。
- 判定 loaded 命名 prompt cache 能否被 `chat/completions` 消费；若不能，实现最小显式请求契约，或用测试明确记录该 gap。
- 修复或隔离 Cache Advisor，使其无需 `KMP_DUPLICATE_LIB_OK=TRUE` 即可运行。
- 保持稳定 pane4 行为：`base_url_host=127.0.0.1:8002`、`bad_chars=false`、四 pane prewarm 的 cached token 阈值。
- 证据输入（只读参考）：four-pane prewarm JSON、`thunderomlx_start_8002.sh`、`server.py`、`prompt_cache_manager.py`、`thunderomlx_cache_advisor_report.py`。

## 约束 / Constraints
- 不重新启用 partial block cache / full skip / approximate skip。
- 不把 cache 写入移到 Toshiba 盘。
- 不打印或持久化 auth token。
- 不更换 model（保持 `Qwen3.6-35b-a3b`）。
- 保持当前安全 cache 配置：RAID0 SSD cache、8GB hot cache、`initial_cache_blocks=256`、不安全 skip 特性 disabled。
- 所有产出不放入 `/tmp`（STATE.md 全局约束）；不破坏现有 API 接口。环境 macOS arm64 (Mac mini M4)。

## 风险 / Risks
- 为修 422 而误改 KV capture 逻辑，可能波及稳定推理路径（高）——局部修复，回归测试覆盖 pane0-2/pane4 阈值。
- 隔离 OpenMP（libomp 重复初始化）若用 `KMP_DUPLICATE_LIB_OK` 掩盖，可能埋下数值/崩溃隐患（中）——优先定位重复加载根因（duplicate libomp 链接），而非设环境变量绕过。
- loaded 命名 cache 实际不被 inference 复用，导致“成功 save 但无收益”（中）——需用测试验证消费链路或明确标记 unsupported。
- 探针/报告误打印 auth token 进日志（中）——证据统一脱敏。

## 开放问题 / Open Questions
- `save` 返回 422 的根因是 KV capture 找不到 SSD blocks——是持久化时机问题，还是 block 路径/命名约定问题？（待 Builder 探测 `prompt_cache_manager.py`）
- loaded 命名 prompt cache 是否有被 `chat/completions` 消费的现成契约，还是需要新增显式请求字段？
- libomp 重复初始化来自哪个依赖（mlx / numpy / torch 链）？是否能在打包/链接层根治而非运行时绕过？

## 架构交接 / Planner Handoff
- handoff_to: planner
- 建议拆分：(1) 定位并修复 Prompt Cache `save` 422（KV capture/SSD block）；(2) 验证或实现 loaded cache 的 inference 消费契约；(3) 根治 Cache Advisor 的 libomp 重复初始化（不依赖 KMP workaround）；(4) 回归/smoke（save/list/load、大小写 model 名、bad_chars=false、四 pane prewarm 阈值）；(5) 最终报告。
- 复用现有 server.py / prompt_cache_manager 接口，避免改动稳定路径。
- 验收锚点见上文 Acceptance。
- 状态纪律：PM 保持 status=drafting，不修改 .finalized；Planner 接手生成 sprint contract。

