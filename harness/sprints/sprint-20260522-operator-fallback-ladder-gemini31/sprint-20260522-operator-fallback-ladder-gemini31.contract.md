# Contract: Operator Fallback Ladder + Gemini 3.1 Pro Registration

Sprint: `sprint-20260522-operator-fallback-ladder-gemini31`

## Execution Rules

- Work on Mac mini under `/Users/lisihao/.solar/harness`.
- Prefer the verified Google Antigravity Gemini 3.5 Flash operator for implementation nodes.
- Treat Anthropic org monthly limit as a real quota blocker, not a transient retry condition.
- Do not leak secrets. Registry must contain only `secret_ref`, `key_ref`, or account labels.
- Do not kill tmux panes or delete task directories.
- Do not change unrelated active sprints.
- Do not re-enable unsafe ThunderOMLX cache features.
- Preserve compatibility with existing `physical-operators.json` fields.

## Deliverables

### Code / Config

- Update `config/physical-operators.json` or add a companion catalog/policy file that includes:
  - Claude Opus planner/reviewer
  - Claude Sonnet builder
  - GLM-5.1 builder
  - ThunderOMLX/Qwen knowledge/local operators
  - Antigravity Gemini 3.5 Flash text/image operators
  - Antigravity Gemini 3.1 Pro reasoning operator
  - Local scan/checker operators
  - RouterMeta and AuditLedger operators
- Add an auditable 4.1-4.10 operator class coverage matrix:
  - DeepArchitect
  - RootCauseDebug
  - Implementation
  - FastSubagent
  - ParallelExploration
  - Verifier
  - ResearchSynthesis
  - BrowserComputerUse
  - GoogleStack
  - LocalPrivacy
- Include canonical ids for all recommended operators, even when their current state is `missing` or `pending`.
- Include apply/avoid boundaries for each class.
- Include strict Browser/Computer-use permissions:
  - `external_login=ask`
  - `payment_action=denied`
  - `secrets_form_fill=denied`
  - `destructive_action=ask`
- Include RootCauseDebug handoff policy: hypothesis operator and reproduction/patch operator are separate.
- Include Verifier policy: writer and final verifier cannot be the same operator; critical work prefers cross-provider verification.
- Add quota-aware fallback ladder policy.
- Add quota-clock policy as a first-class scheduling input:
  - provider
  - account_label
  - plan_type
  - period
  - refresh_at
  - remaining_estimate
  - soft_stop_threshold
  - hard_stop_threshold
  - reserve_for
  - on_exhausted
- Add provider-specific quota degradation rules:
  - Claude Opus below soft threshold is reserved for ARCH_DESIGN, ROOT_CAUSE_DEBUG, and FINAL_REVIEW.
  - Codex GPT-5.5 low quota degrades implementation to mini/Gemini/Antigravity while preserving strong final validation when possible.
  - Antigravity low quota reduces fan-out parallelism.
- Add observed quota support for subscription CLIs:
  - CLI stderr/stdout limit text
  - HTTP 429/quota/rate-limit failures
  - latency anomalies
  - task failure type
  - manual refresh_at
- Add lifecycle state-machine policy:
  - created
  - warming
  - idle
  - leased
  - running
  - draining
  - cooldown
  - quota_exhausted
  - auth_expired
  - stale_context
  - disabled
  - needs_human_review
  - error
- Add naming convention policy:
  - canonical ids follow `op.<surface>.<provider>.<model>.<role>.<config>.<index>`
  - pane titles follow `[PROVIDER][MODEL][ROLE][CONFIG][INDEX]`
  - current `mini-*` aliases must map to canonical ids
- Add tmux startup policy:
  - target session uses operator panes running `operatord run <operator_id>`
  - DAG must not directly call `tmux send-keys`
  - dispatch goes through `operator_runtime.submit(task)` or the current documented migration equivalent
- Add operatord responsibility contract:
  - read registry
  - resolve secret refs
  - inject environment
  - launch CLI/SDK/local runtime
  - heartbeat
  - receive task envelope
  - write logs
  - capture stdout/stderr
  - parse quota/auth/error
  - report task result
- Add or document normal DAG authoring policy: nodes should express `task_type`, `required_capabilities`, `constraints`, and `preferred_operator_classes`, not concrete model names.
- Add the first-version task-type routing policy for architecture, debug, implementation, refactor, tests, research, parallel exploration, Google-stack, UI, docs, soft/hardware optimization, security-sensitive work, and low-cost scan.
- Add or verify the first-version selector scoring factors:
  - capability fit
  - quality score or current placeholder
  - quota score
  - latency/cost score
  - availability score
  - context affinity
  - risk match
  - recent error penalty
  - same-model/same-operator verifier penalty
- Extend selector logic and tests if current selector cannot express the policy.
- Extend monitor bridge output if runtime latest lacks operator fleet fields.

### Tests

- Targeted selector test for quota-exhausted Opus fallback.
- Targeted selector test for Gemini 3.1 Pro fallback/unavailability.
- Targeted selector test or static audit proving a normal DAG node can be routed without `preferred_operator` or concrete `model`.
- Targeted selector test or report section proving task-type policy and scoring factors are applied or explicitly marked as first-version placeholders.
- Report section proving all 4.1-4.10 operator classes are covered and identifying which are implemented, pending, missing, or disabled.
- Report section proving quota clock and lifecycle state machine coverage, including gaps that remain pending.
- Report section proving naming convention, tmux startup contract, and operatord contract coverage, including implementation gaps.
- Targeted bridge test for operator fleet fields.
- JSON parse/schema validation for registry and policy.

### Report

- `/Users/lisihao/.solar/harness/monitor-reports/operator-fallback-ladder-gemini31.md`

## Safety Gates

- No raw token/API key in any output.
- Writer and verifier cannot be the same `operator_id`.
- Disabled/pending operators may appear in catalog but must not be selected.
- Gemini 3.1 Pro may be `pending` if Antigravity CLI cannot prove availability; fallback behavior must still pass.
- Bridge restart is allowed only for the monitor bridge session/window, not for active task panes.
- `preferred_operator` is allowed for this migration sprint, but final report must call it out as a bootstrap exception and specify the normal DAG shape.

## Done Definition

Each node must write its handoff with:

- Files changed.
- Commands run.
- Acceptance result.
- Remaining blocker if any.
- Next safe action.
