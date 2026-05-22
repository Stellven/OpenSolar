# PRD: 核心实现与数据模型

epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s03-core-runtime`
slice: `core-runtime`

## 用户原始需求

P0 修复 ThunderOMLX KVTC 接入质量：基于 arXiv 2511.01815 / ICLR 2026 KV Cache Transform Coding 论文，对当前 kvtc_codec.py、kvtc_calibration_store.py、paged_ssd_cache.py 做根因修复。背景：论文方法可信，但当前 ThunderOMLX 移植实现 A/B 失败，真实 Qwen3.6 SSD KV block 的 KVTC decode p95 rel_rmse 达 0.68-0.98、min cosine 低到 0.19/0.72；named prompt cache save 也返回 422 无法抓取 KV。核心假设：当前问题来自实现与接入偏差，不是 KVTC 论文本身。必须完成：1) 论文对齐审计，确认 PCA 维度、校准粒度、sink/recent token bypass、RoPE 处理、K/V 分离、层类型 family 分组、bit allocation budget 是否与论文一致；2) 修复 calibration key，从 per-model 单一校准改成 per-model + tensor_family + shape_signature + layer_type + rope_state 的校准，不允许把 key dim 8192/value dim 128/mamba-like dim 256 混成一个 basis；3) 在 encode 前做 shape/family classifier，非 transformer KV 或混合/不支持 family 必须回退 lz4，不可产出 .kvtc；4) 增加 sink/recent token bypass 和 lossless side-band 存储，默认保留 first sink tokens 与 recent window；5) 增加 reconstruction gate：每个候选 .kvtc 写入前抽样 decode，要求 p95_rel_rmse <= 0.02、min_cos >= 0.999 或按 family profile 配置；否则自动回退 lz4 并记录原因；6) 修复 /v1/cache/prompt/save 抓不到 KV block 的 422 问题或明确禁用该 API 的 misleading 文案；7) 完成 scripts/kvtc_ab_correctness.py 升级为 CI/regression gate，覆盖真实 SSD block、同维 family、混合 family、synthetic outlier、named prompt cache；8) UI 默认仍关闭 KVTC，开启前必须显示最近一次 A/B gate 结果。验收：pytest 通过；真实 Qwen3.6 block A/B 不再失败或自动回退 lz4；不得出现乱码/坏字符；不污染现有主服务 cache；提供 rollback 指令。

## 本切片目标

实现核心库、状态机、schema、持久化和向后兼容适配层。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026.epic.md`、`epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 核心 API 有单测覆盖
- 旧路径兼容，不破坏现有 wake/dispatch/status
- 状态变更可由元数据或事件重建

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s03-core-runtime.design.md`
- `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s03-core-runtime.plan.md`
- `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s03-core-runtime.task_graph.json`
- `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s03-core-runtime.handoff.md`
- `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s03-core-runtime.eval.md` 或 `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s03-core-runtime.eval.json`
