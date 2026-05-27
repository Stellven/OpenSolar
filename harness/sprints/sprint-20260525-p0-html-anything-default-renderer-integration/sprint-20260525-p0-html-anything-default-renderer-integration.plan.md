# Implementation Plan — HTML Anything Default Renderer Integration

## Phase Map

```
N1 (strategy/contract) ──► N2 (adapter + default switch) ──► N3 (surfaces + compat) ──► N4 (tests + fallback)
```

Sequential chain. Each node gates the next via `required_node_status: passed`.

---

## N1: Integration Strategy / Renderer Contract / Self-Contained Export Policy

**Goal**: Define the html-anything adapter contract, install strategy, self-contained export constraints, and profile system.

**Requirements**: REQ-DEFAULT-001, REQ-SELF-001

**Write Scope**:
- `harness/vendor/html-anything/package.json` (pinned dependency)
- `harness/lib/html_anything_adapter.py` (adapter skeleton + contract)
- `harness/templates/html-anything-profiles/prd.json`
- `harness/templates/html-anything-profiles/planning.json`
- `harness/templates/html-anything-profiles/design.json`

**Read Scope**:
- `harness/lib/render_sprint_html.py`
- `harness/lib/html_artifact.py`
- `harness/lib/accepted-artifact-export.py`
- `harness/templates/html-artifact.visual-template.html`

**Acceptance**:
- `html_anything_adapter.py` exposes `render(markdown: str, profile: str) -> str` returning self-contained HTML
- html-anything pinned in `package.json` with exact version
- Profile JSON files define prd/planning/design surface configs
- Self-contained verification function present: `_verify_self_contained(html: str) -> bool`

**Verification**:
```bash
cd ~/.solar/harness && python3 -c "
from lib.html_anything_adapter import render, _verify_self_contained
html = render('# Test', profile='prd')
assert _verify_self_contained(html), 'not self-contained'
print('N1 PASS')
"
```

**Gate**: G_DEFAULT_RENDERER

---

## N2: Default Renderer Adapter + PRD/Planning Default Switch

**Goal**: Rewire `render_sprint_html.py` to delegate to html-anything adapter by default. Legacy renderer becomes `_render_legacy()`, gated by `SOLAR_USE_LEGACY_RENDERER` env var.

**Requirements**: REQ-DEFAULT-001, REQ-SURFACE-001, REQ-FALLBACK-001

**Write Scope**:
- `harness/lib/render_sprint_html.py` (refactor: dispatcher pattern)
- `harness/vendor/html-anything/` (pnpm install)

**Read Scope**:
- `harness/coordinator.sh` (verify call signature preserved)
- `harness/personas/pm.md`
- `harness/personas/planner.md`
- `harness/lib/workflow_guard.py`

**Acceptance**:
- `render(args)` default path calls `html_anything_adapter.render()` — not `_render_legacy()`
- `prd.html` rendered via html-anything when no override is set
- `planning.html` rendered via html-anything when no override is set
- `SOLAR_USE_LEGACY_RENDERER=1` env var triggers legacy path
- Missing html-anything runtime auto-falls back to legacy with explicit warning

**Verification**:
```bash
cd ~/.solar/harness && python3 lib/render_sprint_html.py render \
  --sid sprint-20260525-p0-html-anything-default-renderer-integration \
  --kind prd --json --output /tmp/test-n2-prd.html
# Verify html-anything was used, not legacy
grep -c "html-anything" /tmp/test-n2-prd.html || echo "check renderer identity"

SOLAR_USE_LEGACY_RENDERER=1 python3 lib/render_sprint_html.py render \
  --sid sprint-20260525-p0-html-anything-default-renderer-integration \
  --kind prd --json --output /tmp/test-n2-legacy.html
# Verify legacy path was used
```

**Gate**: G_DEFAULT_RENDERER

---

## N3: Architecture/Design HTML Surface + Artifact/Export/Status Compatibility

