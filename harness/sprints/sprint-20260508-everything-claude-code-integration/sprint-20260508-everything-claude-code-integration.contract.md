---
sprint_id: sprint-20260508-everything-claude-code-integration
title: Everything Claude Code Integration Backlog
priority: P1
lane: agent-ecosystem
owner: planner
created_at: 2026-05-08T16:52:52Z
status: contract_ready
handoff_to: planner
blocked_by: sprint-20260508-external-integrations-closeout
---

# Sprint Contract - Everything Claude Code Integration Backlog

## Intent

Register and evaluate Everything Claude Code as a Solar/Solar-Harness agent ecosystem candidate.

The user remembered "EverythingCloudCode". GitHub evidence indicates the likely project is
Everything Claude Code:

- Canonical source: https://github.com/affaan-m/everything-claude-code
- Mirror/fork found by search: https://github.com/WorldFlowAI/everything-claude-code

This sprint must not blindly install all agents, hooks, commands, skills, or MCP configs into
`~/.claude` or Solar. It must first audit, classify, sandbox, and selectively integrate pieces
that improve Solar without breaking existing coordinator, QMD/Obsidian, Gstack, Superpowers, or
Codex behavior.

## Current Local Evidence

- No active Solar integration artifact was found for `everything-claude-code`,
  `EverythingCloudCode`, or `Everything Claude Code` outside archived Codex sessions.
- Existing related local systems:
  - Gstack rules are referenced in `/Users/lisihao/Solar/CLAUDE.md`.
  - Superpowers is enabled as a Codex plugin in `/Users/lisihao/.codex/config.toml`.
  - Solar already has its own skills, hooks, coordinator, events, status server, and knowledge
    ingestion paths.

## Upstream Evidence

Everything Claude Code contains Claude Code agents, skills, hooks, commands, rules, MCP configs,
contexts, scripts, and tests. Its README describes plugin installation through Claude Code
marketplaces or manual copying into `~/.claude/agents`, `~/.claude/rules`,
`~/.claude/commands`, and `~/.claude/skills`.

## Non-Goals

- Do not overwrite existing Solar, Claude, Codex, Gstack, or Superpowers config.
- Do not enable upstream hooks globally before review.
- Do not copy MCP configs containing placeholder credentials into live config.
- Do not change Solar coordinator roles or pane routing in this sprint.
- Do not treat this repo as already integrated until acceptance criteria pass.

## Deliverables

1. `/Users/lisihao/.solar/harness/vendor/everything-claude-code/`
   - Read-only upstream clone or snapshot.
   - Must record source URL, commit SHA, license, and fetched_at.

2. `/Users/lisihao/.solar/harness/reports/everything-claude-code-audit-20260508.md`
   - Inventory of agents, skills, commands, hooks, rules, MCP configs, scripts, and tests.
   - Classify each item as `adopt`, `adapt`, `reject`, or `defer`.
   - Include collision analysis against Solar/Gstack/Superpowers/Codex.

3. `/Users/lisihao/.solar/harness/config/everything-claude-code.allowlist.json`
   - Explicit allowlist for components Solar may install or reference.
   - Empty or conservative by default.

4. `/Users/lisihao/.solar/harness/lib/everything_claude_code_adapter.py`
   - Implements `doctor`, `inventory`, `install-dry-run`, `sync-allowlisted`, and `rollback`.
   - Must be non-interactive and idempotent.

5. `/Users/lisihao/.solar/harness/solar-harness.sh`
   - Adds:
     - `solar-harness everything-claude-code doctor [--json]`
     - `solar-harness everything-claude-code inventory [--json]`
     - `solar-harness everything-claude-code install --dry-run`
     - `solar-harness everything-claude-code sync --allowlist <path>`

6. `/Users/lisihao/.solar/harness/lib/external-integrations-health.py`
   - Reports Everything Claude Code as a first-class integration candidate.

7. `/Users/lisihao/.solar/harness/tests/test-everything-claude-code-integration.sh`
   - Regression tests for inventory, collision detection, dry-run install, rollback, and status.

## Acceptance Criteria

### A1 - Source Is Vendored But Not Activated

Required:
- Upstream repo is cloned or snapshotted under harness vendor.
- No live config is modified during fetch.
- Commit SHA and source URL are recorded.

Verify:

```bash
test -d /Users/lisihao/.solar/harness/vendor/everything-claude-code/.git
git -C /Users/lisihao/.solar/harness/vendor/everything-claude-code rev-parse HEAD
```

