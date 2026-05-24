# PRD: Actor Host Runtime Completion Audit

Sprint: `sprint-20260524-actor-host-runtime-completion-audit`
Owner: `PM pane / Codex`
Priority: `P0`
Lane: `strategy`
Handoff To: `planner`
Created: `2026-05-24T02:02:34Z`
Parent Sprint: `sprint-20260523-pane-as-physical-operator-architecture`

## 背景 / Context

`solar-harness` 已完成一轮从 `PM -> Planner -> DAG -> headless pool` 到 `pane-as-physical-operator` 的主链收口，也已经补齐了：

- physical operator taxonomy
- compatibility cutover
- pane pool recycle / reuse
- 8765 主状态页 observability
- evaluation_plan 初版

但用户现在要求的不是“继续凭感觉补”，而是让 `solar-harness` **自己逐项检查** 下面 13 个升级点，到底哪些已经：

- 真正在当前实现里完成
- 只完成了 contract / PRD
- 只完成了部分 runtime
- 仍然缺失

并且要求：

- 不能只给口头判断
- 必须给代码 / 配置 / 运行时产物证据
- 必须明确哪些只是“设计目标”，哪些已经是“生产真值”

## Summary

对以下 13 个升级点做一次 **逐项 completion audit**：

1. 从 `pane = 算子` 升级到 `pane 承载 actor，actor 才是算子`
2. `tmux send-keys` 只做 bootstrap，不做主任务协议
3. 以 `lease` 为核心，而不是只看 idle/running
4. 引入 `capability / risk / cost` 三张画像
5. 引入逻辑算子类型系统，而不是 DAG 直绑物理算子
6. 引入 `OperatorScore` 动态评分，而不是人工拍脑袋
7. 把验证做成 DAG 强制结构
8. 引入 `Evidence Ledger`
9. 上下文外置到 `Context Store`
10. 权限落实为 `capability token`
11. Antigravity 正确放在 fan-out，而不是最终裁决位
12. 为 operator 建立 `failure fingerprint`
13. 评估目标架构图与当前实现的偏差

## Problem

当前最大的风险不是“没做”，而是 **完成度语义混乱**：

- 有些点已经有 PRD / contract，但 runtime 没落地
- 有些点已经有局部实现，但没有全链路闭环
- 有些点已经在 8765/dispatcher/operator runtime 里部分成真
- 但系统缺一张统一矩阵来回答：`complete / partial / contract-only / missing`

这会导致：

- 误判系统成熟度
- 把“设计目标”当成“生产能力”
- 下一轮 repair 没有清晰优先级

## 用户故事 / User Stories

- **US1 — 作为 PM / 操盘者**，我希望看到 13 条升级点的逐项完成度矩阵，而不是一句“差不多做了”。
- **US2 — 作为 Planner**，我希望把当前代码、配置、8765 状态面和 accepted artifacts 对齐成统一审计结论。
- **US3 — 作为 Builder / Runtime 维护者**，我希望明确哪些点是现网真值，哪些只是 contract，避免误改。
- **US4 — 作为 Evaluator**，我希望每条结论都有证据，不接受无引用口头判断。

## Product Goal

产出一份 **Actor/Operator Runtime Completion Audit**，将 13 条升级点映射为：

- `implemented`
- `partial`
- `contract_only`
- `missing`

并给出：

- 代码路径
- 配置路径
- 运行时证据
- 已知缺口
- 后续 remediation 建议

## 审计对象 / Audit Scope

必须至少覆盖：

- `graph_node_dispatcher.py`
- `graph_scheduler.py`
- `multi_task_runner.py`
- `operator_runtime.py`
- `operatord.py`
- `status-server.py`
- `physical-operators.json`
- `agent-actors*`
- `docs/pane-as-physical-operator-final-contract-summary.md`
- `~/.solar/harness/run/*` 中与 lease / inbox / result / status 相关的运行时产物

## 非目标 / Non-Goals

- 这张单默认不是“立刻重做全部 runtime”
- 不要求在本 sprint 内把 13 条全部补完
- 不允许把审计单偷换成泛泛设计文档
- 不允许只产 roadmap，不产完成度判定
- 不允许只读 PRD/contract 就宣布 implemented

## 用户目标 / Goals

| ID | 目标 | 映射 |
|----|------|------|
| G1 | 逐条判定 13 个升级点当前完成度 | US1, US4 |
| G2 | 区分实现真值 vs contract 真值 | US1, US3 |
| G3 | 每条结论都绑定代码/配置/运行时证据 | US4 |
| G4 | 输出 remediation backlog 和优先级 | US2, US3 |

