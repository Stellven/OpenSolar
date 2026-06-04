# Design — S02 Architecture (AI Influence YouTube 报告流默认流程固化与验收)

Sprint: `sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s02-architecture`
Epic: `epic-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收`
Slice: `architecture`  ·  Priority: `P0`  ·  Lane: `strategy`
Author: Planner pane (`solar-harness:0.1`, Opus 4.7)
Authored-At: 2026-05-29T10:36Z

Knowledge Context: `solar-harness context inject used` (Mirage `timeout` degraded; QMD solar-wiki / Solar DB / Obsidian Vault active)
Harness Modules Used: `harness-knowledge`, `harness-graph`

---

## 0. Sprint scope (re-stated)

S02 is the **architecture slice** of the AI Influence YouTube 报告流 P0 epic. S01 (requirements) has shipped `passed` with three spec docs (`docs/ai-influence-youtube-report/N{1,2,3}-*.md`) and a 10-outcome traceability matrix. S02 must convert the S01 outcomes into:

- A layered **architecture** (control plane / data plane / state machine / observability / failure recovery / degraded modes).
- Explicit **interface contracts** (CLI + Python module entrypoints).
- **Data model** (JSON schemas) for every cross-component artifact.
- **Compatibility & migration** path against the existing `plan-ai-influence-reports` code path and two upstream epics.
- A buildable `task_graph.json` so S03 (core-runtime) / S04 (orchestration-ui) / S05 (verification-release) can be dispatched with no further architecture re-plan.

S02 is **spec-only**: no code changes; no live calls to Browser Agent ChatGPT or `plan-ai-influence-reports`; no fixture generation; no smoke runs. All of that is downstream (S03/S04/S05).

---

## 1. Architecture overview

### 1.1 Layered view

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│  L7 Reporting Surface (reader-facing)                                              │
│  - markdown report  /  html report (SVG inline)  /  evidence_map.json              │
│  - archive layout: Knowledge/_raw/tech-hotspot-radar/ai-influence-planned/<date>/  │
│                                                                                    │
│   ↑                                                                                │
│  L6 Validator (8 checks; any-FAIL ⇒ reject archive)                                │
│  - Check 1 grep blacklist  · 2 bare-video-id regex  · 3 truncation tail            │
│  - Check 4 SVG present     · 5 evidence_map complete  · 6 T3-not-in-core           │
│  - Check 7 group_type whitelist · 8 hierarchy intact                               │
│                                                                                    │
│   ↑                                                                                │
│  L5 Browser Agent ChatGPT 5.5 Thinking high (3 phases, judgment-bearing only)      │
│  - Phase 1 plan  · Phase 2 per-chapter writing  · Phase 3 final synthesis          │
│  - model_call_ledger (call_id / stage / cost / sprint_id / browser_session_id)     │
│  - ChatGPT session URL archived to project "杂项"                                  │
│                                                                                    │
│   ↑                                                                                │
│  L4 Report Hierarchy Builder (deterministic; no LLM)                               │
│  - trend → chapter → subsection skeleton from L3 group output                      │
│  - evidence_refs pinned to transcript segment ids, not video_id                    │
│                                                                                    │
│   ↑                                                                                │
│  L3 Video Grouping (7 group_type, multi-signal classifier)                         │
│  - 6 signals (title pattern / channel type / duration / speaker count /            │
│              Q&A presence / slide density), multi-signal mandatory                 │
│  - confidence threshold per group_type + fallback to "other"                       │
│  - signal_breakdown emitted for debug                                              │
│                                                                                    │
│   ↑                                                                                │
│  L2 Transcript Quality Gate (T0-T3 grading)                                        │
│  - T0/T1: core evidence  ·  T2: weak evidence (labeled)  ·  T3: reject (excluded)  │
│  - reuses YouTube Transcript epic S03 metrics (entity_recall / WER / segment_dens) │
│  - T3_exclusions block emitted for L6 validator hook                               │
│                                                                                    │
│   ↑                                                                                │
│  L1 Video Inventory & Metadata (read-only consumer)                                │
│  - source: existing tech-hotspot-radar inventory + transcript-status               │
│  - no mutation of inventory                                                        │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Control plane vs data plane

