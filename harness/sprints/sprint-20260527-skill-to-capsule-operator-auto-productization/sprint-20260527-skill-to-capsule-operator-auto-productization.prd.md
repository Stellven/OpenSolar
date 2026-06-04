# 对 Solar Harness 正式下单一轮 skill-to-capsule/operator auto-productization full PRD。目标

## 1. Problem
对 Solar Harness 正式下单一轮 skill-to-capsule/operator auto-productization full PRD。目标是让已安装或新安装的 skill/plugin 能被系统自动发现、规范化、封装并有机接入 Solar Harness 的任务编排、调度、管理、执行机制，而不是停留在 inventory/readiness/记账层。必须覆盖：1）skill/plugin discovery 与 capability normalization；2）skill-to-capsule compiler，自动或半自动生成 capability capsule draft、artifact contract、physical operator binding、actor derivation；3）当调度过程中命中某个 capability capsule 时

## 2. Users / Stakeholders
- PM
- Planner
- Builder
- Evaluator

## 3. Goals / Non-goals
Goals:
- 对 Solar Harness 正式下单一轮 skill-to-capsule/operator auto-productization full PRD。目标是让已安装或新安装的 skill/plugin 能被系统自动发现、规范化、封装并有机接入 Solar Harness 的任务编排、调度、管理、执行机制，而不是停留在 inventory/readiness/记账层。必须覆盖：1）skill/plugin discovery 与 capability normalization；2）skill-to-capsule compiler，自动或半自动生成 capability capsule draft、artifact contract、physical operator binding、actor derivation；3）当调度过程中命中某个 capability capsule 时

Non-goals:
- 不在首批交付中做完整四区 PM pane 重构。
- 不绕过 planner 直接进入 builder。

## 4. User Scenarios
用户输入需求后，需要被结构化、合约化、任务图化，然后再派给执行链路。

## 5. Functional Requirements
- PRD、contract、TaskDAG 互相对齐。
- 实施、验证、兼容/发布路径均已显式表达。
- 每条验收标准都能追溯到验证或 gate。
- understand-anything 代表性 case 必须把 deterministic 扫描/解析链与 semantic LLM layer 拆开建模。
- understand-anything 的 semantic LLM layer 必须优先路由到 ThunderOMLX，不允许默认回落到高成本模型。

## 6. Non-functional Requirements
- 可验证
- 可追溯
- 与现有 PM -> Planner -> Builder 主链兼容
- 语义分析后端默认低成本，可审计实际 backend 路由。

## 7. UX / Interaction Model
首批仅提供编译结果视图与 handoff bar，不重做完整 UI。

## 8. Data Model
Requirement IR 为唯一事实源，PRD/contract/DAG/handoff 均从 IR 派生。

## 9. Acceptance Criteria
- PRD、contract、TaskDAG 互相对齐。
- 实施、验证、兼容/发布路径均已显式表达。
- 每条验收标准都能追溯到验证或 gate。
- understand-anything 的 semantic backend 在设计、runtime 与 handoff 中均显式固定为 ThunderOMLX。

## 10. Risks / Open Questions
- [medium] PRD / contract / DAG 多份产物漂移 -> 用 Requirement IR 做唯一事实源，所有视图从 IR 编译。
- [medium] 原始需求直接派给 Builder 导致执行发散 -> 强制走 product-brief / planner handoff，不允许 raw request 直派 builder。
- [medium] 验收标准没有映射到验证步骤 -> 编译期做 acceptance coverage 检查，缺失时阻断派单。
- [medium] understand-anything 语义阶段误用高价模型导致成本放大 -> 把 `semantic_backend=ThunderOMLX` 写成 contract 硬约束并在 handoff 留证据。

Open Questions:
- 当前请求缺少显式 success metric，需在 PRD 中补齐。

## 11. Release Plan
先交付后端编译底座，再逐步扩展 PM pane UI 与 eval loop。

---

## 背景 / Context

