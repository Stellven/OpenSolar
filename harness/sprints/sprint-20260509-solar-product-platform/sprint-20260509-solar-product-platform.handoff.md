# Handoff — Solar Product Platform Unification

**Sprint**: sprint-20260509-solar-product-platform
**From**: planner (pm_proxy)
**To**: coordinator → builder_main (S0 first)
**Created**: 2026-05-09T03:18:00Z
**Phase**: planning_complete

## Artifacts

| File | Purpose |
|------|---------|
| `sprint-20260509-solar-product-platform.contract.md` | P0 contract (intent/non-negotiables/architecture/D0-D6/gates/stops) |
| `sprint-20260509-solar-product-platform.prd.md` | PRD: context/problem/goals/8 user stories/FR-0..FR-8/A1..A10/non-goals/constraints/risks/OQ/handoff |
| `sprint-20260509-solar-product-platform.design.md` | Architecture: tenets/component map/JSON schemas/data flow diagrams/ADRs/risk-slice map |
| `sprint-20260509-solar-product-platform.plan.md` | Implementation plan: S0..S7 slices/topology/sequencing/G0 checklist/risk routing/OQ routing |

## First Gate (G0) — BLOCKING

Coordinator/PM must:

1. **Do not dispatch any builder until S0 is scoped**.
2. Create S0 sub-contract with the exclusive write scope listed in plan §1 S0.
3. Dispatch builder_main (Sonnet) to S0 only.
4. Wait for evaluator G0 verdict (snapshot+restore dry-run+round-trip+secret exclusion).
5. **Only after G0 PASS** parallel dispatch S1 (builder_codex) + S2 (builder_glm) + S6 (builder_main).
6. S3 starts after G2/G3 + state DB schema ready.
7. S4 → S5 → S7 strictly sequential.

## Forbidden Until G0 PASS

- Any move/rename of `_raw` PDFs.
- Any change to launchd primary services.
- Any change to existing solar-harness start/status/wiki/qmd/status-server paths.
- Any plaintext secret operation in git/log/UI/release.

## Slice → Builder → Gate Map

| Slice | D | Builder | Gate |
|-------|---|---------|------|
| S0 | D0 | builder_main | G0 (blocking) |
| S1 | D1+FR7+FR8 | builder_codex | G2+G3 |
| S2 | D2 | builder_glm | G4 |
| S3 | D3 | builder_main | G5 |
| S4 | D4 | builder_glm | A10 |
| S5 | D5 | builder_codex | A9 |
| S6 | D6 | builder_main | G6 |
| S7 | release | builder_main + 双签 | G7 |

## Status Transition

- queued → drafting → spec → prd_ready → planning → planning_complete (current)
- Next: coordinator/PM picks up to scope S0 → status=active 时由 coordinator 决定。
- **Planner 不会自行推 active**（按昊哥指令 G0 先过）。

## Risk Register Snapshot

R1 PDF 误删 (高) | R2 Skill 软链冲突 (高) | R3 容器漂移 (中) | R4 协调器破坏 (中) | R5 autopilot 误判 (中) | R6 Drive 伪 ok (中) | R7 plugin 过度设计 (低) | R8 evolution 误晋级 (低) | R9 secret 漏检 (中) | R10 MinerU OOM (低)

详见 PRD §10、Design §6、Plan §4。

## Open Questions Routed

OQ-1..OQ-10 已分配到具体 slice 与设计期解答（详见 plan §5）。

## Notes

- brain-router MCP 在本会话中两次调用 -32000 失败；PRD/Design/Plan 由 planner 直接撰写，已记录 by=pm_proxy_planner。
- coordinator 之前对 sprint-20260509-mineru-mirage-closeout 出现过 dispatch_failed 误判 (pane busy 当 pane dead)，本 sprint S6 D6.4 直接覆盖该缓解。
