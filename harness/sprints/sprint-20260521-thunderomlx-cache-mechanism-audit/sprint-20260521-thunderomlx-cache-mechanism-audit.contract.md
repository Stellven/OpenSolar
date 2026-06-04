# Contract — ThunderOMLX Cache Mechanism Audit

Sprint: `sprint-20260521-thunderomlx-cache-mechanism-audit`
Created: 2026-05-21T12:17:50Z

## Scope
Read-only analysis of `/Users/lisihao/ThunderOMLX`, `/Users/lisihao/.omlx/settings.json`, `/Users/lisihao/.solar/harness/logs/thunderomlx-8002.log`, and current 8002 runtime. Write only monitor report and node handoffs.

## Hard Rules
- Do not print secrets or API tokens.
- Do not kill/restart ThunderOMLX.
- Do not delete cache directories.
- Do not enable partial block cache, approximate skip, full skip, or unsafe skip features.
- Do not mutate ThunderOMLX source in this sprint.

## Required Evidence
- Use `find`, `grep`, docs, tests, settings, process args, logs, and API smoke where safe.
- Include direct file path evidence for every mechanism.
- For runtime checks, redact auth values and only report presence/host/model/status.

## Report Required Sections
1. Executive summary
2. Current runtime cache configuration
3. Full mechanism inventory
4. Mechanism interaction map
5. Known bugs and blockers
6. Safe optimization candidates
7. P0/P1/P2 experiment backlog
8. Commands used and evidence paths
9. Risk and rollback notes
