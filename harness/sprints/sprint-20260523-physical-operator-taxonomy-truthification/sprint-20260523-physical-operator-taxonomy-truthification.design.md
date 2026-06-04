# Design — Physical Operator Taxonomy Truthification

sprint_id: `sprint-20260523-physical-operator-taxonomy-truthification`
priority: `P0`
lane: `strategy`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-23T19:50:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
parent_sprint: `sprint-20260523-pane-as-physical-operator-architecture` (architecture truth, **不回滚不重写**)
parallel_protect: `sprint-20260523-lease-based-model-fleet-runtime` 不被 block / rewrite

## 0. 本切片的边界（强制 read-first）

- **Follow-up sprint**：父 sprint 已锁定 Registry/Runtime/Scheduler 三层 + writer/verifier 分离 + secret_ref/quota/policy/evidence；本 sprint 只补 **10 类 operator taxonomy 真值化** 缺口。
- **不允许**：回滚父 `design.md` / `task_graph.json`；taxonomy 退回旧 `planner/builder/evaluator/architect/external` 桶；provider/model 当 taxonomy 主轴；DAG 节点直写 model/provider；Browser/Google-stack/Local Privacy 合并到 generic external；writer/verifier separation 脱离 taxonomy；含糊 runtime state；raw secret 落盘；引入新进程模型 (systemd/Docker/k8s)；改 5-pane 拓扑；block 父 sprint 或 parallel lease-fleet sprint。
- **允许 Write/Edit**：
  - `sprints/<sid>.{design,plan,task_graph,planning_html}.md/json/html`（本轮）
  - `sprints/<sid>.workstream-{A..F}-*.md`（N1..N6 产出）
  - `sprints/<sid>.parent-repair-addendum.md`（N6 给父 sprint 的注入文档，不动父原文件）
- 父 sprint 父 sprint 的 `design.md` / `task_graph.json` **read-only** — 仅引用，不修改。
- 知识库降级 `mirage:nonzero`：本 sprint self-contained。

## 1. 10-class Operator Taxonomy（核心真值，per FR1/G1）

按 **执行角色 / 任务语义** 分类（D1），provider/model 仅作 implementation binding（D2）。

| # | Class Name | Primary task types | Preferred capabilities | Policy delta | Quota posture | Verifier constraints | Example operator ids |
|---|------------|--------------------|------------------------|--------------|---------------|----------------------|----------------------|
| 1 | `DeepArchitect` | ARCH_DESIGN / MULTI_FILE_REFACTOR / SOFT_HW_OPT 主设计 | planning≥5, long_context≥5, academic_critique≥4 | none extra (default architect policy) | premium reserve, avoid bulk | verifier ≠ writer; high_risk → cross-provider | `pane-aiops-0-planner-opus47`, `pane-aiops-3-architect-opus47` |
| 2 | `RootCauseDebugger` | ROOT_CAUSE_DEBUG / SOFT_HW_OPT 诊断 | root_cause_debug≥5, long_context≥4 | shell read allowed; no destructive | premium reserve | cross-provider verifier 建议 | `pane-aiops-3-architect-opus47` (sub-mode) |
| 3 | `ImplementationWorker` | CODE_IMPL / MULTI_FILE_REFACTOR 执行 / DOC_REPORT | code_impl≥4, test_generation≥3, speed≥3 | patch_only write; repo_local shell | standard | verifier ≠ writer operator_id | `pane-aiops-1-builder-glm51` / `codex-cli-impl-gpt55` |
| 4 | `FastSubagent` | PATCH / TEST_GEN mini / LOW_COST_SCAN | code_impl≥3, speed≥4 | patch_only; no destructive | cheap pool; avoid premium tasks | verifier 建议 standard tier 复核 | `codex-mini-fast-01` / `gemini-flash-fast-01` |
| 5 | `ParallelExplorer` | PARALLEL_EXPLORATION / UI_PROTOTYPE / FAST_FANOUT | speed≥4, multi_agent_coordination≥3 | no final-authority on critical paths | metered fan-out budget | verifier 必须独立 class（DeepArchitect / Critic） | `antigravity-gemini35flash-parallel-01` / `codex-subagents-fanout-01` |
| 6 | `Verifier` | FINAL_REVIEW / ACADEMIC_CRITIQUE | academic_critique≥4, test_execution≥3 | read-only on writer artifacts; **block self-verification** | standard, reserve for FINAL_REVIEW | hard: `verifier.operator_id ≠ writer.operator_id`; high_risk: `verifier.provider ≠ writer.provider` | `pane-aiops-2-evaluator-glm51` / `claude-opus-verifier-01` |
| 7 | `ResearchSynthesizer` | RESEARCH_SYNTHESIS / DOC_REPORT / academic literature collation | research_synthesis≥4, long_context≥5 | docs network allowed; no shell writes | standard | cross-provider verifier 建议 | `codex-research-gpt55` / `gemini-research-flash` |
| 8 | `BrowserOperator` | BROWSER_VALIDATION / UI_PROTOTYPE browser leg | browser_use≥3, gui_use≥2 | **special**: payment=denied, login=requires_human, secrets_form_fill=denied, network=full-but-redacted, file_write=denied | metered browser-session budget | verifier 强制 non-browser class（Verifier / DeepArchitect） | `gstack-browser-qa-01` / `playwright-headless-01` |
| 9 | `GoogleStackOperator` | GOOGLE_STACK / ANDROID_FIREBASE | google_stack≥3, code_impl≥3 | **special**: google scopes only; firebase auth via secret_ref; no cross-google-account writes | quota per google account | verifier 必须 cross-provider（避免 google echo） | `antigravity-google-stack-01` |
| 10 | `LocalPrivacyOperator` | LOCAL_PRIVACY_SCAN / SECURITY_SENSITIVE / local-only推理 | code_impl≥3, security_review≥3 | **special**: network=none, secrets_access=denied (env白名单), file_write=patch_only-in-scope, no cloud upload | local CPU/memory clock | verifier 必须非 cloud operator（避免数据外流） | `thunderomlx-local-privacy-01` / `local-shell-scanner-01` |

