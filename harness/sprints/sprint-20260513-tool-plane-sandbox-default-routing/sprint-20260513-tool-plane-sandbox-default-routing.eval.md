# Sprint Evaluation — Tool Plane Sandbox Default Routing

Sprint: `sprint-20260513-tool-plane-sandbox-default-routing`
Evaluator: Solar Judge (Opus 4.7)
Date: 2026-05-13T21:18Z
Round: 1

Knowledge Context: solar-harness context inject used
Session Log: solar-harness session evaluate used
Harness Modules Used: harness-knowledge, harness-graph (read-only)

## 总判定

**PASS**

只评 parent sprint 合约 6 条 Acceptance。R0 已经通过 node-level eval (R0-eval.md / R0-eval.json)；R1-R4 由 contract-patrol 标 passed，本次以 builder handoff + 实跑验证作为 parent-level 复核证据。

## Evidence Checked (独立复跑)

1. **All 7 deliverable files exist** (`ls -la`)
   - `reports/tool-plane-sandbox-routing/{inventory,qmd-route,document-route,closeout}.{json,md}` — 8/8
   - `reports/capability-activation-proof-latest.json` (7343B, mtime 17:11)
   - `Knowledge/_raw/solar-harness-local-disposable-sandbox-assessment-20260513.md` (20508B, sprint-update section line 238+)
   - `Knowledge/_raw/tool-plane-sandbox-default-routing-closeout-20260513.md` (5893B, new)

2. **Activation proof 13/13 PASS** (fresh re-run `python3 lib/capability_activation_proof.py`)
   - 11 prior proofs + 2 new (`mirage_search.search_qmd routes through SandboxHand` + `wiki-upload-backfill extract routes through SandboxHand`)
   - Persisted `capability-activation-proof-latest.json` 也是 13/13 PASS，与命令行复跑一致。

3. **5 contract-required regression tests** (fresh run)
   | Test | Result |
   |------|--------|
   | `tests/runtime/test-hands-runtime.sh` | 53/0 PASS |
   | `tests/test-status-capability-health-projection.sh` | PASS (`global_status=warn` 是非阻塞，pane projection 仍 PASS) |
   | `tests/test-mirage-substrate.sh` | 15/0 PASS |
   | `tests/test-mirage-unified-vfs.sh` | 36/0 PASS |
   | `tests/plugins/test-ruflo-integration.sh` | 10/0 PASS |

4. **2 sprint extension tests** (fresh run)
   - `tests/test-solar-kb-qmd-fallback.sh` → 12/0 (T11 + T12 显式确认 `mirage_search.search_qmd` 命中 SandboxHand + argv 模式 evidence 文件)
   - `tests/test-wiki-upload-ingest-closure.sh --case sandbox-extract` → 8/0 (`cat` + `pdftotext` 双路径都拿到 sandbox+argv+evidence)

5. **Python compile**: `hands_runtime.py / solar_mirage.py / ruflo_adapter.py / capability_activation_proof.py / mirage_search.py / wiki-upload-backfill.py` → 全部 `ALL_COMPILE_OK`。

6. **Code-level cross-check** (grep)
   - `mirage_search.py:318` 存在 `_qmd_search_sandboxed`，`LAST_QMD_ROUTE` global @line 48
   - `wiki-upload-backfill.py:59` 存在 `_run_extract_sandboxed`，`LAST_EXTRACT_ROUTE` global @line 56
   - `capability_activation_proof.py:646/703` 两个新 proof，`main` proofs list 注册在 line 848-849

7. **Stop-rule audit** (grep + json scan of recent evidence)
   - 扫 `reports/hands-sandbox-evidence/*/evidence.json` (近 48h) argv first token — 0 命中 `tmux/ssh/rsync/launchctl/qmd-embed`。
   - 最近 sandbox `command_name` 全部为合法 tool/data-plane CLI: `qmd-search, doc-extract-cat, doc-extract-pdftotext, qmd-status, ruflo-help, ruflo-version, doctor-smoke, activation-sandbox`。

## Done 条件逐条检查 (Acceptance Result)

| # | Acceptance | Verdict | Evidence |
|---|---|---|---|
| **A1** | 完整 inventory 把剩余 `subprocess.run` 分到 5 类 | PASS | R0-eval 已确认 (6 planes 含全部 5 必需 + 1 infrastructure)；`inventory.json` 现存 11283B；mirror 到 `_raw` 与 repo 文件 `diff` IDENTICAL |
| **A2** | 至少一条 user-triggered tool/data-plane 路径迁移到 SandboxHand，并带 executor/mode/evidence_file | PASS | **4 条**迁移完成: `qmd status / qmd search / pdftotext / qlmanage`。Activation proof 两条新 proof 全 PASS。Sandbox evidence 文件存在且 `execution_mode=argv`、`command_name` 匹配。 |
| **A3** | QMD 和 document extraction 分别分析；长跑 embed 不被前台 sandbox | PASS | `qmd-route.md` + `document-route.md` 分两份独立报告。Inventory 把 `qmd-embed` 标 `background_worker` 并明确排除；closeout "Intentionally excluded" 第一条就是 `QMD long-running embed worker`。 |
| **A4** | Activation proof 在迁移路径退化为 host 时报错 | PASS | 两个新 proof 硬编码 `route.get("executor") == "sandbox" and route.get("execution_mode") == "argv" and evidence_file.exists()` (`capability_activation_proof.py:676-682, 742-750`)。任何 regression 都会 flip 到 `status=error`。 |
| **A5** | 回归测试覆盖 host 路径阻塞 / allowed write / evidence 生成 | PASS | 5 合约必需测 (53+15+36+10 + status PASS) + 2 sprint extension (12 + 8) = **131 个独立断言全绿**。`sandbox-extract` case 显式断言 `evidence exists: True`、`execution_mode=argv`。 |
| **A6** | `_raw` 文档更新 migrated / 未迁移 / pending | PASS | `solar-harness-local-disposable-sandbox-assessment-20260513.md` 在 line 238+ 新增 "Update — 2026-05-13" 节；`tool-plane-sandbox-default-routing-closeout-20260513.md` 是新建 closeout，含三栏 migrated / excluded / pending 表格。 |

