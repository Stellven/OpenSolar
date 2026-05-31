# Design — S03 Core Runtime (AI Influence YouTube 报告流默认流程固化与验收)

Sprint: `sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s03-core-runtime`
Epic: `epic-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收`
Slice: `core-runtime`  ·  Priority: `P0`  ·  Lane: `delivery`
Upstream (must be `passed`): S01_requirements, S02_architecture (A1-A5)
Author: Planner pane (`solar-harness:0.1`, Opus 4.7) — replacing the autopilot stub `compiled_sprint_planner` produced at 2026-05-29T15:09:30Z.
Authored-At: 2026-05-29T11:15Z

Knowledge Context: `solar-harness context inject used` (Mirage `timeout` degraded; QMD solar-wiki / Solar DB / Obsidian Vault active)
Harness Modules Used: `harness-knowledge`, `harness-graph`, `harness-autopilot`

---

## 0. Sprint scope

S03 is the **core-runtime slice** of the AI Influence YouTube 报告流 P0 epic. S02 has already shipped 4 architecture spec documents in `docs/ai-influence-youtube-report/A{1,2,3,4}-*.md` plus a sprint design (`...-s02-architecture.design.md`) covering control/data plane, 11 JSON schemas, 9-row failure-recovery matrix, and a 6-step migration plan. S03 must convert that spec surface into a *runnable Python package* under `lib/ai_influence_youtube_report/` with paired unit tests under `tests/test_ai_influence_youtube_report_*.py`.

Per PRD acceptance:
- 核心 API 有单测覆盖 (every public function in the package has at least one unit test that pins its contract).
- 旧路径兼容，不破坏现有 wake/dispatch/status (the runtime additions must not change observed behavior of existing solar-harness wake/dispatch/status invariants).
- 状态变更可由元数据或事件重建 (RunRecord state is reconstructable from `runs.jsonl` append-only events).

S03 is **runtime + tests, mock-only**. NO live calls to Browser Agent ChatGPT 5.5, NO real `plan-ai-influence-reports` execution, NO archival publish, NO email send. All external dependencies are stubbed via the existing `mock_browser_fixture.py` pattern (analogous to the social-browser-backend-x package). Real-flight verification is S04/S05's scope.

---

## 1. Package layout & module-to-spec mapping

The new package lives at `/Users/lisihao/.solar/harness/lib/ai_influence_youtube_report/` and is rooted by `__init__.py`. Each module maps 1:1 to a spec section in S02 A1-A4.