**子类 / routing tags（双层结构，per Q1 答案）**：`operator_class` = 一级 10 枚举；`routing_tags` = free-form set 用于 fine-grained 匹配（e.g., `{multimodal, gpu_required, long_context_v2}`）。父 sprint schema v2 草案的 `capability` 节加 `routing_tags: list[str]`。

**子类与一级 class 关系（per Q2 答案）**：`ResearchSynthesizer` 和 `DeepArchitect` 是**并列一级类**（任务语义不同：synthesizer 汇总 vs architect 设计），不退化为 capability overlay。

## 2. P0 / Reservation / Follow-up 分配（per D4 + G8 + A10）

无含糊 TBD：

| Class | 分配 | 理由 |
|-------|------|------|
| 1 DeepArchitect | **P0** 落 schema + routing | 父 sprint 已部分包含 |
| 2 RootCauseDebugger | **P0** | 与 DeepArchitect 同级，scheduler 必须能区分 |
| 3 ImplementationWorker | **P0** | 现有 builder 桶的真值化承接 |
| 4 FastSubagent | **P0 routing reservation** | schema 字段就位；具体 operator id 可后续 |
| 5 ParallelExplorer | **P0 routing reservation** | 路由规则在 scheduler 真值；Antigravity 实际接入 follow-up |
| 6 Verifier | **P0** | writer/verifier separation contract 必入 schema |
| 7 ResearchSynthesizer | **P0 routing reservation** | Codex Bridge follow-up |
| 8 BrowserOperator | **P0 schema + policy** | 高风险必入 policy；具体 operator id follow-up |
| 9 GoogleStackOperator | **P0 schema + policy** | 同上 |
| 10 LocalPrivacyOperator | **P0 schema + policy** | 同上；ThunderOMLX local 接入 follow-up |

合计：10 类全部 P0 落 schema/routing/policy；其中 4/5/7/8/9/10 的**具体 operator id 注册**留 follow-up sprint。

## 3. Schema Truthification（per FR2 + G1）

`operator_class` 在 schema v2 中：

```yaml
operator_class:
  $type: enum
  $values:
    - DeepArchitect
    - RootCauseDebugger
    - ImplementationWorker
    - FastSubagent
    - ParallelExplorer
    - Verifier
    - ResearchSynthesizer
    - BrowserOperator
    - GoogleStackOperator
    - LocalPrivacyOperator
  $required: true
  $version: capability_schema_version="v2"

routing_tags:
  $type: list[str]
  $optional: true
  $examples: [multimodal, gpu_required, long_context_v2, browser_session, google_workspace]

# 父 sprint capability_tags 字段不变；新增 operator_class 一级枚举
```

