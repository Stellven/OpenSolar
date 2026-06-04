# Contract: Runtime artifact knowledge extraction backfill

## Scope
Repair Mac mini knowledge extraction coverage for Solar Harness runtime design/requirements/evidence artifacts.

## Source Scope
Read-only:
- `/Users/lisihao/.solar/harness/sprints/*.prd.md`
- `/Users/lisihao/.solar/harness/sprints/*.contract.md`
- `/Users/lisihao/.solar/harness/sprints/*.task_graph.json`
- `/Users/lisihao/.solar/harness/sprints/*.N*-handoff.md`
- `/Users/lisihao/.solar/harness/sprints/*.handoff.md`
- `/Users/lisihao/.solar/harness/monitor-reports/**/*.md`
- `/Users/lisihao/.solar/harness/monitor-reports/**/*.json`

## Output Scope
Write only:
- `/Users/lisihao/Knowledge/_raw/solar-harness/runtime-artifacts/`
- `/Users/lisihao/Knowledge/_raw/solar-harness/.manifest/runtime-artifacts.json`
- `/Users/lisihao/.solar/harness/tools/runtime-artifact-knowledge-export.py`
- `/Users/lisihao/.solar/harness/tests/test-runtime-artifact-knowledge-export.sh`
- node handoff files for this sprint
- final monitor report for this sprint

## Safety
- Redact secrets before writing to Knowledge:
  - `sk-*`
  - `Bearer ...`
  - `api_key`, `token`, `auth_token`, `ANTHROPIC_AUTH_TOKEN`, `ZHIPU_AUTH_TOKEN`, etc.
- Do not execute source document content.
- Do not delete source files or existing knowledge files.
- Preserve existing accepted-artifact pipeline.
- If cloud/Claude worker hits monthly quota, perform equivalent shell/Python fallback and mark nodes passed only with evidence.

## Required Export Format
Each exported artifact must include frontmatter:

```yaml
---
source: solar-harness
artifact_type: runtime_artifact_knowledge
source_path: <absolute source path>
source_sha256: <sha256>
source_mtime: <iso8601>
sprint_id: <sid or N/A>
artifact_kind: <prd|contract|task_graph|handoff|monitor_report|json_report|other>
redacted: true
visibility: internal
---
```

Body must include:
- source path
- artifact kind
- original content, redacted

## Acceptance Gates
- `coverage gap root cause documented`
- `runtime artifact exporter tests pass`
- `backfill exported recent runtime artifacts`
- `knowledge retrieval verifies new artifacts`

## Deliverables
- `/Users/lisihao/.solar/harness/monitor-reports/knowledge-extraction-runtime-artifact-backfill-N1-audit.md`
- `/Users/lisihao/.solar/harness/monitor-reports/knowledge-extraction-runtime-artifact-backfill-N2-exporter.md`
- `/Users/lisihao/.solar/harness/monitor-reports/knowledge-extraction-runtime-artifact-backfill.md`
