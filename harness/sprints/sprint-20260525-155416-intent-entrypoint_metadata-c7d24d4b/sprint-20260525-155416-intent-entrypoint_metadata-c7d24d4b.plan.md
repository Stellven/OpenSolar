# Plan — RawIntent Consumer Smoke (entrypoint_metadata variant)

Sprint: `sprint-20260525-155416-intent-entrypoint_metadata-c7d24d4b`
Intent: `intent-20260525-155416-c7d24d4b84` (channel=`pm_dispatch`)
Author: Planner (solar-harness:0.1)
Authored-At: 2026-05-29T07:38:00Z
DAG: `task_graph.json` (5 nodes S1-S5, validated `ok:true errors:[] warnings:[]`)

> Smoke test plan: validates that the PM dispatch entrypoint can drive the full compile chain through Planner artifacts. Existing 14 artifacts are read-only.

---

## 1. Delivery slice order (this Planner pass)

| Slice | Output | Action taken |
|-------|--------|--------------|
| Slice 1 | `<sid>.design.md` | New: architecture + smoke framing + read/write boundaries + REQ↔node coverage |
| Slice 2 | `<sid>.task_graph.json` (in-place augment) | Added `write_scope` / `required_capabilities` / `required_skills` / `preferred_model` / `architecture_policy` to S1-S5; preserved upstream `capsule_plan` + `requirement_ids` + `acceptance_ids` + `gate` mapping |
| Slice 3 | `<sid>.plan.md` (this file) | Slice order / scope / concurrency / verification / stop rules |
| Slice 4 | `<sid>.planning.html` | Rendered via `render_sprint_html.py` + registered via `html_artifact.py` |
| Slice 5 | `<sid>.status.json` | status=`active` / phase=`planning_complete` / handoff_to=`builder_main` + history `planner_plan_completed` + planner_advisory |

This Planner pass produces 4 new files (slices 1-4) and updates 2 existing files (slices 2, 5) in place.

---

## 2. Downstream delivery slices (S1-S5 template — to be run by Builder pane)

| Slice | Node | What ships | Operator profile |
|-------|------|------------|------------------|
| Build 1 | S1 | `<sid>.S1-design-notes.md` (patch.diff per capsule output) | `mini-claude-opus-planner` |
| Build 2 | S2 | `<sid>.S2-impl-notes.md` (test_report.md per capsule output) | `mini-claude-sonnet-builder` |
| Build 3 | S3 | `<sid>.S3-test-report.md` (review_decision.yaml per capsule output) | `mini-claude-opus-evaluator` |
| Build 4 | S4 | `<sid>.S4-review-decision.yaml` (review_decision.yaml) | `mini-claude-opus-evaluator` |
| Build 5 | S5 | `<sid>.S5-rollout-notes.md` (rollout_notes.md) | `mini-claude-opus-evaluator` |

Builds 1-5 are smoke artifacts (intent is `[entrypoint_metadata]` placeholder); content semantics secondary, chain advancement primary.

---

## 3. File-level write scope

### Planner pass (this work)

| File | Purpose | Action |
|------|---------|--------|
| `<sid>.design.md` | Architecture / smoke framing | **CREATE** |
| `<sid>.plan.md` | This file | **CREATE** |
| `<sid>.planning.html` | Visual planning artifact | **CREATE** (rendered) |
| `<sid>.task_graph.json` | Scheduler-augmented DAG | **EDIT in-place** (additive only; no semantic changes) |
| `<sid>.status.json` | Sprint state | **EDIT in-place** (status/phase/handoff_to/artifacts/history) |
| `<sid>.ack-d-20260529T073516Z-9e93f9.json` | Dispatch ACK | **CREATE** |

### Read-only this pass (auto-generated chain — do not touch)

