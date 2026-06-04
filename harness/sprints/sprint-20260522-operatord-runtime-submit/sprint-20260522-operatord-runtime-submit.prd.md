# PRD: Operatord Runtime Submit Foundation

Sprint: `sprint-20260522-operatord-runtime-submit`
Priority: P0
Owner host: `lisihao@100.122.223.55`

## Background

The Model Fleet Operator Runtime now has a registry, selector, quota-aware fallback policy, and monitor bridge visibility. The next gap is the physical execution layer: panes still behave like ad hoc task runners. The target architecture requires every physical operator pane to run the same daemon shell:

```text
operatord run <operator_id>
```

Normal DAG execution must submit structured task envelopes through runtime APIs, not directly send instructions to tmux panes.

## Goals

1. Implement a first-version `operatord` CLI for running physical operator panes.
2. Add `operator_runtime.submit(task)` or equivalent API to create task envelopes, acquire leases, and route tasks to an operator-owned inbox.
3. Add canonical pane-title generation and application for tmux operators.
4. Add a lint/test gate that prevents normal DAG nodes from using direct `tmux send-keys` dispatch.
5. Preserve existing `solar-harness multi-task` behavior while adding the new runtime path as a safe foundation.

## Non-Goals

- Do not migrate every active pane to `operatord` in this sprint.
- Do not kill existing tmux panes.
- Do not print or persist raw API keys, OAuth tokens, or cookies.
- Do not globally install packages.
- Do not re-enable unsafe ThunderOMLX cache features.

## Required Interfaces

### Persona Bank Binding

Every physical operator must bind to the local persona bank under `personas/`. The binding is part of the operator contract, not just display metadata.

Required persona files:

```text
┌────────────────────────────────────────────┬────────────────────────────────────────────┐
│ Persona                                    │ Responsibility                             │
├────────────────────────────────────────────┼────────────────────────────────────────────┤
│ personas/pm.md                             │ Product brief, scope, clarification         │
│ personas/planner.md                        │ Task graph decomposition and dependencies   │
│ personas/builder.md                        │ Real code/test implementation               │
│ personas/evaluator.md                      │ Contract done-list validation and red-team   │
│ personas/architect.md                      │ Second-stage architecture/final gate         │
│ personas/evaluator-verification-protocol.md│ Executor verification protocol               │
│ personas/lab-builder.md                    │ Experimental implementation                 │
│ personas/lab-evaluator.md                  │ Experimental validation                     │
│ personas/observer.md                       │ Static observation and log recording         │
│ personas/second-builder.md                 │ Backup or parallel implementation           │
└────────────────────────────────────────────┴────────────────────────────────────────────┘
```

Required behavior:

- `physical-operators.json` entries must include `persona` or a canonical persona binding.
- `operatord run <operator_id>` must load the referenced persona file and include it in the task envelope context.
- Missing persona files must make the operator `needs_human_review` or not dispatchable.
- The evaluator role must also load `evaluator-verification-protocol.md` when present.
- Bridge/status output must expose persona binding so a human can see not only the model, but the working role contract.

### Canonical Operator ID

```text
op.<surface>.<provider>.<model>.<role>.<config>.<index>
```

### Pane Title

```text
[CLAUDE][OPUS47][ARCH][XHIGH][01]
[CODEX][GPT55][IMPL][01]
[AG][G35FLASH][PAR][03]
[LOCAL][MLX][SCAN][01]
```

### Operator Daemon

```text
solar-harness operatord run <operator_id>
```

Minimum daemon responsibilities:

- Read operator registry.
- Resolve `secret_ref` without logging raw secrets.
- Set canonical pane title when running under tmux.
- Write heartbeat/state files.
- Receive task envelope files from an operator inbox.
- Launch the configured backend command in dry-run/smoke mode or real mode when explicitly permitted.
- Capture stdout/stderr into execution logs.
- Parse quota/auth/runtime errors into structured status.
- Write a structured task result.

### Runtime Submit API

Python API:

```python
operator_runtime.submit(task_envelope: dict) -> dict
```

CLI:

```text
solar-harness operator-runtime submit --operator <operator_id> --task-envelope <path>
```

Submit must:

- Validate envelope shape.
- Validate operator availability.
- Acquire lease.
- Write envelope to operator inbox.
- Return task id, operator id, lease id, inbox path, and status.

### Task Envelope

```yaml
task_id: dag-20260522-node-03
sprint_id: sprint-...
node_id: N3
task_type: CODE_IMPL
objective: Implement operator runtime submit.
constraints:
  write_files: true
  run_tests: true
  git_commit: false
output_contract:
  required_artifacts:
    - execution_summary.md
    - result.json
verifier:
  required: true
  cannot_use_same_operator: true
```

