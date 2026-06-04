# Design — ThunderOMLX P0 Cache Warm + Advisor Metrics

Sprint: `sprint-20260520-thunderomlx-cache-warm-advisor`
Author: Planner (solar-harness:0.1, opus 4.7)
Authored-At: 2026-05-29T04:50:00Z
Dispatch: `d-20260529T044633Z-aa846a`

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-graph

> **Status note:** This sprint's 4 nodes (N1-N4) shipped and were evaluator-PASSED on 2026-05-23T14:29:07Z (file `<sid>.finalized` records 14:30:22Z). The Planner artifacts in this turn are a **retrospective augmentation** to close the `gate_prd_schema` / `graph_parent_ready_revoked` loop that pulled the sprint back into `drafting/prd_ready` on 2026-05-26T17:56:53Z. No new scope, no new code, no new builder run is being proposed.

---

## 1. Architecture Overview

The shipped system is a **read-only post-startup cache visibility loop** layered on top of an unchanged ThunderOMLX core. Three components participate, none of them mutate runtime parameters:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Mac mini M4 (host)                              │
│                                                                          │
│  ┌──────────────────┐    /health (1×)     ┌──────────────────────────┐  │
│  │ ThunderOMLX 8002 │◀────────────────────│ thunderomlx_auto_        │  │
│  │ Qwen3.6-35b-a3b  │                     │   prewarm.py             │  │
│  │ (unchanged core) │   /v1/chat (4×)     │ (post-startup hook)      │  │
│  │                  │◀────────────────────│                          │  │
│  │  - hot RAM 8GB   │     pane 0/1/2/3    │ → 4-pane sys-prompt fire │  │
│  │  - RAID0 SSD KV  │                     │ → write JSON/MD report   │  │
│  │  - paged SSD KV  │                     └────────┬─────────────────┘  │
│  │                  │                              │                    │
│  │  unsafe paths    │                              ▼                    │
│  │  remain disabled │              ~/.solar/harness/monitor-reports/    │
│  └──────────────────┘              thunderomlx-four-pane-prewarm-*.{json,md}
│                                              │                          │
│                                              ▼                          │
│                                   ┌──────────────────────┐              │
│                                   │ cache_tuning_advisor │              │
│                                   │   (N3, read-only)    │              │
│                                   │  → reads report      │              │
│                                   │  → emits advisor MD  │              │
│                                   │  → audits unsafe     │              │
│                                   │     feature guards    │              │
│                                   └──────────────────────┘              │
└──────────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Path | Owner Node | Role |
|-----------|------|------------|------|
| `thunderomlx_auto_prewarm.py` | `~/.solar/harness/scripts/thunderomlx_auto_prewarm.py` | N2 | Post-startup hook: waits for `/health`, fires one full-system-prompt request per pane, records cached_tokens/verify_s/bad_chars |
| `thunderomlx_prewarm_four_pane.py` | `~/.solar/harness/scripts/thunderomlx_prewarm_four_pane.py` | N2 | Manual fallback (identical payload, idempotent) |
| Launcher edits | `ThunderOMLX/src/omlx/server.py` startup-adjacent | N2 | Persist `--hot-cache-max-size 8GB` + RAID0 SSD cache path; lowercase model-id alias `qwen3.6-35b-a3b` (commit `c8ca823b`) |
| Advisor metrics | `ThunderOMLX/src/omlx/cache_tuning_advisor.py` (read-only) | N3 | Reads prewarm report; renders markdown advisor report; flags unsafe-feature audit |
| Reports directory | `~/.solar/harness/monitor-reports/thunderomlx-four-pane-prewarm-*.{json,md}` | N2/N3 | 20+ shipped reports already on disk (oldest 2026-05-20T19:02:35Z) |

### Data flow

1. **Startup** — ThunderOMLX 8002 boots with hot RAM 8GB + RAID0 SSD KV cache. Unsafe paths (partial block cache / full skip / approximate skip) stay disabled by config.
2. **Health gate** — auto-prewarm polls `GET /health` until 200; bails (no report, no retry storm) if `/health` never reaches ready within timeout.
3. **Prewarm fire** — auto-prewarm issues one `POST /v1/chat/completions` per pane (0/1/2/3) using the canonical system prompt for that pane. Each request waits for cache to write; subsequent requests inherit cached_tokens.
4. **Report write** — auto-prewarm writes a paired JSON + Markdown report to `~/.solar/harness/monitor-reports/thunderomlx-four-pane-prewarm-<UTC>.{json,md}` with per-pane: `prompt_hash`, `prompt_chars`, `warm_s`, `verify_s`, `cached_tokens`, `bad_chars`.
5. **Advisor render** — `cache_tuning_advisor` reads the most recent report and renders a human-readable advisor markdown that also audits unsafe-feature guard status (`partial_block_cache=disabled`, etc.).
6. **Audit** — N4 verification confirms HTTP 200, lowercase model-id alias works, cached_tokens floors satisfied (or exemption logged), `bad_chars=false`.

### Hard invariants (from contract + PRD)

- ThunderOMLX core is **not modified** — only startup-adjacent code and read-only advisor.
- Advisor is **read-only**: never writes runtime knobs, never re-enables unsafe paths, never enables KVTC or semantic cache on the main pane.
- Reports go to `~/.solar/harness/monitor-reports/` only. No `/tmp`, no `/Volumes/toshiba` writes.
- API tokens are read from the Claude pane process env at runtime (`ps eww`) and never written to disk.
- Cache directories (`/Volumes/RAID0-Main/omlx-cache/`) are never deleted by any of these scripts.

