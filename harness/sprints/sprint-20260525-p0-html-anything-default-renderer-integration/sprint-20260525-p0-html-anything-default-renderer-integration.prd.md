# HTML Anything Default Renderer Integration

## 1. Problem

`solar-harness` currently treats HTML as a first-class human review artifact but still relies on a local handcrafted renderer centered on `render_sprint_html.py`. The new requirement is to integrate `nexu-io/html-anything` and make it the default Solar HTML output tool for requirement, planning, architecture, and design documents.

## 2. Users / Stakeholders

- PM
- Planner
- Architect
- Builder
- Evaluator
- Solar operators reviewing sprint artifacts

## 3. Goals / Non-goals

Goals:

- Make `html-anything` the default renderer for `prd.html`.
- Make `html-anything` the default renderer for `planning.html`.
- Extend the same renderer family to future architecture/design HTML artifacts.
- Preserve Solar artifact registration, status exposure, accepted export, and local-first delivery guarantees.

Non-goals:

- Do not remove markdown canonical artifacts.
- Do not ship a second long-lived parallel HTML default path.
- Do not accept a manual opt-in integration as done.

## 4. User Scenarios

1. PM writes `prd.md`; Solar automatically renders `prd.html` via the default `html-anything` path.
2. Planner writes `design.md` / `plan.md`; Solar automatically renders `planning.html` via the same renderer family.
3. Future architecture/design document generation emits HTML through the same default renderer instead of a separate handcrafted path.
4. Status-server and accepted-artifact export continue surfacing these HTML artifacts without schema drift.

## 5. Functional Requirements

- Solar must define an `html-anything` renderer adapter or runtime wrapper.
- Default HTML generation must route through that adapter.
- Solar must support document-specific profiles for PRD, planning, and architecture/design views.
- The renderer must export self-contained single-file HTML suitable for Solar artifact storage and downstream export.
- The legacy renderer must be demoted to emergency fallback only.
- Render failures must produce explicit diagnostics and preserve operator visibility.

## 6. Non-functional Requirements

- local-first
- deterministic enough for regression tests
- no required network at render time
- explicit license traceability for upstream dependency
- compatible with accepted-artifact-export and status-server

## 7. UX / Interaction Model

Operators and users should not need to choose the renderer manually. If they ask Solar for an architecture/design/PRD/planning HTML artifact, the default generated surface should already come from the `html-anything` family. Legacy fallback, if kept, must be operator-only.

## 8. Data / Artifact Model

Canonical markdown artifacts remain source-of-truth:

- `prd.md`
- `design.md`
- `plan.md`

Human-facing HTML artifacts become `html-anything`-backed compiled views:

- `prd.html`
- `planning.html`
- future `design.html` / architecture HTML views if Solar formalizes them

Artifact registration keys remain stable:

- `prd_html`
- `planning_html`
- any newly added architecture/design HTML keys must follow the same status exposure discipline

## 9. Acceptance Criteria

- `prd.html` is rendered through an `html-anything`-backed default path.
- `planning.html` is rendered through an `html-anything`-backed default path.
- At least one architecture/design HTML surface is wired to the same default renderer family.
- Outputs are self-contained and survive artifact registration + accepted export.
- Legacy renderer is no longer default.
- Tests cover rendering, registration, compatibility, and fallback behavior.

## 10. Risks / Open Questions

- [high] Upstream is a pnpm/Next workspace, not a minimal embeddable library.
- [medium] Upstream preview/export assumptions may conflict with Solar's self-contained artifact contract.
- [medium] Existing accepted export/status exposure may assume the current local renderer shape.

Open Questions:

- Vendoring strategy: subtree, pinned mirror, wrapper runtime, or extracted package?
- Profile storage: prompt-like skill profiles vs. code-side templates?
- Should Solar add a generalized `design_html` artifact class now or defer until the default adapter lands?

## 11. Release Plan

1. Define adapter contract and integration strategy.
2. Wire default renderer path for existing PRD/planning artifacts.
3. Extend to architecture/design HTML output.
4. Update tests, migration notes, and rollback controls.
5. Roll out with explicit fallback switch but default enabled.