## Acceptance Criteria

- `solar-harness operatord run --help` or equivalent CLI exists.
- `operator_runtime.submit(task)` exists and has unit tests.
- Submit rejects disabled, leased, running, quota-exhausted, auth-expired, and unknown operators.
- Submit writes a task envelope to a deterministic operator inbox path.
- Pane title canonicalizer maps registry/model aliases to `[PROVIDER][MODEL][ROLE][CONFIG][INDEX]`.
- Tmux title apply is no-op outside tmux and safe inside tmux.
- Lint/test gate finds direct `tmux send-keys` in normal DAG dispatch code and allows only approved tmux adapter/startup code.
- No raw secrets are logged.
- Persona bank binding is validated for pm/planner/builder/evaluator/architect/lab-builder/lab-evaluator/observer/second-builder and evaluator verification protocol.
- Operatord loads the persona file for the selected operator or reports a structured blocker.
- Final report exists at `/Users/lisihao/.solar/harness/monitor-reports/operatord-runtime-submit.md`.

## Evidence Required

- Changed files.
- Unit test commands and results.
- Submit smoke with a safe local/dummy operator.
- Pane title canonicalizer examples.
- Lint gate result.
- Remaining gaps for full pane migration.

---

## 背景 / Context

- Model Fleet Operator Runtime 之前已建好 registry / selector / quota-aware fallback / monitor bridge 可视化（参见 sprint-20260523-lease-based-model-fleet-runtime），但**物理执行层**还停留在"pane 当 ad-hoc task runner"的状态：DAG 节点直接 `tmux send-keys` 把自然语言任务塞进去，pane 不知道自己是什么角色，secrets 路径不规范，缺持久 daemon。
- 本 sprint 要造的是这套体系的**daemon shell + submit API**：每个物理 operator pane 跑统一 `operatord run <operator_id>`；DAG 通过 `operator_runtime.submit(task_envelope)` 投递 structured task envelope 到 operator 自己的 inbox，而不是直接喷 keys。
- 状态：sprint 已 `.finalized` 2026-05-22T21:00:56Z（N5 evaluator verdict=**PASS**，**50/50 tests pass / persona 10/10 / operator-binding 12/12 / lint gate 275 files / 0 secret leak**），coordinator 当前拉回 `drafting/prd_ready` 仅为 gate_prd_schema 触发的回溯。
- 本切片即修复 PRD schema，不重做实施 / 不动 .finalized / 不动 5 个 N* handoff / 不动代码 / 不动 monitor-reports。

## 用户问题 / Problem

- **PB-1 pane 角色不持久**：之前每次给 pane 派任务都要重传 persona，tmux pane 重启后就忘了自己是 builder 还是 evaluator；persona 漂移导致 role 边界混乱。
- **PB-2 任务通道直接 send-keys**：DAG 把自然语言指令直接 `tmux send-keys` 进 pane，没有结构化 envelope，没有 lease，没有 verifier 边界；安全审计 / lease 抢占 / 失败重试都没着力点。
- **PB-3 secrets 路径不规范**：当前 secrets 直接走环境变量或在 prompt 里出现；没有 `secret_ref` + daemon 解 ref 的统一路径，token 容易被记到日志。
- **PB-4 pane 标题没规范**：tmux 标题靠人手命名（"pane-0" / "claude" / "evaluator"），人看不清这个 pane 是什么 provider/model/role/config。
- **PB-5 verifier 边界缺失**：writer 可以自我认证 done，没有"writer ≠ verifier"强制。
- **PB-6 persona 文件存在但未绑定**：`personas/*.md` 在仓库里有，但 operator registry 没引用，pane 起来时不会自动加载 persona。
- **PB-7 PRD schema 8 节缺失**：coordinator gate_prd_schema 拉回 drafting；本切片即修复。

## 用户故事 / User Stories

- **US-01 (DAG 作者)**：作为 DAG 作者，我希望调 `operator_runtime.submit(task_envelope)` 就行，不要写 `tmux send-keys`；envelope 校验 / lease / inbox / status 都由 runtime 管。
  - 验收：PRD §Runtime Submit API + N4 实施 `lib/operator_runtime.py` ✅ + N5 50 tests pass。
- **US-02 (Operator 维护者)**：作为 operator 维护者，每个 pane 跑 `operatord run <operator_id>` 是统一入口；daemon 读 registry / 解 secret_ref / 设 pane 标题 / 写心跳 / 收 inbox envelope / 启动 backend / 抓 stdout/stderr / 解析 quota/auth/runtime 错误。
  - 验收：PRD §Operator Daemon 列 9 项最小责任 + N3 实施 `tools/operatord.py` ✅。
