# Handoff — sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s05-verification-release

Builder: 建设者化身 (Mac mini, solar-harness:0.2)
Dispatch: Wake (协调器恢复指令, workflow guard PM+Planner ready → builder DAG)
Submitted: 2026-05-27T12:23:00Z

Harness Modules Used: harness-knowledge (Read STATE/contract/plan/design/status/task_graph/traceability/D0-handoff), harness-graph (verified gate state in task_graph), harness-contracts (handoff-submit), harness-status (round bump).
Knowledge Context: solar-harness context inject **not used** in this rollup round; reused the unified context already injected during the Wave-2..Wave-5 build rounds (2026-05-22). 本轮只做现状盘点 + 文件落证。

## 本轮范围

本 handoff 是 **sprint-level rollup**，不是新代码 round。触发原因：
- 2026-05-22T06:42 `.finalized` 已写
- 2026-05-27T12:20 planner 补齐 plan.md（满足 Workflow Guard 文件清单）
- 2026-05-27T12:22 autopilot 触发 `wake_workflow_guard_to_builder` → 本 dispatch
- 缺口：S05 sprint-level `.handoff.md` 不存在 → coordinator 还认 sprint
  `status=active / round=2 / handoff_to=builder_main`，gate 已 passed 但 sprint 收尾
  未盖章

本轮唯一动作：写出本文件，把已落地的 D0-D6 evidence 全部聚合，让 evaluator 可在
sprint 级别盖章。**未触碰** `src/omlx/*` 或任何 S01-S04 sprint 的 artifact。

## task_graph 节点状态（live, 2026-05-27）

| Node | Status | Gate | depends_on | 备注 |
|---|---|---|---|---|
| D0_ab_correctness_cli_upgrade | reviewing | G_S05_verification_release_passed (passed) | — | handoff_md 已写；node-level status 仍 `reviewing` 是 stale 元数据，gate 已 passed |
| D1_fixtures_15_cells | passed | G_S05... (passed) | D0 | — |
| D2_e2e_tests | passed | G_S05... (passed) | D0 | — |
| D3_ci_workflow | passed | G_S05... (passed) | D0 | — |
| D4_smoke_run_evidence | passed | G_S05... (passed) | D1+D2+D3 | 真跑 evidence at reports/kvtc-ab/20260522T094040Z/ |
| D5_release_docs | passed | G_S05... (passed) | D4 | docs/KVTC_RELEASE.md |
| D6_handoff_traceability_epic_close_prep | passed | G_S05... (passed) | D5 | traceability.json 已写 |
| **Gate G_S05_verification_release_passed** | **passed** | — | — | 2026-05-22T10:38:12Z |

## 变更文件（本 dispatch 仅 sprint-level 文件）

- `/Users/lisihao/.solar/harness/sprints/sprint-20260521-...-s05-verification-release.handoff.md` （本文件，新建）
- `/Users/lisihao/.solar/harness/sprints/sprint-20260521-...-s05-verification-release.status.json` （round bump + reviewing）

引用已落地的 D0-D6 artifacts（前序 round 已写入，本 dispatch 未改）：

仓库 `/Users/lisihao/ThunderOMLX/`：
- `scripts/kvtc_ab_correctness.py` (23 KB, +393/-29，CI-gate mode added，legacy preserved) — D0
- `scripts/fetch_kvtc_fixtures.sh` — D1
- `tests/fixtures/kvtc/manifest.json` (7.8 KB) + 16 `.npz` fixtures — D1
- `tests/regression/test_kvtc_e2e.py` (9.9 KB) + `tests/regression/__init__.py` — D2
- `.github/workflows/kvtc-regression.yml` (8.8 KB) — D3
- `reports/kvtc-ab/20260522T094040Z/ab_correctness.summary.json` — D4
- `reports/kvtc-ab/20260522T094040Z/recon_gate.jsonl` — D4
- `reports/kvtc-ab/20260522T094040Z/per_fixture/*.json` (14 files) — D4
- `docs/KVTC_RELEASE.md` (12 KB) — D5

Solar sprint 区：
- `sprint-20260521-...-s05-verification-release.D0_ab_correctness_cli_upgrade-handoff.md` — D0 node-level handoff
- `sprint-20260521-...-s05-verification-release.traceability.json` — D6 (schema `solar.sprint.verification_release_traceability.v1`)

## 合约 Acceptance 对照

合约三条 acceptance：

1. **"单测、集成测、负控和 activation-proof 全部可复现"** ✅
   - D2 e2e: `./venv/bin/python -m pytest tests/regression/ -v` (CPU ≤60s, 不真起 uvicorn)
   - D0 CLI 自检: 11/11 PASS (T1-T11，验证 schema/flags/exit codes/14 字段)
   - D4 真跑 evidence: 14 fixtures, exit 0, `hard_violations=0`，`p95_rel_rmse=0.01197 < 0.02`，
     `min_cos=0.999076 ≥ 0.999`，1 soft violation
   - 负控：`tests/fixtures/kvtc/named_prompt_cache_001_skip.npz`、
     `synthetic_outlier_001_nan_reject.npz`、`hybrid_family_001_force_kvtc_reject.npz` 全在 manifest
