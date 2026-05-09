# Design — Everything Claude Code Integration Backlog

Sprint: sprint-20260508-everything-claude-code-integration
Author: planner
Created: 2026-05-08
Source PRD: sprint-20260508-everything-claude-code-integration.prd.md
Source contract: sprint-20260508-everything-claude-code-integration.contract.md

## 0. Background

User remembers an open-source repo "EverythingCloudCode" (likely typo). Search confirms upstream is `affaan-m/everything-claude-code` — a Claude Code plugin marketplace bundle containing 80 agents, 117 commands, 61 skills, 72 hooks, 130 rules, 2 MCP configs, 157 scripts, 117 tests, 5 contexts.

The upstream is **high blast-radius**: hooks fire on every Claude session, MCP configs may carry placeholder credentials, install scripts touch `~/.claude` directly. Naive "just install everything" would silently overwrite Solar/Gstack/Superpowers and risk credentials leak.

Sprint goal: **register as candidate, audit thoroughly, sandbox install path, never auto-activate**. Solar must end up with:
- a vendored read-only copy
- a machine-readable inventory + collision map
- a CLI that explains `dry-run` install consequences
- an empty-by-default allowlist
- explicit sync/rollback semantics
- a passing regression test that does not touch live `~/.claude`

## 1. Current Pre-Work (PM-completed before planner pickup)

| Deliverable | State | Evidence |
|-------------|-------|----------|
| Vendor at `~/.solar/harness/vendor/everything-claude-code/` | ✅ exists | `git rev-parse HEAD` = `841beea45cb25ba51f29fa45b7e272938d19b80a` |
| Audit report `reports/everything-claude-code-audit-20260508.md` | ✅ exists | head shows verdict + inventory + 41 collisions table |
| Allowlist `config/everything-claude-code.allowlist.json` | ✅ exists | `default_action=defer`, all surfaces empty, hooks/mcp/install_scripts blocked by default |
| Adapter `lib/everything_claude_code_adapter.py` | ✅ partial (365 lines) | has `doctor`, `inventory`, `dry_run`, `write_report`, `collision_report`, `compatibility`; **missing `sync` + `rollback`** |
| `solar-harness.sh` subcommands | ✅ partial | has `doctor / inventory / report / install --dry-run`; **missing `sync --allowlist <path>`** |
| `external-integrations-health.py` registration | ✅ exists | line 304: entry `affaan-m/everything-claude-code` linked to vendor + allowlist + audit |
| Test `tests/test-everything-claude-code-integration.sh` | ❌ does not exist | Single biggest gap |

**Implication for planner**: this is mostly a closure sprint, not a greenfield design. Plan must respect existing implementation choices and only fill gaps. No rewrite of `adapter.py` allowed.

## 2. Architecture

### 2.1 Surface Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│  upstream: github.com/affaan-m/everything-claude-code       │
│            commit 841beea45                                 │
└──────────────────┬──────────────────────────────────────────┘
                   │ git clone (read-only)
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Vendor:  ~/.solar/harness/vendor/everything-claude-code/   │
│  (read-only, never mutated by adapter)                      │
└──────────────────┬──────────────────────────────────────────┘
                   │ scan
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Adapter:  lib/everything_claude_code_adapter.py            │
│   doctor / inventory / dry_run / write_report / sync /      │
│   rollback                                                  │
└──────────┬──────────────────────────────┬────────────────────┘
           │ reads                        │ writes (allowlisted only)
           ▼                              ▼
   ┌──────────────┐         ┌─────────────────────────────────┐
   │ Allowlist    │         │ Staging: ~/.solar/harness/      │
   │ (config)     │         │   staging/everything-claude-code│
   │ default      │         │ Live:    ~/.claude/{agents,...} │
   │ empty        │         │   (only on `sync` + allowlist)  │
   └──────────────┘         └─────────────────────────────────┘
```

### 2.2 Default Behavior Matrix

| Action | Touches live `~/.claude`? | Touches staging? | Reads upstream? | Writes report? |
|--------|--------------------------|------------------|-----------------|----------------|
| `doctor` | no | no | no (cached) | no |
| `inventory` | no | no | yes (read-only) | no |
| `report` | no | no | yes | yes (audit md) |
| `install --dry-run` | **no (asserted live_hook_changes=0)** | no | yes | no |
| `sync --allowlist X` | **only allowlisted entries** | yes (staging mirror) | yes | no |
| `rollback` | restore from `.solar/harness/run/ecc-backups/<ts>/` | no | no | no |

### 2.3 Why empty allowlist by default

41 collisions detected against `.agents/skills/` (e.g., `api-design`, `backend-patterns`, `e2e-testing`, `eval-harness`, `exa-search`, `frontend-patterns`). Each is a Solar/Gstack-owned skill name. Auto-install would shadow Solar's curated versions silently. Therefore the contract demands `default_action=defer` until human review explicitly adds entries.

## 3. Component Design

### 3.1 Adapter additions (`lib/everything_claude_code_adapter.py`)

Add two top-level functions and route them via `main()`:

```python
def sync(allowlist_path: Path, dry_run: bool = False) -> dict:
    """
    Read allowlist JSON; for each allowed entry:
      1. Resolve upstream path under VENDOR.
      2. Compute collision against local target (e.g., ~/.claude/skills/<name>).
      3. If collision and not --force: skip + record reason.
      4. If no collision: backup any pre-existing same-path file to
         ~/.solar/harness/run/ecc-backups/<sync_ts>/<rel_path> and copy.
      5. Stage a mirror under
         ~/.solar/harness/staging/everything-claude-code/<surface>/<name>
         regardless (always staged, only conditionally synced live).
      6. Append to ledger:
         ~/.solar/harness/run/ecc-sync-ledger.jsonl
    Returns:
      {sync_ts, allowlist_version, actions[{surface,name,result,backup_path?,target?}],
       counts:{synced,skipped,collided,backed_up}, live_hook_changes (always 0 unless allowlist explicitly contains hooks)}
    """

