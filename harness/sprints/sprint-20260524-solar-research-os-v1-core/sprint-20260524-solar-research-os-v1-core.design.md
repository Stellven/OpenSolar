# Architecture Design — sprint-20260524-solar-research-os-v1-core

Knowledge Context: `solar-harness context inject` 已执行；命中 solar-wiki / accepted sprint / harness 架构资料。结论与本地代码现状一致：Deep Research 底座已有 data plane、DAG、gate、status-server 雏形，但默认闭环、claim 级验证、单入口 closeout 仍未统一。
Role: 规划者 / research-compiler-design
Inputs consumed: requirement IR + compiled PRD/contract + local harness architecture + existing research runtime / graph scheduler / status server code
Design Stance: 本设计不重写 Solar，不再发明第二套 agent 框架；下一版必须复用现有 `physical operator + APO/optimizer + graph scheduler + evidence ledger + quality gate + status-server` 主链。
Source of Truth: `requirement_ir.json` 仍是需求真值；`task_graph.json` 是机器执行真值；`design.md` 负责解释为何这样切分。

---

## 0. 设计结论

Solar 下一版不做“更长输出 + 更多搜索源”的 Deep Research agent，而做一个 **claim-verified Research Compiler**：

```text
Research Intent
  -> Research Contract
  -> Logical Research Plan
  -> APO-scored Physical Plan
  -> Evidence / Claim / Figure Ledger
  -> Report Compiler
  -> Final Closeout Gate
  -> Repair DAG
```

核心差异不是模型更聪明，而是：

1. 关键句子必须能反查到 claim graph。
2. citation 只能从 ledger 渲染，不允许 model-generated citation。
3. high-impact claim 默认做 contradiction-first 检索。
4. closeout gate 只能有一个最终 verdict。
5. 近期窗口必须由 `task.started_at - 183 days` 动态计算。
6. report/figure/gate 失败时进入 repair DAG，而不是 silent degrade。

---

## 1. v1 Core 边界

### 1.1 必做

- P0 止血：修 deepresearch quality gate / closeout 回归，默认开启 evidence ledger、survey gate、final gate，禁止 model-generated citation。
- P1 核心编译链：ResearchTaskSpec、StateMachineRunner、SourceConnectorRegistry、Claim Compiler v2 seam、ContradictionSearch seam、Report Blueprint / Section Contract。
- P2 图表最小闭环：FigureSpec、architecture diagram、figure grounding、trend/timeline seams。
- P3 扩展缝：Delta-friendly artifacts、Lab/Memory contract、AI Infra pack seam，不在本 sprint 完整实现 runtime。

### 1.2 明确暂缓

- Full Research Console UI
- Global cross-run memory network
- Marketplace / domain pack marketplace
- Full human expert review workflow
- Full empirical benchmark lab runtime

---

## 2. 目标架构