- **US-03 (Persona 绑定使用者)**：作为派任务的人，我希望每个 operator 必须绑定 persona（pm/planner/builder/evaluator/architect/lab-builder/lab-evaluator/observer/second-builder + evaluator-verification-protocol），缺 persona 的 operator 不能派任务。
  - 验收：PRD §Persona Bank Binding 表 10 行 + N5 §6 实测 persona 10/10 + operator binding 12/12 ✅。
- **US-04 (Pane 看板)**：作为运维，我希望 tmux pane 标题统一 `[PROVIDER][MODEL][ROLE][CONFIG][INDEX]`，一眼看清 pane 是什么。
  - 验收：PRD §Pane Title + N4 8 operator 全部正确 canonical title ✅。
- **US-05 (安全审计)**：作为安全审计，我希望禁止 DAG 代码直接 `tmux send-keys` 派任务；只允许 approved 启动 adapter 用。
  - 验收：PRD §Acceptance "Lint/test gate finds direct tmux send-keys" + N5 lint 275 files / 10 ALLOW / 0 DENY ✅。
- **US-06 (Secrets / 合规)**：作为合规检查者，daemon 解 `secret_ref` 时不允许把 raw token 打到日志。
  - 验收：PRD §Non-Goals + N5 grep `sk-|ghp_|gho_|gsk_|api_key|token=` 命中 0 substantive（只匹配到 `--task-id` argparse flag）✅。
- **US-07 (Coordinator / PM)**：作为 coordinator，本 PRD 通过 gate_prd_schema，sprint 不再循环。
  - 验收：本切片即修复，`validate.sh prd` → PASS。

## 功能需求 / Requirements

- **FR-1 `operatord` CLI daemon**：`solar-harness operatord run <operator_id>` 启动 daemon，9 项最小责任（读 registry / 解 secret_ref / 设 pane 标题 / 写心跳 / 收 inbox envelope / 启动 backend 含 dry-run/smoke/real / 抓 stdout-stderr / 解 quota/auth/runtime 错误结构化 / 写 structured result）。
- **FR-2 `operator_runtime.submit(task_envelope)` API**：Python + CLI 双入口；返回 `task_id / operator_id / lease_id / inbox_path / status`；rejects disabled / leased / running / quota_exhausted / auth_expired / unknown operators。
- **FR-3 Task envelope schema**：YAML/JSON 标准（`task_id / sprint_id / node_id / task_type / objective / constraints / output_contract / verifier`）；verifier `required=true` + `cannot_use_same_operator=true`。
- **FR-4 Persona bank binding**：`physical-operators.json` 每个 entry 含 `persona` 或 canonical 绑定；缺失 → operator `needs_human_review`；evaluator 角色额外加载 `evaluator-verification-protocol.md`；bridge/status 暴露 persona 绑定。
- **FR-5 Canonical Operator ID**：`op.<surface>.<provider>.<model>.<role>.<config>.<index>`。
- **FR-6 Pane title canonicalizer**：`[PROVIDER][MODEL][ROLE][CONFIG][INDEX]` 例：`[CLAUDE][OPUS47][ARCH][XHIGH][01]` / `[CODEX][GPT55][IMPL][01]` / `[AG][G35FLASH][PAR][03]` / `[LOCAL][MLX][SCAN][01]`；tmux 外 no-op，tmux 内安全。
- **FR-7 Lint/test gate ban `tmux send-keys`**：scan 仓库；DAG dispatch 代码命中即 fail；只允许 approved tmux adapter / startup code（whitelist）。
- **FR-8 Secrets 0-leak**：所有 stdout/stderr/log/envelope 不出现 raw token；secret_ref 解析路径明确。
- **FR-9 不动现有 multi-task**：`solar-harness multi-task` 继续可用；新 runtime 路径只作"安全基础"叠加，不强制迁移。
- **FR-10 最终报告**：`~/.solar/harness/monitor-reports/operatord-runtime-submit.md` 写出 11 节含 changed files / tests / submit smoke / title 例 / lint gate / persona coverage / operator→persona mapping / safety posture / verdict / next-sprint plan。
- **FR-11 PRD schema 合规**：通过 `validate.sh prd`（本切片即修复 gate_prd_schema）。

## 约束 / Constraints