**Goal**: Wire at least one architecture/design HTML surface to the same renderer family. Verify html_artifact registration, accepted-artifact-export, and status-server all continue working with the new renderer output.

**Requirements**: REQ-SURFACE-002, REQ-COMPAT-001

**Write Scope**:
- `harness/lib/html_artifact.py` (extend `VALID_KINDS` with `"design_html"`)
- `harness/lib/render_sprint_html.py` (add `"design"` to `VALID_KINDS`, add `_render_design`)
- `harness/lib/accepted-artifact-export.py` (add `design_html` collection)

**Read Scope**:
- `harness/lib/symphony/status-server.py`
- `harness/tests/test-html-artifact-helper.sh`
- `harness/tests/test-pm-planner-html-artifacts.sh`
- `harness/tests/test-accepted-artifact-knowledge-sync.sh`

**Acceptance**:
- `design_html` artifact kind registered in html_artifact.py's `VALID_KINDS`
- `render_sprint_html.py` supports `--kind design` producing design.html via html-anything
- `_collect_artifacts()` in accepted-artifact-export picks up `design.html`
- status-server exposes registered HTML artifacts without schema change
- Existing test suite passes without modification

**Verification**:
```bash
cd ~/.solar/harness
bash tests/test-html-artifact-helper.sh
bash tests/test-pm-planner-html-artifacts.sh
bash tests/test-accepted-artifact-knowledge-sync.sh
```

**Gate**: G_COMPAT_EXPORT

---

## N4: Tests / Fallback / Rollout / Rollback

**Goal**: Add regression tests for default renderer selection, self-contained output, compatibility, and fallback behavior. Document rollback procedure.

**Requirements**: REQ-SELF-001, REQ-FALLBACK-001, REQ-TEST-001

**Write Scope**:
- `harness/tests/test-html-anything-adapter.sh` (new)
- `harness/tests/test-html-anything-self-contained.py` (new)
- `harness/docs/html-renderer-migration.md` (new)
- `harness/lib/render_sprint_html.py` (final adjustments if needed)

**Read Scope**:
- `harness/lib/**`

**Acceptance**:
- Test suite verifies default path is html-anything (not legacy)
- Test suite verifies self-contained output (no external CSS/JS/CDN references)
- Test suite verifies `SOLAR_USE_LEGACY_RENDERER=1` triggers legacy path
- Test suite verifies html_artifact registration works with new renderer output
- Migration doc specifies: default path, fallback trigger, rollback steps
- All existing tests still pass

**Verification**:
```bash
cd ~/.solar/harness
bash tests/test-html-anything-adapter.sh
python3 tests/test-html-anything-self-contained.py
bash tests/test-html-artifact-helper.sh
bash tests/test-pm-planner-html-artifacts.sh
bash tests/test-accepted-artifact-knowledge-sync.sh
```

**Gate**: G_TEST

---

## Cross-Cutting Hard Gates

| Gate | Check | Enforced At |
|------|-------|-------------|
| G_DEFAULT_RENDERER | Default render path resolves to html-anything, not legacy | N2, N4 |
| G_SELF_CONTAINED | Rendered HTML has zero external CSS/JS/CDN references | N1, N4 |
| G_COMPAT_EXPORT | html_artifact register + accepted export + status-server work | N3 |
| G_TEST | All HTML-related test suites pass | N4 |

## Stop Rules

1. If default path still resolves to legacy renderer → do not mark done.
2. If output is not self-contained → do not mark done.
3. If html_artifact registration/export regresses → do not mark done.
4. If existing test suite breaks → do not mark done.

## Rollback Procedure

1. Set `SOLAR_USE_LEGACY_RENDERER=1` in harness environment.
2. All renders immediately fall back to legacy `_render_legacy()`.
3. No data loss — markdown canonical artifacts are unaffected.
4. Remove env var to re-enable html-anything default.
