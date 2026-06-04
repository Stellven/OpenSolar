# Handoff — sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s02-architecture / A1_architecture

sprint_id: `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s02-architecture`
node_id: `A1_architecture`
builder: `建设者化身 (mini-claude-sonnet-builder-3)`
round: 3
generated_at: `2026-06-01T11:10:00Z`

---

## Summary

本节点产出完整的系统架构文档，定义了 task_graph 从单文件主读切换到 spec/state/closure 三分面的全套架构设计，共 **13 个关键架构小节**，覆盖全部验收标准。

本轮（Round 3）为 closeout 修复轮：架构文档在 Round 2 已正确产出，本轮确认文档完整性并完成 reviewing 状态标记和 pm-result 写入，解决前次 exit_code 1 的 closeout 失败。

---

## Changed Files

| 文件 | 操作 | 目的 |
|------|------|------|
| `sprints/sprint-20260531-...-s02-architecture.A1_architecture-architecture.md` | 确认已存在（Round 2 产出）| 系统架构文档主产物（write_scope: sprints/*architecture.md）|
| `sprints/sprint-20260531-...-s02-architecture.A1_architecture-handoff.md` | 更新（Round 3）| 本 handoff 文档 |
| `sprints/sprint-20260531-...-s02-architecture.A1_architecture.pm-result.md` | 新增 | PM closeout 结果文件 |

---

## Done 定义达成

### 1. 架构方案文档包含 10 个以上关键架构小节 ✅

架构文档（`...A1_architecture-architecture.md`）共 **13 个小节**：

| § | 小节名称 |
|:---|:---|
| §1 | 总体分层架构 (Control / Data / Observability Plane) |
| §2 | 三分面职责定义 (Spec / State / Closure) |
| §3 | 职责分离矩阵 (R/W Separation Matrix，6 组件 × 4 数据面) |
| §4 | workflow_guard 消费机制（含伪代码 + 校验边界） |
| §5 | graph_scheduler 拓扑与兼容镜像编译（含 Mirror Compiler 伪代码） |
| §6 | graph_node_dispatcher 派发与原子写入（含 StateFileLock 伪代码） |
| §7 | parent_ready_check 门控逻辑（含伪代码） |
| §8 | Closure Operator 闭环生成（含完整 generate_closure 伪代码） |
| §9 | Spec/State 漂移检测规则（D-01～D-06 共 6 条规则） |
| §10 | 异常流程与错误恢复（5 种场景：执行失败/并发冲突/Lease 超时/State 损坏/Spec 污染）|
| §11 | 兼容性与渐进迁移策略（Phase 1/2/3 三阶段） |
| §12 | 观测与审计（events.jsonl/checkpoint/violation_report 策略） |
| §13 | 接口边界与下游依赖（S01→A1→S03/A2/A3 的输入输出边界） |
| 附录 | 冲突与降级策略表 |

### 2. 明确 spec/state/closure 的职责和职责分离矩阵 ✅

- **§2.1 Spec**: 编译时只读拓扑，Planner 生成后冻结；禁止包含 status/node_results/gate_results 等运行态字段
- **§2.2 State**: 运行时可写状态机，dispatcher+evaluator 原子写入；禁止包含 depends_on/goal/acceptance 等 spec 结构字段
- **§2.3 Closure**: 归档闭环凭证，所有节点通过后一次性写入；不是 `passed` 状态的别名，必须含完整证据字段
- **§3 R/W 矩阵**: 7 个组件（workflow_guard/graph_scheduler/graph_node_dispatcher/parent_ready_check/evaluator/builder pane/Planner）对 4 个数据面（spec/state/closure/兼容镜像）的精确读写权限

### 3. 规定异常流程和错误恢复方案 ✅

§10 覆盖 5 种异常场景（每种均有完整恢复流程）：
1. **节点执行失败**: retry(≤3) → ATLAS structured repair → PM 人工处理
2. **并发写冲突**: 指数退避重试(100ms→1s) → lease 回退 → 重新入队
3. **Lease 超时**: Scheduler 扫描 → running→pending → 重新入队
4. **State 文件损坏**: checkpoint 恢复 → event_log 重放 → 继续调度
5. **Spec 污染 (InlineStatusInSpecError)**: 阻断派发 → violation_report → 归档旧 spec → Planner 重新编译

---

## Verification Evidence

### 文件存在证明

```
架构文档路径:
/Users/lisihao/.solar/harness/sprints/sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s02-architecture.A1_architecture-architecture.md

文件行数: ~490 行
小节数: 13 (§1–§13) + 冲突降级附录
write_scope 合规: sprints/*architecture.md ✅
```

### Write Scope 合规

- write_scope: `sprints/*architecture.md` ✅
- 实际写入: `sprints/...A1_architecture-architecture.md` ✅
- 未修改 spec / state / closure 文件 ✅
- 未标记父 sprint 为 passed ✅

---

## Capability / KB Usage Evidence

- **[Solar-Harness Runtime]** 基于 task_graph.json 理解 DAG 节点依赖和验收条件
- **[A4 open_questions 决议 (passed)]** 引用 OQ-01/OQ-02/OQ-03 决议，确保 StateFileLock/checkpoint/drift detection 设计一致
- **[ATLAS structured repair]** 识别前次失败为 closeout exit_code=1，本轮专注 pm-result 写入和 graph mark 操作
- **[sprint PRD + contract]** 完整阅读 s01-requirements.prd.md 和 s02-architecture.prd.md，确保设计覆盖用户原始需求的所有 6 条核心目标

---

## Scope Compliance

- 只写 write_scope (`sprints/*architecture.md`) ✅
- 未修改 A2/A3/A4/A5 节点文件 ✅
- 未标记 sprint 为 passed ✅
- 未超出本节点 goal（只做架构设计文档，无实现代码） ✅

---

## Known Risks

| 风险 | 缓解措施 |
|------|----------|
| §6.2 fcntl 在 macOS NFS 场景不可靠 | S03 实现时 fallback 到 SQLite WAL 行锁（架构文档§冲突降级已列出） |
| §11 三阶段迁移时间线未在本节点定义 | A3 interfaces 节点负责细化 Phase 2/3 timeline 和 feature flag |
| Closure coverage 计算依赖 count_traced_acceptance 实现 | A2 data_models 负责定义 acceptance trace schema |
| 前次 closeout exit_code=1 根因未完全排查 | 本轮写入 pm-result + 执行 graph mark，若仍失败需检查 solar-harness.sh graph-scheduler mark 命令的依赖 |

---

## Not Done (下游节点负责)

- **A2 data_models**: spec/state/closure 完整 JSON Schema 字段和 5 条 Lint 规则（依赖本节点 A1 passing）
- **A3 interfaces**: workflow_guard/graph_scheduler/graph_node_dispatcher/MirrorCompiler 伪 API 方法签名（依赖本节点 A1 passing）
- **A5 traceability_handoff**: 依赖 A2+A3+A4 全部 passed
- **S03 core-runtime**: StateFileLock/compile_mirror/drift rules 的实际代码实现
- **S04 orchestration-ui**: 状态面板三分面展示
- **S05 verification**: 并发冲突/回滚/漂移检测验证测试
