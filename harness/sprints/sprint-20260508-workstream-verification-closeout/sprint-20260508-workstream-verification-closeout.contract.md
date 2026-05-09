---
sprint_id: sprint-20260508-workstream-verification-closeout
title: Solar Workstream Verification Closeout
priority: P0
lane: reliability
owner: planner
created_at: 2026-05-08T16:40:00Z
status: contract_ready
handoff_to: planner
---

# Sprint Contract — Solar Workstream Verification Closeout

## Intent

Verify and close the loop on all Solar workstreams recently requested and/or dispatched. This sprint is a reliability stop-line: Solar must prove what is finished, identify what is only partially wired, and dispatch fixes for the remaining gaps. Do not start new feature work until the verification matrix is complete.

## Current Evidence Snapshot

```text
┌──────────────────────────────────────────┬─────────┬────────────────────────────────────────────┐
│ Workstream                               │ State   │ Evidence                                   │
├──────────────────────────────────────────┼─────────┼────────────────────────────────────────────┤
│ Obsidian Wiki                            │ ok      │ sprint-20260507-obsidian-wiki passed       │
│ Symphony S2/S3                            │ ok      │ sprint-20260507-symphony2/3 passed         │
│ QMD/MinerU                                │ warn    │ 1103 indexed, 0 vectors embedded           │
│ status-server 8765                        │ ok      │ /healthz ok, /status JSON returns          │
│ Solar KB autouse                          │ pending │ reviewing, eval.md/eval.json missing       │
│ Mirage unified VFS                        │ pending │ active, S1/S2 handoffs missing             │
│ Accepted artifact knowledge               │ pending │ queued behind KB P0                        │
│ Data-plane closeout                       │ pending │ queued behind KB P0                        │
│ Hook failures visibility                  │ warn    │ expected test hook failures shown as warn  │
│ Pane orchestration                        │ warn    │ GLM API 400 + manual reroute happened      │
└──────────────────────────────────────────┴─────────┴────────────────────────────────────────────┘
```

## Deliverables

1. `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.plan.md`
   - Planner-owned verification plan.
   - Must freeze new feature scope and sequence verification before fixes.

2. `/Users/sihaoli/.solar/harness/reports/solar-workstream-verification-20260508.md`
   - One matrix covering all workstreams.
   - For each: status, artifact evidence, command evidence, gaps, next action.

3. `/Users/sihaoli/.solar/harness/reports/solar-workstream-verification-20260508.json`
   - Machine-readable version of the matrix.

4. `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.fix-dispatch.md`
   - Dispatch file listing only required fixes, grouped by owner/pane.

5. `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.handoff.md`
   - Builder/observer handoff summarizing completed verification and fixes.

6. `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.eval.md`
   - Evaluator final verdict.

## Acceptance Criteria

### A1 — Sprint Ledger Truth

Required behavior:
- Scan `sprint-20260507-*` and `sprint-20260508-*`.
- For every sprint, compare `status.json` with required artifacts:
  - `passed` must have `.eval.md` and `.finalized` unless explicitly exempted.
  - `reviewing` must have handoff and evaluator dispatch path.
  - `active/planning_complete` must have plan/design and active builder handoff target.
  - queued items must have blocker and next owner.
- Report false positives where status claims progress but artifact is missing.

Verify:

```bash
python3 /Users/sihaoli/.solar/harness/tools/verify-workstream-ledger.py --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "sprints" in d and d["summary"]["checked"] >= 8'
```

<!-- verify: cmd="python3 /Users/sihaoli/.solar/harness/tools/verify-workstream-ledger.py --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert \"sprints\" in d and d[\"summary\"][\"checked\"] >= 8'" -->

### A2 — Obsidian Wiki Integration Still Works

Required behavior:
- `solar-harness wiki status --json` succeeds.
- Vault path is `/Users/sihaoli/Knowledge`.
- Codex/Claude/Agents skills are installed.
- At least one query or qmd search returns wiki pages.

Verify:

```bash
solar-harness wiki status --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["configured"] and d["vault_path"] == "/Users/sihaoli/Knowledge"'
solar-harness wiki qmd-search "Solar Harness Obsidian" -n 2 --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert len(d) >= 1'
```

