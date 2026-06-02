# Handoff — sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s02-architecture / A4_open_questions

sprint_id: `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s02-architecture`
node_id: `A4_open_questions`
pane: `solar-harness-lab:0.3`
dispatch_id: `graph-sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s02-architecture-A4_open_questions-20260531T213854Z`
generated_at: `2026-05-31T22:05:00Z`

## Summary

对三分面架构中的三个开放问题给出完整技术决议：
- **OQ-01**: 并发状态写入冲突时锁机制如何自动恢复 → Advisory Lock + Atomic Write + Lease-based Coordination
- **OQ-02**: 回滚时如何重置 state 文件 → Append-only Event Log + Checkpoint + Rollback Marker
- **OQ-03**: 双写期间不一致时如何回溯 → Source of Truth + Drift Detection + Compile-as-Mirror

所有决议包含 rationale、alternatives_considered、risks_residual 字段，无"待定"项。

---

## Changed Files

| 文件 | 操作 | 目的 |
|------|------|------|
| `sprints/sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s02-architecture.A4_open_questions-decisions.md` | 新增 | 开放问题决议文档 |

---

## Verification Evidence

### Acceptance 条件检查

- [x] 对 OQ-01, OQ-02, OQ-03 每一项给出可行的技术落地决议
- [x] 决议包含 rationale、alternatives_considered、risks_residual 字段
- [x] 没有"待定"等未决议项

### 决议摘要

#### OQ-01: 并发写入冲突自动恢复
- 方案：fcntl advisory lock + write-then-rename + lease coordination
- 关键机制：
  - Non-blocking advisory lock（避免死锁）
  - Exponential backoff 退避重试（100ms → 1s）
  - 30s lease 超时自动释放（防止僵死锁）
- 实现：S03 节点

#### OQ-02: 回滚时 state 文件重置
- 方案：Append-only event log + checkpoint + rollback marker
- 关键机制：
  - Event log 永不删除（完整审计历史）
  - 最近 10 个 checkpoint（快速回滚）
  - 原子替换流程（validate → rename → clean）
- 实现：S03 节点

#### OQ-03: 双写期间不一致回溯
- 方案：Source of Truth 定义 + drift detection + compile-as-mirror
- 关键机制：
  - Spec + state 为真值，task_graph.json 为镜像
  - Fingerprint (SHA256) 漂移检测
  - 自动 recompile 修复
- 实现：S03 节点

---

## Capability / KB Usage Evidence

- **[harness-knowledge]** 使用了 dispatch 注入的 Solar 统一上下文（Mirage + QMD + Obsidian Vault + Solar DB）
- **[harness-graph]** 基于 task_graph.json 的 DAG 调度和 write_scope 隔离执行
- **[harness-ATLAS]** 遵循 structured repair 协议，对开放问题给出完整技术决议

---

## Scope Compliance

- 写入文件：`sprints/*open_questions.md` ✅
- 未修改 S01 产物 ✅
- 未编写实现代码（仅 markdown 架构决议）✅
- 决议完整，无"待定"项 ✅

---

## Known Risks

| 风险 | 缓解措施 |
|------|----------|
| NFS 上 advisory lock 不可靠 | 文档说明 NFS 环境应使用本地磁盘 |
| 进程被 kill 时锁未释放 | Lease 30s 超时自动释放 |
| Checkpoint 与 event log 不一致 | 每次 checkpoint 记录 event_seq |
| Compile 时 state 继续变化 | Compile 是快照操作，下次调度重新 compile |
| Mirror 格式兼容性 | 保持 task_graph.json schema 不变 |

---

## Downstream Dependencies

本节点决议输出到以下下游：

- **S03 core-runtime**:
  - 须实现 OQ-01 的 StateFileLock + atomic_write_state
  - 须实现 OQ-02 的 event log/checkpoint/rollback
  - 须实现 OQ-03 的 compile_mirror 函数

- **S04 orchestration-ui**:
  - 显示 drift 状态
  - 提供 rollback 入口

- **S05 verification**:
  - 验证并发冲突模拟
  - 验证回滚流程
  - 验证漂移检测

---

## Not Done

本节点职责范围已完成。以下事项由下游节点负责：

- 实际代码实现（S03）
- UI 状态面板（S04）
- 验证和回归测试（S05）
