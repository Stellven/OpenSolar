# PRD: 需求拆解与追踪矩阵

epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements`
slice: `requirements`

## 用户原始需求

P0 修复 ThunderOMLX KVTC 接入质量：基于 arXiv 2511.01815 / ICLR 2026 KV Cache Transform Coding 论文，对当前 kvtc_codec.py、kvtc_calibration_store.py、paged_ssd_cache.py 做根因修复。背景：论文方法可信，但当前 ThunderOMLX 移植实现 A/B 失败，真实 Qwen3.6 SSD KV block 的 KVTC decode p95 rel_rmse 达 0.68-0.98、min cosine 低到 0.19/0.72；named prompt cache save 也返回 422 无法抓取 KV。核心假设：当前问题来自实现与接入偏差，不是 KVTC 论文本身。必须完成：1) 论文对齐审计，确认 PCA 维度、校准粒度、sink/recent token bypass、RoPE 处理、K/V 分离、层类型 family 分组、bit allocation budget 是否与论文一致；2) 修复 calibration key，从 per-model 单一校准改成 per-model + tensor_family + shape_signature + layer_type + rope_state 的校准，不允许把 key dim 8192/value dim 128/mamba-like dim 256 混成一个 basis；3) 在 encode 前做 shape/family classifier，非 transformer KV 或混合/不支持 family 必须回退 lz4，不可产出 .kvtc；4) 增加 sink/recent token bypass 和 lossless side-band 存储，默认保留 first sink tokens 与 recent window；5) 增加 reconstruction gate：每个候选 .kvtc 写入前抽样 decode，要求 p95_rel_rmse <= 0.02、min_cos >= 0.999 或按 family profile 配置；否则自动回退 lz4 并记录原因；6) 修复 /v1/cache/prompt/save 抓不到 KV block 的 422 问题或明确禁用该 API 的 misleading 文案；7) 完成 scripts/kvtc_ab_correctness.py 升级为 CI/regression gate，覆盖真实 SSD block、同维 family、混合 family、synthetic outlier、named prompt cache；8) UI 默认仍关闭 KVTC，开启前必须显示最近一次 A/B gate 结果。验收：pytest 通过；真实 Qwen3.6 block A/B 不再失败或自动回退 lz4；不得出现乱码/坏字符；不污染现有主服务 cache；提供 rollback 指令。

## 背景 / Context

ThunderOMLX KVTC 的论文方向被视为可行，但当前接入质量不达标：真实 Qwen3.6 SSD KV block 的 decode 指标显著劣化，且 named prompt cache save 返回 422，导致无法稳定抓取 KV block 做回归验证。本切片只负责把父 Epic 的 P0 问题拆成可追踪、可验收、可派发的需求矩阵，避免后续 Builder 在缺少边界和证据链时直接改核心缓存路径。

## 用户问题 / Problem

当前风险不是单点代码失败，而是论文实现、KV family 识别、校准粒度、降级策略、验证门禁、API 文案与 UI 开关之间存在系统性接入偏差。若不先建立需求追踪矩阵，后续任务容易混淆 K/V shape、误用 basis、产出损坏 `.kvtc`、绕过 A/B gate，或者把尚未证明安全的 KVTC 默认暴露给用户。

## 本切片目标

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## 用户故事 / User Stories

- 作为用户，我需要 KVTC 修复先被拆成明确 outcomes，这样每个实现任务都有可复现验收，而不是泛泛声明“论文已对齐”。
- 作为 Planner，我需要知道哪些事项必须先 root-cause、哪些可以并行、哪些必须阻止 Builder 直接落代码。
- 作为 Builder，我需要每个子任务给出输入文件、风险边界、回退条件和测试证据要求。
- 作为 Evaluator，我需要可逐项检查的 traceability map，确认真实 SSD block、混合 family、named prompt cache 和 UI gate 都被覆盖。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026.epic.md`、`epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 约束 / Constraints

- 不得把本切片当成实现修复；本切片只产出需求拆解、计划输入和追踪矩阵。
- 不得绕过 Planner 直接派 Builder；缺 `plan.md` 或 `task_graph.json` 时不得进入实现。
- 不得把论文可信性等同于移植实现正确性；所有实现任务都必须回到真实 block 或明确 synthetic 覆盖说明。
- 不得污染主服务 cache；所有 KVTC 启用路径必须保留 lz4 回退和 rollback 指令。
- UI 默认仍关闭 KVTC，除非最近一次 A/B gate 结果可见且达标。

## 验收标准

- 每个 outcome 都有验收标准和风险边界
- 明确哪些工作不能直接派 builder
- 生成父 epic 到子 sprint 的 traceability map

## 风险 / Risks

- 如果需求矩阵缺少 tensor family / shape_signature / rope_state 维度，后续实现会继续把不兼容 KV 混用同一 basis。
- 如果缺 reconstruction gate，坏 `.kvtc` 可能写入缓存并造成乱码或不可恢复结果。
- 如果 named prompt cache 422 未被单独追踪，真实 KV block A/B 可能继续缺数据。
- 如果 UI gate 未被追踪，尚未验证的 KVTC 可能被用户误开。

## 开放问题 / Open Questions

- 父 Epic 中哪些真实 Qwen3.6 block 样本可作为稳定 CI fixture，哪些只能做本地回归？
- `/v1/cache/prompt/save` 的 422 是 API schema、鉴权、路径绑定还是 KV capture 时机问题？
- family profile 是否需要为 key/value/mamba-like tensor 分别设置阈值，还是先统一使用 p95_rel_rmse <= 0.02、min_cos >= 0.999？
- UI 最近一次 A/B gate 结果应读取现有测试产物，还是新增 manifest？

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements.design.md`
- `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements.plan.md`
- `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements.task_graph.json`
- `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements.handoff.md`
- `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements.eval.md` 或 `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements.eval.json`

## 架构交接 / Planner Handoff

- Planner 必须先读取父 Epic、traceability 和本 PRD，产出 `design.md`、`plan.md`、`task_graph.json`。
- `task_graph.json` 必须显式表达依赖：需求矩阵 -> 论文对齐审计 -> calibration key/family classifier -> reconstruction gate -> named prompt cache -> CI gate -> UI gate。
- Builder 只能接收可独立验收的子任务，不得把 S01 当作全量实现任务。
- Evaluator 必须检查父 Epic 到子 sprint 的 traceability map，确认每个用户要求都有下游 owner、验收证据和 stop rule。
- 如果 Planner 发现父级 traceability 缺项，必须回写未闭环项，不得直接标记 planning complete。