2. **"父 epic 不能在所有 required gate 通过前关闭"** ✅
   - `traceability.json` 含 `epic_required_gates_status`，5 条 S01-S05 gate 状态
   - S01-S04 全 `passed`；S05 在 traceability 中标 `reviewing_pending_evaluator`（与
     本 sprint task_graph 的 `gate=passed` 之间存在文档延迟，由本 handoff 解决）
   - `parent_check_ready=false` —— traceability 显式禁止 epic 在 S05 evaluator 盖章前关闭
3. **"产出最终 handoff/eval/report 并写入知识库 raw"** ⚠️ 部分
   - handoff: 本文件 + D0 node handoff
   - report: docs/KVTC_RELEASE.md (R1..R7 + rollback + ATLAS hook 名 + OQ1/OQ2)
   - **eval.md/eval.json: 当前 sprint 区不存在** — 评估侧档由 evaluator 在本 round
     reviewing 后写入。本 handoff 不伪造 eval。
   - 知识库 raw 写入：`/Users/lisihao/Knowledge/_raw/...` 未在本 sprint write_scope 内显式登记，
     建议 evaluator 与 knowledge-ingest 流水线协调（status 中无 `knowledge_export_status` 字段）

## D4 SLO 实测 vs 阈值

| 指标 | 阈值 (hard) | 阈值 (soft) | 实测 | 判定 |
|---|---|---|---|---|
| p95_rel_rmse | > 0.02 FAIL | > 0.015 WARN | 0.01197 | PASS |
| min_cos | < 0.999 FAIL | < 0.9995 WARN | 0.999076 | PASS (擦边) |
| 混合 family kvtc_accept | > 0 FAIL | — | 0 | PASS |
| stable-ci fixtures | < 12 FAIL | < 14 WARN | 14 | PASS |
| hard_violations | > 0 FAIL | — | 0 | PASS |
| NaN/Inf 未 reject | > 0 FAIL | — | 0 | PASS |
| named_prompt_cache 2xx (env=1) | < 0.95 FAIL | < 0.99 WARN | `disabled_skip` | N/A (env=0) |

总览: **soft_violations=1**, **hard_violations=0**, exit=0。符合 S05 合约判定 PASS。

## Stop Rules 合规

- ✅ 不 mock — D4 实测 exit 0 + 14 fixtures
- ✅ 不超 write_scope — 本 dispatch 只写 sprint-level handoff + status；
  `src/omlx/cache/kvtc_*` / `src/omlx/server.py` 未触碰（plan §6 禁区）
- ✅ 不真加载 Qwen3.6 权重 — manifest fixture 是合成 + mocked
- ✅ 不放宽 0.02 / 0.999 阈值 — 实测 0.01197 / 0.999076 均严格优于阈值
- ✅ 不用乐观词 — 本 handoff 显式列出 `node-level status stale` 与 `latest symlink broken` 风险

## 验证方法（evaluator 可重跑）

```bash
# 1. sprint 三件套文件
test -f /Users/lisihao/.solar/harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s05-verification-release.handoff.md && echo handoff OK
test -f /Users/lisihao/.solar/harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s05-verification-release.traceability.json && echo traceability OK
test -f /Users/lisihao/.solar/harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s05-verification-release.finalized && echo finalized OK

# 2. ThunderOMLX 落地 artifacts
test -f /Users/lisihao/ThunderOMLX/scripts/kvtc_ab_correctness.py && echo D0 OK
test -f /Users/lisihao/ThunderOMLX/tests/fixtures/kvtc/manifest.json && echo D1 OK
test -f /Users/lisihao/ThunderOMLX/tests/regression/test_kvtc_e2e.py && echo D2 OK
test -f /Users/lisihao/ThunderOMLX/.github/workflows/kvtc-regression.yml && echo D3 OK
test -f /Users/lisihao/ThunderOMLX/reports/kvtc-ab/20260522T094040Z/ab_correctness.summary.json && echo D4-summary OK
test -f /Users/lisihao/ThunderOMLX/reports/kvtc-ab/20260522T094040Z/recon_gate.jsonl && echo D4-jsonl OK
test -f /Users/lisihao/ThunderOMLX/docs/KVTC_RELEASE.md && echo D5 OK

# 3. D4 SLO 现场验证（不重跑，读取已落盘 summary）
python3 -c "
import json
s = json.load(open('/Users/lisihao/ThunderOMLX/reports/kvtc-ab/20260522T094040Z/ab_correctness.summary.json'))
print('schema:', s.get('schema_version'))
print('hard_violations:', s.get('summary',{}).get('hard_violations','?'))
print('p95_rel_rmse:', s.get('summary',{}).get('p95_rel_rmse_observed','?'))
print('min_cos:', s.get('summary',{}).get('min_cos_observed','?'))
"
# Expect: schema kvtc.ab_summary.v1, hard_violations 0, p95<0.02, min_cos>=0.999

# 4. 父 epic gate roll-up
python3 -c "
import json
t = json.load(open('/Users/lisihao/.solar/harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s05-verification-release.traceability.json'))
for g in t['epic_required_gates_status']:
    print(g['sprint_id'].split('-')[-2], '->', g['status'])
"
# Expect: S01..S04 passed, S05 reviewing_pending_evaluator (本 handoff 推进它)
```