- **环境**：macOS arm64 (lisihaodeMac-mini.local) / bash 5.3.9 / Solar Harness 4-pane / tmux 多 pane。Owner host 标注为 `lisihao@100.122.223.55`（Tailscale）。
- **路径白名单**：实施代码 `~/.solar/harness/lib/operator_runtime.py` + `tools/operatord.py` + `tools/operator_naming.py` + 测试；报告 `~/.solar/harness/monitor-reports/`；handoff `~/.solar/harness/sprints/<sid>.N*-handoff.md`；禁 `/tmp`、禁仓库 git 提交。
- **不强制迁移**：本 sprint 不要求把所有现役 pane 切到 `operatord`；保留旧 `solar-harness multi-task` 路径。
- **不杀现役 tmux pane**：明示 non-goal。
- **不全局安装包**：禁 `pip install` 全局；只在 venv 内。
- **不打 secrets**：raw API key / OAuth / cookie 不允许进 stdout / log / envelope；secret_ref 必须从 daemon 内解。
- **不启用 unsafe ThunderOMLX cache 特性**：明示 non-goal（与 OMLX 相邻 sprint 协同）。
- **API 兼容**：`solar-harness context inject / session evaluate / intent-gateway` 调用方式不变；新增 `operatord` 和 `operator-runtime submit` 子命令。
- **Verifier 边界**：writer ≠ verifier 强制（task envelope `verifier.cannot_use_same_operator=true`）。
- **PM 角色边界**：不写代码、不动 `.finalized` / status.json / 5 个 N* handoff / 实施代码 / monitor-report；本 PRD 修复后保持 `status=drafting`。

## 风险 / Risks

| 风险 | 影响 | 缓解 / 状态 |
|------|------|--------------|
| Pane 直接被 `tmux send-keys` 偷渡 | 控制平面退化 | FR-7 lint gate 扫 275 files；N5 实测 10 ALLOW / 0 DENY（regression evidence） ✅ |
| writer 自证 done | 假 PASS | FR-3 envelope `verifier.cannot_use_same_operator=true` + 强制 verifier 存在 ✅ |
| Persona 缺失但 operator 仍然 dispatchable | role 边界混乱 | FR-4 `needs_human_review` 状态拦截；N5 persona 10/10 + 12/12 mapping ✅ |
| secret_ref 解析时 raw token 漏到 stdout | 安全事故 | FR-8 + N5 grep 6 sensitive pattern 命中 0 substantive（仅 `--task-id` argparse flag） ✅ |
| pane title canonicalizer 在 tmux 外 throw | 跨环境失败 | FR-6 tmux 外 no-op + N4 N5 验证 ✅ |
| operator_runtime.submit 接受 disabled/leased/quota operator | race / 资源冲突 | FR-2 5 类 rejection（disabled/leased/running/quota_exhausted/auth_expired/unknown） + N5 §3 smoke 4 rejection paths ✅ |
| inbox path 不确定（race condition） | envelope 丢 | FR-2 "deterministic operator inbox path" + N4 实施 |
| 旧 multi-task 路径被本 sprint 改动破坏 | 现役 pane 挂 | FR-9 不强制迁移 + Non-Goals 列 "do not kill existing tmux panes" ✅ |
| operator backend cmd 在 real mode 误执行 | 不可控副作用 | FR-1 daemon 默认 dry-run/smoke，real mode 需 explicit 许可 ✅ |
| Lint gate 误报 approved adapter | 开发被阻 | FR-7 显式 whitelist + N5 10 ALLOW 全部确认 ✅ |
| Persona 文件未来重命名导致 mapping 失效 | 派任务卡 | G1-G8 follow-up 含"persona file naming convention"（后续 sprint） |
| sprint 已 finalized 但 PRD schema fail → coordinator 拉回 | 链路循环 | 本切片即修复 ✅ |

## 开放问题 / Open Questions