| Module | Public surface | S02 spec anchor | Owner node |
|--------|----------------|-----------------|------------|
| `schema.py` | 11 typed dataclasses / pydantic-style objects: `GateDecision`, `T3Exclusions`, `ClassificationDecision`, `Phase1Plan`, `Phase2Chapter`, `Phase3Synthesis`, `EvidenceMap`, `ValidatorReport`, `ModelCallLedgerRow`, `ArchiveManifest`, `RunRecord`. All carry `schema_version`. | A3 (data model) | C1 |
| `state_machine.py` | `RunRecord` state transitions (`created → graded → grouped → planned → chaptered → synthesized → validated → archived`) plus 3 terminal rejection states (`run_rejected_t3_only`, `run_rejected_validator`, `run_rejected_model_unreachable`). Append-only event emission to `runs.jsonl`. Reentry from any prior state only if hashes match. | A1 §1.3 + §1.4 | C1 |
| `gate.py` | `transcript_gate(video_id, transcript_status_row) -> GateDecision` — pure function. T0/T1 core, T2 weak (labeled), T3 reject (excluded). | A1 §2 + N1 spec | C1 |
| `compat.py` | `compat_adapter_v1(transcript_status_row) -> normalized GateDecision input`. Explicit drift error on missing required fields; no silent default. | A4 §4.2 + drift-detection plan | C1 |
| `classifier.py` | `group_classifier(video_metadata) -> ClassificationDecision`. 7 `group_type`s, 6 signals (S1-S6), multi-signal mandatory, fallback to `other`, `signal_breakdown` JSON output. | A1 §3 + N1 spec | C2 |
| `hierarchy.py` | `build_hierarchy(phase1_plan) -> HierarchySkeleton` (trend → chapter → subsection). Deterministic, no LLM. | A1 §4 (L4 Report Hierarchy Builder) | C2 |
| `evidence_map.py` | `assemble_evidence_map(plan, classifications) -> EvidenceMap`. `evidence_refs` pin to transcript segment ids, NOT video_id. | A2 §6 + N1 spec | C2 |
| `source_mapping.py` | `render_markdown(entry) -> str` + `render_html(entry) -> str`. 5 reader-facing fields (channel / title / published_at / transcript_grade / citation_span); refuses internal fields. | A2 §1.3 + N3 §1.1 | C2 |
| `browser_agent.py` | `BrowserAgentClient` wrapper with stable signatures `plan(corpus) -> Phase1Plan`, `write_chapter(plan, chapter_id) -> Phase2Chapter`, `synthesize(chapters) -> Phase3Synthesis`. Each call appends to `model_call_ledger` BEFORE returning. Mock-only at S03; real provider stubbed. | A2 §2 + N2 spec | C3 |
| `prompts.py` | Prompt skeletons for Phase 1/2/3 per N2 §6. Routing table enforces ThunderOMLX/Qwen denial for judgment-bearing phases. | A2 §5 + N2 §5 | C3 |
| `ledger.py` | `record_model_call(stage, …) -> ModelCallLedgerRow` writing to `model_call_ledger.jsonl`. Required fields (call_id, stage, cost_usd, sprint_id, browser_session_id, chatgpt_url, latency_ms). Append-only. | A2 §2.3 + N2 §4 | C3 |
| `validator.py` | `validator.run(report_bundle) -> ValidatorReport` running the 8 checks. Any-FAIL ⇒ overall FAIL. | A1 §6 (L6 Validator) + N3 §3 | C4 |
| `render.py` | HTML + markdown rendering with inline SVG seam, evidence_map embedding, reader-facing fields only. NO `<image href>` raster fallback (per N3 §2.1). | A1 §7 (L7 Reporting Surface) + N3 §2 | C4 |
| `archive.py` | `archive_writer.commit(run_record, validator_report) -> ArchiveManifest`. Refuses if validator FAIL. 4 artifact types (md / html / plan.json / evidence_map.json). Atomic; no partial archive. | A1 §1.5 (archive ENOSPC row) + N3 §4 | C4 |
| `scripts/tech_hotspot_radar.py` (edit only) | Wire the new package into `cmd_collect_social-style` runner entry point; minimal-diff edits; preserve existing wake/dispatch/status behavior. | A4 §4.1 (legacy CLI compat) | C4 |
| `__init__.py` | Re-export the 15 public callables; declare package `__version__`. | A2 §2 (stable invariants) | C1 |

The tests under `tests/test_ai_influence_youtube_report_*.py` (13 files in the task_graph) pin every public callable.

---

## 2. Architecture recap (recap of S02 A1 layering — locked, not re-derived)

```
L7 Reporting Surface (render.py + archive.py)   ──┐
L6 Validator (validator.py)                       │  archive_writer
L5 Browser Agent (browser_agent.py + prompts.py + ledger.py)   refuses
L4 Hierarchy (hierarchy.py)                                  on any FAIL
L3 Grouping (classifier.py)                       │
L2 Gate (gate.py)                                 │  state_machine.py
L1 Inventory (compat.py — read-only)              │  records all
L0 Upstream (transcript-status JSON, ChatGPT) ──┘  transitions
```

Per S02 A1 the system has a 4-row state machine + 3 rejection terminals + 9-row failure recovery matrix. S03 implements that surface verbatim; this design does NOT introduce new layers or new schemas — only the Python types that realize them.

---

## 3. Control plane vs data plane