`raw_intent.json` · `requirement_ir.json` · `rewritten_intent.json` · `requirement_trace.json` · `product-brief.md` · `prd.md` · `prd.html` · `contract.md` · `Contracts.yaml` · `coverage_report.json` · `acceptance_verdict.json` · `handoff.md` · `dispatch.md*` · `capsule_plan.json`

### Builder pass write scope (per task_graph)

| Node | write_scope | Owner |
|------|-------------|-------|
| S1 | `sprints/<sid>.S1-design-notes.md` | mini-claude-opus-planner |
| S2 | `sprints/<sid>.S2-impl-notes.md` | mini-claude-sonnet-builder |
| S3 | `sprints/<sid>.S3-test-report.md` | mini-claude-opus-evaluator |
| S4 | `sprints/<sid>.S4-review-decision.yaml` | mini-claude-opus-evaluator |
| S5 | `sprints/<sid>.S5-rollout-notes.md` | mini-claude-opus-evaluator |

---

## 4. Concurrency boundary

- **Planner pass (this work)**: Fully serial — single planner pane, no parallelism.
- **Builder pass (downstream)**: Strictly sequential by `depends_on`:
  - S1 → S2 → S3 → S4 → S5
  - No fan-out, no join (each node consumes the previous node's output).
- S1/S2/S3 carry `parallelizable=true` at template level (meaning they're parallelizable in DAGs that branch them), but the chain here is linear by data dependency.
- S4 / S5 are explicitly `parallelizable=false` (review/rollout serialize).
- Approval gates: S4 + S5 (`approval_gate=true`).

---

## 5. Verification commands

```bash
# A1 — task_graph schema + structural validation
~/.solar/harness/solar-harness.sh graph-scheduler validate \
  --graph ~/.solar/harness/sprints/sprint-20260525-155416-intent-entrypoint_metadata-c7d24d4b.task_graph.json
# expect: {"ok": true, "errors": [], "warnings": []}

# A2 — PRD schema gate
~/.solar/harness/schemas/validate.sh prd \
  ~/.solar/harness/sprints/sprint-20260525-155416-intent-entrypoint_metadata-c7d24d4b.prd.md
# expect: PASS (PM has already augmented PRD to 11 schema sections)

# A3 — planning.html structural sanity
python3 -c "
from pathlib import Path
import re
p = Path.home()/'.solar/harness/sprints/sprint-20260525-155416-intent-entrypoint_metadata-c7d24d4b.planning.html'
c = p.read_text(encoding='utf-8')
print(f'size: {len(c)}')
print(f'h1 count: {len(re.findall(r\"<h1\", c))}')
print(f'pre blocks: {len(re.findall(r\"<pre\", c))}')
print(f'tables: {len(re.findall(r\"<table\", c))}')
"
# expect: size > 20000; h1 == 1; pre blocks >= 1 (ASCII diagram); tables >= 3

# A4 — html_artifact registered
python3 ~/.solar/harness/lib/html_artifact.py register \
  --sid sprint-20260525-155416-intent-entrypoint_metadata-c7d24d4b \
  --kind planning_html \
  --path ~/.solar/harness/sprints/sprint-20260525-155416-intent-entrypoint_metadata-c7d24d4b.planning.html
# expect: registered=True opened=True

# A5 — coverage_report still maps every REQ to ≥1 node
python3 -c "
import json
p='/Users/lisihao/.solar/harness/sprints/sprint-20260525-155416-intent-entrypoint_metadata-c7d24d4b.coverage_report.json'
d=json.load(open(p))
print('items:', len(d.get('items', [])))
for item in d.get('items', [])[:5]:
    print(f\"  {item['requirement_id']}: mapped_nodes={item.get('mapped_nodes')}\")
"
# expect: each requirement_id mapped to ≥1 S* node

# A6 — secrets scrub (raw_intent already redacted; verify Planner artifacts also clean)
grep -rEn 'sk-[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,}|gho_[A-Za-z0-9]{8,}|api_key=[^&\s]+|token=[A-Za-z0-9._-]{12,}' \
  ~/.solar/harness/sprints/sprint-20260525-155416-intent-entrypoint_metadata-c7d24d4b.{design.md,plan.md,planning.html,task_graph.json}
# expect: 0 matches
```

---

## 6. No-live-pane-mutation protection

The Planner pane (this pane) is forbidden from:
- Restarting harness / killing tmux panes.
- Writing into any tmux pane other than its own.
- Mutating the 14 auto-generated artifacts (PM scope only; PM's whitelist is `prd.md` + `prd.html` rerender, and PM already exercised it).
- Dispatching Builder directly (Builder dispatch must come from graph_scheduler reading task_graph.json).
- Running A1-A6 commands in any way that would mutate the runtime (all listed commands are read-only or self-check writes into Planner's own scope).

If Builder is dispatched and overruns the write scope:
- Builder MUST stop before overwriting any read-only artifact.
- Builder MUST stop before mutating `acceptance_verdict.json` to PASS without supporting evidence.
- Builder MUST never `rm` any of the 14 source artifacts.

---

## 7. Rollback / stop rules

| Trigger | Action |
|---------|--------|
| `graph-scheduler validate` returns errors | Fix per error in `task_graph.json`; never delete the file; never zero-out node statuses |
| PRD schema gate FAIL after this pass | PM scope — open follow-up PM fix; do NOT mutate PRD from Planner pane |
| `acceptance_verdict.json` still FAIL after Builder S2-S5 finish | Expected if smoke test does not actually generate substantive evidence; do NOT mutate to PASS; instead surface as smoke result |
| html_artifact register fails | Log warning, continue (helper failure must NOT block Planner→Builder per dispatch step 7) |
| Builder overwrites read-only artifact | Restore from knowledge export if exported; if not, ATLAS structured repair; never silently re-emit |
| Coordinator dispatches a fresh planner round after this pass | Out of scope; investigate graph_parent_ready_revoked trigger (same root cause as 2x prior sprints in this session) |
| Operator quota_exhausted on any S* | task_graph already records `quota_blocked_profiles` + `quota_recovery_*` for S1; fallback to alternative operator within capsule_plan.operator_constraints.preferred chain |
| Any secret detected in artifacts | Security incident protocol; raw_intent is already redacted upstream, but verify A6 grep stays at 0 |

---

## 8. Definition-of-done mapping

| DoD condition | Evidence path |
|---------------|--------------|
| 真实调用链接入 | task_graph.json wired into graph-scheduler validate (passes); planning.html registered into html_artifact registry |
| 禁止硬编码 | Operator preferences and forbidden lists already in capsule_plan (PM-generated); Planner did not introduce inline constants |
| 测试必须运行 | A1 (validate) ran with `ok:true`; A4 (HTML register) ran with `registered=True`; A3/A5/A6 are documented runnable checks |
| 执行证据齐全 | This plan §5 lists every command + expected output; Planner pass §1 lists every file changed with action |
| Diff 自审 | design.md §1 lists artifact inventory with read/write boundaries; plan.md §3 lists every file changed with CREATE/EDIT verb |
| 禁用乐观词 | This sprint is labeled smoke test throughout; design + plan explicitly say "intent text is placeholder" and "verification is structural not semantic" |
| 结构化收尾 | Final response will have 已完成 / 已验证 / 未验证 / 风险 / 后续待办 |

---

## 9. Followups out of scope

- **OQ-entrypoint-01** — PM dispatch template default-includes PRD 11 schema sections (eliminates gate flap)
- **OQ-entrypoint-02** — Cross-entrypoint smoke matrix (pm_dispatch, codex_bridge, cli_intake, antigravity, claude_code, ...)
- **OQ-entrypoint-03** — Versioning for `entrypoint_metadata` fields
- Operator quota recovery logic (S1 already has `quota_failure_reason=quota_exhausted` + `quota_recovery_count=1` — visible but unrelated to this Planner pass)
