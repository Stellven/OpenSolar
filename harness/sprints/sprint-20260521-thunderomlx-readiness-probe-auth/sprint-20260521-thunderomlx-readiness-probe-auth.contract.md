# Contract: ThunderOMLX authenticated readiness probe

## Scope
Implement a durable fix for ThunderOMLX readiness probing on Mac mini so auth-protected endpoints do not create false unhealthy status.

## Required Behavior
- Probe code must not print API keys, Bearer tokens, or request bodies containing secrets.
- If using settings, read the API key from `/Users/lisihao/.omlx/settings.json` under `auth.api_key`.
- Treat these states distinctly:
  - `ok`: authenticated probe succeeded or dedicated health endpoint returned healthy.
  - `auth_required_alive`: unauthenticated probe returned `401` from ThunderOMLX, meaning the service is responding but needs auth.
  - `error`: connection refused, timeout, wrong model, or malformed response.
- Existing monitor/restart loops must not wait forever on unauthenticated `/v1/models`.
- Health evidence must include:
  - process/listener status for `127.0.0.1:8002`;
  - authenticated probe result;
  - live `/v1/messages` smoke result;
  - cache usage field result;
  - bad character check.

## Safe Operations
Allowed:
- Edit ThunderOMLX or solar-harness scripts related to readiness/probe logic.
- Run unit tests and local smoke tests.
- Restart ThunderOMLX 8002 only if code changes require it, preserving current launch args.
- Mark graph nodes passed only after acceptance evidence is written.

Forbidden:
- Print API keys or tokens.
- Enable Partial Block Cache, Full Skip, or Approximate Skip.
- Delete cache directories.
- Change model storage on `/Volumes/toshiba`.
- Kill unrelated Python processes.
- Rewrite unrelated user code.

## Deliverables
- Handoff per node:
  - `/Users/lisihao/.solar/harness/sprints/sprint-20260521-thunderomlx-readiness-probe-auth.N1-handoff.md`
  - `/Users/lisihao/.solar/harness/sprints/sprint-20260521-thunderomlx-readiness-probe-auth.N2-handoff.md`
  - `/Users/lisihao/.solar/harness/sprints/sprint-20260521-thunderomlx-readiness-probe-auth.N3-handoff.md`
- Final report:
  - `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-readiness-probe-auth.md`

## Fallback
If Claude org monthly limit prevents worker execution, use shell/API verification directly, write the required handoff/report, and mark a node passed only when its acceptance is met.
