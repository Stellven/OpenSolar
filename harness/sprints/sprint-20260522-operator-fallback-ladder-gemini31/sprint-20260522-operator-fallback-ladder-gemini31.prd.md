# PRD: Operator Fallback Ladder + Gemini 3.1 Pro Registration

Sprint: `sprint-20260522-operator-fallback-ladder-gemini31`
Owner host: `lisihao@100.122.223.55`
Priority: P0

## Background

Mac mini now has the first Model Fleet Operator Runtime foundation, but the current operator catalog is still incomplete versus the target architecture. The registry currently exposes a small set of working operators, while the intended model fleet includes Claude Opus, Claude Sonnet, GLM-5.1, ThunderOMLX/Qwen, Google Antigravity Gemini 3.5 Flash, Google Antigravity Gemini 3.1 Pro, local scan operators, browser/computer-use operators, router/audit operators, and multimodal/image-capable operators.

Anthropic quota has already produced an org monthly limit failure in a live sprint. Therefore the scheduler must treat quota as a first-class routing signal and fallback to available operators instead of retrying an exhausted provider.

## Goals

1. Reconcile the operator catalog with the full target model-fleet architecture.
2. Add or formalize Gemini 3.1 Pro Antigravity operators as higher-reasoning Google fallback operators.
3. Add quota-aware fallback ladders so DAG nodes do not need hardcoded model names.
4. Ensure `solar_monitor_bridge --all` publishes an operator fleet view with class counts, model/provider counts, readiness, quota blockers, and fallback ladder health.
5. Preserve writer/verifier separation and avoid using the same operator for generation and final review.

## Required Operator Class Coverage

The sprint must explicitly cover all ten physical operator classes from the target architecture. "Covered" means the class appears in the catalog or a companion policy file with recommended operator ids, primary/backup models, intended task types, avoid-task boundaries, permission policy, quota posture, and current implementation state. Missing or unavailable operators must be represented as `enabled=false` / `available=false` with `health_status=missing|pending|disabled`; they must not be silently omitted.

```text
┌──────┬──────────────────────────┬────────────────────────────────────────────┬──────────────────────────────┐
│ 编号 │ Operator Class           │ Required Operator IDs                       │ 当前要求                     │
├──────┼──────────────────────────┼────────────────────────────────────────────┼──────────────────────────────┤
│ 4.1  │ DeepArchitect            │ op.claude.opus47.architect.xhigh.01         │ 架构/系统方案/关键 refactor  │
│      │                          │ op.claude.opus47.architect.max.01           │ 禁用于批量小改/跑测试        │
│ 4.2  │ RootCauseDebug           │ op.claude.opus47.debug.xhigh.01             │ 根因推理                     │
│      │                          │ op.codex.gpt55.repro.exec.01                │ Codex 负责复现/测试/patch    │
│ 4.3  │ Implementation           │ op.codex.gpt55.impl.main.01                 │ 真实多文件实现               │
│      │                          │ op.codex.gpt55.impl.worktree.02             │ 不负责架构拍板               │
│      │                          │ op.codex.gpt55.testfix.01                   │                              │
│ 4.4  │ FastSubagent             │ op.codex.gpt54mini.fastedit.01              │ 短周期小任务/fan-out         │
│      │                          │ op.codex.spark.quickloop.01                 │ 禁用于关键合入               │
│      │                          │ op.antigravity.gemini35flash.subagent.01-03 │                              │
│ 4.5  │ ParallelExploration      │ op.antigravity.gemini35flash.parallel.01-03 │ 多路线试错                   │
│      │                          │ op.antigravity.managed.sandbox.01           │ 不做最终合并判断             │
│ 4.6  │ Verifier                 │ op.claude.opus47.review.xhigh.01            │ 独立审查                     │
│      │                          │ op.codex.gpt55.validation.01                │ writer 不能 verifier         │
│      │                          │ op.local.static.checker.01                  │                              │
│ 4.7  │ ResearchSynthesis        │ op.codex.gpt55.research.compile.01          │ 研究/报告/文档综合           │
│      │                          │ op.claude.opus47.research.critique.01       │ Claude 复核/批判             │
│      │                          │ op.antigravity.gemini35flash.webscan.01     │                              │
│ 4.8  │ BrowserComputerUse       │ op.codex.desktop.browser.01                 │ GUI/browser/截图/点击        │
│      │                          │ op.codex.gpt55.computeruse.01               │ 外部登录/支付/密钥动作受限   │
│      │                          │ op.antigravity.managed.browser.01           │                              │
│ 4.9  │ GoogleStack              │ op.antigravity.gemini35flash.android.01     │ Android/Firebase/GCP/AIStudio│
│      │                          │ op.antigravity.gemini35flash.firebase.01    │ Google 生态优先              │
│      │                          │ op.antigravity.managed.googlecloud.01       │                              │
│ 4.10 │ LocalPrivacy             │ op.local.mlx.qwen8b.static.01               │ 本地扫描/脱敏/低成本预处理   │
│      │                          │ op.local.llamacpp.fastscan.01               │ 不做复杂最终判断             │
│      │                          │ op.local.embedding.retrieve.01              │                              │
└──────┴──────────────────────────┴────────────────────────────────────────────┴──────────────────────────────┘
```

