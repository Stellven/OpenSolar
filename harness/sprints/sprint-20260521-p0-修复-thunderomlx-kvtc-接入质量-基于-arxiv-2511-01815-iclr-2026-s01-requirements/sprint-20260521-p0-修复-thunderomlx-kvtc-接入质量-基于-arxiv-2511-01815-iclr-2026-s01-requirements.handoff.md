# Handoff — S01 Requirements (KVTC 接入质量修复需求矩阵)

sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements`
epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
builder: 建设者化身 (Solar Builder pane)
round: 1
ts: 2026-05-22T05:05:00Z

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-graph (graph-scheduler validate/batches/parent-check), harness-skills (TaskCreate/TaskUpdate)

## 变更文件（write_scope 内，全部为新文件）

- `<sid>.requirements.paper_alignment.md` — N1 论文 ↔ ThunderOMLX 当前实现 7 项 audit 矩阵；下游 owner = S02_architecture。
- `<sid>.requirements.calibration_key.md` — N2 5 维 calibration key BNF + 旧→新迁移 + 回滚指令；下游 owner = S03_core_runtime。
- `<sid>.requirements.family_classifier_bypass.md` — N3 family taxonomy + lz4 fallback 决策表 + sink/recent 默认；下游 owner = S03_core_runtime。
- `<sid>.requirements.reconstruction_gate.md` — N4 抽样 decode 策略 + family-profile 阈值 + 动作链 + log schema；下游 owner = S03 + S05。
- `<sid>.requirements.named_prompt_cache_422.md` — N5 422 复现描述 + 三 root cause + 修/禁用决策树 + 回滚；下游 owner = S04_orchestration_ui。
- `<sid>.requirements.ci_regression_gate.md` — N6 5×3 覆盖矩阵 + CI hook + SLO 阈值 + 失败回归动作；下游 owner = S05_verification_release。
- `<sid>.requirements.ui_default_off_gate.md` — N7 UI 4 状态 state machine + 最近 A/B 数据源 + i18n 文案 + rollback；下游 owner = S04_orchestration_ui。
- `<sid>.requirements.traceability_map.md` — N8 人读对照表（父 epic 8 项 → N1..N7 → 下游 sprint 三层）。
- `<sid>.requirements.traceability.json` — N8 机器读 traceability（schema_version / sprint_id / epic_id / requirements(7) / open_questions(4) / not_in_scope(10) / requirements_blocking_epic(4)）。
- `<sid>.handoff.md` — 本文件。

未触及（合同约束）：ThunderOMLX 源码、`/v1/cache/prompt/save`、UI、`scripts/kvtc_ab_correctness.py`、`epic-….task_graph.json`、`epic-….traceability.json`、`~/.solar/STATE.md`、主服务 cache、live pane。

## Done 定义达成（来自 .contract.md Acceptance + plan.md §10）

1. 每个 outcome 都有验收标准和风险边界：✅ N1..N7 每文件含 Outcome / Acceptance Matrix / Risk Boundary / Stop Rule 段落。证据：plan §5 步 C 自检 PASS。
2. 明确哪些工作不能直接派 builder：✅ N8 §5 (Not in Scope) 与 traceability.json `not_in_scope` 列 10 条；N8 §8 builder_forbidden 聚合 9 条。
3. 生成父 epic 到子 sprint 的 traceability map：✅ N8 traceability_map.md §1 三层对照表 + traceability.json `requirements`（7 条）+ `requirements_blocking_epic`（S02..S05 4 条 queued 占位）。

## 验证方法（已执行）

| 步骤 | 命令 | 结果 |
|------|------|------|
| A. DAG schema | `solar-harness graph-scheduler validate --graph <s01>.task_graph.json` | `{"ok": true, "node_count": 8, "errors": [], "warnings": []}` |
| B. ready batch | `solar-harness graph-scheduler batches --graph <s01>.task_graph.json --max-parallel 3` | batch_count=3：[N1,N2,N3] / [N4,N5,N6] / [N7]；N8 在 W1 全 passed 后 ready |
| C. 段落自检 | 对每个 `<sid>.requirements.*.md` grep 7 段（Outcome/Maps to PRD/Acceptance Matrix/Risk Boundary/Stop Rule/Owner Sprint Brief/Acceptance Evidence Plan） | 7 个 N 文件全部 OK |
| D. JSON schema | python3 断言 `requirements==7 and open_questions and not_in_scope and requirements_blocking_epic and schema_version and sprint_id and epic_id` | OK；requirements=7 / open_questions=4 / not_in_scope=10 / requirements_blocking_epic=4 |
| E. parent-check | `solar-harness graph-scheduler parent-check --graph <epic>.task_graph.json` | `ok=true, ready=false, node_count=5`；缺 gate = S01..S05 全未 passed（预期） |
| F. context inject | `solar-harness context inject --query ...` | mirage degraded → qmd/obsidian/solar_db fallback；已记录到所有 N 文件的 knowledge_context |

## 备注（给规划者 / 审判官）

- 本 sprint 是文档矩阵，禁止真实运行 pytest / ab_correctness / HTTP 调用 / 改源码（与 design §0、plan §6 一致）。任何"修复 ThunderOMLX"动作在 S03..S05 阶段，本节点不能执行。
- N1 audit 表的"ThunderOMLX 当前位置"列保留 `[TBD-S02 read]` 占位，按 design §1 接力，由 S02 在架构阶段通过实际读源码填表；本节点禁止替代该 verification（避免 MEMORY 中"禁止张口就来"教训复发）。
- OQ3 / OQ4 是 PRD §"开放问题" 第 3/4 条；OQ4 已 tentatively_resolved（首选复用 N6 artifact），OQ3 首版用统一阈值并预留 profile 槽位。其余 OQ1 / OQ2 留给 S05 / S04 在自身 sprint 决定。
- N5 的修/禁用决策树两支必须都保留；S04 在 staging 复现后选定一支即可，但禁止默认走"修"。
- 父 epic.traceability.json 中所有子 sprint 当前 status=queued，符合 epic_decomposer 期望；本 sprint passed 后由 epic_decomposer 自动激活 S02_architecture。

## 已完成

- 8 个矩阵文件 + 1 个 handoff 文件全部写入 `~/.solar/harness/sprints/`。
- plan §5 中 A / B / C / D / E 五条验证命令全部 PASS。
- traceability.json 含 schema_version / sprint_id / epic_id / requirements(7) / open_questions(4) / not_in_scope(10) / requirements_blocking_epic(4) / builder_forbidden_aggregate / evidence_collection_plan。
- PRD §"开放问题" 4 条 100% 复现到 traceability.json `open_questions`（OQ1..OQ4）+ traceability_map.md §4。
- 父 epic 8 项用户要求 1:1 映射到 N1..N7 共 7 节点 + N8 join 聚合（traceability_map.md §1）。
- N8 acceptance 的"禁止 builder 直接派发清单 6 项"（kvtc_codec.py / kvtc_calibration_store.py / paged_ssd_cache.py / /v1/cache/prompt/save / UI / scripts/kvtc_ab_correctness.py）显式落在 §5 与 traceability.json `not_in_scope`。

## 已验证（本 sprint 边界内）

- DAG schema (validate) → ok。
- ready batch (3 批) → 与 plan §1 表一致。
- 每节点 7 段段落 grep → 全 OK。
- traceability.json 结构断言 → OK。
- 父 epic parent-check → ok=true，缺 gate 列表与 epic 状态一致。

## 未验证（下游 sprint 责任，本节点禁止替代）

- N1 audit 表 [TBD-S02 read] 占位项 → 由 S02 在 design.md 中填 ThunderOMLX 当前位置 / gap。
- N2 / N3 / N4 acceptance 单元测试 → 由 S03 在 core-runtime 阶段实施 + pytest 运行。
- N5 staging 复现 422 → 由 S04 在 orchestration-ui 阶段执行（本 sprint 禁止真调 HTTP）。
- N6 stable-ci 15 fixture 物理拉取 → 由 S05 在 verification-release 阶段实施。
- N7 UI 4 状态 e2e 截图 → 由 S04 在 staging 跑（本 sprint 禁止改 UI）。
- 真实 Qwen3.6 block A/B 修复后 p95_rel_rmse ≤ 0.02 / min_cos ≥ 0.999 → S05 final regression。

## 风险

- mirage 知识库降级 → 论文引用源仍依赖 qmd/obsidian/solar_db 联合；若后续再降级，N1 论文章节号引用可能需 S02 复核。
- N5 staging 复现 422 时可能发现 root cause 不在 H1/H2/H3 中（例如 500/404），需回写 N5 acceptance 表；本 sprint 已留 Stop Rule 强制回写。
- 真实 Qwen3.6 block 当前 p95_rel_rmse 0.68-0.98 表明 calibration 极度污染；S03 实施 N2 新 key 后若 calibration sample 不足，需 N3 family classifier 大比例 fallback lz4，主服务延迟会上升。
- N6 stable-ci fixture 体积约束（每个 ≤ 100 MB）可能在真实 Qwen3.6 32B block 上紧张，S05 实施时若超限需走 `scripts/fetch_kvtc_fixtures.sh` 外部 host。
- UI 4 状态 state machine 中 `enabled → blocked_by_gate_fail` 阈值（1% / 5min）尚未在生产观测中校准；S04 上线后需 1-2 周观察是否过敏感。

## 后续待办（给协调器 / 审判官 / 下游 sprint）

1. **本 sprint**: 协调器将状态从 `active/planning_complete/builder_main` 推到 `reviewing/builder_done/evaluator`，等审判官评估。
2. **审判官**: 跑 `solar-harness session evaluate sprint-20260521-…-s01-requirements --json`，按 contract.md acceptance + plan §5 验证清单做评审；若 FAIL 必须明示哪条 acceptance / 哪个文件 / 哪段段落。
3. **S01 passed 后**: 由 epic_decomposer 自动激活 S02_architecture sprint；S02 必读 N1 + N8 然后产出 design.md。
4. **后续 S03/S04/S05** 按 epic.task_graph.json 的依赖关系顺序激活，每个 sprint 在自身的 builder_forbidden / Acceptance Evidence Plan 范围内执行。
5. **epic 关闭门禁**: traceability.json `requirements_blocking_epic` 中 S02..S05 全部进入 passed 状态前，epic 不许标 done（呼应 activation_policy.passed_child_statuses）。