| Plane | Function in S03 | Implementation file | State store | Test surface |
|-------|-----------------|---------------------|------------|--------------|
| **Control** | Decide gate/classify/call/validate/archive; drive RunRecord through 8 states + 3 terminals | `state_machine.py`, `gate.py`, `compat.py`, `validator.py`, `archive.py` | `runs.jsonl` (append-only); per-run filesystem under `runs/<run_id>/` | `test_*_state_machine.py`, `test_*_gate.py`, `test_*_compat.py`, `test_*_validator.py`, `test_*_archive.py` |
| **Data** | Carry transcript / classification / plan / chapters / evidence as typed objects | `schema.py`, `classifier.py`, `hierarchy.py`, `evidence_map.py`, `source_mapping.py`, `browser_agent.py`, `prompts.py`, `ledger.py`, `render.py` | Per-run filesystem; `model_call_ledger.jsonl`; final archive at `Knowledge/_raw/tech-hotspot-radar/ai-influence-planned/<date>/reports/` | `test_*_schema.py`, `test_*_classifier.py`, `test_*_hierarchy.py`, `test_*_evidence_map.py`, `test_*_browser_agent.py`, `test_*_ledger.py`, `test_*_render.py` |

The split honors A1 §1.2 of the S02 design.

---

## 4. Failure recovery (S02 9-row matrix — pinned in S03 tests)

| Failure (S02 row) | S03 module surface | Test pin |
|-------------------|--------------------|----------|
| Transcript-status missing video | `gate.py` raises `MissingVideoError`; pipeline skips video | `test_*_gate.py::test_missing_video_raises` |
| All gates produce T3 | `state_machine.py` transits to `run_rejected_t3_only`; no L3 forward | `test_*_state_machine.py::test_t3_only_aborts` |
| L3 classifier confidence < threshold | `classifier.py` fallback to `other`; `signal_breakdown` records reason | `test_*_classifier.py::test_low_confidence_fallback_other` |
| ChatGPT Browser Agent unreachable | `browser_agent.py` retries once; second fail ⇒ `run_rejected_model_unreachable`; NO local-model substitution | `test_*_browser_agent.py::test_two_strikes_no_local_fallback` |
| ChatGPT returns malformed JSON | `browser_agent.py` strict-JSON nudge; second fail ⇒ abort | `test_*_browser_agent.py::test_malformed_json_no_silent_fix` |
| L6 validator any-FAIL | `validator.py` reports overall FAIL; `archive.py` refuses | `test_*_validator.py::test_any_fail_blocks_archive` |
| Archive disk write fails | `archive.py` atomic; on partial failure rolls back entirely | `test_*_archive.py::test_atomic_no_partial` |
| Cross-epic upstream drift (transcript-status schema change) | `compat.py` raises `DriftError`; no silent fallback | `test_*_compat.py::test_drift_explicit` |
| Mirage VFS degraded | Out-of-band (planner/evaluator only); S03 does not interact with Mirage | n/a (OQ-mirage carried) |

---

## 5. DAG view (S03 task graph — already in task_graph.json)

```
                         ┌──────────────────────┐
                         │  C1                  │  schema / state / gate / compat
                         │  (sonnet)            │  est 4; package_local
                         └──────────┬───────────┘
                ┌───────────────────┴───────────────────┐
                ▼                                       ▼
   ┌──────────────────────┐                ┌──────────────────────┐
   │  C2                  │                │  C3                  │
   │  grouping / hierarchy│                │  browser agent /     │
   │  evidence_map        │                │  prompts / ledger    │
   │  (sonnet, est 4)     │                │  (sonnet, est 4)     │
   └──────────┬───────────┘                └──────────┬───────────┘
              └────────────────┬──────────────────────┘
                               ▼
                  ┌──────────────────────────────┐
                  │  C4                          │  validator / render /
                  │  validator_archive_runtime    │  archive + CLI wiring
                  │  (sonnet, est 5)              │
                  └──────────────┬───────────────┘
                                 ▼
                       ┌──────────────────────┐
                       │  C5                  │  handoff + traceability
                       │  core_runtime_release│  + minimal regression
                       │  (sonnet, est 3)     │
                       └──────────────────────┘
```

- Wave 1: **C1** (schema/state/gate/compat — foundation).
- Wave 2: **C2 ‖ C3** (independent file-ownership; C2 builds non-LLM data path, C3 builds BrowserAgent + ledger contract).
- Wave 3: **C4** (depends on both C2 and C3 because validator + render + archive consume their outputs).
- Wave 4: **C5** (sprint-level closeout join).