The catalog may use current Mac mini aliases such as `mini-*` during migration, but the final report must map each alias back to the canonical `op.<surface>.<provider>.<model>.<role>.<config>.<index>` naming scheme.

## Non-Goals

- Do not print or persist raw API keys, OAuth tokens, cookies, or refresh tokens.
- Do not install global packages.
- Do not disable working ThunderOMLX cache configuration.
- Do not re-enable unsafe ThunderOMLX cache features.
- Do not make Claude the only execution path while Anthropic quota may be exhausted.

## Current Gap

```text
┌──────────────────────────────────────┬────────┬──────────────────────────────────────────────┐
│ 项目                                 │ 状态   │ 差距                                         │
├──────────────────────────────────────┼────────┼──────────────────────────────────────────────┤
│ Claude Opus planner/reviewer         │ ok/warn│ 已注册，但 quota failure 必须降权             │
│ Claude Sonnet builder                │ ok     │ 已注册，可做中等复杂 fallback                 │
│ ThunderOMLX Qwen knowledge           │ ok     │ 已注册，适合知识抽取和低成本后台任务          │
│ Antigravity Gemini 3.5 Flash image   │ ok     │ 已注册且 smoke 通过，适合多模态/快速实现      │
│ Antigravity Gemini 3.5 Flash text    │ warn   │ 注册但 disabled，需要明确原因和可替代路径      │
│ Antigravity Gemini 3.1 Pro           │ pending│ 设计需要，但 registry 尚未形成可调度算子       │
│ GLM-5.1                              │ pending│ 用户设计中存在，需纳入 catalog 或标记缺口       │
│ Local scan / Router / Audit operators│ pending│ 目标架构中存在，需纳入 catalog 或标记缺口       │
│ Bridge operator_fleet                │ warn   │ 代码有变更，但运行态 latest 未显示新字段       │
└──────────────────────────────────────┴────────┴──────────────────────────────────────────────┘
```

## Target Fallback Policy

```text
┌──────────────────────┬────────────────────────────────────────────────────────────────────┐
│ Task Type            │ Fallback Ladder                                                    │
├──────────────────────┼────────────────────────────────────────────────────────────────────┤
│ ARCH_DESIGN          │ Claude Opus -> Gemini 3.1 Pro -> Claude Sonnet -> Gemini 3.5 Flash │
│ ROOT_CAUSE_DEBUG     │ Claude Opus -> Gemini 3.1 Pro -> Claude Sonnet -> Gemini 3.5 Flash │
│ CODE_IMPL            │ Gemini 3.5 Flash -> Claude Sonnet -> GLM-5.1 -> ThunderOMLX/local  │
│ TEST_GEN/TEST_RUN    │ Gemini 3.5 Flash -> Claude Sonnet -> local shell/checker           │
│ RESEARCH_SYNTHESIS   │ Gemini 3.1 Pro -> Claude Sonnet -> Gemini 3.5 Flash -> local draft │
│ KNOWLEDGE_EXTRACTION │ ThunderOMLX/Qwen -> GLM-5.1 -> Gemini 3.5 Flash                    │
│ MULTIMODAL_UI_CHECK  │ Gemini 3.5 Flash image -> Gemini 3.1 Pro multimodal if available   │
│ FINAL_REVIEW         │ Claude Opus -> Gemini 3.1 Pro -> Claude Sonnet, never same writer  │
└──────────────────────┴────────────────────────────────────────────────────────────────────┘
```

## DAG Authoring Policy

DAG nodes must describe logical operator requirements, not concrete model names. A node should not set `model: claude-opus-4-7` or equivalent model-specific routing as its primary scheduling interface. The scheduler must select a physical operator from the registry using task type, capability requirements, constraints, policy, quota, runtime availability, and verifier separation.

Required node shape:

```yaml
node_id: design-runtime-scheduler
task_type: ARCH_DESIGN
required_capabilities:
  planning: ">=5"
  coding: ">=3"
  long_context: ">=4"
constraints:
  max_cost_tier: high
  write_files: false
  privacy: repo_private
  deadline: relaxed
preferred_operator_classes:
  - DeepArchitect
  - RootCauseDebug
verifier_required: true
```

Allowed override:

- `preferred_operator` remains a hard override only for bootstrap, smoke, migration, or emergency operations.
- Any node using `preferred_operator` must record why logical routing was bypassed.
- Future normal DAGs must prefer `task_type`, `required_capabilities`, `constraints`, and `preferred_operator_classes`.

## Task Type Routing Policy

```text
┌──────────────────────┬──────────────────────────────┬────────────────────────────┬──────────────────────────────┐
│ Task Type            │ 首选算子                     │ 备选算子                   │ 策略                         │
├──────────────────────┼──────────────────────────────┼────────────────────────────┼──────────────────────────────┤
│ ARCH_DESIGN          │ Claude Opus architect         │ Gemini 3.1 Pro / Codex     │ 强模型做判断，文档模型整理    │
│ ROOT_CAUSE_DEBUG     │ Claude debug                  │ Gemini 3.1 Pro / Codex     │ Claude 推因果，执行算子复现   │
│ CODE_IMPL            │ Codex/Gemini impl             │ Sonnet / GLM / local       │ 执行型模型落地，强模型审查    │
│ MULTI_FILE_REFACTOR  │ Architect -> Implementation   │ Review operator            │ 先设计再执行再审查            │
│ TEST_GEN             │ Codex/Gemini test             │ Codex mini / local         │ 低风险可用快模型              │
│ TEST_RUN             │ local shell / Codex test      │ local checker              │ 跑命令优先不用强模型          │
│ RESEARCH_SYNTHESIS   │ Codex/Gemini research         │ Claude critique            │ 汇总与批判分离                │
│ ACADEMIC_CRITIQUE    │ Claude Opus / Gemini 3.1 Pro  │ Codex research             │ 深推理优先                    │
│ PARALLEL_EXPLORATION │ Antigravity Gemini 3.5 Flash  │ Codex mini                 │ fan-out 多路线                │
│ ANDROID_FIREBASE     │ Antigravity GoogleStack       │ Codex                      │ Google 栈优先                 │
│ UI_PROTOTYPE         │ Antigravity / browser operator│ Codex impl                 │ 多方案快速生成                │
│ DOC_REPORT           │ Codex/Gemini research         │ Claude review              │ 出稿和去水分分离              │
│ SOFT_HW_OPT          │ Claude architect/debug         │ Codex bench/test           │ 判断瓶颈与跑实验分离          │
│ SECURITY_SENSITIVE   │ Claude review + local scan    │ manual gate                │ 高权限必须人工确认            │
│ LOW_COST_SCAN        │ local operator                │ Codex mini / GLM           │ 先本地，必要时升级            │
└──────────────────────┴──────────────────────────────┴────────────────────────────┴──────────────────────────────┘
```

Core rule: strong models are for judgment, implementation models are for landing changes, fast models are for parallel fan-out, and local models are for preprocessing and quota savings.

## Scheduler Scoring Model

The selector must not rank operators only by model strength. It should use a rule-based score in this first version:

```text
score(operator, task) =
  capability_fit
  + quality_score
  + quota_score
  + latency_score
  + cost_score
  + availability_score
  + context_affinity
  + risk_match
  - recent_error_penalty
  - same_model_verifier_penalty
```

Required first-version behavior:

- Skip operators with disabled/degraded availability unless no safe candidate exists and the node explicitly permits manual review.
- Skip operators in `leased`, `running`, `quota_exhausted`, `auth_expired`, or `disabled` runtime states.
- Skip operators whose quota reserve would be violated by a low-value task.
- Enforce writer/verifier separation.
- Prefer task-type routing policy before falling back to generic scoring.
- Record `operator_fallback_reason` when a preferred or higher-ranked operator is skipped.

## Quota As First-Class Scheduling Input

Each physical operator must have a quota clock. The system must not discover quota only after a task fails; quota posture is part of dispatch eligibility and fallback scoring.

Required quota shape:

```yaml
quota:
  provider: anthropic
  account_label: anthropic-main
  plan_type: max_or_api
  period: monthly
  refresh_at: "2026-06-01T00:00:00-06:00"
  remaining_estimate: 0.63
  soft_stop_threshold: 0.20
  hard_stop_threshold: 0.05
  reserve_for:
    - ROOT_CAUSE_DEBUG
    - ARCH_DESIGN
  on_exhausted: disable_and_fallback
```