## 已知风险 / 数据漂移

- **D0 node-level status 仍 `reviewing`**：task_graph gate 已 `passed`，但 D0 节点 status
  没回写 `passed`。属 stale metadata，不应影响 sprint 收尾（gate 是判定准则）。建议
  evaluator 在盖章时一并刷为 passed。
- **`reports/kvtc-ab/latest` 软链断裂**：当前指向
  `/private/var/folders/.../pytest-of-lisihao/pytest-27/test_e8_summary_mismatches_emp0/.../e2e_e8` —
  是 D2 pytest tmpdir 残留，不是 D4 真跑 evidence 路径。Plan §7 表里 `latest_symlink`
  应该是 `reports/kvtc-ab/latest -> 20260522T094040Z/`。本 round 不在 write_scope 范围内 fix，
  建议 evaluator 让 D5/D6 在 release 流程中重建符号链接。
- **traceability `parent_check_ready=false`**：故意如此（S05 还在 reviewing），由 evaluator
  PASS 之后由 coordinator/epic_decomposer 写 `parent_check_ready=true`，触发 parent-check。
- **`eval.md/eval.json` 缺失**：evaluator 的产物，本 handoff 不伪造。
- **knowledge_export 未触发**：status 中无 `knowledge_export_status` 字段，未走
  `_raw/solar-harness/accepted/` 流水线；与 housekeeping/S04 sprint 不同（那些有
  `knowledge_export_status: exported`）。建议 evaluator 盖章后再触发 knowledge ingest。

## 结构化收尾

- **已完成**:
  - sprint-level handoff 写入
  - 与 D0 (handoff)、D1-D6 (passed) 节点 evidence 对账完毕
  - 4 个 ThunderOMLX artifact 路径（D0/D1/D2/D3/D4/D5）实地确认存在
  - D4 summary.json 内 SLO 数值与 plan §4 阈值表逐条对账（hard 0、p95 0.01197、min_cos 0.999076）
- **已验证**:
  - 所有 D0-D6 落地文件 `test -f` 通过（见验证方法 #1, #2）
  - D4 SLO `hard_violations=0`, `p95_rel_rmse=0.01197 < 0.02`, `min_cos=0.999076 ≥ 0.999`
  - traceability.json 含 5 gate 全集，S01-S04 = passed
  - task_graph `required_gates: ['G_S05_verification_release_passed']` 已 passed
- **未验证**:
  - 本 round 没有重跑 D2 pytest / D4 真跑（依赖 ThunderOMLX venv + 真实 fixture，不在
    rollup round write_scope；引用 2026-05-22 evidence 落盘的实测数字）
  - D0 node status `reviewing` 仍未刷新为 passed（stale metadata，待 evaluator）
- **风险**:
  - `latest` symlink 断裂（指向 pytest tmpdir）— evaluator 应触发 D5/D6 release 流程重建
  - eval.md/eval.json 缺失 — 本 handoff 不伪造
  - parent_check_ready=false — 由 evaluator + coordinator 接力
- **后续待办**:
  - evaluator 盖章 sprint-level PASS（基于本 handoff + D0-D6 evidence + D4 SLO）
  - coordinator/epic_decomposer 在 evaluator PASS 后跑 parent-check 关闭 epic
    `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
  - 修 `reports/kvtc-ab/latest` symlink 指向 `20260522T094040Z/`（D5/D6 范围）
  - knowledge ingest pipeline 触发 `_raw/solar-harness/accepted/` 落 S05 accepted artifact

## 上游依赖与下游影响

- **上游**: S01-S04（contract / requirements / architecture / core-runtime / orchestration-ui）
  已全部 passed，本 sprint 是 epic 末尾切片。
- **下游 (intra-sprint)**: 无—D6 是最后节点。
- **跨 Sprint**: 父 epic close 依赖本 sprint evaluator PASS；S03 不触发 round-2（D4
  SLO 都在阈值内）。
