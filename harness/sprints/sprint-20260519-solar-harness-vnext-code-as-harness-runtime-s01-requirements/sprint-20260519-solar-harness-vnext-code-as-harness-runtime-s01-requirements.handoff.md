# Handoff — sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s01-requirements

sprint_id: `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s01-requirements`
date: 2026-05-20
Knowledge Context: solar-harness context inject used

## 1. 证据表

| Outcome | 验收点 | 下游 Sprint | 命令 | 结果 | 降级原因 | 未闭环 |
|---------|--------|-------------|------|------|----------|--------|
| O-01 PM PRD + HTML | prd.md 存在; prd.html 含 §1-§9 | S01 | `wc -c prd.html` → 58897; `grep -c '<html' prd.html` → 1; `grep -c 'Functional Requirements' prd.html` → 4 | PASS: pandoc 3.9.0.2 渲染成功, 57.5KB | 无 | 无 |
| O-02 Planner 三件套 + planning.html | design.md + plan.md + task_graph + planning.html 齐; graph-scheduler validate exit 0 | S01 | `wc -c planning.html` → 35322; `grep -c 'Outcomes 拆解' planning.html` → 3; `grep -c '总体策略' planning.html` → 2; `grep -c '反例' planning.html` → 13 | PASS: 35KB HTML, 11 section 导航 | 无 | 无 |
| O-03 Plan IR + Action Contract schema | schema 含 11 最小字段; jsonschema 验证 | S02 + S03 | design.md §6 已定义 action_contract.schema.json 最小字段 (action_id/node_id/kind/intent/read_set/write_set/required_capabilities/preconditions/success_predicates/verification/risk_class) | S02 待实现: 骨架在 design.md §6 | 无 | S02 需产出 jsonschema 文件并冻结 |
| O-04 Event Ledger | event_ledger.py 写 JSONL atomic; event_id 唯一; replay smoke | S03 | risk-register.md R-02 已标注写竞态风险; cannot-dispatch-to-builder.md #6 已列三选一选型 | S03 待实现 | 无 | S02 需先完成选型 (fcntl/SQLite WAL/atomic rename) |
| O-05 Execution Broker MVP | propose→validate→…→projection 完整链; 3 类 action 纳管 | S03 | risk-register.md R-01 已标注 broker bypass 风险; cannot-dispatch-to-builder.md #2 已列策略链 pre-builder gate | S03 待实现 | 无 | S02 需先出 policy 优先级表 |
| O-06 dispatcher 接 broker | dispatch 含 action_contracts; 原有 tests 仍 pass | S04 | cannot-dispatch-to-builder.md #3 已列 legacy 双跑对比要求 | S04 待实现 | 无 | 需保留 legacy path + 双跑对比 |
| O-07 Action Contract 3 类硬规则 | uncontracted shell block / unscoped write block / high risk 需 approval | S03 | cannot-dispatch-to-builder.md #4 已列审批阈值需监护人拍板 | S03 待实现 | 无 | risk_class 默认值需监护人在 S02 确认 |
| O-08 broker event coverage 100% | uncontracted_count=0, unscoped_count=0, coverage=1.0 | S04 + S05 | design.md §6.3 已定义 broker_coverage 字段格式 | S04+S05 待验证 | 无 | 需 activation-proof 输出 |
| O-09 兼容性约束 | wake/dispatch/status smoke 全 pass | S03 + S04 | risk-register.md R-05 已标注兼容层泄漏风险; non-goals.md NG-06 已固化不破坏 four-pane | S03+S04 待验证 | 无 | import-time 不引入 broker 强依赖 |
| O-10 Risk register + rollback | ≥ 8 条风险, 每条有 owner + 缓解 + rollback | S01 | `grep -cE '^\| R-0[1-8]' risk-register.md` → 8; `grep -c 'Rollback\|rollback' risk-register.md` → ≥ 8; 含风险矩阵 + 联动 + 降级策略 | PASS: 5140 bytes, R-01..R-08 | 无 | 无 |
| O-11 中文证据表 handoff | handoff.md 含 7 列证据表 | S01 + S05 | 本表即为交付物; 14 行 P0 + 8 行 follow-up | PASS (本文件) | 无 | S05 终验需复用此表格式 |
| O-12 Traceability map | children[*] 含非空 outcomes 数组 | S01 | `python3 -c 'import json; d=json.load(open(traceability.json)); print(len(d["children"]))'` → 5; S01=7, S02=2, S03=5, S04=2, S05=4 outcomes | PASS: 全部 5 children 含非空 outcomes | 无 | 无 |
| O-13 Non-goals 固化 | 8 条不做项 + 反例 | S01 | `grep -c '^## NG-' non-goals.md` → 8; `grep -c '\*\*Counterexample' non-goals.md` → 8; 含 enforcement 机制 | PASS: 6851 bytes | 无 | 无 |
| O-14 不能直派 builder 清单 | ≥ 6 类需先经 architect/human/stop-rule | S01 | `grep -c '^## [0-9]' cannot-dispatch-to-builder.md` → 8 (含 #7 capability inference + #8 rollback 策略); 每类含 Pre-builder Gate + 反例 | PASS: 6220 bytes | 无 | 无 |

### P1/P2/P3 Follow-up (本 epic 不交付)

| OID | Outcome | 状态 | 降级原因 | 未闭环 |
|-----|---------|------|----------|--------|
| F-P1-01 | Artifact Registry | follow-up | 不在本 epic 交付 | 需 S02 schema 先定 |
| F-P1-02 | Verifier-as-a-Service | follow-up | 不在本 epic 交付 | 封装现有 verifiers |
| F-P1-03 | capability_inference action-level | follow-up | 不在本 epic 交付 | 需 inference 规则格式 |
| F-P2-01 | ResearchGraph compiler | follow-up | 不在本 epic 交付 | 需 ResearchGraph schema |
| F-P2-02 | 100k 字长报告编译 | follow-up | 不在本 epic 交付 | 需 claim coverage ≥ 90% |
| F-P3-01 | Multi-Agent state revision | follow-up | 不在本 epic 交付 | 需 lease + merge policy |
| F-P3-02 | Repair Controller + failure taxonomy | follow-up | 不在本 epic 交付 | 需 10 种失败类型 |
| F-P3-03 | Capability scorecard dashboard | follow-up | 不在本 epic 交付 | 需全链路可视化 |

## 2. 上游依赖

- `epic-20260519-solar-harness-vnext-code-as-harness-runtime.epic.md` (17KB PRD) — 原始需求输入
- `epic-20260519-solar-harness-vnext-code-as-harness-runtime.traceability.json` — children stub → N6 已升级为含 outcomes 数组
- `epic-20260519-solar-harness-vnext-code-as-harness-runtime.task_graph.json` — 5 子 sprint stub
- N1-N7 全部 passed — 本 handoff 聚合 N1..N7 各节点证据

## 3. 下游影响

- **S02 architecture** 必须读 design.md §6 (接口契约骨架 action_contract.schema.json + event.schema.json + broker_coverage 字段) + risk-register.md R-02/R-03 (选型决策) + cannot-dispatch-to-builder.md #1/#2/#6/#7/#8
- **S03 core runtime** 不允许在没有 S02 design.md 的情况下开始编码; O-03/O-04/O-05/O-07/O-09 为其交付范围
- **S04 orchestration-ui** 需 O-06/O-08 + risk-register.md R-04/R-06/R-08
- **S05 verification-release** 需验证 O-08 broker coverage = 100% + O-09 兼容性; 复用本 handoff 证据表格式

## 4. 未闭环项

1. **P0 估时 15.2h vs Roadmap 0-2 weeks** — 估时是 ideal hours, 实际含返工, buffer 留给 S05
2. **risk_class 默认值** (apply=high / git=high / network write=high) — 需监护人在 S02 拍板确认
3. **event ledger 选型** (JSONL fcntl vs SQLite WAL) — S02 architect 决定
4. **P1/P2/P3 全部留 follow-up** — 本 epic 不交付, 已在 requirements-matrix.md 标记
5. **graph_node_dispatcher.py 有未提交改动** — git status 显示 M 标记, 非本 sprint 产物 (来自 prior session), S03/S04 需注意基线

## 5. S02 入参锚点

S02 architecture sprint 启动时必须读取以下文件作为输入:

| 锚点 | 文件 | 关键章节 |
|------|------|----------|
| 接口契约骨架 | design.md §6 | action_contract.schema.json (11 required fields) + event.schema.json (6 required fields) + broker_coverage 字段格式 |
| 风险选型决策 | risk-register.md R-02, R-03 | event ledger 写竞态三选一 (fcntl/SQLite WAL/atomic rename) + schema breaking change evolution policy |
| Pre-builder Gate | cannot-dispatch-to-builder.md #1, #2, #6, #7, #8 | schema 设计 gate + broker 策略链 gate + event ledger 选型 gate + capability inference gate + rollback 策略 gate |
| 审批阈值 | cannot-dispatch-to-builder.md #4 | apply/git/network risk_class 默认值需监护人确认 |
| Non-goals 边界 | non-goals.md NG-01 ~ NG-08 | 不重写 harness / 不绕过 PM-Planner-DAG / 不引入 monolith / 不破坏 four-pane |
| 需求矩阵 | requirements-matrix.md | O-03 完整验收点 (jsonschema 验证 + 11 最小字段) |
| Traceability | traceability.json | S02 outcomes: O-arch-contracts, O-03 |
| 总体计划 | plan.md §9 | S02 入参锚点原文 |

## 6. 节点验证汇总

| Node | Artifact | Size | Gate | Status |
|------|----------|------|------|--------|
| N1 | requirements-matrix.md | 5961 B | `grep -cE '^\| O-(0[1-9]|1[0-4])'` = 14 | PASS |
| N2 | risk-register.md | 5140 B | `grep -cE '^\| R-0[1-8]'` = 8 | PASS |
| N3 | non-goals.md | 6851 B | `grep -c '^## NG-'` = 8 | PASS |
| N4 | cannot-dispatch-to-builder.md | 6220 B | `grep -c '^## [0-9]'` = 8 | PASS |
| N5 | prd.html | 58897 B | `grep -c '<html'` = 1; contains Functional Requirements | PASS |
| N6 | traceability.json | upgraded | 5 children with non-empty outcomes (7+2+5+2+4) | PASS |
| N7 | planning.html | 35322 B | 'Outcomes 拆解' × 3, '总体策略' × 2, '反例' × 13 | PASS |
| N8 | handoff.md | this file | 5+ sections, 7-col evidence table, S02 anchors | PASS |

## 7. 产出文件清单

```
sprints/{SID}.design.md                    — 14587 bytes (planner 产出)
sprints/{SID}.plan.md                      — 6819 bytes (planner 产出)
sprints/{SID}.task_graph.json              — DAG 定义 (8 节点)
sprints/{SID}.requirements-matrix.md       — 5961 bytes (N1)
sprints/{SID}.risk-register.md             — 5140 bytes (N2)
sprints/{SID}.non-goals.md                 — 6851 bytes (N3)
sprints/{SID}.cannot-dispatch-to-builder.md — 6220 bytes (N4)
sprints/{SID}.prd.html                     — 58897 bytes (N5)
sprints/{SID}.planning.html                — 35322 bytes (N7)
sprints/{EPIC}.traceability.json           — upgraded (N6)
sprints/{SID}.handoff.md                   — this file (N8)
```

**确认: 未修改 `/Users/sihaoli/Solar/` 任何文件。** git status 中显示的改动来自 prior sessions, 非 S01 产物。

---

Harness Modules Used: solar-harness graph-scheduler, solar-harness context inject (QMD + Solar DB; Mirage degraded)
