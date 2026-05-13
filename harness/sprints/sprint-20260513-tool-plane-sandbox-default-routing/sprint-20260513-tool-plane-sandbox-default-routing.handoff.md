# Handoff — sprint-20260513-tool-plane-sandbox-default-routing

Builder: builder incarnation (pane 0.2, anthropic:sonnet)
Round: 1
Submitted: 2026-05-13T20:50:00Z
Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge

## 1. 变更文件

### Library code (lib/)

- `lib/qmd_adapter.py` — `_qmd_status_sandboxed` already migrated in prior round; kept intact.
- `lib/mirage_search.py` — added `SandboxHand` import block (+ `LAST_QMD_ROUTE` module global), new `_qmd_search_sandboxed(query, max_hits)` helper, and reroute of `search_qmd()` so it always tries SandboxHand first and falls back to host_fallback record only when import fails.
- `lib/wiki-upload-backfill.py` — added `SandboxHand` import block (+ `LAST_EXTRACT_ROUTE` module global), new `_run_extract_sandboxed(cli_name, argv, timeout)` helper, modified `extract_pdf_text` (pdftotext) and `extract_pages_text` (qlmanage) to route through sandbox first.
- `lib/capability_activation_proof.py` — added `_load_module_by_path` helper, `proof_qmd_search_routes_through_sandbox`, `proof_pdftotext_extract_routes_through_sandbox`; both registered in `main` proofs list. Total proofs grew **11 → 13**.

### Tests (tests/)

- `tests/test-solar-kb-qmd-fallback.sh` — added T11 (mirage_search.search_qmd routes through SandboxHand) + T12 (evidence file argv mode + command_name=qmd-search). Total cases 10 → 12, all PASS.
- `tests/test-wiki-upload-ingest-closure.sh` — added `sandbox-extract` case (8 assertions: cat sandbox routing + pdftotext sandbox routing with evidence file existence + argv mode). All PASS.

### Reports / Knowledge

- `reports/tool-plane-sandbox-routing/document-route.{json,md}` — new R2 deliverable.
- `reports/tool-plane-sandbox-routing/closeout.{json,md}` — new R4 deliverable.
- `reports/capability-activation-proof-latest.json` (regenerated, 13/13 PASS).
- `~/Knowledge/_raw/solar-harness-local-disposable-sandbox-assessment-20260513.md` — appended sprint-update section with migration table, exclusions, pending list, verification ledger.
- `~/Knowledge/_raw/tool-plane-sandbox-default-routing-closeout-20260513.md` — new file.

### Not changed (and intentionally so)

- `lib/wiki-upload-extract.py` — listed in R2 write_scope but no functional change needed; the extraction CLI lives in `wiki-upload-backfill.py`. No edit recorded.
- `lib/symphony/status-server.py` — no edit needed; status UI projection of `sandbox` check still passes 11/11 → 13/13 via existing health channel.
- `tests/storage/test-s3-storage.sh` — listed in R1 write_scope, but s3 storage is unrelated to sandbox routing; no edit needed.
- `lib/hands_runtime.py` — no public API change.

## 2. Done 定义达成

| Acceptance | Evidence |
|------------|----------|
| **A1** R0 inventory `inventory.json` + `inventory.md` + 5-tag classification | `reports/tool-plane-sandbox-routing/inventory.{json,md}` (written prior round; 38 files, 132 occurrences classified) |
| **A2** QMD path migrated or explicit pending (no fake ok) | `mirage_search.search_qmd` migrated, `qmd_adapter._qmd_status_sandboxed` migrated; foreground QMD embed **not** sandboxed (Stop Rule honored), background_worker tag noted in inventory and closeout |
| **A3** Document extraction smoke sandbox-ized or N/A | `wiki-upload-backfill.extract_pdf_text` (pdftotext) and `extract_pages_text` (qlmanage) migrated. Small text fixture regression case `sandbox-extract` runs through `cat` argv (8/0 PASS). Secret names empty in evidence (no inline creds). |
| **A4** Activation proof fails if migrated path regresses to host | Both new proofs check `executor == "sandbox"`, `execution_mode == "argv"`, and evidence file existence. Any regression to naked subprocess flips proof to `error`. |
| **A5** Status UI / report surfaces migrated routing | `proof_status_ui_capability_health_projection` still passes; `reports/capability-activation-proof-latest.json` now lists 13 proofs incl. 2 new positive routes. `closeout.md` summarizes route status. |
| **A6** Five regression tests stay green | hands-runtime 53/0, status-projection PASS, mirage-substrate 15/0, mirage-unified-vfs 36/0, ruflo-integration 10/0. Plus extension tests: qmd-fallback 12/0, wiki-upload sandbox-extract 8/0. |
| **A7** Closeout 3 columns + parent readiness | `closeout.md` three-column table + `evaluator_can_review: true` in `closeout.json`. |
| **A8** Evaluator (not builder) declares passed | Builder hands off; status flips to `reviewing` for evaluator pane. |