| Plane | Function | Components | State store | Failure surface |
|-------|----------|-----------|------------|-----------------|
| **Control** | Drive the run, decide what to gate / classify / call / validate / archive | CLI `plan-ai-influence-reports`, state machine `RunRecord`, scheduler hooks | `runs.jsonl` append-only log + `report_state.json` per run | Run aborts on gate failure or validator FAIL; idempotent restart from last passed phase |
| **Data** | Carry transcript / classification / plan / chapters / evidence | L1-L5 outputs as JSON; final L7 artifacts as md/html/json | Per-run filesystem under `runs/<run_id>/`; final under `Knowledge/_raw/tech-hotspot-radar/ai-influence-planned/<date>/reports/` | Bad data fails L6 validator; any-FAIL ⇒ archive rejected, run keeps `runs/<run_id>/` for forensics |

### 1.3 State machine

```
created
  │  ingest L1 inventory + transcript-status
  ▼
graded                                  ──(T3 only)──┐
  │  apply L2 gate, write T3_exclusions block        │
  ▼                                                  │
grouped                                              │
  │  L3 classifier; multi-signal; fallback to "other"│
  ▼                                                  │
planned                                              │
  │  L5 Phase 1 ChatGPT 5.5 Thinking high            │
  ▼                                                  ▼
chaptered                                       run_rejected_t3
  │  L4 hierarchy build + L5 Phase 2 per-chapter
  ▼
synthesized
  │  L5 Phase 3 final synthesis
  ▼
validated
  │  L6 8 checks; any-FAIL ⇒ run_rejected_validator
  ▼
archived (final)
```

State transitions are **append-only** to `runs.jsonl`. Re-entry from any prior state is allowed only if all upstream artifacts on disk match the recorded hash.

### 1.4 Observability

- Every L2/L3/L5/L6 step emits a structured event (`step`, `run_id`, `t_start`, `t_end`, `outcome`, `evidence_paths`) into `runs.jsonl`.
- Every L5 call appends to `model_call_ledger.jsonl` (per N2 §4).
- The L6 validator emits a `validator_report.json` per run with 8 check results.
- Archive writer emits `archive_manifest.json` recording every file added to the date-bucketed `Knowledge/_raw/.../reports/` folder.
- No `print()` for runtime telemetry; structured JSON only.

### 1.5 Failure recovery & degraded modes

| Failure | Detection | Recovery | Degraded mode |
|---------|-----------|----------|---------------|
| Transcript-status missing video | L2 gate input check | Mark video missing; exclude from this run; do not retry inline | Run can proceed with surviving videos; if <3 survive, abort with `under_quorum`. |
| All gates produce T3 | L2 gate ⇒ count=N inventory, T3=N | Abort run; emit `run_rejected_t3_only`; no L3 forward | None — no useful corpus. |
| L3 classifier confidence < threshold | L3 emits `confidence<0.65` | Fallback to `other` per group_type | Report still generated, but "other" bucket may be large; OQ noted. |
| ChatGPT Browser Agent unreachable | L5 Phase 1 timeout > 90s | Retry once with same prompt; on second failure abort run with `run_rejected_model_unreachable` | NO fallback to ThunderOMLX/Qwen for judgment-bearing phases (NG3). |
| ChatGPT returns malformed JSON | L5 JSON-schema validation | Retry once with strict-JSON nudge; on second failure abort | Same as above. |
| L6 validator any-FAIL | L6 check function | Reject archive; keep run forensics; surface 8-check diff | NO bypass to publish despite FAIL. |
| Archive disk write fails | filesystem ENOSPC / EPERM | Surface error, do not retry inline | NO partial archive; either all 4 artifact types or none. |
| Cross-epic upstream drift (transcript-status schema change) | A4 compatibility check at S03 build | Wrap upstream output with `compat_adapter`; surface drift to OQ | Block S03 until adapter is added; do not silently misread. |

---

## 2. Interface contracts (S03/S04/S05 will implement)

These contracts are spec-only at S02 level. The downstream A2 deliverable (`docs/ai-influence-youtube-report/A2-interfaces.md`) will carry the canonical signatures; this section locks the surface.

### 2.1 CLI

- `plan-ai-influence-reports run --week <YYYY-WW> [--inventory-path <p>] [--dry-run] [--output-dir <p>]`
  - Exit 0 = run reached `archived`; 1 = validator FAIL; 2 = operator error; 3 = upstream/cross-epic drift; 4 = under_quorum or t3_only.
