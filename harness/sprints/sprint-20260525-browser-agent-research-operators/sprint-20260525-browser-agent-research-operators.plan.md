# Plan — sprint-20260525-browser-agent-research-operators

## Topology
RawIntent -> RequirementCompiler -> LogicalOperator -> Scheduler -> BrowserAgentOperator -> Async Browser Job -> Evidence Ledger -> Verifier.

## DAG
- N1 designs concrete schema and registry addenda.
- N2 implements schema/config/logical operator bindings.
- N3 implements async browser job runtime contract and mock adapter.
- N4 implements session/auth broker and capability-token safety policy.
- N5 integrates scheduler fallback and bridge observability.
- N6 adds tests and lint gates.
- N7 writes docs/operator playbook/manual re-login procedure.
- N8 independent verification and final report.

## Parallelization
N2/N3/N4 depend on N1. N5 depends on N2/N3/N4. N6 depends on N5. N7 can run after N2/N3/N4. N8 joins all.

## Validation Commands
- `python3 -m py_compile lib/operator_runtime.py lib/actor_runtime.py lib/logical_operator_router.py tools/monitor_bridge.py`
- `python3 -m pytest tests/runtime/test_operator_runtime.py tests/runtime/test_actor_runtime.py tests/runtime/test_logical_operator_router.py tests/test_physical_operator_schema.py tests/test-solar-monitor-bridge-global.py -q`
- New browser-operator tests added by sprint must be included in final verification.