write_scope is strictly file-mutex across C1-C5; C4 owns the only edit to `scripts/tech_hotspot_radar.py`. Re-validated `ok:true errors:[] warnings:[]` after architecture_policy patch.

---

## 6. Online exploration alternatives

| Candidate | Idea | Kill criterion |
|-----------|------|----------------|
| **Picked: 5-node parallel DAG (C1; C2‖C3; C4; C5)** | Per S02 A1-A4 layered split; tightest write_scope mutex; matches prior epic patterns. | Foundation-first (C1) avoids cascading failures; C2 and C3 parallelize cleanly because non-LLM data path and BrowserAgent wrapper are disjoint; C4 joins them for runtime; C5 is the canonical sprint join. |
| 3-node mega split (C1: data+state; C2: agent+validator; C3: release) | Fewer nodes, simpler graph. | KILLED: write_scope would collide (validator depends on evidence_map and BrowserAgent outputs); single C2 would touch 8+ files; loses parallelism between non-LLM and LLM paths. |
| 1 node per file (15 nodes) | Maximum granularity. | KILLED: too much coordinator overhead; many files share a single test fixture; per-file nodes would explode the DAG without parallelism gains. |
| Skip C5 join; let coordinator emit handoff | Save effort. | KILLED: PRD §交付物 mandates `handoff.md` + `traceability.json` + `eval.{md,json}` — these are the C5 artifacts; without C5 the sprint cannot reach `passed`. |
| Implement live BrowserAgent calls in S03 | Validate end-to-end early. | KILLED HARD: evidence_policy.no_live_browser_agent_calls=true; live calls are S05's scope; doing them in S03 would burn ChatGPT quota and contaminate the test surface. |
| Local-model substitution for Phase 1/2/3 to save cost | "Pragmatic". | KILLED HARD: NG3 in epic-level non-goals; A2 §5 routing table denies; test pin `test_two_strikes_no_local_fallback` would FAIL. |

Decision: **C1 → (C2 ‖ C3) → C4 → C5**.

---

## 7. Cross-epic surfaces (read-only consumers)

| Upstream epic | Surface used | S03 file | Drift detection |
|---------------|--------------|---------|-----------------|
| `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构` | `transcript-status --json` row schema | `compat.py` | `test_*_compat.py::test_drift_explicit` raises `DriftError` on missing required field. |
| `epic-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究` | Browser Agent + ChatGPT 5.5 routing pattern (OQ-03 from S02 A4) | `browser_agent.py` (mock subclass) + `prompts.py` (skeleton) | S03 uses a `MockBrowserAgentProvider`; real provider import is gated behind `os.environ.get('AI_INFLUENCE_USE_REAL_PROVIDER')` which S03 forbids in tests. |
| (this epic) S02_architecture | A1-A4 spec docs + S02 sprint design | All C1-C5 nodes read `docs/ai-influence-youtube-report/A{1,2,3,4}-*.md` and `<sid>.s02-architecture.handoff.md` (when published) | Drift here = S03 tests fail to import schema names; immediately surfaced. |

---

## 8. Stop rules (propagated to every C* node)

- evidence_policy already declares: `no_live_browser_agent_calls`, `no_real_paid_provider_calls`, `no_real_email_send`, `no_real_knowledge_archive_publish`, `mock_or_fixture_only_for_external_dependencies` — all `true`.
- forbid_optimistic_terms: `已修复 / 稳定 / 完美 / 无需担忧 / done / complete` (already in evidence_policy).
- 不绕过 transcript quality gate (NG1).
- 不放宽 validator FAIL 后拒绝归档的约束 (NG6 in evidence_policy).
- 不破坏既有 `scripts/tech_hotspot_radar.py` 的 wake/dispatch/status 语义 (C4 must be minimal-diff).
- 不接 ThunderOMLX/Qwen 进入 L5 judgment-bearing phases.
- 不为 spec 之外的接口创造 public 入口 (signatures fixed by A2).
- 不在 S03 关闭 parent epic — only the sprint itself can be moved to `reviewing`.