<!-- verify: cmd="solar-harness wiki status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d[\"configured\"] and d[\"vault_path\"] == \"/Users/sihaoli/Knowledge\"' && solar-harness wiki qmd-search 'Solar Harness Obsidian' -n 2 --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert len(d) >= 1'" -->

### A3 — QMD/MinerU Is Indexed And Its Limitation Is Explicit

Required behavior:
- `qmd status` reports collection `solar-wiki`.
- File count >= 1000.
- If vectors are 0, report `warn` not `pass`; include next command `qmd embed -c solar-wiki`.
- MCP health on 8181 must be checked.

Verify:

```bash
qmd status | rg "solar-wiki|Total:|Vectors:"
curl -fsS http://localhost:8181/health >/dev/null
```

<!-- verify: cmd="qmd status | rg 'solar-wiki|Total:|Vectors:' && curl -fsS http://localhost:8181/health >/dev/null" -->

### A4 — Status Server And Recent Events Are Honest

Required behavior:
- `/healthz` and `/status` succeed.
- `/status` must not show endless `Loading...`.
- `recent_events` must distinguish expected test hook failures from real hook failures, or report this as a fix dispatch.
- Current sprint and pane assignments must be artifact-aware, not pane-output-only.

Verify:

```bash
curl -fsS http://127.0.0.1:8765/healthz >/dev/null
curl -fsS http://127.0.0.1:8765/status \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "current_sprint" in d and "main_screen" in d'
```

<!-- verify: cmd="curl -fsS http://127.0.0.1:8765/healthz >/dev/null && curl -fsS http://127.0.0.1:8765/status | python3 -c 'import json,sys; d=json.load(sys.stdin); assert \"current_sprint\" in d and \"main_screen\" in d'" -->

### A5 — Solar KB Autouse P0 Gets Real Evaluation

Required behavior:
- Run the A1-A7 verify commands from `sprint-20260508-solar-kb-obsidian-autouse.contract.md`.
- Create eval files:
  - `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-solar-kb-obsidian-autouse.eval.md`
  - `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-solar-kb-obsidian-autouse.eval.json`
- If any acceptance fails, do not mark PASS; generate targeted fix dispatch.

Verify:

```bash
test -s /Users/sihaoli/.solar/harness/sprints/sprint-20260508-solar-kb-obsidian-autouse.eval.md
test -s /Users/sihaoli/.solar/harness/sprints/sprint-20260508-solar-kb-obsidian-autouse.eval.json
```

<!-- verify: cmd="test -s /Users/sihaoli/.solar/harness/sprints/sprint-20260508-solar-kb-obsidian-autouse.eval.md && test -s /Users/sihaoli/.solar/harness/sprints/sprint-20260508-solar-kb-obsidian-autouse.eval.json" -->

### A6 — Mirage VFS Does Not Fake Progress

Required behavior:
- Wait for or force completion of S1/S2 handoffs:
  - `handoff-s1.md`
  - `handoff-s2.md`
- Verify `solar-harness mirage doctor --json`.
- Verify missing Mirage SDK/CLI degrades cleanly.
- Verify no full `$HOME` mount and no Drive write by default.

Verify:

```bash
test -s /Users/sihaoli/.solar/harness/sprints/sprint-20260508-mirage-unified-vfs.handoff-s1.md
test -s /Users/sihaoli/.solar/harness/sprints/sprint-20260508-mirage-unified-vfs.handoff-s2.md
solar-harness mirage doctor --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "drive" in d and d["drive"]["status"] in ("ok","warn","degraded","disabled")'
```

<!-- verify: cmd="test -s /Users/sihaoli/.solar/harness/sprints/sprint-20260508-mirage-unified-vfs.handoff-s1.md && test -s /Users/sihaoli/.solar/harness/sprints/sprint-20260508-mirage-unified-vfs.handoff-s2.md && solar-harness mirage doctor --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert \"drive\" in d and d[\"drive\"][\"status\"] in (\"ok\",\"warn\",\"degraded\",\"disabled\")'" -->

### A7 — Accepted Artifact Knowledge Is Either Implemented Or Properly Blocked

