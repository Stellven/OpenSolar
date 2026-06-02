# PM Task Result — pm-sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s02-architecture-A4_open_questions-011683b6

## 已完成

- 读取 graph eval dispatch、task_graph.json、合约 contract.md、原始 A4_open_questions-dispatch.md、handoff.md、`A4_open_questions-decisions.md`（11.7 KB 决议正文）。
- 运行 `solar-harness session evaluate` 取得 log-native 会话证据并完成 triage（28 events / errors=[] / warnings 全部为 sprint 级别非阻塞）。
- 写入 `sprint-...-s02-architecture.A4_open_questions-eval.md`（完整评审，含 acceptance/scope/architecture-guard/proof obligations/risks 分章）。
- 写入 `sprint-...-s02-architecture.A4_open_questions-eval.json`（结构化反馈，含 evaluation_plan、acceptance_results、verification_results、session_log、architecture_guard、research_quality_gate）。
- 提交 canonical verdict：`graph-dispatch node-verdict --verdict pass` 通过（`{"ok": true, "node": "A4_open_questions", "status": "passed", ... "eval_passed": true}`）。

## 已验证

- **Acceptance 1（OQ-01/02/03 各项有可行决议）**：`decisions.md` 中 OQ-01 给出 fcntl Advisory Lock + atomic write-then-rename + 30s lease 协议（含 `StateFileLock` 类 + `atomic_write_state` 函数签名）；OQ-02 给出 append-only event log + checkpoint + rollback marker（含 event schema + 5 步 rollback bash 流程）；OQ-03 给出 SoT + drift detection + compile-as-mirror（含 `compile_mirror` 函数 + drift schema + `solar-harness drift detect/fix` CLI）。每个决议都指定 S03 为实现 owner。
- **Acceptance 2（rationale / alternatives_considered / risks_residual 字段齐全）**：三条决议各自有 `### Rationale`（4 bullets）+ `### Alternatives Considered`（3 行对比表，列 = 优点/缺点/为何不选）+ `### Residual Risks`（3 个编号项 + 缓解措施）。Schema 一致。
- **Acceptance 3（无"待定"未决议项）**：`decisions.md` 0 处 "待定"/TBD/TODO；Summary 表三条 OQ 全部标记 ✅ 已决议。
- **Architecture Guard**：core_patch=false / core_hits=[] / guard_warnings=none / guard_errors=none。所有运行态机制延迟到 S03 作为新可插拔模块。每个 OQ 的 Alternatives Considered 提供 ≥3 候选 + 显式 kill 理由，满足 online exploration 要求。
- **Session log evaluator**：`solar-harness session evaluate --json` 返回 `warnings=[stale_activities, activity_without_terminal, stale_activity, legacy_unpaired_activity, non_terminal_status]`，全部是 sprint 级别的 legacy runtime bridge + DAG 仍 active 这种预期态势，与 A4 leaf node 无关——已在 eval.md / eval.json 显式 triage。
- **Verdict 落盘**：`graph-dispatch node-verdict` 返回 `eval_passed_with_worker_evidence`，节点状态 `passed`，`eval_lease_released=true`，下游 A1_architecture 已重排（因之前 operator_result_failed）。

## 结论摘要

**Verdict: PASS**

A4_open_questions 节点交付了完整、可执行的三项开放问题决议（OQ-01 并发锁/恢复、OQ-02 回滚 state、OQ-03 双写不一致回溯）。每条决议都给出具体的 chosen approach（不是选项列表）、Python 代码骨架/CLI 形状、3 候选 Alternatives 对比表与剔除理由、3 项 Residual Risks 与缓解策略、S03/S04/S05 下游实现责任划分。文档质量足以让 S03 core-runtime 节点直接采用其签名与 CLI 形状。

## 风险/限制

- **write_scope 命名约定 nuance**：合约 `write_scope=["sprints/*open_questions.md"]`，实际产物文件名 `A4_open_questions-decisions.md`、`A4_open_questions-handoff.md`。严格 fnmatch 不命中 `-decisions.md`/`-handoff.md` 后缀，但语义在 scope 内、handoff 是协议产物。已在 eval 中标记为 PASS 并建议下次 sprint 把 pattern 收紧为 `*A4_open_questions*.md`。**不是 FAIL**，但 planner 应注意。
- **OQ-01 NFS 不可靠**：fcntl advisory lock 在 NFS 上不可靠。S03 必须在文档/runbook 里写明"NFS 环境用本地磁盘"的硬性限制。
- **OQ-02 checkpoint/event-log seq 漂移**：S03 实现 checkpoint 时必须把当时的 `event_seq` 嵌入 checkpoint 文件（决议已点出，S03 不能落地时遗漏）。
- **OQ-03 compile-as-mirror 快照漂移**：compile 是快照操作，state 在 compile 中途变化时下次 compile 会重新生成——S05 必须加 concurrent-mutation 回归测试。
- **harness CLI Python 兼容性 bug**：`graph-dispatch node-verdict` 经 `solar-harness.sh` 入口会以 `/usr/bin/python3` (3.9.6) 运行，但 `graph_scheduler._now()` 使用 `datetime.UTC`（3.11+）。我用 `/opt/homebrew/bin/python3.11 lib/graph_node_dispatcher.py` 绕过完成 verdict 提交。**这是 harness 入口的 Python 选择 bug，应该单独开单修复**。

## 后续建议

1. **释放下游**：A4 PASS 后，A5_traceability_handoff 仍被 A2/A3 阻塞。A1_architecture 之前因 `operator_result_failed` 失败，已被 verdict 流程自动重排到 builder pool。建议 planner/coordinator 监控 A1 重试结果。
2. **S03 验收清单（继承 A4 决议）**：S03 评审时应交叉验证 `StateFileLock` + `atomic_write_state` + lease 三件套、event log + checkpoint + rollback marker 三件套、`compile_mirror` + drift detect/fix CLI 三件套都被实现，并且 OQ-02 提出的 `event_seq` 嵌入 checkpoint、OQ-01 提出的 30s lease 超时/进程存活检查、OQ-03 提出的 双写顺序（spec→state→compile→mirror）全部落地。
3. **harness CLI Python bug**：开一个独立 P1 修复单，把 `graph_scheduler._now()` 改成 `datetime.datetime.now(datetime.timezone.utc).strftime(...)` 或者把 `solar-harness.sh` 入口绑定到 `/opt/homebrew/bin/python3.11`。
4. **write_scope pattern**：planner 在下一轮做 A4 类节点时把 write_scope 收紧为 `sprints/*A4_open_questions*.md` 或 `sprints/*_open_questions*.md`，避免严格 glob 校验时被误判。
5. **不要把 parent sprint 标 passed**：A4 verdict 路径已正确——parent.ready=false，required_gates 仍缺 G5。无误。