- `plan-ai-influence-reports validate --report-dir <p>` → re-runs L6 8 checks on an existing artifact bundle. Same exit codes.
- `plan-ai-influence-reports replay --run-id <id>` → restart from last passed phase.

### 2.2 Python module entry points (under `solar_youtube_report/` package, name TBD by A2)

- `transcript_gate(video_id, transcript_status_row) -> GateDecision` — returns `(grade ∈ {T0,T1,T2,T3}, evidence)`. Pure function over the row; no I/O.
- `group_classifier(video_metadata) -> ClassificationDecision` — returns `(group_type, confidence, signal_breakdown)`. Pure; no LLM.
- `BrowserAgentClient.plan(corpus) -> Phase1Plan` — Phase 1 (one call). Strict JSON schema.
- `BrowserAgentClient.write_chapter(plan, chapter_id) -> Phase2Chapter` — Phase 2 (one call per chapter; no batching per N2 §2.2).
- `BrowserAgentClient.synthesize(chapters) -> Phase3Synthesis` — Phase 3 (one call).
- `validator.run(report_bundle) -> ValidatorReport` — runs the 8 checks; returns per-check status + diff.
- `archive_writer.commit(run_record, validator_report) -> ArchiveManifest` — writes 4 artifact types atomically; refuses on any validator FAIL.
- `source_mapping.render_markdown(evidence_map_entry) -> str` and `source_mapping.render_html(...)` — per N3 §1.3.

### 2.3 Stable invariants on the surface

- All function inputs/outputs are JSON-serializable; no raw transcript blobs in args.
- Every output carries a `schema_version` field.
- No function mutates inventory or transcript-status; reads only.
- BrowserAgentClient signs every call with `model_call_ledger` row before returning.

---

## 3. Data model (locked schemas; A3 deliverable will finalize)

Canonical JSON schemas live as fragments in `docs/ai-influence-youtube-report/A3-data-model.md`. Top-level objects:

| Schema | Fields (required) | Used by |
|--------|-------------------|---------|
| `gate_decision.v1` | `video_id`, `grade ∈ {T0,T1,T2,T3}`, `entity_recall`, `wer`, `segment_density`, `evidence_notes` | L2 |
| `t3_exclusions.v1` | `run_id`, `excluded_video_ids[]`, `per_video_reason{}`, `generated_at` | L2 → L6 validator hook |
| `classification_decision.v1` | `video_id`, `group_type ∈ {event,conference,keynote,interview,tutorial,product_update,other}`, `confidence`, `signal_breakdown{S1..S6}`, `fallback_used` | L3 |
| `phase1_plan.v1` | `run_id`, `trends[]{name, chapters[]{title, subsections[]{title, evidence_refs[]}}}`, `model_call_id`, `chatgpt_session_id` | L5 Phase 1 |
| `phase2_chapter.v1` | `chapter_id`, `body_md`, `inline_citations[]{evidence_ref, span}`, `model_call_id` | L5 Phase 2 |
| `phase3_synthesis.v1` | `run_id`, `executive_summary_md`, `cross_chapter_links[]`, `model_call_id` | L5 Phase 3 |
| `evidence_map.v1` | `entries[]{evidence_ref, channel, title, published_at, transcript_grade, citation_span, group_type}` | L4/L5 → L7, L6 Check 5 |
| `source_mapping.v1` | per-entry render of the 5 reader-facing fields per N3 §1.1 | L7 markdown + HTML |
| `validator_report.v1` | `run_id`, `checks[]{id ∈ 1..8, status ∈ {PASS,FAIL}, evidence, diff?}`, `overall ∈ {PASS,FAIL}` | L6 |
| `model_call_ledger.v1` | `call_id`, `stage ∈ {phase1,phase2,phase3}`, `cost`, `sprint_id`, `browser_session_id`, `chatgpt_url`, `latency_ms` | L5 |
| `archive_manifest.v1` | `archive_dir`, `artifacts[]{path, sha256, type ∈ {md,html,plan_json,evidence_map_json}}`, `chatgpt_session_url`, `created_at` | Archive writer |
| `run_record.v1` (state) | `run_id`, `state ∈ {created,graded,...,archived,run_rejected_*}`, `phase_artifacts{}`, `step_log[]` | Control plane |

