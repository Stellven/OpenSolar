# PRD - Everything Claude Code Integration Backlog

## Goal

Evaluate and safely integrate useful parts of Everything Claude Code into Solar without breaking existing Solar coordinator, Claude hooks, Codex Superpowers, Gstack rules, or knowledge ingestion.

## User Need

The user remembers an open-source project called EverythingCloudCode and wants Solar to stop losing track of prior integration ideas. If the project is not already integrated, Solar should place it into the codebase as a clear backlog item and let planner/builder continue from a concrete contract.

## Scope

- Vendor the upstream repository for local review.
- Inventory agents, commands, skills, hooks, rules, MCP configs, scripts, tests, and contexts.
- Detect collisions with local Claude/Codex/Solar/Gstack/Superpowers surfaces.
- Produce a dry-run install plan.
- Keep all hooks, MCP configs, and install scripts disabled until allowlisted.

## Non-Goals

- No live global install in this sprint.
- No overwrite of `~/.claude`, `~/.codex`, `~/.agents`, or Solar config.
- No automatic hook activation.
- No change to pane routing or model routing.

## Acceptance

- Upstream repo is vendored under harness vendor.
- `solar-harness everything-claude-code inventory --json` returns counts and collisions.
- `solar-harness everything-claude-code install --dry-run --json` reports `live_hook_changes=0`.
- Audit report exists and calls out Gstack/Superpowers compatibility.
- Status remains `warn` or `missing` until allowlist sync passes.
