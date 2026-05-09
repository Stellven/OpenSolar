# Builder Plan — sprint-20260508-everything-claude-code-integration

> Planner sign-off: 2026-05-08
> Topology: **solo** (single builder, narrow surface)
> Builder model: **Sonnet 4.6 default**. GLM-5.1 disabled per memory rule (4 prior burns).
> Round: 1
> Reads: contract.md, prd.md, design.md, vendor inventory at /Users/sihaoli/.solar/harness/vendor/everything-claude-code/

## 0. Operating Frame

This sprint **completes** the Everything Claude Code adapter that PM started. PM already shipped:
- vendored upstream (commit 841beea45cb25ba51f29fa45b7e272938d19b80a)
- audit report
- empty/conservative allowlist
- adapter.py with `doctor()`, `inventory()`, `dry_run()`, `write_report()` (~365 lines)
- solar-harness.sh subcommands: `doctor`, `inventory`, `report`, `install --dry-run`
- external-integrations-health.py registration of `affaan-m/everything-claude-code`

**Builder must NOT rewrite the above.** Add the 4 missing pieces only:
1. `sync()` function (allowlist-driven, backup-to-ledger)
2. `rollback()` function (ledger-driven restoration)
3. `solar-harness sync` + `rollback` CLI wiring
4. `tests/test-everything-claude-code-integration.sh` regression suite

Plus testability hardening: adapter must accept `ECC_HOME_OVERRIDE` + `ECC_STAGING` env vars so tests never touch live `~/.claude`.

## 1. Stages

### S1 — Adapter Testability Hardening (env override)

**Owner:** builder_main
**Write Scope (whitelist):**
- `lib/everything_claude_code_adapter.py` (additive — env var support; existing function signatures unchanged)

**Done:**
- [ ] Adapter reads `ECC_HOME_OVERRIDE` env var; when set, treats it as base for `~/.claude`, `~/.agents`, `~/.codex` collision targets
- [ ] Adapter reads `ECC_STAGING` env var; when set, uses it as staging dir base instead of `~/.solar/harness/staging/everything-claude-code/`
- [ ] All existing functions (`doctor`, `inventory`, `dry_run`, `write_report`) still pass the same outputs when env vars are unset (no behavior change in production path)
- [ ] No signature changes to existing public functions

**Verify:**
```bash
# unchanged production path
solar-harness everything-claude-code inventory --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["counts"]["agents"] >= 60'

# overridden path
ECC_HOME_OVERRIDE=/tmp/ecc-test-home ECC_STAGING=/tmp/ecc-test-staging \
  python3 /Users/sihaoli/.solar/harness/lib/everything_claude_code_adapter.py inventory \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "counts" in d'
```

**Rollback:** `git checkout -- lib/everything_claude_code_adapter.py`

**Stop rule:** if S1 changes signatures of existing functions, abort and ping planner.

---

### S2 — `sync()` function (allowlist-driven, backup-to-ledger)

**Owner:** builder_main
**Write Scope (whitelist):**
- `lib/everything_claude_code_adapter.py` (additive — new `sync()` function only)
- `run/ecc-sync-ledger.jsonl` (created on first sync; append-only)
- `run/ecc-backups/<sync_ts>/` (created on first sync; backup tree)
- `staging/everything-claude-code/<surface>/<name>` (created on first sync)

**Done:**
- [ ] `sync(allowlist_path: Path, dry_run: bool = False) -> dict` implemented per design.md §3
- [ ] Reads allowlist JSON; for each allowed entry:
  1. Resolves upstream path under VENDOR
  2. Computes collision against local target (respects `ECC_HOME_OVERRIDE`)
  3. If collision and not `--force`: skip + record reason
  4. If no collision: backup pre-existing to `<run>/ecc-backups/<sync_ts>/<rel_path>` (only if target file existed)
  5. Stage mirror under `<staging>/<surface>/<name>` (does NOT touch live ~/.claude)
  6. Append to `<run>/ecc-sync-ledger.jsonl` (one record per file action; flock-protected)
- [ ] Returns dict: `{sync_ts, allowlist_version, actions: [...], counts: {staged, skipped, backed_up}, live_hook_changes: 0}`
- [ ] Re-running sync with same allowlist is idempotent (no duplicate ledger entries; staged files not re-copied if hash matches)
- [ ] `live_hook_changes` is **always** 0 (sync only writes to staging + backups + ledger; never `~/.claude/settings.json`)
- [ ] Empty allowlist → returns `{counts: {staged:0, skipped:0, backed_up:0}, live_hook_changes: 0}` and writes nothing