## Core Audit Questions

### Q1. Actor vs Host

系统当前是否已经从：

```text
pane = operator
```

升级到：

```text
ActorHost = tmux pane / worktree / managed env / local process
PhysicalOperator = Actor + Lease + Capability + Policy + Quota + Evidence
```

如果没有，当前停在哪一层？

### Q2. Task Protocol

当前任务协议是否已经从直接 `tmux send-keys` 自然语言派发，迁移到：

- file inbox
- structured envelope
- machine-readable result

`send-keys` 是否已经只剩 bootstrap 用途？

### Q3. Lease Truth

当前 runtime 是否真正围绕 lease 运转，而不是只看：

- idle
- running

lease 是否已经决定：

- 占用
- 释放
- 超时
- 抢占边界

### Q4. Capability / Risk / Cost Profiles

当前 operator registry/runtime 是否已经分别建模：

- capability profile
- risk profile
- cost profile

还是仍然只完成 capability 一半？

### Q5. Logical Operator Type System

DAG 当前是否已经普遍使用：

- `logical_operator`
- `task_type`
- `preferred_operator_classes`

而不是仍大量写：

- provider/model/operator_id

### Q6. Operator Score

调度器当前是否已经存在动态 `OperatorScore`，还是仍主要停在 rule-based 过滤和局部排序？

### Q7. Verification Structure

关键任务是否已经强制要求：

1. patch / artifact
2. test or benchmark evidence
3. independent verifier decision

如果没有 verifier 输出，当前系统是否真的会阻断 DONE？

### Q8. Evidence Ledger

当前是否已经存在 per-run ledger，能复盘：

- scheduler decision
- prompts / dispatch
- patch / artifact
- logs
- review decision

### Q9. Context Store

当前上下文是否已经外置为 task/project context packet，还是仍主要依赖 pane 内部上下文与 dispatch 文本注入？

### Q10. Capability Token

当前权限边界是否已经落实为 runtime-enforced token / scope，还是仍主要依赖 prompt、persona 和 shell 守卫？

### Q11. Antigravity Positioning

当前 Antigravity 在 runtime 里是否已经被明确约束在：

- fan-out
- exploration
- Google-stack / prototype

而不是 final verifier / final architect？

### Q12. Failure Fingerprint

当前是否已经收集 operator 的失败指纹，而不是只有 success/availability/alerts？

### Q13. Architecture Gap

用户给出的目标架构图，与当前代码/运行时相比，最大的 5 个缺口是什么？

## Functional Requirements

### FR1: Completion Matrix

必须产出 13 行 completion matrix，每行至少包含：

- upgrade_point
- status (`implemented|partial|contract_only|missing`)
- confidence
- evidence_paths
- blockers
- remediation_hint

### FR2: Evidence-backed Judgment

每条 judgment 至少引用一种：

- code path
- config path
- runtime artifact
- 8765/status evidence

### FR3: No False Green

如果某能力只存在于 PRD/contract/docs，而运行时没落地，必须标：

- `contract_only`

不得标 `implemented`。

### FR4: Remediation Backlog

必须把未完成项收敛成 remediation backlog，至少分：

- P0
- P1
- P2

### FR5: Separate Audit From Repair

`task_graph.json` 必须区分：

- 审计节点
- repair follow-up 节点（如需要）

不能直接跳过审计就进重构。

## Required Deliverables

- `design.md`：completion audit 方法、证据来源、判定规则
- `plan.md`：13 点检查顺序与 proof strategy
- `task_graph.json`：至少覆盖 actor/host, protocol, lease, profiles, logical types, scoring, verification, ledger, context, token, antigravity, fingerprints, gap synthesis
- `handoff.md`：13 条完成度矩阵
- `report.md` 或同等产物：Top gaps + remediation backlog

## PM DAG Input

- N1: Actor vs Host audit
- N2: Task protocol / operatord / send-keys audit
- N3: Lease / lifecycle / runtime truth audit
- N4: Profiles / logical operators / score audit
- N5: Verification / evidence / context / token audit
- N6: Antigravity / failure fingerprint / gap synthesis

## Acceptance Criteria

