# Design — capability/risk/cost runtime constraints S01

Knowledge Context: solar-harness context inject used

## 1. Scope

This requirements slice defines the runtime contract for upgrading `capability_profile`, `risk_profile`, and `cost_profile` from registry metadata into hard scheduling constraints.

This slice does not implement runtime code. It produces the requirement boundary, traceability, acceptance gates, and downstream contract for S02 architecture, S03 runtime, S04 observability, and S05 verification.

## 2. Source Inputs

| Input | Status | Notes |
| --- | --- | --- |
| S01 PRD | ok | `sprints/sprint-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束-s01-requirements.prd.md` |
| S01 contract | ok | `sprints/sprint-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束-s01-requirements.contract.md` |
| Epic spec | ok | `sprints/epic-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束.epic.md` |
| Epic traceability | ok | `sprints/epic-20260530-p0-修复单-把-capability-risk-cost-三张画像从配置层升级为-runtime-强约束.traceability.json` |
| S01 product brief | warn | Requested path missing at planning time. |
| S01 requirement IR | warn | Requested sprint-local path missing; epic-level `*.requirement_ir.json` exists and remains upstream context. |
| S01 task graph | warn | Missing before this planner pass; this design introduces it. |

## 3. Target Requirement Model

### 3.1 Capability Profile

The capability profile is a positive capability declaration consumed by selection and scoring. Minimum capabilities:

- `architecture_reasoning`
- `code_impl`
- `root_cause_debug`
- `test_generation`
- `test_execution`
- `research_synthesis`
- `academic_critique`
- `browser_use`
- `gui_use`
- `long_context`
- `multi_agent_coordination`
- `speed`

Requirement rule: a logical operator may require one or more capabilities. An actor that lacks a required capability is not an eligible candidate unless a documented compatibility fallback explicitly marks the task as degraded and auditable.

### 3.2 Risk Profile

The risk profile is a hard-denial policy consumed before lease acquisition and before submit. Minimum taxonomy:

- `allowed_write_scope`: includes `patch_only`; existing values must remain compatible.
- `allowed_shell_scope`: includes `repo_local`.
- `allowed_network`: includes `docs_only`.
- `allowed_secrets`: includes strict `none`.
- `destructive_actions`: explicit boolean or deny-by-default equivalent.
- `git_commit`: explicit permission boundary.
- `git_push`: explicit permission boundary.
- `payment_or_external_action`: explicit permission boundary.
- `requires_human_for[]`: machine-readable high-risk action classes that require human approval.

Requirement rule: prompt instructions are not sufficient. Runtime policy, router selection, and lease acquisition must deny ineligible actor-task pairs before work is submitted.

### 3.3 Cost Profile

The cost profile is a quota and reservation policy consumed by scoring, routing, fallback, and audit. Minimum taxonomy:

- `cost_tier`: includes `premium`.
- `token_budget_class`: includes `expensive`.
- `quota_period`
- `reserve_ratio`
- `effort`: `low | medium | high | xhigh | max`
- `prefer_for[]`
- `avoid_for[]`

Requirement rule: premium/high-effort actors are reserved for high-value classes such as `ARCH_DESIGN`, `ROOT_CAUSE_DEBUG`, and `FINAL_REVIEW`; they must not be consumed by default for `BULK_DOC_EDIT`, `TRIVIAL_RENAME`, or `GREP_SCAN`.

## 4. Logical Operator Contract

Each logical operator must be able to request:

| Field | Purpose | Runtime effect |
| --- | --- | --- |
| `required_capabilities[]` | Capability minimums | Candidate inclusion gate and scoring input. |
| `risk_constraints` | Write/shell/network/secret/action limits | Hard denial before lease/submit. |
| `cost_hint` | Cost tier, budget class, quota policy | Reserve/avoid/prefer and score input. |
| `effort_hint` | Desired effort class | Prevent trivial tasks from using high-effort actors by default. |

The expected decision chain is:

```text
DAG node
  -> logical_operator
  -> required_capabilities + risk_constraints + cost_hint + effort_hint
  -> actor registry profiles
  -> capability inclusion gate
  -> risk hard gate
  -> cost reservation / avoidance gate
  -> OperatorScore with RiskFit + CostFit explanation
  -> lease acquisition gate
  -> submit
  -> machine-readable audit
```

## 5. Compatibility Strategy

- Existing actor fixtures must continue to validate after schema expansion.
- New taxonomy values are additive unless an existing value is unsafe by design.
- Existing physical bindings must not be hardcoded in DAG nodes; logical operator binding changes must be able to alter actor selection without editing the DAG node.
- Missing profile fields must not silently grant permission. The default for risk-sensitive fields is deny or explicit compatibility degradation with audit.
- Migration must preserve current registry paths and aliases unless S02 explicitly documents a safer replacement.

## 6. Outcomes and Acceptance

| Outcome | Acceptance | Risk boundary |
| --- | --- | --- |
| O1 target schema defined | All required capability/risk/cost fields are listed with compatibility expectations. | No runtime code in S01. |
| O2 logical operator contract defined | Required operator fields and decision chain are explicit. | Do not bind directly to physical actor/model IDs. |
| O3 hard gate semantics defined | Risk/cost/capability gates state pre-lease and pre-submit denial behavior. | Prompt-only enforcement is rejected. |
| O4 migration strategy defined | Existing fixtures and binding changes remain compatible. | Missing fields cannot imply elevated permission. |
| O5 downstream traceability defined | S02-S05 ownership and verification gates are mapped. | Parent epic cannot close from S01 alone. |

## 7. Downstream Impact

| Slice | Impact |
| --- | --- |
| S02 architecture | Must extend schemas and registry contracts to represent the taxonomy exactly. |
| S03 core runtime | Must route through actor profiles, compute real `RiskFit`/`CostFit`, and enforce lease/submit denial. |
| S04 orchestration/UI | Must expose profile summaries and rejection reasons: `risk_denied`, `quota_reserved`, `cost_avoid`, `effort_mismatch`. |
| S05 verification | Must prove premium reservation, low-value avoidance, hard risk blocks, binding-driven route changes, and machine-readable score explanations. |

## 8. Stop Rules

- Do not dispatch builder without a valid task graph.
- Do not mark passed without command evidence.
- Do not claim runtime enforcement complete in S01.
- Do not treat prompt text as a risk gate.
- Do not hardcode business paths, tokens, or actor choices.