```text
┌──────────────────────────────────────────────────────────────┐
│ Control Plane                                                │
│ contract -> logical plan -> APO plan -> DAG -> gate/repair   │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ Data Plane                                                   │
│ run/task/source/document/span/evidence/claim/figure/section  │
│ gate_result/report_artifact                                  │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ Operator Plane                                               │
│ acquisition / normalization / claim / contradiction / report │
│ figure / final gate / repair                                 │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ Artifact Plane                                               │
│ report.{md,html,pdf} / evidence_ledger / claim_graph         │
│ figure_bundle / quality_dossier / delta-ready manifest       │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. 代码落点与改造方向

| 模块 | 当前角色 | v1 Core 改造 |
| --- | --- | --- |
| `harness/lib/research/cli.py` | 线性入口、混合 provider 逻辑 | 收敛为 runner 入口，禁止自由生成 citation，接 task contract / report compiler |
| `harness/lib/research/state_machine.py` | 状态机雏形 | 升级为主执行链，替代直串函数 |
| `harness/lib/research/storage.py` | run/evidence 基础存储 | 将 ledger 默认改为 `required`，补 task/claim/figure/delta-friendly schema |
| `harness/lib/research/sources/` | connector 落地稀疏 | 新增统一 `SourceConnectorRegistry` |
| `harness/lib/research/evaluator.py` / `survey/*` | 混合真指标与 proxy 指标 | 抽成单入口 final closeout gate，区分 P0/P1/P2 |
| `harness/lib/graph_node_dispatcher.py` | graph closeout / repair 路径 | 强制 final closeout gate 挂入 finalize 路径 |
| `harness/lib/graph_scheduler_research.py` | research fan-out / write_scope 隔离 | 继续复用，但 DAG 需从“研究模板”升级成“实现 DAG” |
| `harness/status-server/research_routes.py` | research 可视化入口 | 暴露 figure/gate/claim summary 基础视图 |
| `harness/lib/operator_runtime.py` | operator runtime | 供 research physical operators 复用，不另起 agent runtime |
| `harness/tools/codex_pm_router.py` / `pm_dispatch.py` | requirement compile / sprint emit | 本次继续复用，planner 负责把 generic graph 收敛为 implementation graph |

---

## 4. 核心实体

v1 Core 至少把下面这些对象升成显式 contract：

- `ResearchTaskSpec`
- `SourceConnector`
- `Evidence`
- `Claim`
- `ClaimEvidenceEdge`
- `FigureSpec`
- `SectionContract`
- `ReportArtifact`
- `FinalCloseoutGateResult`
- `DeltaManifest`

最低要求：

1. `Claim` 不能再退化成“按句切分 + supports + 0.7”。
2. `FigureSpec` 必须先于 diagram render。
3. `FinalCloseoutGateResult` 必须是唯一 closeout verdict。
4. `DeltaManifest` 现在先落 schema，不要求完整 living report runtime。

---

## 5. 默认策略

```text
research.mode = deep_research
research.state_machine_required = true
research.evidence_ledger.default = required
research.citation.render_from_ledger_only = true
research.citation.allow_model_generated = false
research.survey_gate.default = required
research.final_closeout.required = true
research.freshness.dynamic_window_days = 183
research.repair.mode = auto_for_p1
```

---

## 6. 单入口质量门禁

v1 Core 不再接受“到处都有 gate，但没人负责 final verdict”的状态。

```text
FinalCloseoutGate
  -> EvidenceLedgerGate
  -> ClaimSupportGate
  -> CitationSpanGate
  -> FreshnessGate
  -> ContradictionCoverageGate
  -> FigureGroundingGate
  -> ReportCompletenessGate
```

输出三态：

- `pass`
- `repairable_fail`
- `hard_fail`

硬规则：

1. `run.finalized -> final_closeout_gate_result exists`
2. 关键 claim 无 direct evidence 时不得 closeout
3. 图表未 grounding 时不得作为正式报告输出

---

## 7. 本 sprint 结构

本 sprint 不直接追求“完整 Research OS”，而是打穿一条可执行主链：

```text
P0  默认可靠
P1  claim-verified compiler
P2  figure/architecture minimum viable path
P3  future seams for lab/memory/delta
```

每个 phase 都必须对应真实文件、测试、handoff 和 builder DAG 节点，不能只停留在口号。

---

## 8. 交付物

本次规划完成后，builder 主链应直接消费：

- [sprint-20260524-solar-research-os-v1-core.plan.md](/Users/lisihao/.solar/harness/sprints/sprint-20260524-solar-research-os-v1-core.plan.md)
- [sprint-20260524-solar-research-os-v1-core.task_graph.json](/Users/lisihao/.solar/harness/sprints/sprint-20260524-solar-research-os-v1-core.task_graph.json)
- [sprint-20260524-solar-research-os-v1-core.design.md](/Users/lisihao/.solar/harness/sprints/sprint-20260524-solar-research-os-v1-core.design.md)

并按 DAG 从 P0 开始推进，而不是再回到 raw request。