All schemas live in `A3` and are versioned. A4 compat plan locks how upstream `transcript-status` and inventory rows map to `gate_decision.v1` and `classification_decision.v1`.

---

## 4. Compatibility & migration

### 4.1 Existing `plan-ai-influence-reports` CLI

- The current CLI exists in the tech-hotspot-radar repo. A4 deliverable must enumerate every flag in use and either:
  - Keep flag semantics (preferred), OR
  - Wrap behind `--legacy-mode` (transitional), with a deprecation note in CLI help.
- New required behavior (gate-before-plan, BrowserAgent for judgment, validator pre-archive) is gated by **default-on** flag `--gate-on` (cannot be opted out without `--allow-bypass`, which itself emits a FATAL log and is disabled in production).

### 4.2 Cross-epic dependency: YouTube Transcript epic

- Epic id: `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构`
- Source-of-truth artifact: `sprint-20260526-...-s03-core-runtime.handoff.md`
- This S02 design treats `transcript-status --json` as the canonical row source for L2 inputs. A4 must:
  - Confirm field names: `entity_recall`, `wer`, `segment_density`, `transcript_path`.
  - Add a `compat_adapter_v1(transcript_status_row) -> GateDecision input` if any field renames before S03 builder runs.

### 4.3 Cross-epic dependency: HF Paper Insight epic

- Epic id: `epic-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究`
- Source-of-truth artifacts: S02 design + S04 orchestration design
- Reused pattern: Browser Agent ChatGPT 5.5 routing (OQ-03 reference). A4 must:
  - Decide whether to import the existing `BrowserAgentClient` from that epic or fork a YouTube-specific subclass.
  - Lock the model_call_ledger row format so both epics write the same shape.

### 4.4 Migration plan

| Step | Owner | Pre-condition | Output |
|------|-------|---------------|--------|
| M1 | S03 builder | A1-A4 specs passed | Implement L2+L3+L4 as a new package; old CLI still default. |
| M2 | S03 builder | M1 PASS | Implement L5 BrowserAgentClient + model_call_ledger; behind `--use-new` flag. |
| M3 | S04 orchestration | M2 PASS | Wire `plan-ai-influence-reports run` to new package; `--use-new` becomes default-on. |
| M4 | S04 orchestration | M3 PASS | L6 validator wired into pre-archive step; any-FAIL blocks archive. |
| M5 | S05 verification | M4 PASS | 2026-W21 fixture smoke run; 8 checks PASS; exit 0. |
| M6 | S05 verification | M5 PASS | Cut `--legacy-mode` flag; remove old code path; OQ list resolved. |

Rollback for each step: revert flag default OR keep `--legacy-mode` active. No DB schema migration in this epic.

---

## 5. DAG view (S02 nodes)

```
                       ┌─────────┐
                       │  A1     │  Layering / state / observability / failure recovery
                       │ (opus)  │  spec_only
                       └────┬────┘
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
        ┌───────┐       ┌───────┐       ┌───────┐
        │  A2   │       │  A3   │       │  A4   │
        │interface│     │data   │       │compat │
        │ (opus) │      │(sonnet)│      │(sonnet)│
        └───┬───┘       └───┬───┘       └───┬───┘
            └───────────────┼───────────────┘
                            ▼
                       ┌─────────┐
                       │  A5     │  Integration / sprint-level design.md + handoff + eval
                       │ (opus)  │
                       └─────────┘
```

- **Wave 1**: A1 (no upstream).
- **Wave 2**: A2 / A3 / A4 in parallel — write_scope mutually exclusive (different `docs/ai-influence-youtube-report/` files).
- **Wave 3**: A5 join.

Acceptance + write_scope + skills are in §10 below and canonically in `task_graph.json`.

---

## 6. Online exploration alternatives

Per rule "≥2 candidates + kill criteria":

