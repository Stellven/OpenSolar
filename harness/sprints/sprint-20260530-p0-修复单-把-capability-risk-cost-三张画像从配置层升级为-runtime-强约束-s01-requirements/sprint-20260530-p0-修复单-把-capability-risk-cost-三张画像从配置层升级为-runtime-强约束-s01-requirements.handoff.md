# Handoff — S01 Requirements

sprint_id: `sprint-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束-s01-requirements`
builder: `builder-incarnation`
round: `1`
phase: `planning_complete`
handoff_to: `evaluator`

## Changed Files

| File | Change Description |
|------|-------------------|
| `*.requirements-gap.md` | NEW — R1 baseline: source artifact inventory, missing artifacts, current gaps |
| `*.requirements-contract.md` | NEW — R2 contract: capability (12 capabilities), risk (9 fields), cost (7 fields), operator contract |
| `*.traceability.md` | NEW — R3 traceability: epic-to-sprint mapping, ownership boundaries, migration strategy, non-goals |
| `*.handoff.md` | NEW — R4 handoff: this document |

## Gate Achievement

| Gate | Status | Evidence |
|------|--------|----------|
| G_REQ_BASELINE | ✅ PASSED | All 8 source artifacts read; 2 missing sprint-local artifacts documented; no runtime source modified |
| G_REQ_CONTRACT | ✅ PASSED | Capability (12 items), Risk (9 fields with types/defaults), Cost (7 fields with types/defaults) all defined; hard-gate semantics explicit; operator fields defined with runtime effects |
| G_REQ_TRACE | ✅ PASSED | 5-requirement-to-4-sprint mapping; ownership boundaries with input/output; additive migration with deny-default; explicit non-goals excluding all runtime work |
| G_REQ_READY | ✅ PASSED | Task graph validates (python3 check); handoff written; PM result written |

## Done Definition Achievement

1. **真实调用链接入**: ✅ All artifacts chain from PRD → design → plan → task_graph → requirements-contract → traceability → handoff
2. **禁止硬编码**: ✅ No hardcoded paths, tokens, or business data in requirements artifacts
3. **执行证据齐全**: ✅ Command evidence: `python3 -c "..."` task graph validation passed
4. **结构化收尾**: ✅ Below

## 验证方法

```bash
# Validate task graph
python3 -c "import json; g=json.load(open('*.task_graph.json')); assert len(g['nodes'])==4"

# Check all required artifacts exist
ls *.requirements-gap.md *.requirements-contract.md *.traceability.md *.handoff.md
```

## Upstream Dependencies

- Epic spec (`epic-20260530-...epic.md`)
- Epic traceability (`epic-20260530-...traceability.json`)
- S01 PRD, contract, design, plan, task_graph

## Downstream Impact

- **S02 Architecture**: Consumes this requirements contract to extend schemas
- **S03 Core Runtime**: Consumes hard-gate semantics and decision chain
- **S04 Orchestration/UI**: Consumes rejection taxonomy
- **S05 Verification**: Consumes acceptance criteria

## Open Items

- `product-brief.md` and sprint-local `requirement_ir.json` remain missing (documented as planning gaps; PRD/contract/design serve as authoritative inputs)
- No runtime code, schema, or UI changes in this slice (by design)

## Risks

| Risk | Mitigation |
|------|------------|
| S02 may find schema extension conflicts | Compatibility strategy: additive + deny-default |
| S03 hard-gate implementation may miss edge cases | Decision chain explicitly defined; S05 verifies |
| Premium reservation may need tuning | `reserve_ratio` is configurable; S05 validates |
