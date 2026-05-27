# Handoff — HTML Anything Default Renderer Integration

Knowledge Context: solar-harness context inject used (degraded — no specific html-anything hits; knowledge gap documented below)
Harness Modules Used: harness-knowledge (context inject, degraded)

## Artifact Table

| Artifact | Path |
|----------|------|
| PRD | `.prd.md` |
| Contract | `.contract.md` |
| Requirement IR | `.requirement_ir.json` |
| Design | `.design.md` |
| Plan | `.plan.md` |
| Task Graph | `.task_graph.json` |
| Status | `.status.json` |

## DAG Summary

```
N1 (strategy/contract) → N2 (adapter + default switch) → N3 (surfaces + compat) → N4 (tests + fallback)
```

| Node | Title | Risk | Depends | REQs | Gate |
|------|-------|------|---------|------|------|
| N1 | Integration Strategy / Renderer Contract / Self-Contained Export | high | — | REQ-DEFAULT-001, REQ-SELF-001 | G_DEFAULT_RENDERER |
| N2 | Default Renderer Adapter + PRD/Planning Switch | high | N1 | REQ-DEFAULT-001, REQ-SURFACE-001, REQ-FALLBACK-001 | G_DEFAULT_RENDERER |
| N3 | Architecture/Design HTML + Compat | medium | N2 | REQ-SURFACE-002, REQ-COMPAT-001 | G_COMPAT_EXPORT |
| N4 | Tests / Fallback / Rollout | medium | N3 | REQ-SELF-001, REQ-FALLBACK-001, REQ-TEST-001 | G_TEST |

## Key Design Decisions

1. **Runtime-wrapper strategy** (AD-1): Install html-anything as pinned npm dep under `harness/vendor/html-anything/`. Python adapter calls it via subprocess. Not subtree/vendor-copy/extracted-package.

2. **Profile-based surface differentiation** (AD-2): One adapter, multiple profiles (`prd.json`, `planning.json`, `design.json`). Avoids N separate renderers.

3. **Default-on, not opt-in** (AD-3): No `SOLAR_USE_HTML_ANYTHING` flag. Default IS html-anything. Only `SOLAR_USE_LEGACY_RENDERER=1` triggers fallback.

4. **Legacy as env-var-gated fallback** (AD-4): Original renderer code preserved as `_render_legacy()`. Only operator emergency override activates it.

5. **Post-process inline for self-contained** (AD-5): Adapter post-processes html-anything output to inline all external CSS/JS. Guarantees single-file regardless of upstream behavior.

6. **html_artifact/export/status APIs unchanged** (AD-6): Registration and export are renderer-agnostic. Only `VALID_KINDS` extension for `design_html`.

7. **`design_html` surface in same rollout** (AD-7): N3 adds design kind to satisfy "at least one architecture/design HTML surface" requirement.

8. **Pinned version** (AD-8): `package.json` with exact version, no floating ranges.

## Existing Baseline

### Current Renderer Architecture
- `render_sprint_html.py` (455 lines): Handcrafted markdown→HTML, `_render_prd()` / `_render_planning()`
- `html_artifact.py` (155 lines): Registration + macOS open, `VALID_KINDS = {"prd_html", "planning_html"}`
- `accepted-artifact-export.py` (~1004 lines): Knowledge vault export, `_HTMLTextExtractor` for text extraction
- Templates: `html-artifact.visual-template.html` provides CSS styling

### Test Baseline
- `test-pm-planner-html-artifacts.sh`: Verifies coordinator/persona HTML wiring + workflow_guard HTML-excluded-from-gates
- `test-html-artifact-helper.sh`: Verifies html_artifact.py registration
- `test-accepted-artifact-knowledge-sync.sh`: Verifies export pipeline

### Key Files Builder Will Modify
- `harness/lib/render_sprint_html.py` — refactor to dispatcher pattern (N2)
- `harness/lib/html_anything_adapter.py` — new (N1)
- `harness/vendor/html-anything/` — new pinned install (N1)
- `harness/templates/html-anything-profiles/*.json` — new profiles (N1)
- `harness/lib/html_artifact.py` — extend VALID_KINDS (N3)
- `harness/lib/accepted-artifact-export.py` — add design_html collection (N3)

## Hard Gates

| Gate | Check |
|------|-------|
| G_DEFAULT_RENDERER | Default render path = html-anything, not legacy |
| G_SELF_CONTAINED | Zero external CSS/JS/CDN references in output |
| G_COMPAT_EXPORT | html_artifact register + export + status-server work |
| G_TEST | All HTML test suites pass |

## Stop Rules

1. Default path still → legacy → stop
2. Output not self-contained → stop
3. html_artifact registration/export regression → stop
4. Existing test suite breaks → stop

## Knowledge Hit Gap

`solar-harness context inject` returned no specific hits for html-anything integration. Knowledge context was degraded (no Mirage/QMD/Obsidian hits for html-anything). Design decisions are based on:
- Direct code reading of existing renderer chain (render_sprint_html.py, html_artifact.py, accepted-artifact-export.py)
- Web search establishing html-anything as pnpm/Next.js workspace
- PRD/contract/requirement_ir analysis

## Next Action

Graph scheduler should dispatch **N1** to builder_main. N1 is the design/contract node that creates the adapter skeleton, pinned install, and profiles.

---

*Planner handoff completed at 2026-05-26T02:35:00Z*