**Verify:**
```bash
# Empty allowlist baseline
ECC_HOME_OVERRIDE=/tmp/ecc-sync-test ECC_STAGING=/tmp/ecc-sync-test/staging \
  python3 /Users/sihaoli/.solar/harness/lib/everything_claude_code_adapter.py sync \
    --allowlist /Users/sihaoli/.solar/harness/config/everything-claude-code.allowlist.json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["live_hook_changes"]==0 and d["counts"]["staged"]==0'

# Idempotency: 2 runs == 1 ledger pair
RUN_DIR=/tmp/ecc-sync-test/run
ls -la "$RUN_DIR/ecc-sync-ledger.jsonl" 2>/dev/null && wc -l "$RUN_DIR/ecc-sync-ledger.jsonl"
```

**Rollback:** `git checkout -- lib/everything_claude_code_adapter.py && rm -rf /tmp/ecc-sync-test`

**Stop rule:** if `sync()` writes anywhere under `~/.claude`, `~/.agents`, `~/.codex` → IMMEDIATELY abort, restore from backup ledger, ping planner.

---

### S3 — `rollback()` function (ledger-driven)

**Owner:** builder_main
**Write Scope (whitelist):**
- `lib/everything_claude_code_adapter.py` (additive — new `rollback()` function only)