Required quota behavior:

- If Claude Opus remaining quota is below the soft stop threshold, low-value work such as `LOW_VALUE_BULK_EDIT` and `DOC_POLISH` must not select it.
- When Claude Opus is near exhaustion, reserve it for `ARCH_DESIGN`, `ROOT_CAUSE_DEBUG`, and `FINAL_REVIEW`.
- If Codex GPT-5.5 quota is low, implementation should degrade to GPT-5.4-mini, Gemini/Antigravity parallel operators, or another configured implementation fallback; final validation should preserve a strong verifier when possible.
- If Antigravity quota is low, fan-out parallelism should be reduced, for example from 4 to 1.
- Subscription CLI quota must support observed quota because many tools do not expose a reliable quota API.

Observed quota signals:

```text
┌──────────────────────┬────────────────────────────────────────────┐
│ 信号                 │ 用途                                       │
├──────────────────────┼────────────────────────────────────────────┤
│ CLI stderr/stdout    │ limit/quota/rate-limit/auth-expired 解析   │
│ HTTP/API errors      │ 429/quota/rate-limit/billing failure       │
│ response latency     │ 异常变慢作为弱降权信号                    │
│ task failure type    │ quota/auth/tool failure 分类               │
│ manual refresh_at    │ 订阅周期或人工配置刷新时间                 │
└──────────────────────┴────────────────────────────────────────────┘
```

The monitor bridge and final report must expose quota posture, blocked reason, and fallback decision evidence without printing secrets.

## Operator Lifecycle State Machine

Every physical operator must have an explicit lifecycle state. Registry existence is not enough to make an operator dispatchable.

```text
CREATED -> WARMING -> IDLE -> LEASED -> RUNNING -> DRAINING -> IDLE
```

Exceptional states:

```text
ERROR
QUOTA_EXHAUSTED
AUTH_EXPIRED
COOLDOWN
DISABLED
STALE_CONTEXT
NEEDS_HUMAN_REVIEW
```

Required dispatch behavior:

```text
┌────────────────────┬──────────────────────────────┬──────────────────────────────┐
│ State              │ Meaning                      │ Scheduler action             │
├────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ CREATED            │ Registry only, pane not live  │ not dispatchable             │
│ WARMING            │ CLI/login/repo loading        │ temporarily not dispatchable │
│ IDLE               │ ready                         │ dispatchable                 │
│ LEASED             │ reserved for a DAG node       │ not dispatchable             │
│ RUNNING            │ executing                     │ not dispatchable             │
│ DRAINING           │ collecting artifacts          │ not dispatchable             │
│ COOLDOWN           │ just failed or completed load │ lower priority / delay       │
│ QUOTA_EXHAUSTED    │ quota exhausted               │ disable until refresh        │
│ AUTH_EXPIRED       │ auth/key invalid              │ human action required        │
│ STALE_CONTEXT      │ polluted or too long context  │ compact/restart/new session  │
│ DISABLED           │ manually disabled             │ never dispatch               │
│ NEEDS_HUMAN_REVIEW │ unsafe or ambiguous state     │ manual gate                  │
│ ERROR              │ runtime failure               │ degrade/fallback             │
└────────────────────┴──────────────────────────────┴──────────────────────────────┘
```

The runtime may use lowercase JSON values such as `created`, `warming`, `idle`, `leased`, `running`, `draining`, `cooldown`, `quota_exhausted`, `auth_expired`, `disabled`, `stale_context`, `needs_human_review`, and `error`, but the semantics must match this table.

## Naming, Tmux Startup, and Operatord Contract

This sprint must distinguish between the current migration state and the target operator runtime architecture.

### Naming Convention

Canonical physical operator ids must follow:

```text
op.<surface>.<provider>.<model>.<role>.<config>.<index>
```

Examples:

```text
op.tmux.anthropic.opus47.architect.xhigh.01
op.tmux.anthropic.opus47.debug.xhigh.01
op.tmux.openai.gpt55.impl.default.01
op.tmux.openai.gpt54mini.fast.lowcost.01
op.tmux.google.gemini35flash.parallel.fast.01
op.managed.google.antigravity.sandbox.default.01
op.local.mlx.qwen8b.scan.q4.01
```

Pane titles should follow:

```text
[CLAUDE][OPUS47][ARCH][XHIGH][01]
[CODEX][GPT55][IMPL][01]
[AG][G35FLASH][PAR][03]
[LOCAL][MLX][SCAN][01]
```

