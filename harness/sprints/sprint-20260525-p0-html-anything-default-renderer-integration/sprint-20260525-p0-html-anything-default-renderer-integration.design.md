# Architecture Design — HTML Anything Default Renderer Integration

## 1. Overview

Replace Solar Harness's handcrafted HTML renderer (`render_sprint_html.py`) with `nexu-io/html-anything` as the **default** renderer for all human-facing HTML artifacts (PRD, planning, architecture/design). Legacy renderer becomes emergency-only fallback.

## 2. Integration Strategy: Runtime Wrapper

**Decision: `runtime-wrapper` with pinned local install.**

| Strategy | Verdict | Reason |
|----------|---------|--------|
| subtree | Rejected | Upstream is a full pnpm/Next.js workspace (~4.1k stars, heavy dependency tree). Subtree merge complexity outweighs benefit. |
| vendor (copy) | Rejected | Cannot vendor a workspace; would need to extract a subset manually, creating maintenance burden. |
| extracted package | Rejected | Upstream does not expose a standalone embeddable package today. |
| **runtime-wrapper** | **Selected** | Install html-anything as a pinned npm dependency under `harness/vendor/html-anything/`. A Python adapter invokes it via subprocess. Clean boundary, pin-able, replaceable. |

**Why runtime-wrapper wins:**
- html-anything is a CLI-capable agentic HTML editor (pnpm/Next workspace). It has a CLI surface that can produce self-contained HTML.
- Solar's Python codebase should not import Node.js internals — subprocess is the natural boundary.
- Pinning via `package.json` + `pnpm-lock.yaml` under `harness/vendor/` gives deterministic installs without polluting global state.
- If upstream later publishes a standalone package, the adapter is the only file that changes.

**Implementation shape:**
```
harness/
  vendor/
    html-anything/           # pinned npm install
      package.json           # pinned dependency
      pnpm-lock.yaml
      node_modules/
  lib/
    html_anything_adapter.py # Python subprocess adapter
    render_sprint_html.py    # rewritten to delegate to adapter
    html_artifact.py         # unchanged API
    accepted-artifact-export.py  # unchanged API
  templates/
    html-anything-profiles/  # document-specific rendering profiles
      prd.json
      planning.json
      design.json
```

## 3. Why Default, Not Sidecar

**The PRD is explicit: "Do not accept a manual opt-in integration as done."**

Three reasons why default-only is correct:

1. **Operator UX**: Every sprint generates PRD and planning HTML. If operators must opt in each time, the default stays legacy and html-anything becomes dead code. Default-on is the only way to get real usage.

2. **No parallel defaults**: Maintaining two renderer paths indefinitely is a non-goal. The contract forbids "keeping two long-lived default renderer systems." Sidecar implies both are first-class — that violates the contract.

3. **Test surface**: Default-on forces every sprint to exercise the new renderer, surfacing integration issues immediately. Sidecar hides bugs.

## 4. Unified Renderer Family

All three HTML surfaces share one adapter with profile-based differentiation:

```
html_anything_adapter.py
  ├── render(markdown, profile="prd")     → prd.html
  ├── render(markdown, profile="planning") → planning.html
  └── render(markdown, profile="design")   → design.html (new)
```

**Profile system**: Each profile is a JSON file under `templates/html-anything-profiles/` that specifies:
- Which sections to emphasize (hero, TOC, DAG diagram, etc.)
- CSS theme overrides
- Layout template hints

All profiles call the same underlying html-anything runtime. The "renderer family" is one adapter + multiple profiles, not multiple renderers.

**Unification contract**:
- `prd.html`, `planning.html`, and future `design.html` are all produced by `html_anything_adapter.render()`.
- The adapter accepts `(markdown_text: str, profile: str) -> str` (HTML output).
- Profiles only control presentation, not rendering logic.

## 5. Self-Contained Artifact Constraint

**Requirement**: HTML output must be a single file, no external CSS/JS/CDN.

**Strategy**:
1. html-anything adapter invokes the upstream CLI with `--self-contained` or equivalent export mode.
2. If upstream cannot produce self-contained output natively, the adapter post-processes:
   - Inlines all `<link rel="stylesheet">` into `<style>` blocks.
   - Inlines all `<script src="...">` into `<script>` blocks.
   - Removes any remaining external references.
3. **Verification gate**: `G_SELF_CONTAINED` test checks rendered HTML for `href="http`, `src="http`, and `<link` external references. Any match = fail.

**Fallback behavior**: If html-anything runtime fails or is missing, legacy renderer produces self-contained HTML (it already does — all CSS is inlined from `html-artifact.visual-template.html`). Self-contained guarantee is preserved in both paths.

## 6. Backward Compatibility

### html_artifact.py — No API changes needed

- `VALID_KINDS = {"prd_html", "planning_html"}` — add `"design_html"` when that surface lands.
- `register(args)` reads the HTML file path and writes to status.json — works regardless of which renderer produced the file.
- `_open_html()` is renderer-agnostic (just calls macOS `open`).

**Change**: Only extend `VALID_KINDS` when adding `design_html`. No other changes to html_artifact.py.

### accepted-artifact-export.py — No API changes needed

- `_collect_artifacts()` discovers HTML files by name pattern (`{sid}.prd.html`, `{sid}.planning.html`).
- `_read_html_artifact()` uses `_HTMLTextExtractor` (stdlib `HTMLParser`) — works on any valid HTML.
- Export format is text-extracted, not structure-dependent.

