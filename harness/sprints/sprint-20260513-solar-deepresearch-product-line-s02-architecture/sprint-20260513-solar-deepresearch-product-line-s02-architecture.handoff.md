# Sprint S02 Architecture — Integration Handoff (N5)

Sprint: `sprint-20260513-solar-deepresearch-product-line-s02-architecture`
Epic: `epic-20260513-solar-deepresearch-product-line`
Node: `N5` (cross-file integration + epic traceability + final handoff)
Builder: 建设者化身 (pane solar-harness-lab:0.0)
Date: 2026-05-14
Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-graph, harness-status

---

## 1. Deliverable Paths (4)

| # | Node | Path | Size | Gate |
|---|------|------|------|------|
| D1 | N1 | `sprint-20260513-solar-deepresearch-product-line-s02-architecture.deepresearch.architecture.md` | 609 lines | `architecture-pass` |
| D2 | N2 | `sprint-20260513-solar-deepresearch-product-line-s02-architecture.deepresearch.schemas.md` | 553 lines | `schemas-pass` |
| D3 | N3 | `sprint-20260513-solar-deepresearch-product-line-s02-architecture.deepresearch.storage.md` | 436 lines | `storage-pass` |
| D4 | N4 | `sprint-20260513-solar-deepresearch-product-line-s02-architecture.deepresearch.dag-template.json` | 363 lines | `dag-template-pass` |

All paths are absolute under `/Users/sihaoli/.solar/harness/sprints/`.

---

## 2. S03 Must-Read Sections

S03 (core-runtime) builder must read these sections before starting implementation:

| Priority | Deliverable | Section | Why |
|---|---|---|---|
| **P0** | architecture.md | §1 Module Layering | Module directory structure, import rules, layer boundaries |
| **P0** | architecture.md | §9 Backward Compatibility | Feature flag, research.db isolation, upgrade/downgrade path |
| **P0** | schemas.md | §4 EvidenceItem | Fields, invariants, ID/hash algorithms — the core data model |
| **P0** | schemas.md | §5 Claim | Fields, invariants — key claim support requirements |
| **P0** | storage.md | §2 SQLite Schema | All 7 CREATE TABLE statements |
| **P0** | storage.md | §4 Hash and Span Verification | SHA-256 + span verification pseudocode |
| **P1** | schemas.md | §1 SourceConnector | Connector protocol, auth_config pattern |
| **P1** | schemas.md | §8 ReportAST | AST structure, nested types, section budgets |
| **P1** | architecture.md | §2 CLI Boundary | Command surface — what S03 must implement first |

---

## 3. S04 Capability Registration Checklist

S04 (orchestration-ui) must register these capabilities on the Solar Capability Plane:

| Capability Name | Module Owner | Registration Target | Readiness Check |
|---|---|---|---|
| `research.source` | `sources/` | `sources/registry.py` | ≥ 1 connector returns non-empty results |
| `research.evidence` | `evidence/` | `evidence/ledger.py` | `ledger verify` exits 0 on test fixture |
| `research.claim` | `graph/` | `graph/claim_miner.py` | `mine` produces claims from test evidence |
| `research.citation` | `evidence/citation_span.py` | `evidence/citation_span.py` | Span verify passes on test fixture |
| `research.report` | `report/` | `report/compiler.py` | `compile` produces final.md from test sections |
| `research.eval` | `eval/` | `eval/metrics.py` | All 7 metrics produce numeric scores |

Additionally, S04 must register the DAG template with graph-scheduler via `deepresearch.dag-template.json` instantiation, substituting `<research-sid>` placeholders.

---

## 4. S05 Factuality Metric Formulas Reference

S05 (verification-release) evaluator must compute these metrics. Formulas are defined in architecture.md §8.4:

| Metric | Formula | Threshold (thorough tier) |
|---|---|---|
| `unsupported_claim_rate` | `sum(section_unsupported) / sum(section_total_key_claims)` | ≤ 5% |
| `citation_span_accuracy` | `sum(section_span_matches) / sum(section_total_spans)` | ≥ 90% |
| `source_authority_score` | `mean(section_authority)` weighted by claim count | Per-source-type thresholds |
| `freshness_score` | `mean(section_freshness)` weighted by evidence count | Depth-appropriate recency |
| `contradiction_coverage` | `1 - (open_contradictions / total_found)` | ≥ 80% (exhaustive tier) |
| `section_repetition_rate` | `1 - (unique_claim_text / total_claim_text)` | ≤ 10% |
| `cross_section_consistency` | `1 - (cross_section_contradictions / total_cross_checks)` | 0 direct contradictions |

Metric scoring and gate enforcement code belongs in `harness/lib/research/eval/metrics.py` and `eval/gates.py`.

---

## 5. Consistency Check

### 5.1 architecture.md schema mentions ⊆ schemas.md 8 models

| Model | architecture.md | schemas.md | ⊆ ? |
|---|---|---|---|
| SourceConnector | ✓ (sources/ module) | ✓ §1 | ✓ |
| SourceHit | ✓ (sources/ module) | ✓ §2 | ✓ |
| SourceDocument | implicit (source provenance) | ✓ §3 | ✓ |
| EvidenceItem | ✓ (evidence/ module) | ✓ §4 | ✓ |
| Claim | ✓ (graph/ module) | ✓ §5 | ✓ |
| ClaimEvidenceLink | ✓ (graph/ module) | ✓ §6 | ✓ |
| CitationSpan | ✓ (evidence/ module) | ✓ §7 | ✓ |
| ReportAST | ✓ (report/ module) | ✓ §8 | ✓ |

