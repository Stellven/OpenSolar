# Plan — Mirage As Unified Data Substrate For Codex And Solar

## P0 Mainline

Implement Mirage adoption and governance in three slices. Builder must keep existing unified-vfs tests passing and run evaluator-facing real-command probes before claiming done.

## Slice S1 — Boundary Probes And Evaluator Gate

Write scope:
- `tests/test-mirage-substrate.sh`
- evaluator verification docs/template if present
- minimal stderr wording fixes in `lib/solar_mirage.py` only if probes require it

Tasks:
1. Add probes for denied host absolute reads: `~/.zshrc`, `/etc/passwd`, and one credential-like path.
2. Add denied write probes for `/knowledge`, `/sprints`, `/solar`, `/cortex`, `/drive`.
3. Add positive probe for `/raw/$(date +%Y-%m-%d)/_probe.md` write/read.
4. Emit JSON summary with `probes_passed` and `probes_failed`.
5. Ensure evaluator eval.md includes a `Real Commands Executed` section.

Validation:
```bash
bash ~/.solar/harness/tests/test-mirage-substrate.sh
```

Stop rule:
- Any host absolute path read succeeds: stop and fix dispatcher boundary before touching UI/docs.

## Slice S2 — Status And Config UI

Write scope:
- `lib/symphony/status-server.py`
- `solar-config-ui.sh`
- `config/mirage.solar.yaml` write path helpers only if needed

Tasks:
1. Add `config.mirage.enabled`, `workspace_id`, `mounts`, `last_probe_at`, `drive_status`, `stale`, `qmd_indexed` to 8765 `/api/status`.
2. Add same field shape to 8789 config UI status.
3. Add Mirage card/section to HTML.
4. Add UI controls: enabled toggle, workspace selector, Drive ro/off state, credential configured/fingerprint display, re-probe action.
5. Persist UI config changes via backup + temp + atomic rename.

Validation:
```bash
curl -fsS http://127.0.0.1:8765/api/status | python3 -m json.tool | grep -A20 '"mirage"'
curl -fsS http://127.0.0.1:8789/api/status | python3 -m json.tool | grep -A20 '"mirage"'
curl -fsS http://127.0.0.1:8789/ | grep -i Mirage
```

Stop rule:
- HTML or JSON leaks a Drive token/path value: stop, redact, and write a P0 finding.

## Slice S3 — Adoption Docs And Dispatch Governance

Write scope:
- `docs/mirage-data-substrate-codex-solar.md`
- `docs/mirage-runbook.md`
- `~/.solar/CLAUDE.md`
- `CODEX-USAGE.md` or existing harness usage doc
- dispatch template text in coordinator/harness only for wording injection

Tasks:
1. Promote Mirage language to `Canonical entry`.
2. Add anti-patterns: direct `rg ~/Knowledge`, direct `sqlite3 ~/.solar/solar.db`, direct host sprint traversal for cross-source reads.
3. Add examples for search, sprint read, Knowledge read, Cortex read, QMD read, and `/raw` draft.
4. Add runbook tables for what goes through Mirage and what uses dedicated write APIs.
5. Inject `use mirage` guidance into Solar/Codex dispatch prompts.

Validation:
```bash
grep -q "Canonical entry" ~/.solar/harness/docs/mirage-data-substrate-codex-solar.md
grep -q "use mirage" ~/.solar/CLAUDE.md
test -s ~/.solar/harness/docs/mirage-runbook.md
```

## Parallelism

- S1 and S3 may run in parallel if workers stay in disjoint files.
- S2 should start after S1 probes are present so UI/status work cannot mask sandbox regression.
- Evaluator work starts only after builder submits S1-S3 handoff.

## Builder Handoff

Primary builder should implement S1 first. If multiple workers are available, dispatch:
- Worker A: S1 tests and evaluator real-command section.
- Worker B: S2 status/config UI.
- Worker C: S3 docs and prompt wording.

Do not edit live tmux panes. Do not restart coordinator from builder work. Do not open Drive write mode.