<!-- verify: cmd="test -d /Users/lisihao/.solar/harness/vendor/everything-claude-code/.git && git -C /Users/lisihao/.solar/harness/vendor/everything-claude-code rev-parse HEAD" -->

### A2 - Inventory Covers Every Upstream Surface

Required:
- Inventory counts agents, commands, skills, hooks, rules, MCP configs, scripts, tests, contexts,
  plugin manifests, and examples.
- Output includes file path, component type, risk level, and proposed action.

Verify:

```bash
solar-harness everything-claude-code inventory --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert all(k in d["counts"] for k in ["agents","commands","skills","hooks","rules","mcp_configs","scripts","tests"])'
```

<!-- verify: cmd="solar-harness everything-claude-code inventory --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert all(k in d[\"counts\"] for k in [\"agents\",\"commands\",\"skills\",\"hooks\",\"rules\",\"mcp_configs\",\"scripts\",\"tests\"])'" -->

### A3 - Collision Analysis Is Mandatory

Required:
- Detect name/path collisions against:
  - `/Users/lisihao/.claude/agents`
  - `/Users/lisihao/.claude/commands`
  - `/Users/lisihao/.claude/skills`
  - `/Users/lisihao/.agents/skills`
  - `/Users/lisihao/.codex/skills`
  - `/Users/lisihao/Solar/CLAUDE.md`
- Gstack and Superpowers must be explicitly called out.

Verify:

```bash
solar-harness everything-claude-code install --dry-run --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "collisions" in d and "gstack" in d["compatibility"] and "superpowers" in d["compatibility"]'
```

<!-- verify: cmd="solar-harness everything-claude-code install --dry-run --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert \"collisions\" in d and \"gstack\" in d[\"compatibility\"] and \"superpowers\" in d[\"compatibility\"]'" -->

### A4 - No Global Hook Activation Without Review

Required:
- Upstream hooks must be classified and copied only to a staging directory.
- Live `~/.claude/settings.json` hook sections must not be changed by default.

Verify:

```bash
solar-harness everything-claude-code install --dry-run --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["live_hook_changes"] == 0'
```

<!-- verify: cmd="solar-harness everything-claude-code install --dry-run --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d[\"live_hook_changes\"] == 0'" -->

### A5 - Allowlisted Sync Is Idempotent And Reversible

Required:
- Sync only allowlisted files.
- Existing files are backed up before modification.
- Re-running sync makes no duplicate changes.
- Rollback restores prior state.

Verify:

```bash
bash /Users/lisihao/.solar/harness/tests/test-everything-claude-code-integration.sh --case sync-rollback
```

<!-- verify: cmd="bash /Users/lisihao/.solar/harness/tests/test-everything-claude-code-integration.sh --case sync-rollback" -->

### A6 - Status Server Shows Candidate State

Required:
- `solar-harness integrations status --json` includes `affaan-m/everything-claude-code`.
- Until A1-A5 pass, status must be `warn` or `missing`, not `ok`.

Verify:

```bash
solar-harness integrations status --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); item=[x for x in d["integrations"] if "everything-claude-code" in x["name"]][0]; assert item["status"] in ("warn","missing")'
```

<!-- verify: cmd="solar-harness integrations status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); item=[x for x in d[\"integrations\"] if \"everything-claude-code\" in x[\"name\"]][0]; assert item[\"status\"] in (\"warn\",\"missing\")'" -->

### A7 - Tests Are Local And Safe

Required:
- Tests must not require real Claude plugin install.
- Tests must not require external credentials.
- Tests must run with temp HOME or temp staging dirs.

Verify:

```bash
bash /Users/lisihao/.solar/harness/tests/test-everything-claude-code-integration.sh
```

<!-- verify: cmd="bash /Users/lisihao/.solar/harness/tests/test-everything-claude-code-integration.sh" -->

## Stop Rules

- Stop if upstream install script attempts to overwrite live `~/.claude` config without dry-run.
- Stop if MCP config contains unresolved secrets or placeholder credentials and would be copied live.
- Stop if hook activation would affect all Claude Code sessions without explicit allowlist.
- Stop if any component conflicts with Gstack/Superpowers and no precedence rule is defined.
- Stop if implementation exceeds 900 lines before tests exist.

## Suggested Plan

Day 1:
- Vendor upstream source.
- Generate inventory and collision report.
- Decide allowlist v0.

Day 2:
- Implement adapter CLI.
- Implement dry-run and status integration.

Day 3:
- Implement allowlisted sync and rollback.
- Add tests and docs.

Day 4:
- Evaluator review: security, collision, hook safety, and default-agent behavior.