No architecture.md model references are outside schemas.md's 8 models. **PASS**.

### 5.2 storage.md tables ⊆ architecture.md SQLite references

| Table | storage.md DDL | architecture.md reference | ⊆ ? |
|---|---|---|---|
| research_runs | ✓ §2.1 | ✓ (§9.3 "7 research tables") | ✓ |
| research_sources | ✓ §2.2 | ✓ (sources/ module) | ✓ |
| evidence_items | ✓ §2.3 | ✓ (evidence/ module) | ✓ |
| claims | ✓ §2.4 | ✓ (graph/ module) | ✓ |
| claim_evidence | ✓ §2.5 | ✓ (graph/ module) | ✓ |
| report_sections | ✓ §2.6 | ✓ (report/ module) | ✓ |
| section_checks | ✓ §2.7 | ✓ (eval/ module) | ✓ |

All 7 storage.md tables map to architecture.md modules. **PASS**.

### 5.3 dag-template.json capabilities ⊆ architecture.md research.* list

Architecture.md defines 6 top-level capabilities: research.source, research.evidence, research.claim, research.citation, research.report, research.eval.

DAG template uses refined capabilities (research.source.web, research.claim.miner, etc.) — these are sub-capabilities that specialize the 6 top-level names.

| DAG Capability | Maps to Architecture Capability |
|---|---|
| research.source.{web,academic,preprint,code,standards,patent,internal} | research.source |
| research.evidence.{ledger,extractor} | research.evidence |
| research.claim.{miner,ledger} | research.claim |
| research.citation (implicit via evidence.ledger) | research.citation |
| research.report_ast, research.long_report_compiler | research.report |
| research.factuality_evaluator | research.eval |
| research.scope_rewrite, research.source_matrix | workflow.planning (existing) |
| research.writer.section | research.report |
| research.evaluator.contradiction | research.eval |
| workflow.planning | Existing harness capability |

All DAG capabilities are refinements of architecture's 6 capabilities + existing harness capabilities. **PASS**.

### 5.4 Cross-file Invariant Consistency

| Invariant | schemas.md | storage.md | Consistent? |
|---|---|---|---|
| EvidenceItem: source_id NOT NULL | ✓ §4 | ✓ FK constraint | ✓ |
| EvidenceItem: span_end > span_start | ✓ §4 | ✓ CHECK constraint | ✓ |
| EvidenceItem: content_hash = sha256(span_text) | ✓ §4 | ✓ §4.1 | ✓ |
| Claim: key claims need ≥ 1 evidence link | ✓ §5 invariant 1 | ✓ claim_evidence FK | ✓ |
| CitationSpan: span_text == byte range | ✓ §7 invariant 1 | ✓ §4.2 verify_span | ✓ |
| Section budget: max 4000 chars | ✓ §8 invariant 4 | — (enforced at compile) | ✓ |
| Feature flag: research.evidence_ledger | — | ✓ §5.1 | ✓ (architecture §9.1 declares flag) |

**PASS** — no cross-file invariant conflicts detected.

---

## 6. Epic Traceability Update

`epic-20260513-solar-deepresearch-product-line.traceability.json` updated:

- `children[1]` (S02_architecture): `status` → `passed`
- `children[1].artifact_links`: 4 deliverable paths populated
- `children[1].passed_at`: `2026-05-14T02:45:00Z`

Downstream children S03 and S04 can now be activated.

---

## 7. Evaluator Review Checklist

1. **architecture-pass (N1)**: ≥ 200 lines (609 ✓), 9 sections, ASCII diagram, 6 capabilities, no hardcoded versions, reuse declarations.
2. **schemas-pass (N2)**: 8 model sections, field tables with types/nullable/default, invariants per model, ID/hash algorithms, versioning policy.
3. **storage-pass (N3)**: ≥ 150 lines (436 ✓), 7 CREATE TABLE DDLs, 5+ JSONL files, hash/span verify pseudocode, feature flag, SQLite/JSONL division.
4. **dag-template-pass (N4)**: 12 nodes R0-R11, valid JSON structure, role-based model names (not version strings), correct topology, fan-out placeholders.
5. **integration-pass (N5)**: 4 paths listed, S03 must-read sections, S04 capability checklist, S05 metric formulas, consistency checks pass, traceability flipped.

Recommended verification commands:

```bash
# Line counts
wc -l sprints/*s02-architecture.deepresearch.architecture.md
wc -l sprints/*s02-architecture.deepresearch.schemas.md
wc -l sprints/*s02-architecture.deepresearch.storage.md

# JSON structure
jq '.nodes | length' sprints/*s02-architecture.deepresearch.dag-template.json
jq '[.nodes[].id]' sprints/*s02-architecture.deepresearch.dag-template.json

# Traceability
jq '.children[1] | {status, artifact_links, passed_at}' sprints/epic-20260513-solar-deepresearch-product-line.traceability.json

# No-code policy (must return 0)
ls sprints/*s02-architecture.*.{py,sh,ts,js} 2>/dev/null | wc -l
```

---

s03_can_start: true
s04_can_start: true
evaluator_can_review: true