**旧角色桶 → 新 taxonomy 兼容映射表（per Q + A2）**：

| Legacy bucket | 新 operator_class | 备注 |
|---------------|-------------------|------|
| `planner` | `DeepArchitect`（pane 0） | pane 角色保留为 display；class 是调度真值 |
| `builder` | `ImplementationWorker`（pane 1） | 同 |
| `evaluator` | `Verifier`（pane 2） | 同 |
| `architect` | `DeepArchitect` + `RootCauseDebugger`（pane 3，可切换 sub-mode） | 父 sprint 5-pane 拓扑保留 |
| `pm` | `DeepArchitect`（产 PRD） + `Verifier`（review）双角色 | pane 4；按 task_type 切 |
| `external` | 不再使用 — **拆为 5 specific class**：`ParallelExplorer` / `ResearchSynthesizer` / `BrowserOperator` / `GoogleStackOperator` / `LocalPrivacyOperator`（per D5 严禁合并） | 旧 entry 必须显式重分类 |

## 4. Scheduler Mapping（per FR3 + G2）

**task_type → preferred_operator_classes → fallback ladder** （A3 钉死 10 个 task_type）：

| Task Type | 首选 class ladder | Fallback | 策略 |
|-----------|-------------------|----------|------|
| `ARCH_DESIGN` | DeepArchitect | ResearchSynthesizer | Claude 出主设计，Codex 整文档 |
| `ROOT_CAUSE_DEBUG` | RootCauseDebugger | ImplementationWorker (repro) | Claude 推因果，Codex 跑复现 |
| `CODE_IMPL` | ImplementationWorker | FastSubagent (only patch-size) | Codex 写，Claude 审 |
| `MULTI_FILE_REFACTOR` | DeepArchitect → ImplementationWorker | Verifier review | 先设计再执行 |
| `TEST_GEN` | ImplementationWorker | FastSubagent (low-risk) | 低风险可 mini |
| `TEST_RUN` | ImplementationWorker (local shell) | LocalPrivacyOperator | 跑命令优先不用强模型 |
| `BENCHMARK_RUN` | ImplementationWorker | LocalPrivacyOperator | 同上 |
| `FINAL_REVIEW` | Verifier | DeepArchitect (cross-provider) | hard contract: writer ≠ verifier |
| `RESEARCH_SYNTHESIS` | ResearchSynthesizer | DeepArchitect (critique) | Codex 汇总，Claude 质检 |
| `ACADEMIC_CRITIQUE` | DeepArchitect | Verifier | Claude 更深推理 |
| `PARALLEL_EXPLORATION` | ParallelExplorer | FastSubagent fan-out | Antigravity Gemini Flash 默认 |
| `FAST_FANOUT` | ParallelExplorer | FastSubagent | 多路线 |
| `BROWSER_VALIDATION` | BrowserOperator | (none — 必走 browser class) | high-risk policy |
| `UI_PROTOTYPE` | ParallelExplorer (UI fanout) → BrowserOperator (validation) | DeepArchitect | 多方案快速生成 |
| `GOOGLE_STACK` / `ANDROID_FIREBASE` | GoogleStackOperator | ImplementationWorker (mock) | Google 栈优先 Antigravity |
| `LOCAL_PRIVACY_SCAN` | LocalPrivacyOperator | (none — 必走 local) | 高敏感数据禁云 |
| `SECURITY_SENSITIVE` | Verifier + LocalPrivacyOperator | DeepArchitect (manual review) | 必须人工确认 |
| `LOW_COST_SCAN` | LocalPrivacyOperator → FastSubagent | ImplementationWorker | 先本地，必要升级 |
| `DOC_REPORT` | ResearchSynthesizer | Verifier (de-fluff) | Codex 出稿，Claude 去水 |
| `SOFT_HW_OPT` | DeepArchitect → RootCauseDebugger | ImplementationWorker (bench) | Claude 判瓶颈，Codex 跑实验 |

