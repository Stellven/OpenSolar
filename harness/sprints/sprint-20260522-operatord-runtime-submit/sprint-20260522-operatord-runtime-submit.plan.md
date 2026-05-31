# Plan — Operatord Runtime Submit Foundation

Sprint: `sprint-20260522-operatord-runtime-submit`
Author: Planner (solar-harness:0.1)
Authored-At: 2026-05-29T06:45:00Z
DAG: `task_graph.json` (5 nodes, validated by `graph-scheduler validate`)

> Retrospective plan: documents the actually-shipped delivery sequence so the coordinator gate accepts the artifact set. The 5 nodes already shipped & PASSED (see `<sid>.finalized` 2026-05-22T21:00:56Z). No new builder run is being authorized here.

---

## 1. Delivery slice order

| Slice | Node | What ships | When (actually) |
|-------|------|------------|-----------------|
| Slice 1 | **N1** | `<sid>.N1-handoff.md` — submit API design, operatord process contract, inbox layout, multi-task compatibility plan, persona-bank binding model | 2026-05-22T18:55Z — 19:19Z (with one quota-cooldown retry) |
| Slice 2A | **N2** | `lib/operator_runtime.py` (submit + validation + lease + inbox + result), `tests/runtime/test_operator_runtime.py` (success + 5 rejection classes + persona-block) | 2026-05-22T19:22Z — 20:27Z |
| Slice 2B | **N3** | `tools/operatord.py` (daemon, 10 responsibilities), `tools/operator_naming.py` (canonical id + pane title), `solar-harness.sh` (CLI wiring), `tests/test_operator_naming.py` (4-vendor matrix) | 2026-05-22T19:22Z — 20:27Z (parallel with N2) |
| Slice 3 | **N4** | `tests/test_no_direct_tmux_send_keys.py` (lint gate scanning 275 files, allowlist 10, deny 0) | 2026-05-22T20:38Z — 20:43Z |
| Slice 4 | **N5** | `monitor-reports/operatord-runtime-submit.md` (11-section report) + `<sid>.N5-handoff.md` (verdict PASS) | 2026-05-22T20:50Z — 21:00:56Z (finalized) |

The delivery is **not re-ordered** by this Planner pass.

---

## 2. File-level write scope

| Node | Write scope (already shipped) | Tracked in task_graph |
|------|-------------------------------|----------------------|
| N1 | `sprints/<sid>.N1-handoff.md` | ✅ |
| N2 | `~/.solar/harness/lib/operator_runtime.py`, `~/.solar/harness/tests/runtime/test_operator_runtime.py`, `sprints/<sid>.N2-handoff.md` | ✅ |
| N3 | `~/.solar/harness/tools/operatord.py`, `~/.solar/harness/tools/operator_naming.py`, `~/.solar/harness/solar-harness.sh`, `~/.solar/harness/tests/test_operator_naming.py`, `sprints/<sid>.N3-handoff.md` | ✅ |
| N4 | `~/.solar/harness/tests/test_no_direct_tmux_send_keys.py`, `sprints/<sid>.N4-handoff.md` | ✅ |
| N5 | `~/.solar/harness/monitor-reports/operatord-runtime-submit.md`, `sprints/<sid>.N5-handoff.md` | ✅ |

Outside scope (do not touch):
- `~/.solar/harness/lib/multi_task_runner.py` — read-only (FR-9 compat)
- `~/.solar/harness/config/physical-operators.json` — read-only for N1 design + N5 audit
- Any active tmux pane (no-live-pane-mutation invariant)
- `<sid>.finalized` or prior N* handoffs (do not overwrite)

---

## 3. Concurrency boundary

- **Serial**: N1 must complete before N2 or N3 start (both depend on the design/contract).
- **Parallel**: N2 ∥ N3 — write-scopes disjoint:
  - N2: `lib/operator_runtime.py` + `tests/runtime/`
  - N3: `tools/operatord.py` + `tools/operator_naming.py` + `solar-harness.sh` + `tests/test_operator_naming.py`
- **Join**: N4 requires `passed(N2) ∧ passed(N3)`; N5 requires `passed(N2) ∧ passed(N3) ∧ passed(N4)`.

Encoded in `task_graph.json` via `depends_on`:
- N1: `[]`
- N2: `["N1"]`
- N3: `["N1"]`
- N4: `["N2", "N3"]`
- N5: `["N2", "N3", "N4"]`

---

## 4. Verification commands (already executed by N5; re-runnable)

