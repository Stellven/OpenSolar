# Design — Actor Host Runtime Completion Audit

sprint_id: `sprint-20260524-actor-host-runtime-completion-audit`
priority: `P0`
lane: `strategy`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-24T02:10:00Z`
knowledge_context: `solar-harness context inject used (mirage timeout -> qmd/obsidian/solar_db fallback)`
parent_sprint: `sprint-20260523-pane-as-physical-operator-architecture`（read-only 引用）
related_sprints: `physical-operator-taxonomy-truthification` / `operator-class-compatibility-cutover` / `lease-based-model-fleet-runtime`（全部 read-only）

## 0. 本切片的边界（强制 read-first）

- **P0 audit sprint**：对 13 个升级点做 **逐项 completion audit**，输出 `implemented | partial | contract_only | missing` 四档判定 + 证据路径 + remediation backlog。**不实施修复**（per Hard Rules §「不允许把审计单偷换成立即大改实现」）。
- **严格禁止**：
  - 把 contract/doc 当 implemented（FR3 + Hard Rules §1）
  - 只凭印象判定（Hard Rules §2）
  - 跳过运行时证据（Hard Rules §3）
  - 审计中直接做 repair（FR5 + Hard Rules §4）
  - 遗漏任一升级点（Hard Rules §5）
  - 修改任何被审计的 production code / config / runtime artifact（audit = read-only）
  - 修改父 sprint / related sprints 任何 artifact
  - 写 raw secret / token / cookie
  - 改 `~/.solar/STATE.md` / epic.* / 其他 sprint
- **允许 Write/Edit**：
  - `sprints/<sid>.{design, plan, task_graph, planning_html}.{md,json,html}`（本轮）
  - `sprints/<sid>.audit-Q*-*.md`（N1..N6 audit 报告）
  - `sprints/<sid>.completion-matrix.md`（N6 必交：13 行 matrix）
  - `sprints/<sid>.remediation-backlog.md`（N6 必交：P0/P1/P2 backlog）
  - `~/.solar/harness/monitor-reports/actor-host-runtime-completion-audit.md`（N6 最终报告）
- 知识库降级 `mirage:timeout`：本 sprint self-contained（审计只需 read 现有 repo）。

## 1. 完成度判定 Rubric（per FR1 + Mandatory Design §1-3）

四档判定，**绝不**含模糊「应该」「差不多」：

| Status | 定义 | 必须证据 |
|--------|------|---------|
| `implemented` | 现网真值已落地，所有 code path + config + runtime artifact 全到位 | code path（具体文件 + 行号）+ config 文件 + runtime artifact（log/sqlite/state 文件）3 类证据齐全 |
| `partial` | 部分 code path 已实现，但缺关键 sub-feature 或缺全链路闭环 | code path（已实现部分）+ gap 清单（缺什么 + 哪个 sub-feature） |
| `contract_only` | 仅 PRD / contract / docs 提及，runtime 完全未落地 | PRD/contract/doc 路径（已有什么文档）+ runtime grep 失败证据（无对应代码） |
| `missing` | 既无设计也无实现 | grep 全空 + 无 PRD/contract 引用 |

**confidence 0-100**：每条 judgment 必须附 confidence 分数（依据证据强度），低于 60 必须解释为什么。

**No False Green 铁律**（FR3）：仅 PRD/contract 存在但 runtime 未落地 → **必须** `contract_only`，**严禁** `implemented`。审计中如发现误标，立即降级。

## 2. Evidence Source 4 类（per FR2 + Audit Scope）

每条 judgment 至少引 1 类，理想引 ≥2 类：

| 类别 | 示例路径 | 用途 |
|------|---------|------|
| Code path | `lib/graph_node_dispatcher.py:NNN-MMM`、`lib/operator_runtime.py:func_name` | 证明代码逻辑存在 |
| Config path | `config/physical-operators.json`、`config/agent-actors.json` | 证明配置 schema 就位 |
| Runtime artifact | `~/.solar/harness/run/agent-actors/<actor_id>/`、`run/multi-task/<task_id>/lease.json`、`8765 status payload snapshot` | 证明 runtime 真在用 |
| Document/contract | `docs/pane-as-physical-operator-final-contract-summary.md`、`sprints/<related-sprint>.design.md` | 区分 contract_only vs implemented |

## 3. 13 升级点 → DAG 节点映射

| # | 升级点 | Audit Question | DAG Node |
|---|--------|---------------|----------|
| 1 | pane=算子 → pane 承载 actor，actor 才是算子 | Q1 | N1 |
| 2 | tmux send-keys 仅 bootstrap | Q2 | N2 |
| 3 | 以 lease 为核心 | Q3 | N3 |
| 4 | capability / risk / cost 三画像 | Q4 | N4 |
| 5 | 逻辑算子类型系统（DAG 不直绑物理算子） | Q5 | N4 |
| 6 | OperatorScore 动态评分 | Q6 | N4 |
| 7 | 验证作为 DAG 强制结构（patch + test + verifier 三件） | Q7 | N5 |
| 8 | Evidence Ledger | Q8 | N5 |
| 9 | Context Store 上下文外置 | Q9 | N5 |
| 10 | Capability Token 权限落实 | Q10 | N5 |
| 11 | Antigravity 正确放在 fan-out（非最终裁决） | Q11 | N6 |
| 12 | Operator Failure Fingerprint | Q12 | N6 |
| 13 | 目标架构图 vs 当前实现 — 最大 5 个缺口 synthesis | Q13 | N6 |

## 4. Audit Workflow Per Node

每节点遵循 **6 步证据驱动审计**（防 false green）：

```
Step 1: 列出本节点负责的 upgrade_point + Q
Step 2: 列出 expected evidence（code/config/runtime/doc 各类应该长什么样）
Step 3: 实际跑 grep / cat / sqlite query / ls 取证（read-only）
Step 4: 对比 expected vs actual，标 implemented/partial/contract_only/missing
Step 5: 写 judgment row：upgrade_point + status + confidence + evidence_paths + blockers + remediation_hint
Step 6: 自审 — 是否把 contract_only 错标 implemented？是否缺 runtime evidence？
```

每个 Step 3 的取证命令必须落到 audit md 内（可复现）。

## 5. Completion Matrix 字段集（per FR1 + Mandatory Design §1）

`<sid>.completion-matrix.md` 必含 13 行，每行 6 列：

| upgrade_point | status | confidence | evidence_paths | blockers | remediation_hint |

示例（fictional 演示格式）：

```markdown
| 1. pane→actor 升级 | partial | 70 | code: lib/operator_runtime.py:120-280 (lease 部分实现); config: config/physical-operators.json (actor_id 字段已加); runtime: run/agent-actors/ 目录不存在 | actor_id 已就位但 ActorHost/PhysicalOperator 解耦未完成；run/agent-actors/ 未创建 | P0: 创建 ActorHost registry + run/agent-actors/ 目录 schema |
```

## 6. Remediation Backlog（per FR4 + Mandatory Design §5）

`<sid>.remediation-backlog.md` 必分 3 档：

```markdown
## P0（关键路径阻断 / 高频被使用 / 已知 bug 触发）
- [ ] <upgrade_point#> <action> — owner: <future sprint>; effort: <S/M/L>

