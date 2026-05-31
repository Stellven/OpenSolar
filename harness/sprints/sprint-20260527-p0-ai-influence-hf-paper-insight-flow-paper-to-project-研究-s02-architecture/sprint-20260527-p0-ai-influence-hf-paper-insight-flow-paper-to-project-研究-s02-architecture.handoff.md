# Handoff — sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture

## Summary

- A1 `architecture.md`: 10-section architecture slice covering 10-layer topology, control/data plane split, 5 decisions D1-D5, and S03/S04 relay package.
- A2 `data_models.md`: markdown-only data model contract covering 6 core entities, weight profile tables, 4-channel knowledge store indexes, 4 graph tables, dedup priority, lifecycle policy, and storage estimate.
- A3 `interfaces.md`: markdown-only interface contract covering collector/canonicalizer/enricher/classifier/scoring+packet/reasoning+resonance/compiler+store+watch+cli+config signatures.
- A4 `open_questions_resolutions.md`: OQ-01..OQ-05 all resolved with explicit decision/rationale/alternatives/risks/owner/fallback.
- A5 `traceability.json`: aggregated 5 decisions, 5 OQ resolutions, module inventory, schema inventory, and S03/S04/S05 kickoff package.

## Artifact Paths

- `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture.architecture.md`
- `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture.data_models.md`
- `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture.interfaces.md`
- `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture.open_questions_resolutions.md`
- `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture.traceability.json`
- `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s02-architecture.handoff.md`

## D1-D5 Decision Summary

- D1: 默认持久化引擎为 SQLite WAL + JSON 字段；PG 迁移保留 in scope。
- D2: 5 provider 各自限流、熔断和指数退避，不采用统一共享限流。
- D3: 高推理复用现有 Browser Agent 路径，不新建 browser runtime。
- D4: 36 权重按 profile 存在 YAML，支持 hot-reload，缺失时回退到硬编码默认值。
- D5: raw 同步写盘后异步触发 extracted/QMD/graph，失败时进入 fallback file + ATLAS repair。

## OQ-01..OQ-05 Resolution Summary

- OQ-01: 存储引擎选 SQLite WAL，PG 留作规模升级路线。
- OQ-02: 每个 provider 明确速率、熔断阈值与退避策略。
- OQ-03: 高推理通过 gstack `browser.browse` 复用 ChatGPT 5.5 Thinking high。
- OQ-04: 权重存储在 `hf_paper_insight_weights.yaml`，按 profile hot-reload。
- OQ-05: Knowledge ingest 顺序为 raw sync → derived async，失败走文件缓冲与修复。

## S03 Kickoff Checklist

- 实现 L0-L10 模块骨架并对齐 A3 接口签名。
- 落地 6 核心实体、weight profile 表、4 graph 表与 4 通道存储索引。
- 实现 5 provider 限流、熔断和退避。
- 实现 Browser Agent reasoning path 与 fallback。
- 实现 packet gate / insight gate / resonance gate 的 runtime 判定。

## S04 Kickoff Checklist

- 对接 CLI 10 flags 与 status 视图。
- 接入 Config 5 子段与 hot-reload。
- 把 provider health / quality gate / queue state 投到 orchestration-ui。
- 保留 `HF ranking 只是 attention signal` 的 UI/CLI 约束提示。

## S05 Kickoff Checklist

- 验证 D1-D5 与 OQ-01..OQ-05 是否被 runtime 真实现。
- 验证存储估算、降级路径和 Browser Agent fallback 的经验数据。
- 验证 packet/raw 边界未被破坏，禁止 raw list 直接送高模型。

## Residual Risks

- Browser Agent 高推理路径仍缺 runtime 实测证据。
- 存储估算与 provider 限流目前是 architecture contract，不是压测结论。
- graph rebuild / stale enrichment 策略仍需 S05 验证实际副作用。

## Explicit Constraints

- 禁止把 HF ranking 当研究结论。
- 禁止把 raw paper list 直接喂给高模型，必须先经过 Packet Gate。
- 禁止在本 sprint 中夹带 Python / shell / YAML 实施代码作为验收替代物。
