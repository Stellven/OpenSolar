# Implementation Plan — sprint-20260521-thunderomlx-knowledge-extract-smoke (Rev 2)

Knowledge Context: solar-harness context inject used

## Done 定义

本 sprint 是 state-repair sprint（N1 功能产出已存在，仅缺 graph 状态闭合）。以下 6 条全部满足才算完成：

- D1. `task_graph.json` 中 `nodes[].id=N1` 的 `status` 字段最终为 `passed`
- D2. `status.json` 中 `stage=completed` / `open_nodes=[]` / `completed_at` 非空
- D3. `graph-dispatch node-verdict` CLI 返回 `{"ok": true, "status": "passed"}`
- D4. `solar-harness graph parent-ready-check`（或等价）返回 `ready=true`
- D5. `.finalized` 文件不被破坏；Knowledge vault accepted artifact 路径不被改动
- D6. `N1-eval.md` + `N1-eval.json` 文件存在，PASS 判定与原 evaluator PASS (2026-05-23) 一致

## 现状分析

### Sprint 生命周期
1. 2026-05-21: 创建，N1 (knowledge extraction smoke) 分配给 multi-task worker
2. 2026-05-23 14:46: Evaluator PASS, coordinator finalized (`finalized` 文件创建于 2026-05-23 10:46:50)
3. 2026-05-24: accepted artifact 导出到 Knowledge vault (`accepted.md`, 1562 bytes)
4. 2026-05-26 17:56: graph_doctor `graph_doctor_repair_sync` 重新同步 task_graph
5. 2026-05-26 17:59: `graph_parent_ready_revoked` 撤销 ready 状态 → sprint 退回 active
6. 2026-05-26~27: coordinator 反复 dispatch (6+ 次 autoresearch_optimizer_recorded)，均未完成

### N1 状态
- task_graph 中 N1.status = `reviewing`
- handoff 已写: `sprint-20260521-...N1-handoff.md` — 内容完整
- 产出文件全部存在且非空:
  - `/Users/lisihao/.solar/harness/run/knowledge-extract-smoke/output/extracted-knowledge.md` (7846 bytes)
  - `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-knowledge-extract-smoke.md` (2736 bytes)
- N1 handoff acceptance criteria 全部满足:
  - backend=ThunderOMLX
  - local_model=Qwen3.6-35b-a3b
  - bad_chars=false
  - usage.json 有 input/output tokens
- accepted artifact 已入库: `/Users/lisihao/Knowledge/_raw/solar-harness/accepted/...accepted.md`
- 无 contract.md / design.md / eval.md — 走 legacy 通道

### 根因
graph_doctor 在 5/26 执行 `graph_doctor_repair_sync` 重新同步了 task_graph，然后撤销了 ready 状态。这导致 sprint 从 finalized 退回 active，N1 从 completed 退回 reviewing。兄弟 sprint `-rerun` 已按 `graph-dispatch node-verdict` 路径修复闭合。

### 核心问题
Sprint 已经实质完成（evaluator PASS + finalized + accepted artifact 导出），但 graph 状态不一致导致无法闭合。需要通过 sanctioned API 修复 graph 状态使 sprint 可以正常关闭。

## 变更文件

### 1. N1-eval.json (新建)
**路径**: `~/.solar/harness/sprints/sprint-20260521-thunderomlx-knowledge-extract-smoke.N1-eval.json`
**改动**: 新建，基于 N1 handoff 已验证证据 + accepted artifact 反填 verdict=PASS
**参考**: `-rerun` sprint 的 `.N1-eval.json` 结构

### 2. N1-eval.md (新建)
**路径**: `~/.solar/harness/sprints/sprint-20260521-thunderomlx-knowledge-extract-smoke.N1-eval.md`
**改动**: 新建，包含 verdict / evidence checked / acceptance result / risks

### 3. task_graph.json (通过 API 间接修改)
**路径**: `~/.solar/harness/sprints/sprint-20260521-thunderomlx-knowledge-extract-smoke.task_graph.json`
**改动**: 通过 `graph-dispatch node-verdict` API 将 N1 status 从 `reviewing` 改为 `passed`
**注意**: 禁止手改 task_graph.json 的 status 字段 — 使用 sanctioned API