## P1（重要但不阻断 / 长期影响一致性）
- [ ] ...

## P2（nice-to-have / 长期演进）
- [ ] ...
```

每条 backlog 必须含：

- 升级点编号引用
- 具体 action（不允许「优化一下」级别模糊语）
- owner（建议下一个 sprint id 或 follow-up sprint 类型）
- effort 估算（S=≤1 dispatch round / M=2-3 / L=>3）

## 7. Audit Scope 文件清单（必须 cover）

`lib/`：
- `graph_node_dispatcher.py`
- `graph_scheduler.py`
- `multi_task_runner.py`
- `operator_runtime.py`
- `operatord.py`
- `actor_runtime.py` / `actor_lease.py` / `actor_mailbox.py` / `actor_profiles.py`（如存在）
- `evidence_ledger.py` / `context_store.py` / `capability_token.py` / `failure_fingerprint.py`（如存在）

`tools/`：
- `status-server.py`
- `monitor_bridge.py`

`config/`：
- `physical-operators.json` / `physical-operators.schema.json`
- `agent-actors.json` / `agent-actors.schema.json`（如存在）
- `actor-hosts.json` / `logical-operators.json` / `context-store.json` / `capability-token.schema.json`（如存在）

`run/`：
- `run/agent-actors/<actor_id>/`（lease/inbox/outbox/state/heartbeat）
- `run/multi-task/<task_id>/`（lease/result/log）
- `run/monitor-bridge/global.latest.json`

`docs/` + `sprints/`：
- `docs/pane-as-physical-operator-final-contract-summary.md`
- `sprints/sprint-20260523-pane-as-physical-operator-architecture.*`
- `sprints/sprint-20260523-physical-operator-taxonomy-truthification.*`
- `sprints/sprint-20260523-lease-based-model-fleet-runtime.*`
- `sprints/sprint-20260523-operator-class-compatibility-cutover.*`

## 8. Separate Audit From Repair（per FR5）

`task_graph.json` 节点全部 audit 类型（无 repair 节点）：

- N1..N6 = audit only
- remediation backlog（N6 产）是 **planning input** 给下一 sprint，不是本 sprint repair 节点
- 任何节点试图修改被审计代码 / config → evaluator FAIL + ATLAS structured repair

## 9. 已知风险（per Hard Rules）

- **False green**：见 §1 No False Green 铁律 + Step 6 自审
- **遗漏升级点**：N6 acceptance 强制 13 行 matrix 缺一即 FAIL
- **审计变 repair**：plan §7 stop rule + N* acceptance「未修改任何被审计文件」
- **凭印象判定**：每条 judgment 必须含 evidence_paths（plan §5 grep 校验）
- **runtime evidence 缺失**：每条 `implemented` 必须含 runtime artifact 证据；只有 code+config 无 runtime → 降级 `partial`

## 10. 非目标（per Non-Goals）

- 不立刻重做 runtime
- 不在本 sprint 把 13 条全部补完
- 不允许审计单偷换成泛泛设计文档
- 不只产 roadmap 不产完成度判定
- 不只读 PRD/contract 就宣布 implemented
- 不动 `~/.solar/STATE.md` / epic.* / 其他 sprint artifact
- 不 block / rewrite 父 sprint / related sprints
- 不打开 live tmux pane / 不重启 harness / 不杀 in-flight worker
- 不写 raw secret

## 11. 接力 evaluator / 下一 sprint

evaluator 必须按 A1..A10 逐项核（plan §6 提供命令）。

下一 sprint：从 N6 remediation-backlog.md 的 P0/P1 项中选择具体 follow-up sprint（每个 backlog 项可能对应一个独立 sprint，例如「补 evidence_ledger 真实落地」或「补 Antigravity 位置约束」）。

最终报告 `monitor-reports/actor-host-runtime-completion-audit.md` 是给 PM 的决策输入。
