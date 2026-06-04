# Design — ThunderOMLX 知识抽取 Smoke (graph 状态合规闭合)

sprint_id: `sprint-20260521-thunderomlx-knowledge-extract-smoke`
epic_id: null (standalone legacy sprint)
slice: `verification-and-graph-close`
role: planner
status: planning_complete
generated_at: 2026-05-27T18:17:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
upstream_prd: `sprints/<sid>.prd.md` (PM 5/27 18:05 回填)
sibling_sprint: `sprint-20260521-thunderomlx-knowledge-extract-smoke-rerun` (cache hit, 同款 4 节点修复模式已闭合 N1+N2)
no_live_pane_mutation: true (本 sprint 不动 tmux pane / 不重启 harness)

## 0. 切片边界

- **本 sprint 是 legacy standalone sprint 的 graph 状态合规闭合**：N1 功能产出已 finalized (2026-05-23 10:46 `.finalized` 文件)，但 graph_doctor 周期性 sync 把 sprint 从 finalized 退回 active；本 sprint 通过 4 节点修复模式让 sprint 正式 passed。
- **本 sprint 允许的写范围** (per task_graph 4 节点 write_scope):
  - `~/.solar/harness/run/knowledge-extract-smoke/output/` (N1 产物已存在, 不重写)
  - `~/.solar/harness/monitor-reports/thunderomlx-knowledge-extract-smoke.md` (N1 产物已存在)
  - `~/.solar/harness/sprints/<sid>.N1-handoff.md` (已存在)
  - `~/.solar/harness/sprints/<sid>.N1-eval.md` + `.N1-eval.json` (N2 已产出 5/27 13:02)
  - `~/.solar/harness/sprints/<sid>.N3-handoff.md` + `.N3-verdict-output.json` (待 N3 通过 CLI 产出)
  - `~/.solar/harness/sprints/<sid>.N4-handoff.md` + `.N4-drift-evidence.json` (待 N4)
  - `~/.solar/harness/sprints/<sid>.{prd,design,plan,task_graph,planning.html,handoff,traceability}.{md,json,html}` (sprint artifacts)
- **严格禁止**:
  - 真改 task_graph.json 中 N1.status 字段 (per N3 evidence_policy.forbid_direct_status_field_writes_on_task_graph)
  - 重跑 N1 功能 (产出已 .finalized)
  - 触动 Knowledge vault 已导出的 accepted artifact
  - 破坏 `.finalized` 文件 (2026-05-23 10:46)
  - 把 cooldown 当作最终修复 (per PRD non-goals)
  - 真调 ThunderOMLX / 真生产 DB / 真跑 yt-dlp (sprint 是 graph 闭合非功能复跑)
  - 改 sibling sprint `smoke-rerun` 任何 artifact
  - 触碰 live tmux pane / 重启 harness (per dispatch 步骤 11)

## 1. 现状摘要 (在写 design 前先核查事实)

| 维度 | 事实 (Python 直查 task_graph + status + ls 验证) |
|------|--------------------------------------------------|
| N1 status | passed (4 节点模式生效) |
| N1 功能证据 | handoff (959 字节, 2026-05-21) + extracted-knowledge.md + monitor-reports/thunderomlx-knowledge-extract-smoke.md |
| N1 acceptance | 5 条 (monitor report / extracted-knowledge / 中文+bad_chars=false / 127.0.0.1:8002 local route / handoff+reviewing) 全 satisfied |
| N1 cache_read | 0 (首次抽取 cache miss, 属预期；sibling smoke-rerun 才是 cache hit=6656) |
| N2 status | dispatched (N1-eval.md 7180 字节 + N1-eval.json 6622 字节 已落盘 5/27 13:02) |
| N3 status | 未启动 (等 N2 evaluator passed → 推 status=passed → 解锁 N3) |
| N4 status | 未启动 (等 N3 passed) |
| Gate | G_smoke_n1_closed_via_node_verdict = blocked |
| PRD | 已 backfill (5/27 18:05, 13.6 kB) |
| Plan | 已存在 (5/27 11:34, 6967 字节) |
| task_graph | 已存在 (5/27 16:17, solar.task_graph.v1, 4 节点, validate ok) |
| planning.html | 已存在 (5/27 12:18, 20976 字节) |
| .finalized | 仍存在 (2026-05-23 10:46, 0 字节) |
| Sibling smoke-rerun | N1 已 passed via 同款 4 节点模式 (跨 sprint 同源验证有效) |