### 4. status.json (API 副作用)
**路径**: `~/.solar/harness/sprints/sprint-20260521-thunderomlx-knowledge-extract-smoke.status.json`
**改动**: 由 `graph-dispatch node-verdict` 的副作用更新

### 5. task_graph.json evidence_policy (加分项)
**路径**: 同上 task_graph.json
**改动**: 加入 `must_use_sanctioned_api` + `forbid_direct_status_field_writes_on_task_graph` + `non_goals`（参考 `-rerun` sprint 已有的 evidence_policy）

## 技术方案

### 步骤

1. **验证 N1 产出完整性** — 确认 write_scope 文件存在且非空 (已验证: extracted-knowledge.md=7846B, monitor report=2736B)
2. **验证 acceptance criteria** — 确认 N1 handoff 中 4 条 criteria 全部满足 (已验证: ThunderOMLX, Qwen3.6, bad_chars=false, tokens logged)
3. **验证 accepted artifact** — 确认 Knowledge vault 中已有 accepted.md (已验证: 1562 bytes)
4. **写 N1-eval.json** — 基于 handoff 已验证证据，参考 `-rerun` 模板，4/4 ACs PASS
5. **写 N1-eval.md** — 人类可读 eval 报告，含 verdict / evidence / acceptance table / risks
6. **调用 `graph-dispatch node-verdict`** — 通过 sanctioned API 将 N1 标记为 passed:
   ```bash
   bash ~/.solar/harness/solar-harness.sh graph-dispatch node-verdict \
     --graph ~/.solar/harness/sprints/sprint-20260521-thunderomlx-knowledge-extract-smoke.task_graph.json \
     --node N1 \
     --verdict pass \
     --eval-json ~/.solar/harness/sprints/sprint-20260521-thunderomlx-knowledge-extract-smoke.N1-eval.json
   ```
7. **验证 D1-D6** — 逐条检查 Done 定义中的 6 项条件
8. **防再漂移检查** — 确认 node-verdict 写入后 task_graph 中 N1.status=passed 且 status.json 中 open_nodes=[]；确认 graph_doctor 下次 sync 不会重新打开

### 数据流
```
N1-eval.json + N1-eval.md (新建)
  → graph-dispatch node-verdict --verdict pass --eval-json
  → task_graph(N1=passed) + status(completed)
  → D1-D6 验证
```

## Non-goals

- 不触动 knowledge ingest 通道（status.json `knowledge_closure_required=true` / `knowledge_ingested_at=null` 由独立 vault dispatcher 处理）
- 不修改 Knowledge vault 中已导出的 accepted artifact
- 不破坏 `.finalized` 文件
- 不重跑 N1 知识抽取本身（功能产出已存在且验证）

## 风险点

1. **graph_doctor 再次同步覆盖** — node-verdict 写入后，如果 graph_doctor 基于其他字段判断不一致，可能再次 revoke。缓解: 步骤 8 确认 open_nodes=[] 后立即验证 parent-ready-check。
2. **node-verdict 命令失败** — 如果 eval.json 格式不符合 graph-scheduler 预期，命令会报错。缓解: 严格按 `-rerun` 模板的 schema_version 和字段结构编写。
3. **accepted artifact 一致性** — Knowledge vault 中已有 accepted artifact (5月24日导出)。状态闭合不应影响已入库数据。
4. **兄弟 sprint `-rerun` 已闭合** — 两个 sprint 独立闭合，方法一致但文件互不影响。

## 验证方法

1. `ls -la` 确认 write_scope 文件存在且非空 ✅ (已验证)
2. 读取 N1 handoff 确认 acceptance criteria 全部满足 ✅ (已验证)
3. `graph-dispatch node-verdict` CLI 返回 `{"ok": true, "status": "passed"}` (D3)
4. `jq .nodes[0].status` 确认 task_graph N1=passed (D1)
5. `jq .stage, .open_nodes` 确认 status.json stage=completed / open_nodes=[] (D2)
6. `.finalized` 文件 mtime 不变 (D5)
7. `N1-eval.md` + `N1-eval.json` 存在且 verdict=PASS (D6)