def rollback(sync_ts: str | None = None) -> dict:
    """
    If sync_ts is None: rollback the most recent sync (read from ledger tail).
    For each backed-up file in ~/.solar/harness/run/ecc-backups/<sync_ts>/:
      restore to original path; remove synced new file if it had no backup.
    Update ledger with rollback event.
    Returns: {sync_ts, restored_count, removed_count, status}
    """
```

CLI wiring in `solar-harness.sh` `everything-claude-code|ecc)` block:
- add `sync) shift; ALLOWLIST=$(get_arg --allowlist); python3 .../adapter.py sync --allowlist "$ALLOWLIST" "$@"`
- add `rollback) shift; python3 .../adapter.py rollback "$@"`

### 3.2 Inventory JSON schema (verify existing matches contract A2)

Must contain top-level `counts` with all 8 keys: `agents commands skills hooks rules mcp_configs scripts tests`. Existing `inventory()` produces this; verify with smoke test in S1.

### 3.3 Dry-run JSON schema (verify A3, A4)

Must contain:
- `collisions: [...]` (each: surface, name, upstream_path, local_path, severity)
- `compatibility: { gstack: {...}, superpowers: {...} }` with explicit fields
- `live_hook_changes: 0` (integer; >0 only if allowlist has `hooks` entries AND `--force-live-hooks` passed; never default)

Existing `dry_run()` already returns these per code inspection (lines 240-256). S1 verifies schema.

### 3.4 Integrations status integration (A6)

`solar-harness integrations status --json` must include an item with `name="affaan-m/everything-claude-code"` and `status` ∈ `{warn, missing, ok}`. PM has registered this in `external-integrations-health.py:304`. Until allowlist non-empty AND last sync produced no collisions, status must remain `warn`. Logic:

```python
def _status_for_ecc():
    al = json.load(open(allowlist_path))
    has_allowed = any(al["allowed"][k] for k in al["allowed"])
    if not has_allowed:
        return "warn"  # vendored but not activated
    # additional checks: ledger present + last sync clean
    return "warn"  # pin to warn until human explicitly approves
```

S3 verifies behavior; if existing health.py returns `ok` it must be downgraded to `warn`.

### 3.5 Test architecture (`tests/test-everything-claude-code-integration.sh`)

Must use temp directories — never touch live `~/.claude`. Contract A7.

```
TMPHOME=$(mktemp -d)
TMPSTAGING=$(mktemp -d)
ECC_HOME_OVERRIDE=$TMPHOME ECC_STAGING=$TMPSTAGING bash adapter.py ...
```

Adapter must accept env vars `ECC_HOME_OVERRIDE` and `ECC_STAGING` for testability. If not currently supported, S2 adds them (small surgical patch — env-vars only, no signature change).

Test cases (organized by `--case`):

| Case | Asserts | Contract clause |
|------|---------|-----------------|
| `inventory` | counts has 8 surfaces, total ≥ 700 items | A2 |
| `collisions` | dry-run reports ≥ 30 collisions, all entries have surface/name/local/upstream | A3 |
| `compatibility` | dry-run includes `compatibility.gstack` + `compatibility.superpowers` keys | A3 |
| `dry-run-no-live` | `live_hook_changes == 0` | A4 |
| `sync-rollback` | sync with empty allowlist → 0 changes; sync with sample allowlist into TMPHOME → backups created; rollback restores | A5 |
| `idempotent-sync` | run sync twice → second run reports 0 new changes | A5 |
| `status-warn` | `solar-harness integrations status --json` shows ecc with status `warn` | A6 |
| (default) | runs all cases | A7 / A8 |

`--case foobar` → exit 2 + usage hint (avoid the wiki-upload-ingest D7 trap).

## 4. Risks

| ID | Risk | Mitigation |
|----|------|------------|
| R-D1 | Adapter `sync` accidentally writes to live `~/.claude` during test | Hard-require `ECC_HOME_OVERRIDE` env var when `ECC_TEST=1`; refuse to write to `$HOME/.claude` if test mode |
| R-D2 | Allowlist gets accidentally populated | Add unit test asserting committed allowlist file has empty `allowed` arrays |
| R-D3 | Rollback ledger corruption on concurrent sync | Use `flock` on ledger file; document single-writer invariant in adapter docstring |
| R-D4 | `live_hook_changes` regression after future commits | Test asserts strict `== 0` not `<= 0`; CI catches |
| R-D5 | Upstream vendor drift (force-push) | Pin commit SHA in audit report; doctor reports drift |
| R-D6 | Status server returns `ok` prematurely | S3 explicit downgrade; test asserts `status in (warn, missing)` (per contract A6) |

## 5. Out of Scope

- Implementing actual integrations of upstream agents into Solar workflow (separate sprints per allowlist decision)
- Marketplace publishing
- Renaming colliding skills (separate Gstack ownership decision)
- Removing PM-completed artifacts (vendor/audit/allowlist/adapter/solar-harness wiring/health.py registration are FROZEN)

## 6. Migration

This sprint is additive — no live config changes. Migration story is the allowlist itself: future planners can add `agents/foo` to `allowed.agents` and re-run sync to bring it in selectively.

## 7. Planner Sign-off

Design respects PM pre-work (no rewrite); fills the four gaps (sync, rollback, integrations status verification, regression suite); enforces hard test isolation; pins empty-allowlist invariant. Builder slice is single (solo topology) — small surface, no need for parallel mixture.