---

## 2. DAG (delivered)

```
        ┌──────┐
        │  N1  │  audit: locate startup hook + metric sources
        │ (audit)│
        └──┬───┘
           │ depends_on
     ┌─────┴─────┐
     ▼           ▼
   ┌────┐     ┌────┐
   │ N2 │     │ N3 │   parallel:
   │auto│     │adv │   N2 owns scripts/launcher;
   │prw │     │isor│   N3 owns advisor + reports/
   └─┬──┘     └─┬──┘
     └────┬─────┘
          ▼
        ┌────┐
        │ N4 │  end-to-end verify + handoff
        │eval│
        └────┘
```

- N1 is the only **serial root**; N2 and N3 run in parallel because their `write_scope` sets do not overlap (N2 → scripts + server.py; N3 → cache_tuning_advisor.py + monitor-reports/).
- N4 joins on `passed(N2) ∧ passed(N3)`.

### Architecture guard alignment

- New code is delivered as **side-car scripts** under `~/.solar/harness/scripts/` and a **read-only advisor module**; no patches to the ThunderOMLX scheduler.
- N3's `architecture_policy.package_boundary = "scripts/thunderomlx_*.py + monitor-reports/"`, `core_patch_allowed = false`.
- Rollback is **null operation**: deleting generated reports has no service-side effect (advisor never mutates knobs).

---

## 3. Online exploration alternatives (and why rejected)

Per system rule "≥2 candidates + kill_criteria", the planner considered:

| Candidate | Idea | Kill criterion |
|-----------|------|----------------|
| **Picked: side-car script + read-only advisor** | Post-`/health` shell wrapper invokes auto-prewarm; advisor only reads | Already shipped & PASS; no ThunderOMLX core risk |
| Inline integration in `server.py` lifespan | Auto-prewarm fires from FastAPI startup event | Killed: blocks `/health` first-ready signal; risks deadlock if model load is slow; harder to disable without redeploy |
| Re-enable PBC / full skip / approximate skip | Get cached_tokens "for free" via faster cache paths | Killed by contract: caused previous乱码/empty-reply incidents; not allowed |
| KVTC on main pane | Higher hit ratio | Killed by contract `non_goals` |
| Semantic response cache for coding builder | Reuse prior completions | Killed by contract `non_goals` |

---

## 4. Requirement → Node coverage

| Requirement | N1 | N2 | N3 | N4 |
|-------------|:--:|:--:|:--:|:--:|
| FR-1 auto 4-pane prewarm | | ● | | ● |
| FR-2 report fields | | ● | ● | |
| FR-3 cached_tokens floors | ● | | | ● |
| FR-4 bad_chars=false | | ● | | ● |
| FR-5 lowercase model id | | ● | | ● |
| FR-6 unsafe-feature audit | | | ● | ● |
| FR-7 launch flag persistence | | ● | | ● |
| FR-8 read-only advisor | | | ● | |
| FR-9 PRD schema | (PM/coordinator — not a node) |
| US-01 maintainer | | ● | | ● |
| US-02 builder TTFT | | ● | | ● |
| US-03 cache advisor report | ● | | ● | ● |
| US-04 security audit | | | ● | ● |
| US-05 launch flags persist | | ● | | ● |
| ACC-1 auto-prewarm runs + report | | ● | | ● |
| ACC-2 report 7 fields | | ● | ● | ● |
| ACC-3 cached_tokens floors w/ exemption | ● | | | ● |
| ACC-4 bad_chars=false + HTTP 200 + lowercase | | | | ● |
| ACC-5 launch flag preserved | | ● | | ● |
| ACC-6 unsafe-feature audit log | | | ● | ● |

Every requirement is mapped to ≥1 node; every node carries an explicit `requirement_ids` array in `task_graph.json`. The map is non-trivial (not a single broadcast list).

---

## 5. Risks and stop rules (planner view)

| Risk | Trigger | Stop rule |
|------|---------|-----------|
| Auto-prewarm fires before `/health` ready | Race on cold boot | Auto-prewarm polls `/health` with bounded retries; bail-without-retry on permanent failure (do not loop) |
| Report path drift | Future refactor changes `monitor-reports/` location | N3 advisor reads from a single env-resolvable path; refactor would need this Planner-doc updated too |
| Re-enabled unsafe feature slips through | Silent config drift | FR-6 audit asserts `disabled=true`; advisor emits ALERT if any unsafe path is `enabled=true` |
| `cached_tokens` falls below floor | Prompt change | Exemption-logged: report records `prompt_diff_hash` + advisor flags but doesn't fail-hard |
| Token leak | `ps eww` output captured to file | N4 verified `ps eww` is read in-process, never persisted |
| RAID0 SSD full | Cache writes fail silently | Out of scope for this sprint (OQ-04: ops monitoring sprint) |

---

## 6. Anti-redo guard

This Planner artifact does **not** authorize a new Builder dispatch. Per PRD §架构交接 / Planner Handoff, the coordinator should:

1. Re-run `validate.sh prd` → PASS (the schema-gate flap is being closed via the augmented `task_graph.json` + this design + the new `plan.md`).
2. Re-recognize `<sid>.finalized` → return sprint to `passed`.
3. **Not advance to a fresh planner round**.

If the coordinator nevertheless dispatches Builder, the builder should observe: every node already `reviewing`, every gate already `passed`, and produce a no-op handoff that simply re-states the existing evidence.