合计 **20 个 task_type**（超过 A3 ≥10 要求）；每个 task_type 都有 ≥1 首选 class + ≥0 fallback。

## 5. DAG 节点 schema（per D3.1 + G3 + A4）

DAG 节点必须用逻辑算子需求表达，**禁止直写 `model=` / `provider=`**：

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
  - RootCauseDebugger
verifier_required: true
# 以下字段全部 deprecated（仅 fallback / migration）：
# model: <deprecated>
# provider: <deprecated>
# preferred_operator_id: <仅显式硬指定>
```

**Q6 答案**：DAG schema 不直接禁止 `model/provider` 字面（保留 1 sprint 兼容），但 validator 在 dispatch-time 给出 `WARN: deprecated_model_binding` 并自动转换为 `preferred_operator_class` 路由；PR-time lint 推荐升级（per parent sprint Q12）。

## 6. Rule-Based Scoring 模型（per FR5 + G5 + A5）

**10 项 score / penalty**（deterministic，可手算，可单测）：

```text
OperatorScore =
    capability_fit          * 0.20   # task.required_capabilities 满足率
  + quality_score           * 0.15   # operator.capability_tags 综合得分
  + quota_score             * 0.10   # 1 - 已用/上限 ratio
  + latency_score           * 0.10   # 历史 p50 latency 反比
  + cost_score              * 0.10   # cost_tier 倒数
  + availability_score      * 0.10   # runtime_state ∈ {IDLE} = 1, else 0
  + context_affinity        * 0.10   # repo / branch / topic / recent-lease 匹配 (per Q7)
  + risk_match              * 0.10   # policy 与 task.constraints 完全允许 = 1
  - recent_error_penalty    * 0.10   # 末 N task 失败比例
  - same_model_verifier_penalty * 0.15  # verifier 角色 + 同 provider → 重罚（per Q8 = high_risk hard 门禁；非 high_risk soft 降权）
```

**Context_affinity 量化（per Q7 答案）**：多因素加权 = `0.4 * repo_match + 0.3 * branch_match + 0.2 * topic_tag_match + 0.1 * recent_lease_within_24h`，全部 0-1 范围。

**Same_model_verifier_penalty（per Q8 答案）**：
- `task.role == "verifier"` **且** `task.high_risk == true` 且 `verifier.provider == writer.provider` → **hard block**（penalty=∞，直接出局）
- 非 high_risk → soft penalty=0.5（仍可参选，但显著降权）

**Scoring 输出契约**：select_operator 必须返回 `{selected_operator_id, score, factors: dict[str, float], penalties: dict[str, float], rejected: list[{operator_id, reason}]}` — 可解释、可审计。

## 7. Lifecycle State Machine（per FR6 + G6 + D6 + A7）

**主路径 6 状态**：`CREATED → WARMING → IDLE → LEASED → RUNNING → DRAINING → IDLE`

**异常态 7 状态**：`ERROR`、`QUOTA_EXHAUSTED`、`AUTH_EXPIRED`、`COOLDOWN`、`DISABLED`、`STALE_CONTEXT`、`NEEDS_HUMAN_REVIEW`

共 13 状态，每个状态对应明确 dispatch 动作（PRD §FR6 表，逐项已在父 sprint workstream-B 部分含 7 canonical + 7 exception；本 sprint 补到 13 完整匹配 PRD）：

| 状态 | 调度动作 | 备注 |
|------|---------|------|
| CREATED | 不可调度 | registry 有，pane 未启 |
| WARMING | 不可调度 | CLI 加载 / 登录 / repo |
| IDLE | 可调度 | scheduler 主拣选目标 |
| LEASED | 不再分配 | 已被某 DAG node 预占 |
| RUNNING | 不再分配 | 执行中 |
| DRAINING | 不再分配 | 收集 artifact + heartbeat 保持 |
| COOLDOWN | **soft penalty 降权**（per A7 #1） | 失败 / 重任务后短暂降权；非 hard block |
| QUOTA_EXHAUSTED | 禁用到 refresh | 远端 quota event 触发 reset |
| AUTH_EXPIRED | 人工处理 | `last_verified_at` TTL 超时 |
| STALE_CONTEXT | **检测信号 = token 用量 > 80% context window 或同 topic 连跑 > 3 task**（per A7 #2） | 触发 compact / restart |
| DISABLED | 不调度 | 运维手动 |
| ERROR | 禁止继续派发 | 需 evaluator 介入 |
| NEEDS_HUMAN_REVIEW | **触发条件 = security gate FAIL 或 policy hard deny 后用户未 ack** （per A7 #3）| escalation artifact 写 `escalation/<sprint_id>/<node_id>.escalation.yaml` (per Q10) |

**DRAINING → IDLE artifact gate（per A7 #4）**：必须满足 `lease.result_path 存在 + result.yaml 字段完整（含 decision/score/asi）+ secret scrub passed`；任一缺失 → 转 ERROR。

## 8. Safety Policy 边界（per FR4 + G4 + D5 + A6）

**3 类 high-risk operator 单列 policy**（绝不合并到 generic external）：

### 8.1 BrowserOperator 专门 policy

```yaml
browser_operator_policy:
  allowed_actions: [navigate, read_dom, click_safe_links, screenshot, fill_non_secret_form]
  denied_actions:
    - payment
    - login (要求 requires_human)
    - secrets_form_fill
    - file_write
    - cross_origin_post_with_creds
    - download_executable
  network: full-with-domain-allowlist
  redact_envs: ["BROWSER_*", "PLAYWRIGHT_*"]
  session_budget: bounded (metered)