| Candidate | Idea | Kill criterion |
|-----------|------|----------------|
| **Picked: 5-node parallel-spec DAG (A1; A2‖A3‖A4; A5)** | Lock layering first, then fan out interface/data/compat in parallel, join into integration. | Maximises parallelism; clean write_scope mutex; matches S01 wave-and-join pattern; cheap to verify per-node. |
| Single mega-node "A1: full architecture doc" | One pass, no fan-out. | KILLED: bottlenecks builder pane; loses parallelism; mega-doc is hard to review and conflicts with eval Acceptance "列出冲突、依赖和降级策略" (better split). |
| 7-node 1:1 with L1-L7 layers | Each layer gets a spec. | KILLED: too granular for S02 architecture slice — L1 (inventory) and L7 (archive layout) belong inside A1/A4; per-layer spec is S03 builder work, not S02 architecture. |
| Skip A4 (compat) and inline migration in A1 | Reduce node count. | KILLED: A4 is explicit PRD requirement (验收 "写清楚接口边界和旧系统兼容方式") and references two upstream epics — needs its own surface. |
| Defer A5 join, let coordinator stitch | Save effort. | KILLED: PRD 交付物 contract demands `design.md` + `handoff.md` + `eval.md` (or `.json`); A5 owns these, otherwise S02 cannot reach `passed`. |
| Replace ChatGPT 5.5 with Solar Opus to save quota | Lower cost. | KILLED HARD: NG3 explicitly forbids local model for judgment-bearing phases; this is a PRD-level invariant, not a planner choice. |

Decision: 5-node `A1 → (A2 ‖ A3 ‖ A4) → A5`.

---

## 7. Cross-epic surface (locked)

| Upstream epic | Surface used | Schema/contract owner | Drift detection |
|---------------|--------------|----------------------|-----------------|
| `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构` | `transcript-status --json` rows (entity_recall, WER, segment_density, transcript_path) | YouTube Transcript epic S03 | A4 spec adds a `compat_adapter_v1` test; CI smoke fails fast on rename. |
| `epic-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究` | Browser Agent + ChatGPT 5.5 routing pattern; OQ-03 routing table | HF Paper Insight epic S02 | A4 spec must decide import vs fork; if import, version-pin the symbol. |
| (this epic S01) | N1/N2/N3 specs + traceability.json + S01 handoff S02 kickoff checklist | S01 N4 traceability | A5 integration must reference each S01 outcome (O1..O10) by id. |

---

## 8. Stop rules (planner view, propagated to all S02 nodes)

- No code changes (spec-only sprint).
- No live calls to Browser Agent ChatGPT 5.5 from this sprint.
- No real `plan-ai-influence-reports` runs.
- No ASCII chart as final figure (NG2). Architecture diagrams in S02 may be ASCII in design.md and A1, but L7 final report charts will be SVG (per N3).
- No exposure of internal fields in reader-facing surfaces; `video_id` may appear in spec discussion (this design.md) but not in final report output.
- No bypass of L2 transcript gate.
- No ThunderOMLX/Qwen substitution for L5 judgment-bearing phases (NG3).
- No close of parent epic.
- No "done/complete/implemented" language until S05 verification passes the 2026-W21 fixture smoke with exit 0.

---

## 9. Risks & follow-ups (OQ)

| Risk | Mitigation | OQ id |
|------|------------|-------|
| Upstream transcript-status field rename | A4 compat adapter + CI smoke | OQ-S02-01 |
| ChatGPT 5.5 quota exhaustion on Phase 2 (one call per chapter) | model_call_ledger budget per run; abort on `model_quota_exceeded`; OQ for batch optimization later | OQ-S02-02 |
| 11-char video_id false positive in validator Check 2 | A2 interface uses markdown-AST predicate inside reader-facing prose block, not raw regex | OQ-S02-03 |
| Confidence threshold 0.65-0.70 tuning | A1 §1.5 fallback to "other"; S05 fixture run will produce calibration data; tuning sprint after S05 | OQ-S02-04 |
| ChatGPT session URL reachability stale | A3 archive_manifest carries URL only; reachability audit is out-of-band | OQ-S02-05 |
| Parallel A2/A3/A4 may produce overlapping schema mentions | A5 join must dedupe; write_scope mutex prevents file collision but content overlap is possible | OQ-S02-06 |
| Mirage VFS degraded during context inject (this pass) | Other 3 sources covered; not S02-fixable | OQ-S02-07 (carry from S01) |

---

## 10. Acceptance ↔ S02 node coverage

S02 contract acceptance:
- AC1 — 设计覆盖 control/data plane、状态、失败恢复和观测
- AC2 — 写清楚接口边界和旧系统兼容方式
- AC3 — 列出冲突、依赖和降级策略