- Solar Harness 目前的 skill / plugin 体系停留在 **inventory / readiness / 记账**层：`skills/registry.yaml`（stable/candidate/canary 状态）+ `plugins/*/manifest.yaml`（手工登记 capabilities/commands/write_scope）+ `config/capability-capsules.registry.yaml`（6 capability 手工 + guard + resource）+ `lib/capability_capsules.py`（`DEFAULT_CAPSULE_BY_LOGICAL_OPERATOR` 硬编码）+ `config/physical-operators.json`（pane profile，无 skill 绑定）。
- 已安装 / 新安装的 skill 没法**自动**变成可调度的 capability capsule：plugin.manifest 列了 capabilities[] 但没编译路径到 capsule_id；capsule 命中后如何在 TUI pane 内跑 / 观测 / 判定成功失败 / cooldown / 幂等 — 没有规约；skill_id ↔ logical_operator ↔ physical_operator 映射没显式化。
- `understand-anything` 是已安装的代表性 plugin，目前没自动产品化路径 — 它的 deterministic 扫描/解析链 与 semantic LLM layer 必须分开建模，且 semantic layer 必须默认走 **ThunderOMLX**（不允许默认回落到 Claude/Codex 高成本模型）。
- S1 (DeepArchitect, logical_operator) **已完成**：S1-design.md (125 行) + S1-plan.md (100 行) + S1-handoff.md。**核心决策**：方向 B（可插拔模块 + 最小侵入），拒绝方向 A（侵入式重写）。
- 4 个新模块 + 2 个最小修改文件 + understand-anything 作为首个落地 case（auto-generated capsule，非手工）已在 S1-design 锁定。
- 本切片是 PM 修复入口（gate_prd_schema 触发回溯，PRD 缺 4 schema 必需 section）。

## 用户故事 / User Stories

- **US-01 (Skill 维护者)**：作为 skill / plugin 维护者，我希望 manifest.yaml 写完后 `solar-harness skill-to-capsule compile <plugin_id>` 一行命令就能产 capability capsule draft + artifact contract + physical operator binding，不要再手工往 `capability-capsules.registry.yaml` 里编辑。
  - 验收：S1-design §3 第 1 模块 `skill_to_capsule_compiler.py` + S2 Phase 1 实施。
- **US-02 (Planner / DAG 编排)**：作为 DAG 编排，我希望节点引用 `logical_operator` 时，scheduler 能从 skill_operator_registry 自动找出可用 physical operator + capsule 绑定，不要再手改 `DEFAULT_CAPSULE_BY_LOGICAL_OPERATOR` 硬编码。
  - 验收：S1-design §3 第 4 模块 `skill_operator_registry.py` + §4 `capability_capsules.py` 的 +20L hook。
- **US-03 (Capsule 执行者 / TUI pane)**：作为 TUI pane 执行 capsule，我希望有统一执行约定（输入完整性校验 → 前置条件 → 幂等/去重 → cooldown → 执行 → proof obligations → 成功/失败/blocked 判定），不要每次自己写。
  - 验收：S1-design §3 第 2 模块 `capsule_execution_gate.py` + 第 3 模块 `pane_runtime_contract.py`。
- **US-04 (Cost 控制 / understand-anything 维护者)**：作为 cost 控制者，understand-anything 的 semantic LLM layer 默认必须路由到 **ThunderOMLX**，不允许默认回落到 Claude/Codex；runtime 路由要可审计。
  - 验收：PRD §5 FR `semantic_backend=ThunderOMLX` 写成 contract 硬约束 + §9 Acceptance "understand-anything 的 semantic backend 在设计 / runtime / handoff 中均显式固定为 ThunderOMLX" + §6 NFR "语义分析后端默认低成本，可审计实际 backend 路由"。
- **US-05 (Solar-harness CLI 用户)**：作为运维，我希望 `solar-harness skill-to-capsule` 子命令完整（list / compile / verify / publish），不要靠手工拼接。
  - 验收：S1-design §4 `solar_skills.py` +30L 子命令实施。
- **US-06 (Evaluator)**：作为 Evaluator，我希望 capsule 编译产物可被程序化验收（draft / contract / binding / actor derivation 四件套齐全才能 publish）。
  - 验收：PRD §9 Acceptance + S1-plan §S4/S5 gate 检查项。