| ID | 必须回答的问题 |
|----|----------------|
| A1 | 13 个升级点是否逐项给出 `implemented|partial|contract_only|missing` |
| A2 | 每条判定是否给出证据路径 |
| A3 | 是否明确 actor host 与 physical operator 的现状差距 |
| A4 | 是否明确 `send-keys` 当前还剩哪些责任 |
| A5 | 是否明确 lease 已实现边界与缺口 |
| A6 | 是否明确 capability/risk/cost 三画像完成度 |
| A7 | 是否明确 logical operator / score / verifier 结构完成度 |
| A8 | 是否明确 evidence ledger / context store / capability token 缺口 |
| A9 | 是否明确 Antigravity 的正确位置与当前偏差 |
| A10 | 是否给出 remediation backlog |

## 约束 / Constraints

| ID | 约束 | 说明 |
|----|------|------|
| C1 | 这是 **审计 sprint，不是 repair sprint** | Planner/Builder 不得借审计之名 mutate 生产代码、registry、scheduler、runtime；任何改动只能落 remediation backlog，由后续 sprint 处理。 |
| C2 | 不破坏现有 API 接口 | `physical-operators.json`、`operator_runtime`、`operatord`、`status-server` 调用方保持向后兼容；本 sprint 仅读不写代码。 |
| C3 | 不允许只读 PRD / contract / docs 就标 `implemented` | 任何 `implemented` 判定必须绑定 **运行时证据**（live process / sqlite row / 8765 payload / runtime artifact），仅有代码不算实施。 |
| C4 | 不允许猜 — 全部用证据 | 引用必须给绝对路径 + 行号 / SQL query / API 响应；禁止 "我感觉" / "应该是" / "看起来像"。 |
| C5 | 不动 in-flight sprint | 父 sprint (`pane-as-physical-operator-architecture`)、兄弟 sprint (`physical-operator-taxonomy-truthification`、`operator-class-compatibility-cutover`) 仍在跑；不持其 lock、不 mutate 其 artifact、不读其 secret。 |
| C6 | macOS arm64 + bash 5.3.9 | 审计脚本必须在 `/opt/homebrew/bin/bash` 下可跑；不写 /tmp（落 sprint 目录）。 |
| C7 | 不引入新 dependency | 审计只用已有工具：`solar-harness` CLI、sqlite3、jq、grep、Python stdlib、ripgrep；不允许新加 PyPI 包或外部服务。 |
| C8 | 不停机审计 | 审计期间 coordinator / autopilot / 8765 server / tmux pane 全部保持运行；不允许为审计而 stop / restart 任何 daemon。 |
| C9 | 不向 evaluator 妥协 confidence | 每条 judgment 必须明确 `confidence: high/medium/low`；"high" 需要 ≥ 2 个证据源（code + runtime artifact）；"low" 必须列出未确认原因。 |
| C10 | 不允许偷换审计范围 | 13 个升级点必须全部覆盖；不能因为某点"太难审"或"暂时找不到证据"就跳过；找不到必须明确标 `missing` 或 `unknown` + 阻塞原因。 |
| C11 | 不允许把 audit 写成 design doc | 输出必须是判定 + 证据 + backlog；不写"我建议怎么改"以外的设计提案；具体重做方案推到下一轮 repair sprint。 |
| C12 | 不引入 ML / autosearch 自动判定 | 13 条全部由 Planner/Architect 手工判定，必要时由 evaluator 二审；不允许把判定外包给 RAG / LLM agent 自动给结论。 |

## 风险 / Risks

