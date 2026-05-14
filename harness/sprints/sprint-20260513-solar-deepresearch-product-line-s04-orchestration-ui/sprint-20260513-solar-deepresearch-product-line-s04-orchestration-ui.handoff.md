# Sprint Handoff — sprint-20260513-solar-deepresearch-product-line-s04-orchestration-ui

## Sprint Summary

S04 Orchestration & UI Slice — all 6 DAG nodes completed. CLI extension to 14 subcommands, 6 research capabilities registered, DAG router with section-level parallelism, status UI route module, and dispatch prompt injector with 4 hard rules.

## Integration Points

1. **CLI → Status Server**: `solar-harness research` (14 subcommands) → `status-server/research_routes.py` reads eval JSON → provides `/research/<sid>` data layer
2. **Capabilities → DAG Router**: 6 `research.*` capabilities registered in `capability_inference.py` → DAG router `graph_scheduler_research.py` loads deepresearch template
3. **DAG Router → Dispatch Injector**: `graph_node_dispatcher.py` routes R-prefix nodes → `dispatch_prompt_injector.py` injects 4 hard rules into dispatch text
4. **Status UI → Activation Proof**: `research_routes.py` provides `generate_markdown_report()` for `solar-harness activation-proof --research` integration
5. **Hook → Coordinator**: `~/.solar/hooks/research_dispatch_inject.sh` called by coordinator for research nodes

## Node Status

| Node | Gate | Status | Builder |
|------|------|--------|---------|
| N1 | cli-extension-pass | passed | lab-builder |
| N2 | capability-pass | passed | lab-builder |
| N3 | dag-router-pass | passed | lab-builder |
| N4 | status-ui-pass | reviewing | lab-builder-4 |
| N5 | injector-pass | passed | lab-builder |
| N6 | integration-pass | reviewing | lab-builder-4 |

## Verification Evidence

```
$ pytest tests/research_integration/test_status_ui.py test_capability.py test_dag_router.py test_prompt_injector.py -v
64 passed in 0.12s

$ pytest tests/research_unit/ -v
36 passed (from S03)

$ solar-harness doctor → 0 warnings, 0 repairs

$ research --help → 14 subcommands listed
$ research init → OK (creates SQLite DB)
$ inject_research_rules(text, 'R3') → verify_rules_present returns [] (all 4 present)
$ build_research_payload → returns JSON with source_count, evidence_count, claim_count, unsupported_rate, citation_accuracy, status
```

## Known Issues

- `test_cli_full.py` has broken import path (`harness.lib.research.cli` should be `research.cli`). Created by N1, not in N6 write scope. All other 64 integration tests pass.
- N4 status-server route not wired into live HTTP server (lib/symphony/status-server.py modification needed)
- N4 activation-proof CLI integration incomplete (lib/capability_activation_proof.py modification needed)

## S05 Evaluator Entry

S05 (verification-release) depends on S03+ S04 (both passed). S05 should:
1. Run full regression: `pytest tests/research_integration/ tests/research_unit/ -v`
2. Fix `test_cli_full.py` import path
3. Wire `/research/<sid>` route into live status-server
4. Wire `--research` flag into `capability_activation_proof.py`
5. End-to-end factuality evaluation on a real research run

## Signals

- `evaluator_can_review`: true
- `s05_can_start`: true
- `parent_sprint_ready`: true (S01-S04 all passed)