- **US-07 (PM / Coordinator)**：作为 coordinator，本 PRD 通过 gate_prd_schema 不再循环。
  - 验收：本切片即修复，`validate.sh prd` → PASS。

## 约束 / Constraints

- **环境**：macOS arm64 (lisihaodeMac-mini.local) / bash 5.3.9 / Solar Harness 4-pane / ThunderOMLX 8002 / Qwen3.6-35b-a3b。
- **路径白名单**：
  - **新增 4 模块**（S2 Phase 1-2 实施）：
    - `lib/skill_to_capsule_compiler.py`
    - `lib/capsule_execution_gate.py`
    - `lib/pane_runtime_contract.py`
    - `lib/skill_operator_registry.py`
  - **最小修改 2 文件**（S2 Phase 3-4）：
    - `lib/capability_capsules.py` 仅 +20L hook（不重写硬编码 mapping）
    - `tools/solar_skills.py` 仅 +30L 子命令（不动现有 inventory/readiness 行为）
  - 报告 `~/.solar/harness/monitor-reports/`；handoff `~/.solar/harness/sprints/<sid>.N*-handoff.md`；禁 `/tmp`。
  - PM 切片 (本切片) 写 `<sid>.prd.md` + 重渲染 `<sid>.prd.html` + ACK。
- **方向 B 锁定 / 方向 A 禁用**（S1-design §2）：
  - **采纳方向 B**：可插拔模块 + 最小侵入；新增 4 模块、改 2 文件。
  - **拒绝方向 A**：侵入式重写（重做 `DEFAULT_CAPSULE_BY_LOGICAL_OPERATOR` / 重写 capability_capsules.py 主流程）。
- **understand-anything 硬约束**（PRD §5 FR + §6 NFR + §9 Acceptance + S1-design §5）：
  - Deterministic 扫描/解析链 与 semantic LLM layer **必须分开建模**。
  - semantic LLM layer **必须** 默认路由到 **ThunderOMLX**；不允许默认回落到 Claude/Codex 等高成本模型。
  - Runtime backend 路由必须可审计（handoff 留路由证据）。
  - `semantic_backend=ThunderOMLX` 写成 contract 硬约束。
- **Auto-generated vs hand-rolled**：understand-anything capsule 必须通过 `skill_to_capsule_compiler.py` **自动产生**，不允许手工编辑 capability-capsules.registry.yaml 加进去。
- **不重做 PM pane**：明示 non-goal（PRD §Non-goals 第 1 条）。
- **不绕过 planner 直派 builder**：明示 non-goal（PRD §Non-goals 第 2 条）。
- **Requirement IR 唯一事实源**（PRD §8）：所有视图从 IR 派生。
- **secrets**：plugin manifest / capsule draft / runtime 路由日志 不允许打 token / API key / OAuth code。
- **API 兼容**：`solar-harness context inject / session evaluate / intent-gateway` 调用方式不变；只新增 `skill-to-capsule` 子命令 + hook 而不重写主流程。
- **PM 角色边界**：不写代码、不动其他 19 份产物（S1-design / S1-plan / S1-handoff / S1-capsule-plan / S1-physical-plan / S1-dispatch / contract / Contracts.yaml / task_graph / handoff / requirement_ir / requirement_trace / product-brief / coverage_report / acceptance_verdict / 4 个 dispatch 元数据）；本 PRD 修复后保持 `status=drafting / phase=spec`。

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD（含 11 原始 numbered section + 本次补的 4 schema 必需 section）。
- 上游 S1 产物（**已交付，PM 不动**）：
  - `<sid>.S1-design.md` — 125 行 8 节（§1 问题陈述 + §2 方向 A kill + 方向 B 选择 + §3 4 模块规约 + §4 现有文件最小改动 + §5 understand-anything 落地 + §6 文件边界 + §7 关键约束 + §8 已知限制与风险）
  - `<sid>.S1-plan.md` — 100 行（S2 Phase 1-4 步骤 + S3 测试 + S4/S5 gate 检查项）
  - `<sid>.S1-handoff.md` — Summary + Changed Files + Verification Evidence
  - `<sid>.S1-capsule-plan.json` + `<sid>.S1-physical-plan.json`
  - `<sid>.S1-dispatch.md`（builder pane `solar-harness-lab:0.3` 收到 dispatch）