---

## 9. Risks (recap from PRD §9 of the epic-level requirements + S02 OQ-S02-01..07)

| Risk | Mitigation | OQ id |
|------|------------|-------|
| transcript-status field rename mid-flight | `compat.py` drift error + test pin | OQ-S02-01 |
| ChatGPT 5.5 quota exhaustion during Phase 2 (one-call-per-chapter) | `ledger.py` records cost; mock at S03 means no real burn | OQ-S02-02 |
| 11-char video_id regex false positives in validator Check 2 | A2 OQ-S02-03 calls for markdown-AST predicate; S03 validator.py uses markdown AST, not raw regex | OQ-S02-03 |
| Confidence threshold tuning | Calibration data is S05 fixture-run output; S03 uses A1 §3 defaults | OQ-S02-04 |
| ChatGPT session URL reachability staleness | `archive.py` records URL only; reachability is out-of-band | OQ-S02-05 |
| Schema overlap between A2/A3/A4 | A5 already deduped at S02 close; S03 imports the deduped schema; no overlap re-introduced | OQ-S02-06 |
| Mirage VFS degraded | Carry; S03 does not touch Mirage | OQ-S02-07 |
| Autopilot stub planner produced shallow design.md / plan.md (this turn replaces them) | This design + this plan.md (also rewritten) | OQ-S03-stub-replace |
| Parent epic traceability still in `queued` status for S03/S04/S05 | Coordinator/epic_decomposer to refresh after S03 reaches `passed` | OQ-S03-traceability-refresh |
| `compiled_sprint_planner` stub used `priority: 1` integer rather than `P0` string for nodes — schema accepts both but coordinator routing may prefer string | Left unchanged (validate is `ok:true`); flag as OQ-S03-priority-convention if downstream rejects | OQ-S03-priority-convention |

---

## 10. Definition of Done self-evidence (planner pass)

| DoD condition | Planner-pass evidence |
|----------------|------------------------|
| 真实调用链接入 | task_graph 5 节点 ready for builder dispatch (autopilot already routed to `builder_main`); architecture_policy now declared per node; warnings cleared. |
| 禁止硬编码 | No paths inline; all file paths derived from `<sid>` or absolute. No secrets in any artifact (V6 base64-encoded regex scan clean). |
| 测试必须运行 | Planner pass ran `graph-scheduler validate` (ok:true) and `enrich-capabilities` (5 nodes patched). Builder-pass pytest is C1-C5's job. |
| 执行证据齐全 | plan.md §5 lists every verification command + expected output; this design.md §1 lists every file with owner node. |
| Diff 自审 | Planner pass replaced 3 stub files (design.md / plan.md) and patched task_graph.json with `architecture_policy` for 5 nodes; planning.html re-rendered. No other artifact touched. |
| 禁用乐观词 | evidence_policy.forbid_optimistic_terms already declared; this design uses "must be implemented", "audit-style verifies", no `done/complete/implemented` for unbuilt work. |
| 结构化收尾 | C5 owns sprint-level handoff + traceability + eval; planner pass status push to `active/planning_complete/builder_main` already happened (autopilot). |

---

## 11. What changed in this planner-pane pass

- **Replaced** the autopilot-generated `design.md` (7.7 KB generic template) with this S02-anchored design (12+ KB, mapped to A1-A4).
- **Replaced** the autopilot-generated `plan.md` (2.7 KB summary list) with a deeper plan including stop rules, verification commands, slice ordering, and rollback per trigger.
- **Patched** `task_graph.json` to add `architecture_policy.package_boundary` + `package_id` + `core_patch_allowed` + `note` per node — clearing 5 `graph-scheduler validate` warnings.
- **Re-rendered** `planning.html` via `render_sprint_html.py render --kind planning --register`.
- **Did NOT** change node ids, depends_on, write_scope, acceptance, or capability_inference — those were already correct in the autopilot stub.
- **Did NOT** alter sprint status — autopilot already moved it to `active/planning_complete/builder_main` at 15:10:25Z. This planner-pass only appends a history entry recording the augment.