Required behavior:
- Confirm whether current P0 is passed.
- If passed, activate `sprint-20260508-accepted-artifact-knowledge`.
- If not passed, leave queued but explain blocker and verify contract completeness.
- Do not ingest failed/draft artifacts.

Verify:

```bash
test -s /Users/sihaoli/.solar/harness/sprints/sprint-20260508-accepted-artifact-knowledge.contract.md
python3 -m json.tool /Users/sihaoli/.solar/harness/sprints/sprint-20260508-accepted-artifact-knowledge.status.json >/dev/null
```

<!-- verify: cmd="test -s /Users/sihaoli/.solar/harness/sprints/sprint-20260508-accepted-artifact-knowledge.contract.md && python3 -m json.tool /Users/sihaoli/.solar/harness/sprints/sprint-20260508-accepted-artifact-knowledge.status.json >/dev/null" -->

### A8 — Capture Server And Auto Ingest Are Verified

Required behavior:
- Verify capture server status if intended to stay running.
- Verify copy/paste capture writes into `/Users/sihaoli/Knowledge/_raw`.
- Verify file upload path under `_raw/file-uploads`.
- Verify dispatch watcher or scheduler processes raw files automatically, or report exact missing daemon.

Verify:

```bash
solar-harness wiki capture-server status
test -d /Users/sihaoli/Knowledge/_raw
```

<!-- verify: cmd="solar-harness wiki capture-server status && test -d /Users/sihaoli/Knowledge/_raw" -->

### A9 — Pane Orchestration And Model Routing Are Stable Enough

Required behavior:
- Detect panes stuck in plan mode while assigned work is active.
- Detect assignments that point to a sprint with missing artifact after timeout.
- Document GLM API 400 / concurrency issue and prefer Sonnet/DeepSeek fallback for active builder work.
- Do not mark lab handoff ok based only on old `obsidian-wiki-lab/*handoff.md`.

Verify:

```bash
tmux list-panes -t solar-harness:0 -F '#{pane_index} #{pane_current_command} #{pane_title}' >/dev/null
tmux list-panes -t solar-harness-lab:0 -F '#{pane_index} #{pane_current_command} #{pane_title}' >/dev/null
```

<!-- verify: cmd="tmux list-panes -t solar-harness:0 -F '#{pane_index} #{pane_current_command} #{pane_title}' >/dev/null && tmux list-panes -t solar-harness-lab:0 -F '#{pane_index} #{pane_current_command} #{pane_title}' >/dev/null" -->

### A10 — Fix Dispatch Is Minimal And Safe

Required behavior:
- Generate fix dispatch only for failed/warn items.
- Each fix must list owner, write scope, verification command, and rollback.
- No fix may overwrite user files, real Drive, or accepted vault pages.

Verify:

```bash
test -s /Users/sihaoli/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.fix-dispatch.md
rg -n "Owner|Write Scope|Verify|Rollback" /Users/sihaoli/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.fix-dispatch.md
```

<!-- verify: cmd="test -s /Users/sihaoli/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.fix-dispatch.md && rg -n 'Owner|Write Scope|Verify|Rollback' /Users/sihaoli/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.fix-dispatch.md" -->

## Stop Rules

- Stop if evaluator is asked to PASS without running the verify commands.
- Stop if a status field is treated as proof without corresponding artifact.
- Stop if a fix tries to write real Google Drive.
- Stop if a fix mounts all of `/Users/sihaoli`.
- Stop if a test writes outside temp paths except explicit `/Users/sihaoli/Knowledge/_raw` smoke.
- Stop if a new feature sprint is started before this closeout report is produced.

## Planner Instructions

1. Produce:
   `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.plan.md`
2. Build the verification matrix first; do not fix before matrix.
3. Use observer/evaluator style: commands, artifacts, status, pane state.
4. If fixes are required, generate `fix-dispatch.md` with small independent tasks.
5. Only after fixes run, send to evaluator for final verdict.

## Definition Of Done

- A1-A10 are either PASS or explicitly WARN with owner and next action.
- `solar-workstream-verification-20260508.md/json` exist.
- Active/reviewing sprint gaps are no longer silent.
- Solar has a concrete fix dispatch for every remaining gap.
- Evaluator signs final verdict in `eval.md`.