```bash
# A1 — submit API unit tests (covers success + 5 rejection classes + persona block)
cd ~/.solar/harness && python3 -m pytest tests/runtime/test_operator_runtime.py -v
# expect: all green; rejection cases: disabled, leased, running, quota_exhausted, auth_expired, unknown, missing_persona

# A2 — operator_naming tests (canonical id + 4-vendor pane title matrix)
cd ~/.solar/harness && python3 -m pytest tests/test_operator_naming.py -v
# expect: all green; titles: [CLAUDE][OPUS47][ARCH][XHIGH][01], [CODEX][GPT55][IMPL][01],
#                            [AG][G35FLASH][PAR][03], [LOCAL][MLX][SCAN][01]

# A3 — lint gate (ban direct tmux send-keys in DAG dispatch code)
cd ~/.solar/harness && python3 -m pytest tests/test_no_direct_tmux_send_keys.py -v
# expect: 275 files scanned, 10 ALLOW (allowlisted adapter/startup), 0 DENY

# A4 — operatord CLI help (FR-1)
~/.solar/harness/solar-harness.sh operatord run --help
# expect: exit 0; usage text

# A5 — submit smoke with safe dummy operator
~/.solar/harness/solar-harness.sh operator-runtime submit \
  --operator mini-claude-sonnet-builder \
  --task-envelope <(cat <<'YAML'
task_id: smoke-$(date +%s)
sprint_id: sprint-20260522-operatord-runtime-submit
node_id: SMOKE
task_type: SMOKE
objective: verify submit pipeline
constraints: {write_files: false, run_tests: false, git_commit: false}
output_contract: {required_artifacts: []}
verifier: {required: true, cannot_use_same_operator: true}
YAML
)
# expect: returns {task_id, operator_id, lease_id, inbox_path, status}; envelope written to inbox

# A6 — secrets grep (FR-8)
cd ~/.solar/harness && grep -rEn 'sk-[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,}|gho_[A-Za-z0-9]{8,}|gsk_[A-Za-z0-9]{8,}|api_key=[^&\s]+|token=[A-Za-z0-9._-]{12,}' lib/ tools/ tests/ monitor-reports/operatord-runtime-submit.md
# expect: 0 substantive hits (only argparse flag literals like `--task-id` which are false-positives)

# A7 — persona coverage audit (FR-4)
cd ~/.solar/harness && python3 -c "
import json
ops = json.load(open('config/physical-operators.json'))
missing = [o for o in ops.get('operators', []) if not o.get('persona')]
print(f'operators={len(ops.get(\"operators\", []))} missing_persona={len(missing)}')
"
# expect: missing_persona=0
```

Shipped evidence: `monitor-reports/operatord-runtime-submit.md` (11 sections) records the actual run output of A1-A7 from 2026-05-22.

---

## 5. No-live-pane-mutation protection

The Planner pane (this pane) is forbidden from:
- Restarting `operatord` daemons in any active tmux pane.
- Writing into any tmux pane other than its own.
- Running A5 smoke (which writes to a real operator inbox) — that smoke was N5's responsibility and is already recorded.
- Touching `<sid>.finalized`, prior `N*-handoff.md`, the shipped Python code, or the final report.

If the coordinator dispatches Builder anyway, Builder MUST:
- Verify `<sid>.finalized` exists; if so, write a no-op handoff and exit 0.
- Never `rm` shipped scripts, tests, reports, or persona files.
- Never restart any operatord process or kill active panes.

---

## 6. Rollback / stop rules

| Trigger | Action |
|---------|--------|
| `validate.sh prd` still fails after this Planner pass | Re-check PRD against `schemas/prd.schema.json`; do **not** retry Planner without first fixing PRD; do **not** dispatch Builder |
| `graph-scheduler validate` returns errors | Fix `task_graph.json` per error; never delete the file; never zero-out node statuses |
| Builder dispatched and overwrites a passed N* handoff | STOP. Restore from knowledge export (`~/Knowledge/_raw/solar-harness/accepted/<sid>.accepted.md` if present, else git). Surface to user. |
| Submit smoke returns failure on a real operator after this | Builder re-run not required — open a follow-up sprint scoped to that operator; do not roll back submit API |
| Lint gate reports new DENY | Open a follow-up sprint scoped to that specific code path; do not relax the lint allowlist silently |
| `operatord` daemon process detected as zombie in any pane | Out of scope for this sprint (autopilot/ops sprint); do not auto-kill — surface to user |
| Persona file gone missing | operatord will report `needs_human_review`; do NOT auto-create; surface to user |
| Any secret detected in logs/envelope post-shipping | Treat as security incident; open dedicated sprint; revoke leaked credentials before any patch lands |

---

## 7. Definition-of-done mapping

| DoD condition | Evidence path |
|---------------|--------------|
| 真实调用链接入 | `lib/operator_runtime.py` is the only submit entrypoint; `tools/operatord.py` is wired through `solar-harness.sh`; sibling sprint `sprint-20260523-lease-based-model-fleet-runtime` consumes the lease API |
| 禁止硬编码 | `secret_ref` indirection (no inline tokens); inbox path computed from operator id; pane title derived from registry alias |
| 测试必须运行 | A1-A3 pytest, A4 CLI smoke, A5 submit smoke, A6 secrets grep, A7 persona audit — all executed by N5 (see report) |
| 执行证据齐全 | `monitor-reports/operatord-runtime-submit.md` 11 sections include 50/50 pytest output, 12/12 operator binding map, lint scan summary |
| Diff 自审 | N2/N3/N4 handoffs each list changed files + acceptance status |
| 禁用乐观词 | Planner doc only states "shipped & PASSED with documented migration gaps G1-G8"; this pass adds NO new claims of done |
| 结构化收尾 | This plan §1-§7 + design.md cover 已完成 / 已验证 / 未验证 / 风险 / 后续待办 |

---

## 8. Follow-ups out of scope (G1-G8)

From N5 §7 + PRD §开放问题:

- **G1** existing pane migration to `operatord` → migration sprint (OQ-01)
- **G2** cross-host inbox via SSH/Tailscale → cross-host sprint (OQ-04)
- **G3** lint gate IDE integration → lint evolution sprint (OQ-05)
- **G4** canonical_id ↔ logical_operator namespace integration → runtime协同 sprint (OQ-06)
- **G5** persona lifecycle / versioning → persona lifecycle sprint (OQ-07)
- **G6** evaluator-verification-protocol ↔ OperatorScore SameProviderVerifierPenalty → runtime整合 sprint (OQ-08)
- **G7** async `asubmit` API → performance sprint (OQ-02)
- **G8** inbox upgrade from filesystem to SQLite/queue → lease+inbox upgrade sprint (OQ-03)
