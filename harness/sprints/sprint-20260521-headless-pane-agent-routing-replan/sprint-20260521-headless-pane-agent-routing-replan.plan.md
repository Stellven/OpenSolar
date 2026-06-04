# Plan — sprint-20260521-headless-pane-agent-routing-replan

Knowledge Context: solar-harness context inject used (复用 dispatch 内嵌 `<solar-unified-context>`,命中以历史 sprint accepted 为主)
Role: 规划者 / execution-plan
Source of Truth: 三者冲突时以 `task_graph.json` 为机器执行真值;本文件仅人读执行说明,`design.md` 为架构说明。
Companion artifacts: `*.design.md` (架构), `*.task_graph.json` (DAG 真值), `monitor-reports/headless-agent-routing-replan.md` (N5 最终报告)

---

## 0. 本计划目的

把 Claude / Codex / Antigravity / Gemini / ThunderOMLX 五后端在 **角色 × 成本 × 风险 × 并行度 × gate** 上系统化为 dispatcher 可执行契约。本 sprint **只做规划/盘点/设计/backlog/报告**,不改 production profile、不动 live tmux、不启用 Antigravity,所有代码改造下沉到 next sprint 的 builder DAG。

---

## 1. DAG 与并行边界

```
Layer 0:  [N1]                      (runtime audit)            gate G_AUDIT
Layer 1:  [N2]  [N3]                (role matrix | pool arch)  gate G_MATRIX | G_POOL  ← 可并行
Layer 2:  [N4]                      (impl backlog)             gate G_BACKLOG
Layer 3:  [N5]                      (final report + next DAG)  gate G_REPORT
```

并行规则(graph-scheduler layers 已校验 `[N1]→[N2,N3]→[N4]→[N5]`):
- **N2 与 N3 可同批派发**:write_scope 互斥(各写自己的 `*.N2-handoff.md` / `*.N3-handoff.md`),无交集。
- N4 必须等 N2 **且** N3 都 passed 后才 ready(join gate)。
- N5 必须等 N4 passed;N5 写 `monitor-reports/headless-agent-routing-replan.md`,属 R-WS-4 critical section,最多 1 节点写。
- 全局 `max_parallel_recommendation=2`,任意时刻 active workers ≤ 2。

---

## 2. 节点验收 gate

| 节点 | 角色/模型 | gate | 关键验收 | write_scope |
|---|---|---|---|---|
| N1 | planner/opus | G_AUDIT | multi-task profiles + doctor/status + agy auth(不打印 secret) + 未验证项标 pending | `*.N1-handoff.md` |
| N2 | planner/opus | G_MATRIX | 矩阵覆盖 Claude/Codex/Antigravity/ThunderOMLX/Gemini;知识抽取默认**不**走 Claude;agy gated;复杂 debug/架构走 Claude/Codex | `*.N2-handoff.md` |
| N3 | planner/opus | G_POOL | 定义默认+per-backend 并行度、write_scope 冲突处理、status/monitor 输出契约、safe rollout/rollback | `*.N3-handoff.md` |
| N4 | builder/sonnet | G_BACKLOG | 列出 next sprint 待改文件、回归+smoke 测试、agy 保持 disabled、Gemini→Antigravity 迁移 | `*.N4-handoff.md` |
| N5 | evaluator/opus | G_REPORT | 最终报告含路由矩阵+pool 架构+证据路径+next implementation DAG,无 secret | `*.N5-handoff.md`, `monitor-reports/headless-agent-routing-replan.md` |

---

## 3. 强制 Stop Rules(摘自 design §8,dispatcher 必须执行)

1. 不打印 API key / OAuth token / refresh token / authorization code / OAuth URL 原文。
2. 不自动启用 Antigravity dispatch — `enabled_for_dispatch=true` 必须人工修改。
3. 用户提供 benchmark 未实测必须标 `assumption`。
4. 不改 ThunderOMLX 缓存开关。
5. 不 kill 现有 tmux session/pane/process;reap 仅限 multi-task plane。
6. 知识抽取不默认路由 Claude(违反 cost gate)。
7. ThunderOMLX / agy / glm-planner 不得独立通过 review-gate。
8. write_scope 缺失或空 → 拒派。
9. 不修改 four-pane / builder-lab 固定 pane 配置。
10. Planner 不写业务代码 — 实现全部落 task_graph 节点交 builder。

---

## 4. 当前执行状态(2026-05-29 复核)

- 全部 5 节点 handoff 已产出;N4/N5 已有 eval_json 且 `passed`;最终报告 `monitor-reports/headless-agent-routing-replan.md` 已存在(35KB);`.finalized` marker 存在(2026-05-21 23:13)。
- task_graph 校验 `ok=true, errors=[], warnings=[]`。
- parent-check `ready=false`:N1/N2/N3 节点 status 仍为 `reviewing`,对应 gate G_AUDIT/G_MATRIX/G_POOL 在 2026-05-28 被置 `blocked (waiting_for_shared_gate_nodes)`。
- 这是 **finalized 后的状态漂移(reopen drift)**,非规划缺口:下游 N4(依赖 N2,N3)与 N5 已 passed,逻辑上证明上游 handoff 已被消费。N1/N2/N3 为 planner-profile 节点,从未生成独立 eval_json,故停在 `reviewing`。

---

## 5. 后续 Implementation DAG(next sprint 蓝图,见 design §11)

- next: `sprint-NEXT-routing-v2-config-gates` — BL-01 profiles 加 `enabled_for_dispatch`;BL-02 dispatcher cost-gate + enabled pre-check。
- then: `sprint-NEXT-codex-agy-onboarding` — BL-03 codex profile;BL-04 agy-experimenter profile;BL-05 `lib/agy_adapter.py`;BL-06 doctor agy probe。
- later: write_scope prefix 锁、status renderer 字段扩展、Gemini PKCE 修复、stale pane reap、v2 feature flag shadow。

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge (context reuse), harness-graph (task_graph layers/parent-check validated)
