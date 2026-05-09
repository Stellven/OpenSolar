# Plan — Solar Capability Plane Unification

Sprint: `sprint-20260509-solar-capability-plane-unification`  
Topology: solo main builder, with optional lab verification only after D1-D4 pass.

## Slice S1 — Skills Inventory / Doctor / Inject

Owner: builder_main  
Files:

- `lib/solar_skills.py`
- `solar-harness.sh`
- `tests/test-skills-inject-idempotent.sh`

Tasks:

1. Implement skill root discovery.
2. Parse SKILL.md frontmatter/heading/description safely.
3. Detect duplicates and classify Solar native skills.
4. Implement `inventory`, `doctor`, `inject`, `pane-status` subcommands.
5. Cache inventory to `state/skills-inventory.json`.

Acceptance:

- A1, A2, A3, A9.

## Slice S2 — Dispatch Integration

Owner: builder_main  
Files:

- `coordinator.sh`
- `lib/events.sh` only if needed
- tests under `tests/`

Tasks:

1. Add fail-open `inject_dispatch_context()` wrapper.
2. Call wrapper inside `dispatch_to_pane()` after instruction file exists and before `tmux send-keys`.
3. Emit `dispatch_context_injected` or `dispatch_context_inject_failed`.
4. Ensure repeated dispatch retries do not duplicate context blocks.

Acceptance:

- A3, A4, A10.

## Slice S3 — Graph / Cleanup

Owner: builder_main  
Files:

- `lib/harness_graph.py`
- `solar-harness.sh`
- `tests/test-harness-graph.sh`
- `tests/check-top-level-case-duplicates.py`

Tasks:

1. Implement static dependency graph scanner.
2. Output JSON, Markdown, Mermaid.
3. Add top-level duplicate branch checker.
4. Remove duplicate/unreachable `mirage)` and `data-plane)` case branches.

Acceptance:

- A5, A6, A7, A10.

## Slice S4 — Pane / Status Visibility

Owner: builder_main  
Files:

- `pane-launcher.sh`
- `lib/persona-config.sh`
- `lib/symphony/status-server.py`
- `docs/skills-capability-plane.md`

Tasks:

1. Expose MCP mode in `--print-config`.
2. Print short startup capability summary in each pane.
3. Add status-server endpoint or enrich existing status payload with pane capabilities.
4. Render capability cards in UI without raw JSON dump.

Acceptance:

- A2, A7, A8, A10.

## Verification Order

```bash
bash -n ~/.solar/harness/solar-harness.sh
bash -n ~/.solar/harness/coordinator.sh
bash -n ~/.solar/harness/pane-launcher.sh
python3 -m py_compile ~/.solar/harness/lib/solar_skills.py ~/.solar/harness/lib/harness_graph.py
solar-harness skills inventory --json
solar-harness skills doctor --json
bash ~/.solar/harness/tests/test-skills-inject-idempotent.sh
bash ~/.solar/harness/tests/test-harness-graph.sh
python3 ~/.solar/harness/tests/check-top-level-case-duplicates.py ~/.solar/harness/solar-harness.sh
solar-harness graph --format mermaid | head -40
```

## Stop Rules

- Stop if coordinator cannot start after syntax check.
- Stop if any token-like secret appears in inventory/doctor/status output.
- Stop if dispatch injection requires network access.
- Stop if status-server fails to start after UI changes.
