# Compiled Contract — HTML Anything Default Renderer Integration

## Canonical Sources

- `requirement_ir.json` is the source of truth.
- `.contract.md` is the compiled human-readable contract view.

## Product Contract

- goal: integrate `nexu-io/html-anything` as the default Solar HTML renderer for PRD, planning, architecture, and design documents
- success_metrics:
  - `prd.html` default path uses `html-anything`
  - `planning.html` default path uses `html-anything`
  - architecture/design HTML output uses the same renderer family by default
  - accepted export / status-server compatibility preserved
  - legacy renderer no longer default
- non_goals:
  - removing canonical markdown artifacts
  - keeping two long-lived default renderer systems

## Interface Contract

- name: SolarHtmlRendererDefaultContract
- version: 1.0
- invariants:
  - human-facing HTML artifacts remain self-contained single-file documents
  - artifact registration keys remain stable for existing surfaces
  - default renderer selection must favor `html-anything` unless an explicit emergency override is set

## Agent Execution Contract

- allowed_paths:
  - `harness/lib/**`
  - `harness/tests/**`
  - `harness/templates/**`
  - `harness/status-server/**`
  - `harness/docs/**`
  - vendored or wrapped `html-anything` integration path under `harness/` or approved workspace subtree
- forbidden_paths:
  - `.env*`
  - `secrets/**`
  - unrelated production infra
- approval_required_when:
  - adding a new long-lived runtime dependency without pinning
  - introducing external network dependency at render time
  - changing artifact schemas exposed by status-server
- stop_conditions:
  - default path still resolves to legacy renderer
  - output is not self-contained
  - artifact registration/export compatibility regresses
