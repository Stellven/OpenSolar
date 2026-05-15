# Plan — Mirage Unified Virtual Filesystem For Solar

Sprint: sprint-20260508-mirage-unified-vfs  
Phase: planning_complete  
Created: 2026-05-08T14:24:00Z  
Inputs:

- `/Users/lisihao/.solar/harness/sprints/sprint-20260508-mirage-unified-vfs.prd.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260508-mirage-unified-vfs.contract.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260508-mirage-unified-vfs.design.md`

## 1. Planning Summary

Mirage integration is a P1 data-plane sprint. It must give Solar one filesystem-like interface for local knowledge, sprint files, Cortex, Solar DB retrieval, QMD/MinerU search, allowlisted project files, and optional Google Drive.

The local probe found Mirage is not currently installed, so implementation must start with install/doctor/degraded-mode. Do not assume the upstream CLI exists before Slice 1 completes.

## 2. Implementation Slices

```text
┌───────┬─────────┬────────────────────────────────────────┬──────────────────────────────┐
│ Slice │ Owner   │ Scope                                  │ Acceptance                   │
├───────┼─────────┼────────────────────────────────────────┼──────────────────────────────┤
│ S1    │ Builder │ install/doctor/manifest/CLI/workspace  │ A1 A2 A3                     │
│ S2    │ Builder │ unified search: Mirage paths + QMD + DB│ A4                           │
│ S3    │ Builder │ status/events/security/tests/docs      │ A5 A6 A7 A8                  │
└───────┴─────────┴────────────────────────────────────────┴──────────────────────────────┘
```

Recommended concurrency:

- Run S1 and S2 in parallel only after S1 creates the CLI shim interface contract.
- S3 waits for S1+S2 because status/tests depend on command outputs.
- If current P0 is still using builder panes, keep this sprint at planning_complete and dispatch after P0 builder/evaluator release.

## 3. Write Ownership

S1 owns:

- `/Users/lisihao/.solar/harness/config/mirage.solar.yaml`
- `/Users/lisihao/.solar/harness/lib/solar_mirage.py`
- `/Users/lisihao/.solar/harness/solar-harness.sh` only the `mirage)` command family
- `/Users/lisihao/.solar/harness/state/mirage/` runtime files

S2 owns:

- `/Users/lisihao/.solar/harness/lib/mirage_search.py`
- Search-related additions inside `/Users/lisihao/.solar/harness/lib/solar_mirage.py`
- No changes to P0-owned `solar-knowledge-context.py`; call it if it exists, skip if missing.

S3 owns:

- `/Users/lisihao/.solar/harness/lib/symphony/status-server.py` only `mirage` status section
- `/Users/lisihao/.solar/harness/lib/mirage_events.py`
- `/Users/lisihao/.solar/harness/tests/test-mirage-unified-vfs.sh`
- `/Users/lisihao/.solar/harness/docs/mirage-unified-vfs.md`

Do not touch:

- `/Users/lisihao/.claude/hooks/*`
- `/Users/lisihao/.solar/harness/lib/solar-knowledge-context.py`
- `/Users/lisihao/.solar/harness/integrations/wiki-capture-server.py`
- `/Users/lisihao/.solar/harness/integrations/obsidian-wiki-bridge.sh`
- `/Users/lisihao/Knowledge` except temp smoke file under `_raw` during explicit integration test.

## 4. S1 Detailed Plan — Install, Doctor, Manifest, Exec

Deliverables:

- `config/mirage.solar.yaml`
- `lib/solar_mirage.py`
- `solar-harness.sh` `mirage)` subcommands

Steps:

1. Add manifest loader using Python stdlib only. YAML can be a constrained parser if PyYAML is unavailable, or use JSON-compatible YAML subset.
2. Implement `doctor --json` that works even when Mirage is absent.
3. Implement package detection:
   - `which mirage`
   - `python3 -c 'import mirage'`
   - `npm list -g @struktoai/mirage-node`
4. Implement local-only degraded workspace state under `/Users/lisihao/.solar/harness/state/mirage/solar-default.json`.
5. Implement mount resolver:
   - logical path to physical path
   - deny subpaths
   - write mode checks
   - symlink escape checks via resolved absolute path
6. Implement `exec -- <cmd>` for allowed shell verbs first: `ls`, `find`, `grep`, `cat`, `head`, `wc`, `jq` when host tool exists.
7. Add stdout/stderr truncation and redaction.
8. Emit events for install/workspace/command/write-denied.

Acceptance commands:

```bash
solar-harness mirage doctor --json
solar-harness mirage workspace create --id solar-default --json
solar-harness mirage mounts --json
solar-harness mirage exec -- 'find /knowledge -name "*.md" | head'
```

## 5. S2 Detailed Plan — Unified Search

Deliverables:

- `lib/mirage_search.py`
- `solar-harness mirage search`

Steps:

1. Add source adapters:
   - `mirage_path`: bounded grep over `/knowledge`, `/sprints`, `/cortex`, `/projects` allowlist.
   - `qmd`: call `solar-harness wiki qmd-search "<query>" --json` if available.
   - `solar_db`: call `/Users/lisihao/.solar/harness/lib/solar-knowledge-context.py --query ... --json` if present.
2. Normalize hits:
   - `mount`
   - `path`
   - `source_type`
   - `snippet`
   - `provenance`
   - `score_or_rank`
3. Dedupe by canonical path/table/id.
4. Enforce budgets:
   - default 10 hits
   - default 4,000 chars
   - timeout per adapter 2s
5. Degrade instead of fail when QMD or Solar DB router is absent.

Acceptance command:

```bash
solar-harness mirage search "Solar Harness Obsidian" --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["hits"]; assert len({h["source_type"] for h in d["hits"]}) >= 2'
```

## 6. S3 Detailed Plan — Status, Events, Security, Tests, Docs

Deliverables:

- `lib/mirage_events.py`
- status-server `mirage` section
- `tests/test-mirage-unified-vfs.sh`
- `docs/mirage-unified-vfs.md`

Steps:

1. Add `last-probe.json` written by `doctor`.
2. Add status-server reader:
   - no SDK import from status-server
   - never blocks network or Drive
   - timeout-free simple JSON read
3. Add event writer for:
   - `mirage_installed`
   - `mirage_workspace_created`
   - `mirage_command_executed`
   - `mirage_mount_degraded`
   - `mirage_secret_redacted`
   - `mirage_write_denied`
4. Add tests with temp directories:
   - temp knowledge
   - temp raw
   - temp sprints
   - temp cortex
   - missing Drive credentials
   - fake secret redaction fixture
5. Add docs:
   - install
   - doctor
   - manifest fields
   - Google Drive credential policy
   - examples
   - rollback

Acceptance commands:

```bash
curl -fsS http://127.0.0.1:8765/status \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "mirage" in d'

bash /Users/lisihao/.solar/harness/tests/test-mirage-unified-vfs.sh
```

## 7. Security Gate

Block merge if any condition is true:

- `/Users/lisihao` home directory is mounted as a whole.
- `/drive` write succeeds without `--allow-write-drive`.
- secret patterns appear in stdout, events, status, or generated docs.
- tests write to real Google Drive.
- status-server imports Mirage SDK or performs network probing per request.
- command execution can escape mount root through `..` or symlink.

## 8. Builder Dispatch

Builder S1 prompt:

```text
读取 sprint-20260508-mirage-unified-vfs.contract/design/plan。
只做 S1：install/doctor/manifest/CLI/workspace/exec。
你不独占代码库；不要改 P0 sprint 文件，不要改 hooks，不要碰 status-server/search/tests/docs。
完成后写 /Users/lisihao/.solar/harness/sprints/sprint-20260508-mirage-unified-vfs.handoff-s1.md。
```

Builder S2 prompt:

```text
读取 sprint-20260508-mirage-unified-vfs.contract/design/plan。
只做 S2：mirage_search.py 和 solar-harness mirage search。
你不独占代码库；不要改 hooks，不要改 P0-owned solar-knowledge-context.py，只能调用它。
完成后写 /Users/lisihao/.solar/harness/sprints/sprint-20260508-mirage-unified-vfs.handoff-s2.md。
```

Builder S3 prompt:

```text
等 S1/S2 handoff 到齐后执行。
只做 S3：status/events/security/tests/docs。
不得真实写 Google Drive；测试必须 temp。
完成后写 /Users/lisihao/.solar/harness/sprints/sprint-20260508-mirage-unified-vfs.handoff.md。
```

## 9. Evaluator Checklist

Evaluator must verify:

- A1-A8 commands pass.
- `doctor` works before and after Mirage install.
- Missing Drive credentials do not fail local commands.
- `/raw` write succeeds, `/solar` and `/drive` write fail by default.
- `/status` includes `mirage`.
- Search output is sourced and bounded.
- No secret leakage in events/status/docs.

## 10. Rollback

Rollback steps:

```bash
rm -rf /Users/lisihao/.solar/harness/state/mirage
rm -f /Users/lisihao/.solar/harness/config/mirage.solar.yaml
```

Then revert only the `mirage)` block in `solar-harness.sh` and the `mirage` section in `status-server.py`. Do not touch wiki/QMD/Solar DB data.

## 11. Definition Of Done

- Contract A1-A8 pass.
- All changed files are within declared write ownership.
- Local-only mode works without upstream Mirage installed.
- If Mirage SDK is installed, wrapper reports version and can use it without changing CLI contract.
- Google Drive remains optional/degraded/read-only by default.

