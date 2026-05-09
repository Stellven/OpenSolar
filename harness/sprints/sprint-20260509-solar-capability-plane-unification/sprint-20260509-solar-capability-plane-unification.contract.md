---
name: solar-capability-plane-unification
description: Unify Solar skills, MCP, KB context, and harness dependency graph into dispatch/runtime capability plane.
summary: Implement solar-harness skills inventory/doctor/inject, graph command, dispatch context injection, pane/status UI capability visibility, and Solar-native skill extraction.
triggers: [solar-harness, skills, dispatch, graph, status-ui, kb-context]
---

# Sprint Contract — Solar Capability Plane Unification

Sprint: `sprint-20260509-solar-capability-plane-unification`  
Created: 2026-05-09T00:30:27Z  
Status: active  
Phase: planning_complete  
Priority: P0  
Lane: reliability  
Project: `/Users/sihaoli/.solar/harness`

## Summary

Close the split-brain between Solar skills and Solar Harness execution. Add a runtime capability plane so every dispatch has explicit skills + KB context, every pane exposes real skill/MCP/context capability, and maintainers can inspect harness dependencies with `solar-harness graph`.

## Scope

### In Scope

- `solar-harness skills inventory/doctor/inject/pane-status`
- `solar-harness graph`
- coordinator pre-dispatch idempotent injection
- pane startup capability banner
- status-server capability cards/API
- `/Users/sihaoli/Solar/skills` extraction and classification
- duplicate top-level `case` cleanup for `mirage` and `data-plane`
- tests and docs/runbook update

### Out of Scope

- Rewriting coordinator architecture
- Installing Everything Claude Code live hooks
- Moving all skills into one physical folder
- Changing model provider policy
- Enabling full MCP for third-party gateway panes

## Deliverables

```text
┌────┬──────────────────────────────────────────────────────────────┐
│ D  │ Deliverable                                                  │
├────┼──────────────────────────────────────────────────────────────┤
│ D1 │ lib/solar_skills.py + solar-harness skills inventory/doctor  │
│ D2 │ skills inject + coordinator pre-dispatch fail-open wrapper   │
│ D3 │ skills pane-status + pane startup skill/MCP/context summary  │
│ D4 │ status-server pane capability UI/API                         │
│ D5 │ lib/harness_graph.py + solar-harness graph                   │
│ D6 │ duplicate top-level case cleanup                             │
│ D7 │ Solar native skill extraction/classification report/cache     │
│ D8 │ tests + docs/runbook                                         │
└────┴──────────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] D1: Inventory command returns all skill roots and Solar native skills.
  <!-- verify: cmd="solar-harness skills inventory --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d[\"totals\"][\"skills\"] >= 1600; assert d[\"sources\"].get(\"solar-native\",{}).get(\"count\") == 38'" expected_exit=0 -->

- [ ] D2: Doctor command reports pane-level capability without secrets.
  <!-- verify: cmd="solar-harness skills doctor --json | python3 -c 'import json,sys,re; s=sys.stdin.read(); assert not re.search(r\"(ZHIPU_AUTH_TOKEN|ANTHROPIC_AUTH_TOKEN|DEEPSEEK_API_KEY|sk-[A-Za-z0-9])\", s); d=json.loads(s); assert \"panes\" in d and \"overall\" in d'" expected_exit=0 -->

- [ ] D3: Inject is idempotent and writes both context blocks.
  <!-- verify: cmd="bash /Users/sihaoli/.solar/harness/tests/test-skills-inject-idempotent.sh" expected_exit=0 -->

- [ ] D4: Coordinator dispatch path invokes injection before tmux send.
  <!-- verify: cmd="rg -n 'skills inject|solar_skills.py|inject_dispatch_context' /Users/sihaoli/.solar/harness/coordinator.sh" expected_exit=0 -->

- [ ] D5: Graph JSON and Mermaid outputs include core dependencies.
  <!-- verify: cmd="bash /Users/sihaoli/.solar/harness/tests/test-harness-graph.sh" expected_exit=0 -->

- [ ] D6: No duplicate top-level case branch remains for `mirage` or `data-plane`.
  <!-- verify: cmd="python3 /Users/sihaoli/.solar/harness/tests/check-top-level-case-duplicates.py /Users/sihaoli/.solar/harness/solar-harness.sh" expected_exit=0 -->

- [ ] D7: Status UI/API exposes pane capability summary.
  <!-- verify: cmd="python3 -m py_compile /Users/sihaoli/.solar/harness/lib/symphony/status-server.py && rg -n 'capabilit|skills|mcp_mode|kb_context' /Users/sihaoli/.solar/harness/lib/symphony/status-server.py" expected_exit=0 -->

- [ ] D8: Pane launcher displays skill/MCP/context summary and print-config exposes MCP mode.
  <!-- verify: cmd="bash /Users/sihaoli/.solar/harness/pane-launcher.sh --print-config lab-builder | rg 'MCP|STRICT|empty|EXTRA_FLAGS|mcp-config'" expected_exit=0 -->

- [ ] D9: Solar native skill extraction produces classified cache/report.
  <!-- verify: cmd="test -f /Users/sihaoli/.solar/harness/state/solar-native-skills.json && python3 -c 'import json; d=json.load(open(\"/Users/sihaoli/.solar/harness/state/solar-native-skills.json\")); assert len(d.get(\"skills\",[])) == 38; assert all(x.get(\"status\") for x in d[\"skills\"])'" expected_exit=0 -->

- [ ] D10: Static checks pass.
  <!-- verify: cmd="bash -n /Users/sihaoli/.solar/harness/solar-harness.sh && bash -n /Users/sihaoli/.solar/harness/coordinator.sh && bash -n /Users/sihaoli/.solar/harness/pane-launcher.sh && python3 -m py_compile /Users/sihaoli/.solar/harness/lib/solar_skills.py /Users/sihaoli/.solar/harness/lib/harness_graph.py" expected_exit=0 -->

## Implementation Guidance

1. Prefer adding small Python modules for inventory/graph parsing; keep shell as CLI shim.
2. Do not parse or print secret env values. Report only presence/missing.
3. Injection must replace existing `<solar-skills-context>` and `<solar-knowledge-context>` blocks.
4. If `solar-unified-context.py` fails, insert a degraded KB block and emit a warn event.
5. Cache inventory to `state/skills-inventory.json` for status-server performance.
6. Keep duplicate case cleanup minimal: remove unreachable duplicate branches only after tests prove command coverage.

## Files Likely To Change

- `/Users/sihaoli/.solar/harness/solar-harness.sh`
- `/Users/sihaoli/.solar/harness/coordinator.sh`
- `/Users/sihaoli/.solar/harness/pane-launcher.sh`
- `/Users/sihaoli/.solar/harness/lib/symphony/status-server.py`
- `/Users/sihaoli/.solar/harness/lib/solar_skills.py`
- `/Users/sihaoli/.solar/harness/lib/harness_graph.py`
- `/Users/sihaoli/.solar/harness/tests/test-skills-bridge.sh`
- `/Users/sihaoli/.solar/harness/tests/test-harness-graph.sh`
- `/Users/sihaoli/.solar/harness/docs/skills-capability-plane.md`

## Evaluation Requirements

Evaluator must inspect real command output. A PASS is invalid if it only checks files exist. Required evidence:

- inventory JSON excerpt with counts
- doctor JSON excerpt with pane capability
- injected dispatch file excerpt with both context blocks
- graph Mermaid excerpt
- duplicate case checker output
- no-secret grep output