PRD additional acceptance:
- AC4 — 父级依赖、下游影响、未闭项写入 handoff
- AC5 — task_graph 通过 `solar-harness graph-scheduler validate`

| Node | Covers AC | Acceptance count (≥) | Write scope |
|------|-----------|----------------------|-------------|
| A1 (layering + failure recovery + observability) | AC1 | 6 | `docs/ai-influence-youtube-report/A1-layering-failure-recovery.md` |
| A2 (interface contracts; CLI + Python) | AC2 | 6 | `docs/ai-influence-youtube-report/A2-interfaces.md` |
| A3 (data model & schemas) | AC2 (schema side) | 8 | `docs/ai-influence-youtube-report/A3-data-model.md` |
| A4 (compat + migration) | AC2 + AC3 | 6 | `docs/ai-influence-youtube-report/A4-compat-migration.md` |
| A5 (integration / design.md / handoff / eval) | AC4 + AC5 | 5 | `sprints/<sid>.design.md` (this file — A5 will append closeout) + `sprints/<sid>.handoff.md` + `sprints/<sid>.eval.md` + `sprints/<sid>.eval.json` |

---

## 11. Definition of Done self-evidence (planner pass)

| DoD condition | Evidence |
|----------------|----------|
| 真实调用链接入 | This design feeds A1-A5 builder nodes via `task_graph.json`; coordinator dispatches by depends_on. |
| 禁止硬编码 | All node ids / sprint id / write scopes are referenced by `<sid>` or absolute path; no inline secrets. |
| 测试必须运行 | Planner pass runs `graph-scheduler validate` on the new task_graph (V1 in handoff). Sprint-level fixture smoke is S05 work, not S02. |
| 执行证据齐全 | handoff.md §Verification Evidence lists every command + result. |
| Diff 自审 | handoff §Changed Files lists every new artifact. |
| 禁用乐观词 | This design uses "spec-only", "downstream", "deferred", "must be implemented by S03"; no `done/complete/implemented` for unbuilt work. |
| 结构化收尾 | handoff.md ends with 已完成 / 已验证 / 未验证 / 风险 / 后续待办. |

---

## 12. A5 Closeout

### 12.1 Cross-A1/A2/A3/A4 reconciliation

| Surface | Locked by | Reconciled outcome |
|---------|-----------|--------------------|
| Layering / state / observability / degraded modes | `A1` | Becomes the runtime architecture baseline for S03/S04/S05 |
| CLI + Python entrypoints + validator IO | `A2` | Defines the implementation seam; no code path may invent alternate signatures |
| JSON artifact schemas | `A3` | Pins the exchange objects across L2-L7 and archive/validator boundaries |
| Compat / migration / drift handling | `A4` | Ensures the new default flow can absorb upstream field drift without silent behavior changes |

No write-scope conflict exists among A1-A4. The only semantic overlap is between:

- `A2` interface contract field names
- `A3` schema field sets

This overlap is intentional and reconciled as follows:

1. `A2` owns callable surface and invariants
2. `A3` owns payload shape and version pinning
3. If either changes later, the other must update in the same sprint or via a dedicated compatibility sprint

### 12.2 Carry-over decisions

- `OQ-S02-01` remains open until `compat_adapter_v1` is implemented and tested
- `OQ-S02-02` remains open until Phase 2 per-chapter quota/budget is measured in S05
- `OQ-S02-03` remains open until validator false-positive suppression lands
- `OQ-S02-04` remains open until confidence thresholds are calibrated on fixture evidence
- `OQ-S02-05` remains open until session archive reachability is verified in release evidence
- `OQ-S02-06` is resolved for S02 by assigning interface ownership to A2 and schema ownership to A3
- `OQ-S02-07` remains infra-scoped and does not block this sprint closeout

### 12.3 Builder handoff summary

- `S03` consumes A1+A2+A3+A4 to implement gate / grouping / Browser Agent / validator / archive
- `S04` consumes A2+A4 to wire CLI defaults, drift checks, and orchestration behavior
- `S05` consumes A1+A3+A4 to validate smoke, schema completeness, and archive evidence

### 12.4 Closure scope

This closeout marks **S02 only**. It does **not** close:

- parent epic `epic-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收`
- downstream `S03_core_runtime`
- downstream `S04_orchestration_ui`
- downstream `S05_verification_release`