- **OQ-01** 何时开始把现役 pane 迁移到 `operatord`？G1-G8 follow-up 提到 migration plan，但优先级未排。**Owner**：后续 migration sprint。
- **OQ-02** `operator_runtime.submit` 是否需要异步版（`asubmit`）？当前同步阻塞到 lease 到手。**Owner**：performance sprint。
- **OQ-03** Inbox 是 filesystem 还是 SQLite/queue？当前 N4 是 filesystem；并发量大时可能成瓶颈（与 lease broker sprint 的 OQ-04 同问题）。**Owner**：lease + inbox 升级 sprint。
- **OQ-04** 跨主机 operator（owner host `lisihao@100.122.223.55` 暗示有跨 host 场景）的 inbox 通过 SSH / shared FS / Tailscale？**Owner**：cross-host sprint。
- **OQ-05** Lint gate 用什么扫描工具？regex / AST / 已有 linter 扩展？需要在 follow-up sprint 决议是否扩到 IDE 实时提示。**Owner**：lint evolution。
- **OQ-06** `operator_naming.py` canonical id 与 lease-based sprint 的 `logical_operator` 是否需要 cross-reference？两者命名空间可能撞。**Owner**：runtime 协同 sprint。
- **OQ-07** Persona file 同时被多个 operator 引用时如何 versioning？persona 改动是否需要触发所有 binding operator 重启？**Owner**：persona lifecycle sprint。
- **OQ-08** evaluator-verification-protocol.md 与未来 OperatorScore 的 `SameProviderVerifierPenalty` 怎么协同？两套机制都强制 writer ≠ verifier。**Owner**：runtime 整合 sprint。

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD（含 6 原始节 + 本次补的 8 schema 必需节）。
- `<sid>.contract.md`、`<sid>.task_graph.json`。
- 实际 sprint 产出（PM 不动）：
  - `<sid>.N1-handoff.md` 到 `<sid>.N5-handoff.md`（5 节点 handoff）
  - `<sid>.finalized` 2026-05-22T21:00:56Z
  - 实施代码 `~/.solar/harness/lib/operator_runtime.py` + `tools/operatord.py` + `tools/operator_naming.py` + 3 个测试文件（N2/N3/N4 实施）
  - 最终报告 `~/.solar/harness/monitor-reports/operatord-runtime-submit.md`（N5 写出，11 节）
- 协同 sprint：`sprint-20260523-lease-based-model-fleet-runtime`（lease broker / OperatorScore / verification gate / actor profile）建在本 sprint 之上。

### 当前实施状态（已交付，回溯不重做）

| 功能 | 节点 | 状态 | 证据 |
|------|------|------|------|
| FR-1 operatord CLI daemon | N3 | ✅ | `tools/operatord.py` |
| FR-2 submit API + 5 类 rejection | N2 | ✅ | `lib/operator_runtime.py` + N5 §3 smoke 4 rejection paths |
| FR-3 Task envelope schema | N2/N3 | ✅ | envelope 含 verifier + cannot_use_same_operator |
| FR-4 Persona bank binding | N4 | ✅ | N5 §6 persona 10/10 + operator 12/12 mapping |
| FR-5 Canonical operator id | N3/N4 | ✅ | `tools/operator_naming.py` |
| FR-6 Pane title canonicalizer | N4 | ✅ | N5 §4 8 operator 4 vendor 全部正确 |
| FR-7 Lint gate ban tmux send-keys | N4 | ✅ | N5 §5 275 files / 10 ALLOW / 0 DENY |
| FR-8 Secrets 0-leak | 全 | ✅ | N5 §D3 grep 6 sensitive pattern 命中 0 substantive |
| FR-9 不动 multi-task | 全 | ✅ | N5 §7 G1-G8 follow-up 含迁移路径 |
| FR-10 最终报告 11 节 | N5 | ✅ | monitor-reports/operatord-runtime-submit.md |
| FR-11 PRD schema 合规 | 本切片 | 本切片即满足 | validate.sh prd → PASS |

### G1-G8 Follow-up Migration Gaps (来自 N5)

N5 已显式记录 8 个未完成迁移项（G1-G8），不在本 sprint 范围。Planner 在后续 sprint 中应按优先级排队：

- 现役 pane 迁移到 `operatord`（OQ-01）
- 跨主机 inbox 设计（OQ-04）
- Lint gate IDE 集成（OQ-05）
- canonical_id ↔ logical_operator 命名空间整合（OQ-06）
- Persona lifecycle / versioning（OQ-07）
- evaluator-verification-protocol ↔ OperatorScore 协同（OQ-08）

### 给 Coordinator 的明确指令

- **不要重做 sprint**：sprint 已 `.finalized` 2026-05-22T21:00:56Z；N5 verdict=**PASS with documented migration gaps G1-G8**（50/50 tests / persona 10/10 / operator 12/12 / lint 0 DENY / 0 secret leak）。Coordinator 当前拉回 `drafting/prd_ready` 仅为 gate_prd_schema 回溯副作用。
- **触发机制**：PRD mtime 已刷新；coordinator 下一 tick 重跑 `validate.sh prd` → PASS → 关闭 gate；识别 `.finalized` 后让 sprint 回到 passed，不要 advance 到 planner。
- **不动其他 artifact**：N1-N5 handoff / 实施代码 / monitor-report / task_graph。

### Knowledge Context

Knowledge Context: dispatch-embedded unified-context used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中)。

### Harness Modules Used

Harness Modules Used: harness-knowledge (dispatch-embedded unified-context block)。
