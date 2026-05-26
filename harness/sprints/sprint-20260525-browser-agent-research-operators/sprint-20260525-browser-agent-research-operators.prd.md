# PRD — Browser Agent Research Operators

## Context
Solar-Harness 的 Model Fleet / Lease-based Operator Runtime 已有 tmux、Codex、Antigravity、Claude interactive/programmatic、local 等物理算子。新增需求是把浏览器自动化调用的高级网页研究能力纳入同一套物理算子体系，例如 ChatGPT 5.5 Pro / Deep Research、Gemini Deep Research、Gemini Web 高级研究能力。

## Problem
这些能力不是普通 API 模型：它们依赖浏览器 profile、网页登录态、长时间异步任务、人工 re-login、网页结果抽取和截图/下载证据。若直接让 DAG click/type 或直接把自然语言塞给浏览器，会绕开 operator runtime 的 lease、quota、policy、evidence 和 verifier 约束。

## Goals
- 把 Browser Agent 作为正式 ActorHost / PhysicalOperator 类型接入 operator runtime。
- DAG 只能请求 logical_operator（如 DeepResearchBrowser），不能写死 ChatGPT/Gemini 网页工具。
- 支持异步 submit/poll/collect、login health、reauth_required、WAITING_HUMAN、Evidence Ledger 和 bridge observability。
- 先实现 schema、registry、routing、mock/dry-run adapter 与安全测试，不真实消费网页高级研究额度。

## Non-goals
- 不绕过登录、验证码、产品限制或付费边界。
- 不保存或打印 cookie/token/session secret。
- 不让 DAG 直接 browser click/type 或直接向网页塞自然语言。
- 本 sprint 不要求真实调用 ChatGPT/Gemini Deep Research；真实调用后续由人工授权开启。

## Requirements
- R1: Registry/schema 支持 `browser_profile_host`、`browser_agent_session`、`webapp_research_operator`。
- R2: PhysicalOperator 字段覆盖 `browser_profile_ref`、`login_state`、`auth_state`、`reauth_required`、`billing_surface`、`quota_clock`、`supported_webapp_features`、`max_runtime_min`、`async_poll_interval`、`output_extractors`、browser policy。
- R3: Logical operators 新增 `DeepResearchBrowser`、`AdvancedAnalysisBrowser`、`CompetitiveResearchBrowser`、`LongHorizonResearchScout`、`StrategicInsightSynthesizer`。
- R4: Runtime 支持 async browser job state machine：submit -> poll -> collect，状态含 running / waiting_human / reauth_required / done / failed / timeout。
- R5: Session/Auth broker 只记录 profile_ref/account_label/login health，不输出 cookie/token；支持 reauth cadence 和 manual re-login handoff。
- R6: Evidence Ledger 记录 task、scheduler decision、browser_job、redacted screenshots refs、extracted_result.md、sources/citations、download refs、result packet。
- R7: Scheduler fallback ladder：API/managed/local 优先；确需网页高级能力才用 Browser Agent；ChatGPT/Gemini 互为 fallback；reauth_required 进入 WAITING_HUMAN。
- R8: Monitor bridge/status 展示 browser_operator_id、provider/webapp_feature、job_id、async_state、login_state、quota_state、heartbeat、next_poll_at、blocker、evidence paths。
- R9: capability token enforce domains/download/clipboard/payment/secrets/destructive limits。

## Acceptance
- A1: 所有新增 registry/schema/logical_operator 配置通过 schema 和路由测试。
- A2: async browser job mock/dry-run adapter 覆盖 submit/poll/collect、timeout、reauth_required、waiting_human、collect retry。
- A3: 安全测试证明不打印 cookie/token，不允许 payment_action/secrets_form_fill，不自动绕过 reauth。
- A4: bridge/status 测试能看到 browser job/login/quota/evidence 字段。
- A5: DAG 中无 `model: chatgpt` / `tool: gemini web` 硬编码，只有 logical_operator + constraints。
- A6: final handoff/report 包含未验证项、真实调用开关和后续生产接入边界。