| ID | 风险 | 概率 | 影响 | 缓解 |
|----|------|------|------|------|
| R1 | 把 "contract 已写" 错判为 "implemented" → 误判系统成熟度 → 下一轮 repair 优先级失真 | 高 | 高 | FR3 / C3：明确 `contract_only` 是独立等级；evaluator 必须比对运行时证据 vs 代码文件存在性 |
| R2 | 13 条审计耗时过长 → audit sprint 本身阻塞下游 repair | 中 | 中 | 拆分 6 个 workstream node 并行；每 node ≤ 2 条升级点；STOP-A round 3 仍未完成则缩减证据深度 |
| R3 | 审计期间发现严重 production bug，但 C1 禁止 mutate → 用户体验掉头去手修 | 中 | 中 | 严重 bug 单独提 `critical_finding` 标签 + 立即写到 STATE.md + 触发独立 P0 hotfix sprint，不在本 sprint 内修 |
| R4 | runtime artifact 路径找不到（`~/.solar/harness/run/*` 可能被自动清理） | 中 | 中 | 审计前 snapshot 当前 run/ 目录到 `~/.solar/harness/sprints/<sid>.evidence/`；快照失败立即标 R4 |
| R5 | 13 条之间证据强度差异巨大（有些有完整 sqlite log，有些只有 prose docs） → audit 报告深度不均 | 高 | 低 | 每条标 `evidence_strength: strong/medium/weak`；report 末尾列 evidence 分布直方图 |
| R6 | Antigravity / Codex / Claude 现有调用路径分散，难以一次拉全证据 | 中 | 中 | Q11 单列 antigravity_invocation_index，grep 全 repo + sqlite 任务表；找不到入口直接标 `contract_only` |
| R7 | `failure fingerprint` (Q12) 现在可能根本不存在 → 直接 `missing`，但需证明不是"我没找着" | 中 | 中 | grep 关键字 `fingerprint / failure_hash / cluster` + sqlite schema dump + status-server fields；3 路全空才能标 `missing` |
| R8 | 审计结论被 codex_pm 或别的 actor 静默 mutate | 低 | 高 | 报告写 `## Provenance` 段，附 sha256 + 写入时间；后续修改必须保留 audit trail |
| R9 | gap synthesis (Q13) 落到主观偏见 — Planner 判 top-5 缺口未必匹配真实优先级 | 中 | 中 | top-5 缺口必须按 (frequency × blast_radius × user_pain) 三维打分；不允许只凭"我觉得最重要" |
| R10 | mirage 持续 timeout / Solar DB 表 schema 变化导致证据 query 失败 | 中 | 低 | 单条证据失败不算审计失败；记入 `unknown` + 原因；mirage timeout 已是已知降级状态 |

## 开放问题 / Open Questions

> 这些留给 Planner 在 `design.md` 给出明确答案，不在 PRD 阶段决定。

- **Q-OQ1**：13 条 audit 是按 **顺序串行**（Q1→Q13）还是按 **workstream 并行**（N1-N6）？建议并行，但 Q13 gap synthesis 必须最后 — Planner 是否同意？
- **Q-OQ2**：`confidence: high/medium/low` 的边界如何量化？建议 high = ≥ 2 证据源 + runtime 验证；medium = 1 证据源 + runtime；low = 仅代码 / 仅 prose — Planner 是否同意？
- **Q-OQ3**：runtime evidence snapshot（`~/.solar/harness/run/*`）的保留窗口？建议 sprint 全程 + 7 天 — Planner 同意吗？过期后允许 evaluator 删除以省盘？
- **Q-OQ4**：审计发现的 critical_finding 是直接 raise 独立 P0 hotfix sprint，还是先在本报告里 flag、等用户拍板？
- **Q-OQ5**：13 条以外是否允许 Planner 加 audit 项（例如新发现的 Q14）？建议允许但必须先写 `## Out-of-Scope Additions` 段 + 用户确认 — Planner 同意吗？
- **Q-OQ6**：handoff.md 的 13 条 matrix 是否要导出为 sqlite/csv，让后续 dashboard 能查？还是只留 markdown？
- **Q-OQ7**：报告中是否要给每个 `partial` / `contract_only` / `missing` 标 **预估修复成本**（XS/S/M/L/XL）？这会让 backlog 更可用，但增加判定工作量。
- **Q-OQ8**：evaluator 二审时，是 random sample 3-5 条做深度复核，还是全 13 条都过一遍？前者快，后者覆盖完整。
- **Q-OQ9**：审计期间发现 documentation drift（docs 说 implemented，代码不在），是否要顺手更新 docs？还是只 flag、不动？建议只 flag（守 C1）。
- **Q-OQ10**：Q13 gap synthesis 的 "目标架构图" 引用哪份？建议 `~/.solar/docs/4-pane-architecture.md` + `physical-operators` 系列 contract，但需要 Planner 明确锚定。
- **Q-OQ11**：Antigravity 在 audit 期间是否允许被调用做 fan-out 帮忙找证据？还是审计也不允许用 Antigravity（保持独立性）？
- **Q-OQ12**：Audit 输出是否要进 obsidian-wiki / mirage / Solar DB FTS 索引？让后续 sprint 能 context inject 命中。

## 架构交接 / Planner Handoff

**Handoff Target**: `pane 0 (planner, opus)` — audit 性质，需要 opus 的判断力
**Handoff Mode**: 正式 `PM → Planner`，禁止跳过 Planner 直派 Builder
**Stop Rules**: Planner 完成 `design.md + plan.md + task_graph.json + handoff.md (13-条 matrix) + report.md (top gaps + backlog)` 五件套后，状态机进入 `planning_complete` → 由 evaluator (pane 2) + architect (pane 3) 二审；否则保持 `drafting` 并 round++

### 强制 Planner 回答的设计点