```

### 8.2 GoogleStackOperator 专门 policy

```yaml
google_stack_policy:
  allowed_actions: [read_in_scope, write_in_scope, oauth_inside_account]
  denied_actions:
    - cross_google_account_write
    - delete_workspace_assets
    - billing_change
    - admin_console_modify
  auth: secret_ref via macOS Keychain + scope 白名单
  quota: per_google_account_clock
```

### 8.3 LocalPrivacyOperator 专门 policy

```yaml
local_privacy_policy:
  allowed_actions: [local_read, local_compute, patch_only_in_scope]
  denied_actions:
    - network_any
    - cloud_upload
    - secrets_access (除 env 白名单)
    - external_telemetry
  isolation: local_process; data_residency = local_only
```

任何把上述 3 类合并到 `generic external / ImplementationWorker` 的设计 → **D5 violation, evaluator FAIL**。

## 9. Verifier Rules Alignment（per FR4 + A8）

写入 schema + scheduler 双源（不停留在 prose）：

- **hard contract**：`verifier.operator_id ≠ writer.operator_id`（schema 层 enforce + scheduler step 6）
- **high_risk task**：`verifier.provider ≠ writer.provider`（cross-provider；same_model_verifier_penalty=∞）
- **BrowserOperator 输出**：verifier 必须 non-browser class（Verifier / DeepArchitect）
- **GoogleStackOperator 输出**：verifier 必须 cross-provider（防 google echo）
- **LocalPrivacyOperator 输出**：verifier 必须 non-cloud operator（防数据外流）

## 10. Parent Sprint Repair / Adoption（per FR7 + G7 + A9 + Q11）

**父 sprint 不回滚**（per Hard Rules + Constraints + Non-Goals）。

**Repair 路径**：本 sprint 产 `<sid>.parent-repair-addendum.md` 作为正式 addendum，注入父 sprint 的 evaluator/architect review gate：

```yaml
parent_repair_strategy: addendum_injection
parent_sprint_id: sprint-20260523-pane-as-physical-operator-architecture
adoption_points:
  - parent_node: N1_registry_lock
    addendum_section: "operator_class 一级 10 枚举 + routing_tags + 兼容映射"
    review_gate: parent_evaluator_must_check
  - parent_node: N3_scheduler_lock
    addendum_section: "10 task_type ladder + 10 score/penalty 项 + scoring 输出契约"
    review_gate: parent_evaluator_must_check
  - parent_node: N5_migration_lock
    addendum_section: "10 类 P0/Reservation/Follow-up 分配 + 旧桶映射"
    review_gate: parent_evaluator_must_check
