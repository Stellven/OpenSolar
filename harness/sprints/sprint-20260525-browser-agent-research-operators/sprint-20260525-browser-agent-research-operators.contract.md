# Contract — Browser Agent Research Operators

## Source of Truth
- RawIntent: `/Users/lisihao/.solar/harness/sprints/sprint-20260525-browser-agent-research-operators.raw_intent.json`
- Requirement IR: `/Users/lisihao/.solar/harness/sprints/sprint-20260525-browser-agent-research-operators.requirement_ir.json`
- This sprint must preserve RawIntent -> Requirement Compiler -> Planner/task_graph -> Builder -> Verifier chain.

## Done
- [ ] Browser Agent operator schema/registry/logical operator bindings exist and validate.
- [ ] Async browser job runtime has mock/dry-run adapter and state tests.
- [ ] Session/Auth broker represents profile_ref/login health without logging secrets.
- [ ] Evidence Ledger and monitor bridge expose browser job observability.
- [ ] Scheduler fallback ladder routes high-value deep research to Browser Agent only when required.
- [ ] Security tests cover domain whitelist, payment denied, secrets form denied, cookie/token scrub, reauth wait.
- [ ] Final verifier approves source + live harness evidence.

## Security Boundaries
- `external_login`: manual / ask.
- `payment_action`: denied.
- `secrets_form_fill`: denied.
- `destructive_action`: denied unless explicit human approval.
- `downloads`: artifact dir only.
- `clipboard`: scrubbed / restricted.
- Raw cookie/token/session export is forbidden.

## Stop Conditions
- Stop if implementation stores cookie/token/raw session data in registry/logs.
- Stop if DAG directly click/types browser actions outside Browser Agent runtime.
- Stop if reauth_required is bypassed instead of surfaced as WAITING_HUMAN.