**Done:**
- [ ] `rollback(sync_ts: str | None = None) -> dict` implemented per design.md §3
- [ ] If `sync_ts is None`: rollback most recent sync from ledger tail
- [ ] For each backed-up file in that sync's ledger entries: restore to original path (respects `ECC_HOME_OVERRIDE`)
- [ ] For staged-only files (no backup, because target didn't exist before): remove the staged mirror
- [ ] Writes a rollback record to ledger so re-rollback is a no-op
- [ ] Returns dict: `{sync_ts, restored_count, removed_count, status: "ok"|"partial"|"empty"}`
- [ ] `rollback()` on never-synced state → returns `{status: "empty"}` and does nothing

**Verify:**
```bash
# Rollback on empty state
ECC_HOME_OVERRIDE=/tmp/ecc-rollback-test ECC_STAGING=/tmp/ecc-rollback-test/staging \
  python3 /Users/sihaoli/.solar/harness/lib/everything_claude_code_adapter.py rollback \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["status"]=="empty"'
```

**Rollback:** `git checkout -- lib/everything_claude_code_adapter.py`

**Stop rule:** if rollback corrupts ledger or fails to restore a file recorded as backed up → abort, ping planner.

---

### S4 — solar-harness.sh CLI wiring (sync + rollback)

**Owner:** builder_main
**Write Scope (whitelist):**
- `solar-harness.sh` (additive — 2 new subcommands under `everything-claude-code`)

**Done:**
- [ ] `solar-harness everything-claude-code sync --allowlist <path> [--dry-run] [--json]` dispatches to `adapter.sync()`
- [ ] `solar-harness everything-claude-code rollback [--sync-ts <ts>] [--json]` dispatches to `adapter.rollback()`
- [ ] `--json` flag returns the function's dict as JSON
- [ ] Default allowlist path: `/Users/sihaoli/.solar/harness/config/everything-claude-code.allowlist.json`
- [ ] Existing subcommands (`doctor`, `inventory`, `report`, `install --dry-run`) untouched
- [ ] `solar-harness everything-claude-code` (no subcommand) prints help including new subcommands
- [ ] Bogus flag → exit code ≠ 0 with usage hint (avoid wiki-upload D7 trap)

**Verify:**
```bash
solar-harness everything-claude-code sync --allowlist /Users/sihaoli/.solar/harness/config/everything-claude-code.allowlist.json --dry-run --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["live_hook_changes"]==0'

solar-harness everything-claude-code rollback --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["status"] in ("empty","ok","partial")'

# bogus flag
solar-harness everything-claude-code sync --bogus-flag 2>&1 | grep -i 'usage\|unknown'
echo "exit=$?"  # should be non-zero from prior command
```

**Rollback:** `git checkout -- solar-harness.sh`

**Stop rule:** if existing subcommands break → abort.

---

### S5 — Integrations status verification (warn until allowlist non-empty + clean sync)

**Owner:** builder_main
**Write Scope (whitelist):**
- `lib/external-integrations-health.py` (verify-then-patch — only patch if status logic is missing)

**Done:**
- [ ] `solar-harness integrations status --json` returns array with item where `name` contains `"everything-claude-code"`
- [ ] Item's `status` is `"warn"` while allowlist is empty OR no clean sync recorded in ledger
- [ ] Item's `status` becomes `"ok"` ONLY when allowlist has ≥1 entry AND last sync ledger entry is `status=ok` AND no rollback pending
- [ ] Defaults during this sprint: status MUST be `"warn"` (allowlist is empty by design)
- [ ] If existing health check already implements this — leave it; just verify

**Verify:**
```bash
solar-harness integrations status --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); item=[x for x in d["integrations"] if "everything-claude-code" in x["name"]][0]; assert item["status"] in ("warn","missing"), f"got {item[\"status\"]}"'
```

**Rollback:** `git checkout -- lib/external-integrations-health.py`

**Stop rule:** if integration item missing entirely → planner mis-spec, ping planner.

---

### S6 — Regression test suite (tests/test-everything-claude-code-integration.sh)

**Owner:** builder_main
**Write Scope (whitelist):**
- `tests/test-everything-claude-code-integration.sh` (NEW file)

**Done:**
- [ ] Shell script with `--case <case-name>` dispatcher
- [ ] Cases (each must run independently):
  - `inventory` — runs `solar-harness everything-claude-code inventory --json`, asserts counts schema (agents/commands/skills/hooks/rules/mcp_configs/scripts/tests all present)
  - `collisions` — runs `install --dry-run --json`, asserts `collisions` field exists and is non-empty list
  - `compatibility` — runs `install --dry-run --json`, asserts `compatibility.gstack` and `compatibility.superpowers` keys exist
  - `dry-run-no-live` — runs `install --dry-run --json`, asserts `live_hook_changes == 0`
  - `sync-rollback` — uses `ECC_HOME_OVERRIDE` + `ECC_STAGING` to /tmp dir; runs sync with empty allowlist (should be no-op); writes a temp allowlist with 1 entry; runs sync; verifies staged file exists in tmp; runs rollback; verifies restored
  - `idempotent-sync` — uses /tmp; runs sync twice with same allowlist; verifies ledger contains exactly one logical sync (no dup file actions)
  - `status-warn` — runs `solar-harness integrations status --json`, asserts ecc item has status `warn` or `missing`
- [ ] No `--case` flag → runs ALL cases sequentially, exits 0 only if all pass
- [ ] Bogus `--case xxx` → exits 2 with usage hint listing valid cases (avoid wiki-upload D7 trap)
- [ ] Tests MUST NOT touch live `~/.claude`, `~/.agents`, `~/.codex` (use env vars exclusively)
- [ ] Tests MUST clean up their /tmp dirs on exit (trap)
- [ ] No external network calls
- [ ] No real Claude plugin install

**Verify:**
```bash
# All cases
bash /Users/sihaoli/.solar/harness/tests/test-everything-claude-code-integration.sh
echo "exit=$?"  # must be 0

# Individual case
bash /Users/sihaoli/.solar/harness/tests/test-everything-claude-code-integration.sh --case sync-rollback

# Bogus case
bash /Users/sihaoli/.solar/harness/tests/test-everything-claude-code-integration.sh --case bogus-xyz
echo "exit=$?"  # must be 2

# Live ~/.claude untouched
LIVE_BEFORE=$(find ~/.claude -newer /tmp/_marker_empty 2>/dev/null | wc -l || echo 0)
touch /tmp/_ecc_test_marker
bash /Users/sihaoli/.solar/harness/tests/test-everything-claude-code-integration.sh
LIVE_AFTER=$(find ~/.claude -newer /tmp/_ecc_test_marker 2>/dev/null | wc -l)
test "$LIVE_AFTER" -eq 0 || { echo "FAIL: tests touched live ~/.claude"; exit 1; }
```

**Rollback:** `rm -f tests/test-everything-claude-code-integration.sh`

**Stop rule:** if any test touches live `~/.claude` → IMMEDIATELY abort, ping planner. This is the hard line.

---

### S7 — End-to-end verification + handoff

**Owner:** builder_main
**Write Scope (whitelist):**
- `sprints/sprint-20260508-everything-claude-code-integration.handoff.md` (NEW)

**Done:**
- [ ] All 7 contract acceptance verify commands (A1-A7) executed and pass:
  - A1: vendor `.git` exists + commit SHA recorded
  - A2: inventory schema complete
  - A3: collisions + compatibility (gstack + superpowers) present
  - A4: `live_hook_changes == 0`
  - A5: sync-rollback test case passes
  - A6: integrations status item is `warn` or `missing`
  - A7: full test suite passes
- [ ] handoff.md written with:
  - List of all files created/modified (only those in S1-S6 write scopes)
  - Output of all 7 A1-A7 verify commands (paste JSON snippets)
  - Confirmation: live `~/.claude`, `~/.agents`, `~/.codex` untouched
  - Confirmation: allowlist remains empty (PM-frozen)
  - Confirmation: ledger + backups directories under `run/` only
  - Stop rule violations: none
- [ ] Builder DOES NOT update status.json (coordinator handles)

**Verify:**
```bash
test -f /Users/sihaoli/.solar/harness/sprints/sprint-20260508-everything-claude-code-integration.handoff.md
grep -c 'A[1-7]' /Users/sihaoli/.solar/harness/sprints/sprint-20260508-everything-claude-code-integration.handoff.md
```

**Stop rule:** if any A1-A7 fails → builder writes failure into handoff.md, status stays for evaluator review (do NOT silently retry).

## 2. File-Level Write Whitelist (HARD LIMIT)

| Path | Stages |
|---|---|
| `lib/everything_claude_code_adapter.py` | S1, S2, S3 (additive only) |
| `solar-harness.sh` | S4 (additive only) |
| `lib/external-integrations-health.py` | S5 (verify-then-patch) |
| `tests/test-everything-claude-code-integration.sh` | S6 (NEW) |
| `sprints/sprint-20260508-everything-claude-code-integration.handoff.md` | S7 (NEW) |
| `run/ecc-sync-ledger.jsonl` | S2 (created at runtime — not committed) |
| `run/ecc-backups/<ts>/...` | S2 (created at runtime — not committed) |
| `staging/everything-claude-code/...` | S2 (created at runtime — not committed) |

**FROZEN (PM artifacts — DO NOT MODIFY):**
- `vendor/everything-claude-code/` (entire tree)
- `reports/everything-claude-code-audit-20260508.md`
- `config/everything-claude-code.allowlist.json` (must remain empty/conservative)
- `sprint-*.contract.md`, `sprint-*.prd.md`, `sprint-*.design.md`, `sprint-*.plan.md`, `sprint-*.status.json`
- `~/.claude/`, `~/.agents/`, `~/.codex/` (LIVE — touching = stop rule)

## 3. Stop Rules (global, builder-side)

1. **Live filesystem mutation:** any write under `~/.claude`, `~/.agents`, or `~/.codex` → ABORT immediately, restore via rollback, ping planner.
2. **Frozen file mutation:** any write to PM-frozen artifact → ABORT, ping planner.
3. **Allowlist accidental population:** if S2/S3/S6 cause `config/everything-claude-code.allowlist.json` to grow → ABORT, ping planner.
4. **Test isolation breach:** if test touches anything outside `ECC_HOME_OVERRIDE`/`ECC_STAGING` paths → ABORT.
5. **Implementation > 800 lines added:** if total diff exceeds 800 lines (excluding handoff.md) → STOP, ping planner. Suggested target ~400-600 lines.
6. **Builder model drift:** if Sonnet 4.6 unavailable → use Sonnet 4.5; do NOT use GLM-5.1.

## 4. Builder Model

- **Default:** Sonnet 4.6
- **Disabled:** GLM-5.1 (4 prior burns recorded in memory)
- **Fallback:** Sonnet 4.5 if 4.6 unavailable

## 5. Sprint-level Definition of Done

- [ ] S1-S7 all done conditions met
- [ ] All 7 acceptance criteria from contract.md (A1-A7) verified PASS
- [ ] handoff.md written with verify command outputs
- [ ] live `~/.claude`/`~/.agents`/`~/.codex` byte-for-byte unchanged
- [ ] allowlist remains empty
- [ ] tests/test-everything-claude-code-integration.sh runs in <60s
- [ ] No new external dependencies introduced

## 6. Out of Scope (this sprint)

- Actual integration of upstream agents/skills/commands into Solar (requires future allowlist curation sprint)
- Marketplace publishing
- Skill/agent renaming for collision resolution
- Hook activation
- MCP config import
- PM artifact rewrites

These belong to a follow-up sprint after allowlist v0 is curated by a human.

## 7. Planner Sign-off

This plan is surgical: 4 gap-fillers + testability hardening + 1 test suite + 1 handoff. No PM artifact rewrites. No live filesystem touches. Empty-allowlist invariant preserved. Solo topology because the surface is narrow and tightly coupled.

— Planner (sprint-20260508-everything-claude-code-integration)