1. **Audit Method Lock**：design.md 必须开篇定义 `implemented / partial / contract_only / missing` 4 个等级的硬判定规则；定义 `confidence` 三档边界（对齐 Q-OQ2）；定义 `evidence_strength` 三档。
2. **Evidence Source Lock**：明确每条升级点的证据 fetch 命令（grep 命令 / sqlite query / 8765 API 路径 / log 路径），可复制可重跑。
3. **Workstream Lock**：6 个 workstream node (N1-N6) 各自覆盖 2 条升级点 + N6 包含 Q12-Q13 gap synthesis；明确每 node 的 verifier_operator_class（必须 ≠ writer，对齐父 sprint A8）。
4. **Output Schema Lock**：handoff.md 的 13-行 matrix 必须有固定 schema（upgrade_point / status / confidence / evidence_strength / evidence_paths / blockers / remediation_hint / repair_cost_estimate）；machine-parseable（markdown table or YAML block）。
5. **Backlog Lock**：remediation backlog 按 (P0/P1/P2) × (XS/S/M/L/XL) 二维分桶；P0 项必须给 1 行 acceptance proposal，方便后续 sprint 直接吃。

### 必备产出物

| 产出 | 路径 | 验收方 |
|------|------|--------|
| `design.md` | `~/.solar/harness/sprints/sprint-20260524-actor-host-runtime-completion-audit.design.md` | evaluator + architect 二审 |
| `plan.md` | `~/.solar/harness/sprints/...plan.md` | evaluator |
| `task_graph.json` | `~/.solar/harness/sprints/...task_graph.json` | `solar-harness graph-scheduler validate` |
| `handoff.md` (13-行 completion matrix) | `~/.solar/harness/sprints/...handoff.md` | evaluator + 人类操盘者 |
| `report.md` (Top gaps + remediation backlog) | `~/.solar/harness/sprints/...report.md` | evaluator + architect |
| `<sid>.evidence/` 目录（runtime snapshot） | `~/.solar/harness/sprints/<sid>.evidence/` | evaluator 抽样验证 |

### task_graph.json 必须满足

- 每个 node 写 `task_type: AUDIT` + `required_capabilities` + `preferred_operator_classes` (RootCauseDebugger / DeepArchitect / Verifier)；不写 model 字符串
- 至少 6 个 workstream node（N1 Actor-vs-Host / N2 Protocol-operatord-send-keys / N3 Lease-lifecycle-runtime / N4 Profiles-logical-score / N5 Verification-evidence-context-token / N6 Antigravity-fingerprint-gap）
- 每 node 有 `audits` 字段列出覆盖的升级点编号（1-13）
- 每 node 有 `acceptance` 字段映射 PRD A1–A10
- 每 node 满足 `verifier_operator_class != writer_operator_class`（FR5 强制）
- 必须有 1 个 sink node 做 `gap_synthesis` 依赖 N1-N5 全部完成

### Stop Rules

- **STOP-A**：Planner 在 round 3 仍未产出 5 件套 → PM 介入重写切片粒度（可能缩到 P1 升级点集）
- **STOP-B**：审计期间发现 `critical_finding`（生产 P0 bug） → 立即写 STATE.md + 触发独立 hotfix sprint；本 sprint 不修
- **STOP-C**：13 条中 ≥ 4 条标 `unknown`（既不是 implemented/partial 也不是 contract_only/missing） → 触发 architect (pane 3) 二审，重新评估证据采集方法
- **STOP-D**：runtime evidence snapshot 失败（盘满 / 权限 / R4 触发） → 暂停 audit，先修 snapshot 再续

### Non-Negotiables (PM 红线)

- 不允许 Planner 在 audit 期间 mutate 生产代码、registry、scheduler、runtime（C1）
- 不允许 Planner 把 `contract_only` 标成 `implemented` 来粉饰完成度（C3 / FR3）
- 不允许 Planner 用 "我觉得" / "应该是" 作为 judgment（C4）
- 不允许 Planner 跳过 evaluator/architect 二审直接交付
- 不允许 Planner 把 Antigravity 自动派给 audit 判定（C12 / Q-OQ11）

### Knowledge Context

Knowledge Context: `solar-harness context inject` used (mirage timeout，QMD/Solar DB/Obsidian Vault 命中)
Harness Modules Used: `harness-knowledge`（context inject）
ACK File: `~/.solar/harness/sprints/sprint-20260524-actor-host-runtime-completion-audit.ack-d-20260524T020914Z-a30a11.json`