## 3. 验证方法

```bash
# 1. Compile
python3 -m py_compile \
  ~/.solar/harness/lib/hands_runtime.py \
  ~/.solar/harness/lib/solar_mirage.py \
  ~/.solar/harness/lib/ruflo_adapter.py \
  ~/.solar/harness/lib/capability_activation_proof.py \
  ~/.solar/harness/lib/mirage_search.py \
  ~/.solar/harness/lib/wiki-upload-backfill.py

# 2. Regression tests (contract Required Verification)
bash ~/.solar/harness/tests/runtime/test-hands-runtime.sh
bash ~/.solar/harness/tests/test-status-capability-health-projection.sh
bash ~/.solar/harness/tests/test-mirage-substrate.sh
bash ~/.solar/harness/tests/test-mirage-unified-vfs.sh
bash ~/.solar/harness/tests/plugins/test-ruflo-integration.sh

# 3. Sprint extension tests
bash ~/.solar/harness/tests/test-solar-kb-qmd-fallback.sh         # T11/T12 are sprint extension
bash ~/.solar/harness/tests/test-wiki-upload-ingest-closure.sh --case sandbox-extract

# 4. Honest activation proof end-to-end
python3 ~/.solar/harness/lib/capability_activation_proof.py | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["ok"], d["passed"], "/", d["total"])'
# Expected: True 13 / 13
```

## 4. 评估者备注

- 上一轮 builder（同一 pane）由于 `Workflow Guard` 误判（`status.json` drift）被一度阻断；本轮在 `status` 已被 wake 推进到 `phase=planning_complete, handoff_to=builder_parallel, target_role=builder_main`（wake `2026-05-13T20:41:32Z`: "builder DAG dispatch is allowed"）后继续完成 R2/R3/R4。
- PRD / design / plan / task_graph 全部由前序 pane 在 20:34-20:41 写就；本 builder 仅按 plan 执行，无 contract 修改。
- 所有迁移均使用 `SandboxHand` 现有 argv + write_guard API，无新公共接口；secret 处理走 `secret_refs` + redact，evidence 中 `secret_names` 全为空。
- 控制面（tmux/ssh/rsync/launchctl/status-server lifecycle/test-runner orchestration）严格按合约 Stop Rule 未被改动。
- 前台 QMD embed 未被强制 sandbox（Stop Rule 第二条），仅 smoke/status 通道 sandbox 化。
- evaluator 复核入口：先看 `reports/capability-activation-proof-latest.json` 是否 13/13 PASS，然后随机挑一份 `reports/hands-sandbox-evidence/sandbox-*/evidence.json` 验 `command_name` 与 `execution_mode=argv`。

## 5. Stop-rule self-audit

- [x] No `tmux` routed through SandboxHand.
- [x] No `ssh` / `rsync` routed through SandboxHand.
- [x] No `launchctl` routed through SandboxHand.
- [x] No status server lifecycle routed through SandboxHand.
- [x] No test runner orchestration routed through SandboxHand.
- [x] No foreground QMD embed run.
- [x] No claim of full kernel isolation in any deliverable.
- [x] No write_scope exceeded without scope-change note. (One R2 file `wiki-upload-extract.py` was in scope but did not need editing; recorded above.)