## 2. 架构方案 (4 节点修复模式)

本 sprint 不实施任何新功能。架构 = 4 节点 graph 状态收敛模式 (与 sibling smoke-rerun 同款):

```
N1 (reviewing → passed)              已 passed
   │ (N1 功能产出保留, 不重跑)
   ↓
N2_eval_artifact_backfill           dispatched (eval.md/json 已落盘)
   │ (回填 graph 框架缺失的 eval 工件: verdict=PASS / evidence_paths / acceptance_check 5 条)
   ↓
N3_node_verdict_close                pending
   │ (调用 sanctioned CLI: graph-dispatch node-verdict --graph <path> --node N1 --verdict pass --eval-json <N1-eval.json>)
   │ (CLI 副作用: 推 task_graph N1.status → 解 gate blocked)
   ↓
N4_drift_guard                       pending
   │ (5 项校验: status_history_no_new_revoke / finalized_intact / accepted_artifact_intact_or_NA / parent_ready_check_ok / status_stage_completed)
   ↓
gate G_smoke_n1_closed_via_node_verdict → passed
sprint → completed
```

**为何串行**: N2 写 eval evidence → N3 用 eval 调用 CLI → CLI 推 N1.status=passed → N4 校验持久化。每步副作用必须在下一步可见才能继续。

**control plane vs data plane**:
- Control plane: graph-scheduler / coordinator / graph-dispatch CLI (推 status / 解 gate)
- Data plane: N1 输出文件 + N2 eval artifact + N3 verdict output + N4 drift evidence (只读校验, 不改上游)

## 3. 接口 / 决议 (复用 sibling smoke-rerun 决议, 同款修复模式)

| 决议 | 内容 |
|------|------|
| D1 (N1 保留) | 不重跑 N1 功能; 不写 N1.status; 信任 .finalized + accepted artifact 双信号 |
| D2 (N2 eval schema) | N1-eval.json schema = `solar.node_eval.v1` (含 sprint_id / node_id=N1 / verdict=PASS / verdict_reason / evidence_paths / acceptance_check / evaluator_signature / generated_at) |
| D3 (N3 sanctioned API) | 必须用 `solar-harness.sh graph-dispatch node-verdict`; 禁止手改 task_graph.json status 字段 (per PRD §约束) |
| D4 (N4 drift guard 5 项) | status.history / .finalized mtime / accepted artifact hash / parent-ready-check / status stage; 任一失败 sprint 不可 passed |
| D5 (cache miss 处理) | cache_read_input_tokens=0 是 cache miss baseline 属预期; N2 verdict 不能据此 negative (vs sibling smoke-rerun cache hit=6656) |
| D6 (sibling 同源验证) | sibling smoke-rerun 已通过同款模式 N1=passed; 本 sprint 跨 sprint 复用证据 (N3 CLI 可用) |

## 4. 失败恢复 / Stop Rules

- **N1 失败**: 不可能 (已 passed); 若 graph_doctor 再次 revoke → 进入 ATLAS structured repair, 不擅自手改
- **N2 失败**: 单节点重派; eval.md/json 已落盘 → evaluator 检查后推 N2.passed
- **N3 失败** (CLI 不存在或返回 ok=false): 立即记录 stderr + 触发 ATLAS structured repair; 禁止旁路 CLI 手改 task_graph
- **N4 失败** (任一 5 项校验不过): sprint FAIL; 不放过; 调查 graph_doctor 是否再次 revoke; 必要时升级到 sprint-20260527-p0-solar-harness-tui-pane-recover epic 治理
- **rollback / stop rule**:
  - 任一节点 FAIL → 不进下一节点
  - 不允许 cooldown 当作最终修复 (per PRD non-goals)
  - 不允许动 `.finalized` 或 accepted artifact 即使是 "修复"
  - 不允许跨 sprint 互动 (不动 sibling smoke-rerun)