Current `mini-*` aliases may remain during migration, but the catalog/report must map them to canonical ids and identify any missing pane-title enforcement.

### Tmux Startup Contract

The target runtime should start a dedicated operator session such as `solar-aiops`, with windows/panes running `operatord run <operator_id>`. DAG nodes must not directly call `tmux send-keys`; they should submit structured tasks to the runtime.

Target startup pattern:

```text
tmux new-session -d -s solar-aiops -n router
operatord run op.router.meta.01
operatord run op.tmux.anthropic.opus47.architect.xhigh.01
operatord run op.tmux.openai.gpt55.impl.default.01
operatord run op.tmux.google.gemini35flash.parallel.fast.01
```

Required policy:

- DAG calls `operator_runtime.submit(task)`.
- Runtime decides how to write task envelopes to panes.
- Runtime captures stdout/stderr and handoff artifacts.
- Runtime detects completion, failure, quota/auth errors, stale context, and missing output.

### Operatord Contract

Each pane should run the same daemon shell:

```text
operatord run <operator_id>
```

`operatord` responsibilities:

1. Read the registry.
2. Resolve `secret_ref` without logging raw secrets.
3. Inject short-lived environment variables.
4. Launch the underlying CLI/SDK/local runtime.
5. Emit heartbeats.
6. Receive task envelopes.
7. Write execution logs.
8. Capture stdout/stderr.
9. Parse quota/auth/runtime errors.
10. Report structured task results.

Current state: this sprint has foundational `operator_runtime.py` and selector/bridge integration, but a full `operatord run` daemon and `operator_runtime.submit(task)` API remain a follow-up implementation item.

## Acceptance Criteria

- `physical-operators.json` or companion catalog contains the full intended operator inventory with each missing operator marked `enabled=false`, `availability=disabled`, or `health_status=missing` instead of silently omitted.
- Gemini 3.1 Pro Antigravity operator entries exist with provider/model/auth/quota/capability/routing fields and secret references only.
- Fallback selection skips disabled, unhealthy, quota-exhausted, auth-expired, leased, or same-writer verifier operators.
- Normal DAG authoring is documented and tested as logical operator requirements instead of model-name routing.
- Task type to operator-class routing policy is represented in code, config, or an auditable policy table.
- Selector exposes or tests scoring factors for capability fit, quota, availability, latency/cost, context affinity, recent error penalty, and verifier conflict penalty.
- All 4.1-4.10 operator classes are covered in an auditable matrix with implemented/pending/missing state and canonical ids.
- Browser/computer-use operators include strict permission policy for external login, payment actions, secret form filling, and destructive actions.
- RootCauseDebug policy separates Claude hypothesis/review from Codex reproduction/test/patch execution.
- Verifier policy enforces writer/verifier separation and records cross-provider preference for critical work.
- Quota clock coverage includes provider/account/plan/period/refresh/remaining/threshold/reserve/on_exhausted or explicit pending/missing state for every non-local operator.
- Observed quota signals are documented and at least quota/rate-limit stderr parsing is tested or reported.
- Lifecycle state machine coverage includes created/warming/idle/leased/running/draining/cooldown/quota_exhausted/auth_expired/stale_context/disabled/needs_human_review/error semantics.
- Naming convention coverage includes canonical `op.<surface>.<provider>.<model>.<role>.<config>.<index>` ids and pane title templates.
- Tmux startup coverage explicitly states that DAG must not directly use `tmux send-keys`; normal dispatch must go through runtime submission.
- Operatord coverage documents `operatord run <operator_id>` responsibilities and marks current implementation gaps.
- A targeted test proves quota-exhausted Claude Opus falls back to Gemini 3.1 Pro or next available operator.
- A targeted test proves Gemini 3.1 Pro unavailable falls back to Gemini 3.5 Flash or Sonnet according to task type.
- `solar_monitor_bridge --all` writes `operator_fleet`, `operator_class_counts`, `provider_counts`, `model_counts`, `fallback_ladder_health`, and `blocked_by_reason`.
- Running global bridge once on Mac mini produces `/Users/lisihao/.solar/harness/run/monitor-bridge/global.latest.json` with the new fields.
- Final report exists at `/Users/lisihao/.solar/harness/monitor-reports/operator-fallback-ladder-gemini31.md`.

## Evidence Required

- Modified files list.
- Test command output.
- Registry diff summary.
- Bridge latest JSON field proof.
- Smoke result for Gemini 3.1 Pro if available; otherwise explicit `pending` with blocker and fallback proof.