**Change**: Add `design_html` collection when that surface lands. The extraction logic is renderer-agnostic.

### status-server.py — No changes needed

- Exposes whatever artifacts are registered in `status.json`.
- Registration happens through `html_artifact.py`, which is renderer-agnostic.

### coordinator.sh — Wire to new renderer

- Currently calls `render_sprint_html.py render --kind prd/planning`.
- After migration, same call signature, different implementation under the hood.
- The CLI interface of `render_sprint_html.py` is preserved; it just delegates to `html_anything_adapter.py` internally.

### workflow_guard.py — No changes needed

- HTML artifacts are already excluded from routing gates (verified by `test-pm-planner-html-artifacts.sh`).
- Renderer swap is invisible to workflow gates.

## 7. Legacy Renderer Demotion

**Current state**: `render_sprint_html.py` is the only renderer. It's called directly by `coordinator.sh`.

**Target state**: `render_sprint_html.py` becomes a thin dispatcher:

```python
def render(args):
    if _html_anything_available() and not os.environ.get("SOLAR_USE_LEGACY_RENDERER"):
        return _render_via_html_anything(args)
    else:
        return _render_legacy(args)  # original code, renamed
```

**Demotion rules**:
- Default path: html-anything adapter.
- Fallback trigger: `SOLAR_USE_LEGACY_RENDERER=1` env var (operator-only override).
- Automatic fallback: If html-anything runtime is not installed (`harness/vendor/html-anything/` missing or `node_modules` absent), log a warning and fall back to legacy.
- Legacy renderer is never deleted — it stays as `_render_legacy()` for emergency use.
- Tests must verify that default path is html-anything, not legacy.

## 8. Architecture Diagram

```
                          coordinator.sh
                               │
                    ┌──────────▼──────────┐
                    │ render_sprint_html.py│
                    │   (dispatcher)       │
                    └──────┬──────┬───────┘
                           │      │
              default      │      │  SOLAR_USE_LEGACY_RENDERER=1
              path         │      └──────────────┐
                           ▼                     ▼
               ┌───────────────────┐   ┌──────────────────┐
               │html_anything_     │   │ _render_legacy() │
               │adapter.py         │   │ (original code)  │
               └───────┬───────────┘   └──────────────────┘
                       │ subprocess
                       ▼
            ┌─────────────────────┐
            │ html-anything CLI   │
            │ (harness/vendor/)   │
            └──────────┬──────────┘
                       │ profile
                       ▼
            ┌─────────────────────┐
            │  self-contained     │
            │  HTML output        │
            └──────────┬──────────┘
                       │
          ┌────────────▼─────────────┐
          │    html_artifact.py      │
          │  (register + open)       │
          └────────────┬─────────────┘
                       │
          ┌────────────▼─────────────┐
          │ status.json + export     │
          │ (renderer-agnostic)      │
          └──────────────────────────┘
```

## 9. Data Flow

```
prd.md + contract.md + task_graph.json
    │
    ▼
html_anything_adapter.render(markdown, profile="prd")
    │
    ├── reads profile: templates/html-anything-profiles/prd.json
    ├── invokes: harness/vendor/html-anything/node_modules/.bin/html-anything ...
    ├── captures: stdout (HTML string)
    ├── post-processes: inline all external assets
    └── returns: self-contained HTML
    │
    ▼
{sid}.prd.html  →  html_artifact.py register  →  status.json artifacts
    │
    ▼
accepted-artifact-export.py  →  Knowledge vault (text-extracted)
```

## 10. Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| html-anything CLI doesn't support self-contained export | high | Adapter post-processes output to inline assets. If impossible, fall back to extracting and bundling. |
| html-anything runtime install fails (pnpm not available) | medium | Pin Node.js + pnpm via `harness/vendor/` setup script. Auto-fallback to legacy if missing. |
| html-anything output differs from current visual template | medium | Profile system provides theme hints. Accept visual change as long as content fidelity is preserved. |
| Regression in artifact registration/export | medium | Existing test suite (`test-html-artifact-helper.sh`, `test-pm-planner-html-artifacts.sh`) catches regressions. |
| Upstream breaking changes | low | Pin to exact version in `package.json`. Manual upgrade with test verification. |

## 11. Scope Boundaries

**In scope (this sprint)**:
- html-anything pinned install + adapter
- Default renderer switch for `prd.html` and `planning.html`
- At least one architecture/design HTML surface wired
- Self-contained verification
- Legacy demotion
- Test + documentation

**Out of scope**:
- Removing legacy renderer code
- Changing artifact registration schema
- Adding new artifact keys beyond existing `prd_html`/`planning_html` (+ optional `design_html`)
- Network-dependent rendering features

## 12. Architectural Decisions Summary

| # | Decision | Rationale |
|---|----------|-----------|
| AD-1 | Runtime-wrapper integration strategy | Clean boundary, pin-able, works with pnpm/Next workspace |
| AD-2 | Profile-based surface differentiation | One adapter, multiple profiles — avoids N renderers |
| AD-3 | Default-on, not opt-in | PRD contract: no manual opt-in |
| AD-4 | Legacy as env-var-gated fallback | Operator-only emergency path, never default |
| AD-5 | Post-process inline for self-contained | Guaranteed single-file output regardless of upstream |
| AD-6 | Preserve html_artifact/export/status APIs | Renderer swap is internal; external contracts unchanged |
| AD-7 | `design_html` surface in same rollout | PRD requires at least one architecture/design surface |
| AD-8 | Pin html-anything version via package.json | Deterministic installs, no floating dependencies |