## 5. 观测 / Evidence

- N1 evidence: handoff + 2 个产出文件 + status.history seq=eval_reviewed PASS @ 2026-05-23T14:44:50Z
- N2 evidence: N1-eval.md + N1-eval.json (5/27 13:02)
- N3 evidence (待): N3-verdict-output.json (CLI stdout/stderr/exit_code) + N3-handoff.md
- N4 evidence (待): N4-drift-evidence.json (5 项 JSON) + N4-handoff.md
- Sprint final evidence: handoff.md (聚合 N1-N4) + traceability.json + eval.md (sprint 整体)

## 6. 冲突 / 依赖 / 降级

**冲突**:
- 与 sibling smoke-rerun 共享 worker dispatch_id `mt-20260521-175309-...` → N3 用 `--graph <full-path>` 显式区分
- 与 graph_doctor 周期 sync → N4 drift_guard 检测无新 revoke 信号

**依赖**:
- N3 依赖 sanctioned CLI `solar-harness.sh graph-dispatch node-verdict` 存在且可用 (sibling 已实测)
- N4 依赖 graph parent-ready-check CLI 或等价 fallback `graph-dispatch list-ready --sprint <sid>`
- 所有节点依赖 `.finalized` + accepted artifact 不被外部进程改动

**降级**:
- N3 CLI 不存在 → ATLAS structured repair + dispatch ledger 写入失败原因
- N4 graph parent-ready-check 不存在 → 用 `graph-dispatch list-ready --sprint <sid>` fallback
- accepted artifact 字段缺失 → 标 N/A 并附 status.json 实际字段截图 (per N4 acceptance)

## 7. 非目标 (复用 PRD §非目标)

- 不绕过 planner 派 builder
- 不重跑 N1 (产出已存在)
- 不触动 Knowledge vault accepted artifact
- 不破坏 .finalized
- 不真改 task_graph N1.status (per CLI 强制)
- 不真调 ThunderOMLX API
- 不动 sibling smoke-rerun
- 不杀主 pane / 不重启 ThunderOMLX
- 不删用户数据
- 不动生产 DB
- 不实施新功能 (本 sprint 是 graph 闭合)

## 8. 给 epic / 系统的接力

- 本 sprint 是 standalone (无 epic), N4 passed 后 sprint 自动 completed; 不主动激活其他 sprint
- 长期建议: graph_doctor 应识别 `.finalized` + accepted artifact 双信号后停止 revoke → 写入 OQ-01 留给 epic `sprint-20260527-p0-solar-harness-tui-pane-recover` 治理
- N3 sanctioned CLI 在 sibling smoke-rerun 已实测 → 本 sprint 跨 sprint 复用证据可作为 system-level "graph close pattern" 模板

## 9. 与 dispatch 步骤 5.1 / 8 的对齐

dispatch 步骤 5.1 / 8 要求 task_graph 每节点必须含 `requirement_ids` + `acceptance_ids` 显式映射。Requirement IDs 取自 PRD §A1 5 outcome (O1-O5); acceptance IDs 取自每节点已有的 acceptance 数组索引。映射在下文 `task_graph.json` 补字段中明示。

## 10. Knowledge Context / Harness Modules

Knowledge Context: solar-harness context inject used (mirage degraded → QMD + Obsidian + Solar DB)
Harness Modules Used: harness-knowledge (context inject), harness-graph (sibling smoke-rerun 模式实测 + validate), harness-skills (knowledge-extractor profile), harness-ATLAS (N3/N4 失败兜底), harness-autopilot (autopilot_workflow_route_normalized 已在 5/27 18:06 跑过)
