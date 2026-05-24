# Handoff — S01 Requirements & Traceability

> Sprint: `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements`
> Epic:   `epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn`
> Slice:  `requirements`
> Knowledge Context: solar-harness context inject used

## 1. 上游依赖（Upstream Dependencies）

| Item | Status | Where |
|---|---|---|
| User intake | ✅ committed | `/Users/lisihao/Knowledge/_raw/solar-harness/intake/20260524t132500z-knowledge-wide-thunderomlx-semantic-layer.md` |
| Epic decomposition | ✅ created | `epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn.epic.{md,json}` + `.traceability.json` + `.task_graph.json` |
| **Parallel sprint reuse baseline**: `sprint-20260524-105859` (knowledge-ingest-dispatcher) | ✅ status=passed, lib files + sqlite registry **实证存在** | `~/.solar/harness/lib/knowledge_*.py` (9 files), `~/Knowledge/_registry/knowledge_ingest.sqlite` (10 tables) |
| Adjacent: `sprint-20260524-134738` (Skill/MCP/Capsule) | ✅ status=passed | adapter 注册策略可参考；非强依赖 |
| Adjacent: `sprint-20260524-133807` (prerequisite schema) | ⚙ active in builder | Epic 子 sprint 之间 prerequisite 应使用其新结构化 schema |

**Planner 决断**：S02-S05 必须把 105859 deliverables 当作 **baseline**，禁止重造；具体哪些 outcomes 是 reuse / extend / net-new，见 `outcomes_matrix.md` 与 `traceability.json`。

## 2. 下游影响（Downstream Impact）

本切片输出会被以下 Epic 子 sprint 直接消费：

| 下游 sprint | 消费什么 | 用法 |
|---|---|---|
| `s02-architecture` | `outcomes_matrix.md` 全表 + `traceability.json` | 把 14 outcomes 中标 `S02` owner 的（O5/O9/O10/O11/O13）转成 architecture decisions + interface contracts |
| `s03-core-runtime` | `traceability.json` 中 owner=S03 的 outcomes | 实现 O1/O8/O9/O11/O13/O14；O5 等 S02 定名后再改 |
| `s04-orchestration-ui` | `traceability.json` 中 owner=S04 的 outcomes | 实现 O3/O10/O12 的 dashboard + UI |
| `s05-verification-release` | `traceability.json` + Risk Register + "不能直派 builder" 子表 | 端到端实测；**必须不信任 105859 status=passed**，build-from-zero 跑测试 |

**关键约束**：下游 sprint 在写自己 task_graph.json 时，建议 prerequisites 用 sprint-20260524-133807 升级后的结构化 schema：

```jsonc
{
  "sprint_id":"sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements",
  "required_status":"passed"
}
```

## 3. 未闭环项（Unclosed Items / Risks）

| ID | 项 | 严重 | 谁来收尾 |
|---|---|---|---|
| U1 | **命名冲突** `extracted.md` (105859 已用) vs `semantic.md` (intake 要求) | high | **S02 architect** 必须决断 + 给迁移方案 |
| U2 | **schema 字段缺 latency / token_cost / model fingerprint** | med | **S02 architect** 决定 in-place add column vs schema v2 |
| U3 | **query grounding D9** 在 105859 显式 deferred；intake hard req #10 要求实现 | high | **S04 orchestration-ui** 写 grounding hook + **S05** 实测 |
| U4 | **5 类缺失 adapter**: YouTube transcript（迁移）/ GitHub trends / PDF/manual / accepted-sprint / Solar artifact | high | **S03 core-runtime** 实施 + **S02** 先定 adapter strategy |
| U5 | **状态机缺 EXTRACT_FAILED_RETRYABLE / DONE_RAW_ONLY_WARN** （intake 列出但 105859 未实现） | med | **S02** 决断（独立 state vs 合并 VALIDATION_FAILED）+ **S03** 实施 |
| U6 | **idempotency dedupe key 不含 extractor identity** (prompt_template_id + schema_version + model) | med | **S03** 加 extractor identity tuple |
| U7 | **105859 status=passed 但未端到端实测** （所有 9 个 lib + sqlite 落地，但本 sprint 未跑测试验证 contract 全 pass） | high | **S05** 强制 end-to-end 实测，不接受 status=passed 作为证据 |
| U8 | **Tech Hotspot report 优先 semantic md** （intake §Acceptance/Reports 行）未在 105859 改造 | med | **S04** 把 Tech Hotspot reader 切到优先 extracted layer |
| U9 | **dashboard UI**（intake §Acceptance/Observability） | med | **S04** new UI surface |
| U10 | Epic close 时 `parent-check` 必须验证 5 个 child sprint 全 passed，不能任何一个 status flag 单方面声明完成 | high | **S05** 跑 `solar-harness epic-decomposer validate-epic` |

## 4. Sprint Ready-for-Activation Checklist (for Epic Activation Scanner)

- [x] S01 design.md 写完
- [x] S01 plan.md 写完
- [x] S01 task_graph.json 写完且 `graph-scheduler validate` 通过
- [x] S01 planning.html 写完并 register
- [x] S01 handoff.md 写完（本文件，含上游 / 下游 / 未闭环三段）
- [ ] S01 outcomes_matrix.md（**S2 builder 产出**）
- [ ] S01 traceability.json（**S2 builder 产出**）
- [ ] S01 test_report.md（**S3 builder 产出**）
- [ ] S01 eval.md + review_decision.yaml（**S4 solar-harness 产出**）
- [ ] S01 status=passed → Epic scanner 会自动激活 S02_architecture

## 5. Planner 留给 Builder 的简要 brief

**S2 builder**：你的活就是把我 design.md §3 的 14 行表 **原样** 渲染到 `outcomes_matrix.md`（人读）+ `traceability.json`（机器读）。**不要扩写**，**不要"自由发挥"**。schema 在 plan.md §S2-Output-Contract 已固定。

**S3 builder**：跑 plan.md §Verification 4 段命令，把每段的命令 + exit code + stdout 摘要写进 `test_report.md`。105859 的 9 个 lib + sqlite 实证检查是**强制项**，不能跳。

**S4 solar-harness**：你的活是**反 scope leak / 反幻觉**：traceability JSON 里任何标 `epic-net-new` 的 outcome，必须真的在 105859 design / lib / sqlite 里找不到；任何标 `reuse-from-105859` 的，必须真的能 grep 到。
