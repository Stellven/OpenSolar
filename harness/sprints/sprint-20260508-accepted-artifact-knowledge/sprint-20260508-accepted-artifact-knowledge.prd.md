# PRD — Accepted Sprint Artifacts To Knowledge Base

**Source**: Codex PM analysis from user request on 2026-05-08
**Priority**: P1
**Lane**: reliability
**Handoff To**: planner
**Created**: 2026-05-08T07:10:00Z

## 背景 / Context

用户指出：Solar 在开发设计过程中会产出大量高价值内容，包括需求分析、PRD、架构设计、方案设计、实施计划、测试结果、handoff、eval、事件日志等。当前这些产物主要留在 `~/.solar/harness/sprints/`，即使 sprint 已验收 PASS，也不一定稳定进入 Obsidian/Solar 知识库，导致后续查询时无法自动复用“已验收的设计知识”。

## 用户问题 / Problem

Solar 已经能执行 sprint，但“已验收成果 → 长期知识”闭环不完整。尤其是 Symphony/Obsidian/KB 这类系统设计结论，如果只存在于 sprint 文件里，后续 agent 需要靠人工记忆或手动 export/query 才能复用。更严重的是，如果未验收的草稿也进入知识库，会污染事实来源。

## 用户目标 / Goals

- 每个 sprint 只有在 evaluator PASS 并 finalized 之后，才自动生成“验收知识包”。
- 知识包必须包含需求、设计、方案、计划、测试结果、评审结论、变更文件、事件摘要和来源索引。
- 知识包默认脱敏，能进入 `/Users/sihaoli/Knowledge/_raw/solar-harness/accepted/` 并触发 wiki ingest。
- Solar status/server 能显示每个 passed sprint 的知识入库状态。
- 支持回填历史 passed sprint，但必须幂等、不重复、不覆盖用户手写页面。

## 用户故事 / User Stories

- 作为 Solar 操作者，我不需要手动问“要不要 ingest”，每个 PASS sprint 的核心设计会自动进入知识库。
- 作为后续 builder/planner，我查询 Symphony/Obsidian/KB 设计时，能读到验收过的 PRD、架构方案和测试证据，而不是未验收草稿。
- 作为 evaluator，我能看到知识入库前经过脱敏、manifest 幂等、来源可追溯。
- 作为知识库使用者，我能区分 `accepted`、`draft`、`failed`，不会把失败方案当事实。

## 功能需求 / Requirements

- 新增 PASS 后归档器：在 `handle_passed` 或等价 finalized 路径中调用，不阻塞主状态机。
- 归档器生成 accepted artifact markdown，默认写入 `/Users/sihaoli/Knowledge/_raw/solar-harness/accepted/<sid>.accepted.md`。
- 知识包必须包含 PRD、contract、design、plan、handoff/handoff-builder*、eval/eval.json、events、test evidence、changed files、verification summary 的摘要和 source index。
- 默认 redaction：token、Bearer、sk-、api key、env secret、绝对私密路径内容不得原样进入知识库。
- 归档后自动生成 wiki ingest dispatch，或复用 `solar-harness wiki ingest/run-dispatch` 安全路径。
- 写入 status.json 字段：`knowledge_export_status`、`knowledge_export_path`、`knowledge_ingest_dispatch`、`knowledge_exported_at`、`knowledge_ingested_at`、`knowledge_export_error`。
- 提供 `solar-harness wiki export-accepted <sid>` 和 `solar-harness wiki backfill-accepted [--since DATE|--limit N]`。
- 提供测试，覆盖 PASS 才导出、FAIL 不导出、幂等、脱敏、dispatch 生成、状态字段更新。

## 验收标准 / Acceptance Criteria

- A1: passed sprint 触发 accepted artifact export，reviewing/failed/drafting 不触发。
- A2: accepted artifact 至少包含 PRD/contract/design/plan/handoff/eval/events/test evidence/source index 八类内容。
- A3: export 默认 redacted，测试 fixture 中的 `sk-test`, `Bearer x`, `api_key=` 不出现在输出文件。
- A4: 重复运行同一 sid 不产生重复文件，不重复 dispatch；manifest hash 未变则 skip。
- A5: export 后 status.json 有 `knowledge_export_status=exported|ingested|failed` 和路径字段。
- A6: 自动生成 wiki ingest dispatch，目标 vault 为 `/Users/sihaoli/Knowledge`，status 初始为 `dispatched` 或 `queued`。
- A7: `solar-harness wiki backfill-accepted --limit 3 --dry-run` 能列出待回填 passed sprint 且不写真实 vault。
- A8: 回归测试 `bash ~/.solar/harness/tests/test-accepted-artifact-knowledge-sync.sh` 全过。

## 非目标 / Non-Goals

- 不把所有开发中草稿实时写入正式知识库。
- 不覆盖用户手写 Obsidian 页面。
- 不把完整 terminal transcript、secrets、未脱敏 events 原文写入知识库。
- 不要求新外部依赖或云服务。
- 不改变 evaluator PASS/FAIL 判定语义。

## 约束 / Constraints

- 必须只在 PASS/finalized 后进入 accepted 知识流。
- 归档失败不能阻塞 sprint passed/finalized，但必须写状态和事件。
- 单个 accepted artifact 默认不超过 40KB；超出时摘要化并保留 source index。
- 测试必须使用 temp vault/temp sprints，不污染 `/Users/sihaoli/Knowledge`。
- 实现必须兼容已有 `solar-harness wiki export-sprint`。

## 风险 / Risks

- 如果 hook 接太早，会把未验收设计污染知识库。
- 如果只导出 contract/plan，不导出 eval/test evidence，后续无法判断方案是否真的有效。
- 如果没有 manifest，backfill 会重复生成和重复 ingest。
- 如果 status 没有入库状态，用户无法知道知识是否真的被吸收。

## 开放问题 / Open Questions

- accepted artifact 最终是否应生成 Obsidian 正式页面，还是先进入 `_raw/` 再由 wiki-ingest 提炼。
- 历史 passed sprint 回填默认 limit 设多少，避免一次性刷爆 vault。
- 是否把 accepted artifact 同步进 Solar DB FTS，还是依赖当前 KB sprint 的 Obsidian-to-Solar sync。

## 架构交接 / Planner Handoff

Planner 需要把本 PRD 和 contract 转成设计/实施计划，重点确认：

- PASS/finalized 挂点位置。
- accepted artifact schema。
- redaction 与 manifest 策略。
- status/server 可观测字段。
- backfill 的 dry-run/limit/idempotency。