- 上下游产物：
  - `<sid>.contract.md` + `<sid>.Contracts.yaml`
  - `<sid>.task_graph.json`
  - `<sid>.requirement_ir.json` + `<sid>.requirement_trace.json`
  - `<sid>.product-brief.md`
  - `<sid>.coverage_report.json` + `<sid>.acceptance_verdict.json`
  - `<sid>.handoff.md`

### S1 已锁定的 4 新模块（Planner 必须在 S2 Phase 1-2 实施）

| 模块 | 职责 | Phase |
|------|------|-------|
| `skill_to_capsule_compiler.py` | 读 plugin.manifest.capabilities[] → 产 capsule draft + artifact contract + physical operator binding + actor derivation | S2 Phase 1 |
| `capsule_execution_gate.py` | 输入完整性 / 前置条件 / 幂等去重 / cooldown / proof obligations / 成功失败 blocked 判定 | S2 Phase 2 |
| `pane_runtime_contract.py` | TUI pane 内 capsule 执行约定 + 观测输出 schema | S2 Phase 2 |
| `skill_operator_registry.py` | skill_id ↔ logical_operator ↔ physical_operator 映射（替换硬编码 `DEFAULT_CAPSULE_BY_LOGICAL_OPERATOR`） | S2 Phase 1 |

### S1 已锁定的 2 最小修改文件（Planner 必须在 S2 Phase 3-4 实施）

| 文件 | 改动量 | 内容 |
|------|--------|------|
| `lib/capability_capsules.py` | +20L hook | 只加 hook 调 `skill_operator_registry`，不重写硬编码 mapping |
| `tools/solar_skills.py` | +30L 子命令 | `skill-to-capsule` 子命令（list / compile / verify / publish）；不动现有 inventory / readiness 行为 |

### understand-anything 首个落地 case（S2 验证标的）

- **Deterministic 层**：扫描 / 解析（独立建模为一类 capsule）。
- **Semantic LLM 层**：独立建模为另一类 capsule，**硬绑定 `semantic_backend=ThunderOMLX`**。
- **Auto-generated**：必须通过 `skill_to_capsule_compiler.py` 产，不允许手工往 `capability-capsules.registry.yaml` 里加。
- **可审计**：runtime 必须留 `actual_backend_used` 字段在 handoff 里，证明没回落到高成本模型。

### 给 Coordinator 的明确指令

- **本次 PM 仅补 PRD schema 4 节**：背景 / 用户故事 / 约束 / 架构交接。`validate.sh prd` → PASS。
- **PRD mtime 已刷新**：coordinator 下一 tick 重跑 gate 应通过；通过后让 sprint 按 task_graph S2-S5 路径进入下一节点（S1 已 completed，下游 `handoff_to=builder_main`）。
- **不动其他 19 份产物**：包括 S1-design / S1-plan / S1-handoff / S1-capsule-plan / S1-physical-plan / S1-dispatch / contract / Contracts.yaml / task_graph / handoff / 4 个 IR / brief / coverage / verdict / 4 个 dispatch 元数据。

### 未尽事项（留给 S2-S5 实施 / 后续 sprint）

- **S2 Phase 1-4 实施**：4 新模块 + 2 最小修改；understand-anything 落地。
- **S3 测试**：unit / integration / smoke（每个 capsule 至少 1 testset）。
- **S4/S5 gate**：编译产物四件套齐全（draft / contract / binding / actor derivation）+ Evaluator verdict。
- **后续 sprint**：完整 PM pane UI 重构（PRD §Non-goals 显式留）。
- **OQ-product-01**: PRD §10 留的 "当前请求缺少显式 success metric" — Planner 在 S2 plan 必须回写 quantitative success metric（例如：≥10 个已装 skill 在 1 周内全部 auto-compile 成功 / understand-anything 100% 路由到 ThunderOMLX / 0 次手工编辑 capability-capsules.registry.yaml）。

### Knowledge Context

Knowledge Context: dispatch-embedded unified-context used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中)。

### Harness Modules Used

Harness Modules Used: harness-knowledge (dispatch-embedded unified-context block)。