artifact_path: ~/.solar/harness/sprints/sprint-20260523-pane-as-physical-operator-architecture.taxonomy-addendum.md (N6 创建；目标路径在父 sprint 但属于 addendum 而非 mutation)
```

**Q11 答案**：选 addendum 注入（不需新建 repair node）— 父 sprint evaluator 在 review N1/N3/N5 时必须比对本 addendum。任何 review 路径 FAIL → 父 sprint round-2 重新 review（但 design/task_graph 不强制改）。

## 11. Follow-up Boundary（per FR7 + G8 + A10）

无 TBD：

| Item | 本 sprint | Reservation | Follow-up sprint |
|------|-----------|-------------|-----------------|
| 10 类 taxonomy matrix | ✅ design + N1 落 | — | — |
| operator_class 一级枚举 schema | ✅ N2 | — | — |
| 旧桶兼容映射 | ✅ N2 | — | — |
| task_type ladder（20 个）+ scoring 10 项 | ✅ N3 | — | — |
| Rule-based scheduler 实现 | — | ✅ schema/policy 真值就位 | provider-actor binding 真实接入（lease-fleet-runtime sprint） |
| 13 状态 lifecycle 定义 | ✅ N4 | — | — |
| Lifecycle 实施（state machine code） | — | ✅ 父 sprint N2_runtime_lock | 父 sprint Phase 1-2 |
| BrowserOperator / GoogleStack / LocalPrivacy policy | ✅ N5 | — | 具体 operator id 注册 follow-up |
| Parent sprint repair addendum | ✅ N6 | — | — |
| 实际接入 Antigravity / Codex Bridge 真 entry | — | ✅ binding 字段就位 | follow-up sprint |
| ThunderOMLX local privacy operator 真接入 | — | ✅ class 就位 | follow-up sprint |

## 12. 非目标（per Non-Goals + Constraints）

- 不回滚 / 重写父 sprint design.md / task_graph.json
- 不一次性实现 10 类 operator 真实 entry（schema/routing 就位即可）
- 不引入 ML scoring（第一版 deterministic）
- 不替换 5-pane 拓扑
- 不合并 Browser / GoogleStack / LocalPrivacy 到 generic external
- 不在 DAG 节点把 model/provider 字符串作长期真值
- 不引入新进程模型
- 不要求生成新 pane
- 不留 PM prose 层（必须进 schema / matrix / state machine）
- 不在本 sprint 上线 evaluator 之外的安全工具
- 不 block 父 sprint
- 不动 `~/.solar/STATE.md` / epic.* / 其他 sprint artifact / ThunderOMLX 任何代码
- 不 block / rewrite `sprint-20260523-lease-based-model-fleet-runtime`
- 不使用乐观词

## 13. Open Questions 全集回答（per Q1..Q11）

| Q | 答案归宿 |
|---|---------|
| Q1 operator_class 一级 vs 双层 | **双层**：一级 10 枚举 + routing_tags（free-form set）。design §1+§3 |
| Q2 Research Synthesis / DeepArchitect 关系 | **并列一级**（不退化为 overlay）。design §1 |
| Q3 Browser 一级 class vs overlay | **一级 class**（policy 独立）。design §1+§8 |
| Q4 GoogleStack provider family vs domain | **domain specialization**（Google 工作面）。design §1+§8 |
| Q5 LocalPrivacy 表达 | **一级 class + isolation policy + data_residency**。design §1+§8 |
| Q6 DAG schema 禁 model/provider | **保留 1 sprint 兼容**：validator WARN + dispatch-time 转 class 路由；PR-time lint。design §5 |
| Q7 context_affinity 量化 | **多因素加权**：repo 0.4 / branch 0.3 / topic 0.2 / recent-lease 0.1。design §6 |
| Q8 same_model_verifier_penalty | **混合**：high_risk hard block；非 high_risk soft 0.5。design §6 |
| Q9 STALE_CONTEXT 检测 | **token>80% context 或同 topic 连跑>3 task**。design §7 |
| Q10 NEEDS_HUMAN_REVIEW escalation artifact | **是**：`escalation/<sprint_id>/<node_id>.escalation.yaml`。design §7 |
| Q11 父 sprint 是否新 repair node | **不新建**：用 addendum 注入 + parent evaluator review gate。design §10 |

## 14. 接力 evaluator / architect 二审 / 父 sprint

evaluator 必须按 A1..A12 逐项核（plan §6 提供命令）。

architect (pane 3 opus) 可选二审：跨 sprint 一致性（本 sprint matrix vs 父 sprint schema v2 vs lease-fleet-runtime）。