## Stop Rules Self-Audit (独立复核)

| Stop Rule | 状态 | 证据 |
|---|---|---|
| 不路由 tmux/ssh/rsync/launchctl/status-server-lifecycle/test-runner | ✅ | sandbox evidence 扫描 0 命中；handoff §5 checklist 全选；diff 也未触及 control_plane 文件 |
| 不前台跑 QMD embed | ✅ | inventory + closeout 显式标 `background_worker`；activation proof 中没有 `qmd-embed-runner` 调用 |
| 不声称 full kernel isolation | ✅ | 所有交付文档都用 "local process sandbox + policy/evidence" 语言；assessment doc 章节 §Boundaries 明确写出 |
| write_scope 未越界 | ✅ | handoff §1 "Not changed" 显式列出 4 个在 scope 内但未修改的文件 + 解释；无静默越界 |

## `solar-harness session evaluate` 警告 / 错误三角化

```json
verdict: fail
errors: ['terminal_without_start']
warnings: ['stale_activities','pending_model_calls','command_without_start',
           'activity_without_terminal','stale_activity','model_call_pending']
event_count: 212
```

| Field | Value | 阻塞 Parent? | 理由 |
|---|---|---|---|
| `verdict` | `fail` | **No** | session-log 自身的过程审计 verdict，不替代合约 Acceptance 评估 (R0-eval 也是 verdict=fail 但因 deliverables 诚实而 PASS) |
| `terminal_without_start` × 3 | `dispatch_failed:0.1/0.3` + `graph_parent_ready_passed` | No | 派发失败重试 → 协调器框架行为，不是 R1-R4 deliverable 问题；最终 deliverables 全部就位 |
| `stale_activities` | `graph_nodes_dispatched` | No | 由 graph scheduler 内部 batching 残留触发，节点本身 R0/R1/R2/R3/R4 全 `passed` |
| `pending_model_calls` | 1 个 `d-20260513T211404Z-81d4e4` | No | 是 evaluator 本身正在运行的 dispatch；自闭环成立 |
| 5 个 `model_call_failed` | upstream provider blips | No | builder 最终交付的 artifacts 完整，回归测试通过 |

session 框架层警告对 contract Acceptance 6 条无任何阻塞。

## Process Risks (诚实记录，不阻塞 PASS)

1. **R1-R3 节点未走 node-level eval**: task_graph.json `node_results.R1/R2/R3/R4` 是 `contract-patrol repair` 标的 `passed`，不是真正的 node-level evaluator 输出 (对比 R0 有完整 R0-eval.md/R0-eval.json)。本次 parent-level eval 用 builder handoff + 实跑测试 + 文件 diff 作为独立验证替代。下次建议每个节点走完整 eval-pane 闭环。
2. **"executor" 字段命名分裂**: handoff 措辞是 "evidence 文件含 `executor=sandbox`"，但实际 `evidence.json` 用 `hand_type=sandbox`；`executor` 字段在 helper return dict (`LAST_QMD_ROUTE`/`LAST_EXTRACT_ROUTE`) 里。Activation proof 同时检查两端，所以"诚实路由"语义成立。建议后续在 evidence schema 加 `executor` 字段保持术语统一 (cosmetic, P2)。
3. **R0-eval 提到的 count drift** (38/132 vs grep 39/103): 计数口径差异，不影响分类正确性。closeout 未统一口径，建议下次 inventory 顶层加 `scan_command` 字段。

## Required Fixes

无强制修复。Verdict = **PASS**。

## Optional Improvements (非 blocker)

- **P2**: evidence.json schema 增加 `executor` 别名字段 (映射 `hand_type`)，降低未来 evaluator 字段名误解风险。
- **P2**: `dispatch_batches.json` 当前只到 batch-1；R1-R4 已通过 contract-patrol，但 batch-2/3/4 没扩展。下次 sprint 让 graph-scheduler 自动 append，避免依赖 patrol 兜底。
- **P2**: 把本 sprint 的 4 条迁移规则注入 `weekly-report.sh`，让 weekly KPI 含 "sandboxed user-triggered CLI count" 指标。

## Capability / KB Usage Evidence Checked

- Handoff 声明 `Knowledge Context: solar-harness context inject used` — 验证：dispatch.md 头部确实嵌入 `<solar-runtime-context>` + `<solar-unified-context>`，含 mirage/qmd/solar-db 命中。声明诚实。
- Handoff 声明 `Harness Modules Used: harness-knowledge` — 没有过度声称 ruflo/swarm/MarkItDown 等被实际使用 (符合 "injected ≠ used" 规则)。
- KB 命中 (mirage degraded, solar-db default, QMD default) 影响 dispatch context，没有直接驱动 sandbox 路由代码逻辑，与节点性质 (代码迁移 + 测试) 一致。
