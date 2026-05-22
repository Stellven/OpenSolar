# Architecture Design — sprint-20260521-headless-pane-agent-routing-replan

Knowledge Context: solar-harness context inject used (复用 dispatch 内嵌 `<solar-unified-context>`，命中以历史 sprint accepted 为主，未提供新增技术证据)
Role: 规划者 / architecture-design
Inputs consumed: contract + PRD + N1 (runtime audit) + N2 (role matrix) + N3 (pool architecture) + N4 (backlog draft)
Design Stance: 本设计不写业务代码、不动 production profile、不重启 harness、不触碰 live tmux pane；所有变更通过 task_graph 节点分派给 builder 在隔离 worktree 落地。
Source of Truth: 当 design.md、plan.md、task_graph.json 之间出现冲突时，以 task_graph.json 为机器执行真值，design.md 仅作架构说明。

---

## 0. Problem Restatement

Solar-Harness 当前 tmux headless multi-task worker pool 把所有任务都视作"profile × pane × claude-cli/gemini-cli"的固定路由，导致：

1. **错配**：知识抽取、批处理这类"低价值高 token"的任务会落到 Claude opus/sonnet，烧钱。
2. **盲点**：Antigravity (agy) 已安装但 OAuth 未通过，profiles.json / doctor / matrix 三处零登记；调度器对这个能力完全不可见。
3. **回声室**：复杂架构 / 安全 review 没有 single-lane 保护，两个 opus reviewer 可能互相 ack 通过。
4. **假阳性**：Gemini doctor=ok 但 matrix probe=`e_challenge_method` error；当前 dispatcher 不分辨二者。
5. **stale**：multi-task plane 残留 6 个 observed/zsh pane，占槽位但无 active worker。

目标不是立即上线 Antigravity，而是把 Claude / Codex / Antigravity / Gemini / ThunderOMLX 五个后端在 **角色 × 成本 × 风险 × 并行度 × gate** 上系统化，形成 dispatcher 可执行的契约。

---

## 1. 顶层架构图（L0-L6 七层）

```
┌────────────────────────────────────────────────────────────────────┐
│ L6  Recovery        cooldown / stale-pane reap / circuit-break      │
├────────────────────────────────────────────────────────────────────┤
│ L5  Monitor         status renderer (plain|json|md) / safe_advance  │
├────────────────────────────────────────────────────────────────────┤
│ L4  Scheduler       DAG-aware + write_scope-aware + cost-gate +     │
│                     mutual_exclusion + enabled_for_dispatch         │
├────────────────────────────────────────────────────────────────────┤
│ L3  Plane / Pool    four-pane (4 fixed roles, 1 sprint at a time)   │
│                     builder-lab (4 slots, builder-only)             │
│                     multi-task (dynamic, cap≤2, reapable)           │
├────────────────────────────────────────────────────────────────────┤
│ L2  Gate            doctor probe + matrix end-to-end probe + auth   │
│                     + cost cap + review single-lane                 │
├────────────────────────────────────────────────────────────────────┤
│ L1  Backend Adapter claude-cli | gemini-cli | command | agy(future) │
│                     | codex-cli(future)                             │
├────────────────────────────────────────────────────────────────────┤
│ L0  Profile Registry multi-task-profiles.json                       │
│                     (11 现有 + codex-pm/builder + agy-experimenter) │
└────────────────────────────────────────────────────────────────────┘
```

层间硬契约（builder 实现时必须遵守）：

| 边界 | 契约 |
| --- | --- |
| L0→L1 | profile 必须显式声明 `backend`；adapter 不允许猜测后端 |
| L1→L2 | 每个 backend 暴露 `probe(profile_id) -> {ok\|warn\|error, evidence, secret_safe=true}`；禁打印 token |
| L2→L3 | 只有 `gate.ok && cost_gate.ok && enabled_for_dispatch` 同时为 true 的 profile 才可被 plane 接受 |
| L3→L4 | plane 暴露 `available_slots(profile) -> int`；scheduler 不直接 tmux send-keys |
| L4→L5 | 每次 dispatch/ack/complete 写入 monitor event；不可静默 |
| L5→L6 | monitor 检测 `ack_timeout / stale_task / launch_cooldown` 触发 recovery；recovery 限速 ≤ 1 reap / 5 min / plane |

---

## 2. Role × Backend 路由矩阵（v2）

合并 PRD §5.1 + N2 §B。"今日可派发"列严格基于 N1 §A profile probe 实测；"首选"列在落地 codex / agy 前必须显式 fallback。

| # | 任务类型 / 角色 | 首选 | 备用 | 今日可派发 | cost | risk | parallelism | 强制 gate |
|---|---|---|---|---|---|---|---|---|
| R1 | PM 协调 (pm coordinator) | Codex (待落地) | Claude `pm` (sonnet) | ❌ Claude `pm` 兜底 | M | M | 1 | codex profile 落地后切首选 |
| R2 | 架构 / 系统设计 (architect) | Claude opus | Codex GPT-5.5 | ✅ Claude `planner` | H | H | 1 | review-gate single-lane |
| R3 | 复杂 debug / root-cause (debugger) | Claude opus | Codex | ✅ Claude `planner` | H | H | 1-2 | review 必须 opus |
| R4 | 多文件实现 / 测试 / PR (builder) | Codex + Claude worker | Claude Code | ✅ Claude `builder` (sonnet) | M-H | M | 2-3 (write_scope 不冲突) | dispatcher 必须做 write_scope 交集检测 |
| R5 | 多路线并行实验 (experimenter) | Antigravity | Codex multi-agent | ❌ 暂不接此类任务 / Claude × ≤2 兜底 | M / H | M | 4+ (agy 启用后) | agy auth_ok && smoke_ok |
| R6 | Android / Firebase / GCloud (google-ecosystem-builder) | Antigravity | Gemini / Codex | ❌ 暂不接 | M | M | 1 (gated 期间) | agy gate4 或 Gemini PKCE 修复 |
| R7 | 知识抽取 / 批量总结 | ThunderOMLX | Gemini Flash/Lite | ✅ `knowledge-extractor` | **L** | L-M | 4-8 (本地资源限) | **cost-gate 强制禁用 Claude opus/sonnet** |
| R8 | cache / benchmark 粗活 | ThunderOMLX | Codex shell worker | ✅ `thunderomlx-benchmark` | L | L | 2-4 | 同 R7 |
| R9 | 最终评审 / 高风险 gate | Claude opus | Gemini / Codex reviewer | ✅ Claude `evaluator` | H | H | 1 | review-gate single-lane；禁 ThunderOMLX/agy 独立通过 |
| R10 | planner (DAG/合约编排) | Claude opus (今日) → Codex | glm-planner | ✅ Claude `planner` / `glm-planner` | M-H | M | 1 | glm-planner 仅用于轻量规划 |
| R11 | 长上下文整理 / 笔记 | ThunderOMLX | Gemini Flash | ✅ `thunderomlx-local` | L | L | 2-4 | 同 R7 |
| R12 | 安全审查 / token 敏感 | Claude opus (本地) | — | ✅ Claude `evaluator` | H | H | 1 | 禁 agy / gemini 远端处理 secret |

---

## 3. Antigravity Gated Rollout 状态机

```
state          installed  auth_ok  model_list  smoke_ok  enabled_for_dispatch
TODAY (N1):    true       false    unknown     false     false     ← 现状基线
gate1: install true       false    unknown     false     false     ← 已过
gate2: auth    true       true     pending     false     false     ← 目标 (P1)
gate3: list    true       true     true        false     false
gate4: smoke   true       true     true        true      true      ← 唯一启用条件
```

硬规则：
- `enabled_for_dispatch=true` 必须由 **人工** 在 profile 中修改，禁止任何自动化流程切换。
- doctor / matrix / status 任意一处显示 agy 之前，必须显式打印 `pending` 或 `warn`，不允许 false-ok。
- gate4 之前 dispatcher 必须拒绝把任何节点派给 `backend=agy`；fallback 路径见矩阵 R5/R6。
- auth 检测路径：device flow / `agy install` / service account 优先；交互 OAuth prompt 不算 ok（N1 §D 已记录 30s 超时基线）。

---

## 4. Pool 容量与互斥规则

### 4.1 全局容量

| 维度 | 限额 | 依据 |
| --- | --- | --- |
| 全局 active workers | ≤ 2 | task_graph metadata.max_parallel_recommendation=2 |
| Mac mini 内存预留 | free_memory_gb ≥ 4GB 才允许新派发 | N1: free_memory_gb=9.33；4GB 是 1×opus + 1×builder 经验下限（assumption） |
| four-pane plane | 4 固定槽 | sprint 主线，1 sprint at a time |
| builder-lab plane | 4 并行槽 | 但仍受全局 cap=2 限 |
| multi-task plane | 动态，cap ≤ 2 + reap 后 slot | N1: 当前 1 running + 6 observed/zsh 残留需 reap |

### 4.2 Per-backend cap

- claude-cli (opus): ≤ 2
- claude-cli (sonnet): ≤ 2
- claude-cli (glm-5.1 via z.ai): ≤ 2
- claude-cli (thunderomlx-local proxy): ≤ 1
- command (thunderomlx-benchmark / knowledge-extractor): ≤ 1
- gemini-cli: 0 (gated)
- agy: 0 (gated)
- codex-cli: 0 (profile 落地后再开)
- deepseek: 0 (key missing)

### 4.3 互斥组（mutual_exclusion_group）

- `thunderomlx-local`：成员 `knowledge-extractor / thunderomlx-benchmark / thunderomlx-local`，全局合计 ≤ 1 — 防本地 ThunderOMLX GPU 资源争抢。
- `gemini`：成员 `gemini-builder / gemini-evaluator`，gated 期间合计 = 0。
- `agy`：成员 `agy-experimenter` (新增)，gated 期间合计 = 0。

---

## 5. write_scope 冲突规则（R-WS-1 ~ R-WS-7）

| ID | 规则 | builder 落地点 |
| --- | --- | --- |
| R-WS-1 | 集合相交即冲突 | `lib/graph_scheduler.py:write_scope_conflict` 已实现 |
| R-WS-2 | 目录前缀锁 (`/foo/` ∩ `/foo/bar` = 冲突) | 同上函数补 prefix 处理 |
| R-WS-3 | handoff 文件 1:1 唯一 | scheduler dispatch 时校验 |
| R-WS-4 | `monitor-reports/*.md` critical section，最多 1 节点写 | 加 critical_path 配置 |
| R-WS-5 | write_scope 缺失或空 → 拒派 `error: missing_write_scope` | dispatcher pre-check |
| R-WS-6 | 冲突时按 `(priority desc, ready_at asc)` 串行化；禁止抢锁 | scheduler 排序 |
| R-WS-7 | ack 时校验实际写入文件是否越界 → `warn: out_of_scope_write` | dispatcher post-check，阻断 final-report |

---

## 6. Status / Monitor 输出契约

最小字段（per node）：

```
sprint_id, sprint_title, node_id, role, profile, backend, model,
status, updated_at, active_task, blocker, next_action,
safe_advance (bool), gate {doctor, matrix_probe, auth, cost_cap},
evidence_uri, secrets_redacted=true (always), oauth_status (enum)
```

聚合字段（per sprint）：`nodes_total/passed/failed/blocked, active_workers_live/max, free_memory_gb, launch_guard, tracked_tasks_warn, pane_inventory[plane], disabled_profiles[]`。

renderer：`plain` / `json` / `markdown` 必须共用同一 producer，禁止字段漂移。

---

## 7. Safe Rollout / Rollback

Feature flag：`HARNESS_PANE_POOL_V2`（默认 false）。

| 阶段 | 范围 | 进入门槛 | 回滚条件 |
| --- | --- | --- | --- |
| Phase 0 shadow | v2 dry-run，实际派发仍走 v1 | flag 切 false→true | 24h 内 schedule divergence ≥ 1 |
| Phase 1 knowledge-only | 仅 ThunderOMLX 系 profile 走 v2 | shadow 24h divergence=0 | ≥ 1 sprint failed |
| Phase 2 builder-lab | builder-lab plane 接 v2 | Phase 1 跑 ≥ 3 sprint，failed=0 | ≥ 2 sprint failed |
| Phase 3 full | 全量 v2 | Phase 2 跑 ≥ 5 sprint，routing-bug failed ≤ 1 | routing-induced incident |

回滚机制：`HARNESS_PANE_POOL_V2=false` 即时生效，scheduler 每次 dispatch 前 re-read flag；v2 events.jsonl 保留 24h 审计。

---

## 8. Stop Rules（强制）

contract Stop Rules + N3 forbidden 合并：

1. 不打印 API key、OAuth token、refresh token、authorization code、OAuth URL 原文。
2. 不自动启用 Antigravity dispatch — `enabled_for_dispatch=true` 必须人工修改。
3. 不把用户提供 benchmark 当事实，未实测必须标 `assumption`。
4. 不改 ThunderOMLX 缓存开关。
5. 不 kill 现有 tmux session / pane / process；reap 仅限 multi-task plane 且必须先 send-keys 探测。
6. 不把知识抽取默认路由到 Claude（违反 cost gate）。
7. 不允许 ThunderOMLX / agy / glm-planner 独立通过 review-gate。
8. write_scope 缺失或为空的节点拒派。
9. 任何阶段都不修改 four-pane / builder-lab 的固定 pane 配置。
10. Planner 不写业务代码 — 所有实现必须落到 task_graph 节点交给 builder。

---

## 9. 与 PRD Acceptance 对应

| PRD §6 / contract Acceptance | 本设计产出 | 状态 |
| --- | --- | --- |
| 角色路由矩阵 | §2 表 R1-R12 | ✅ 已 verified by N2 |
| Headless pool 分层架构 | §1 七层图 + §4 容量表 | ✅ 已 verified by N3 |
| Antigravity gated rollout | §3 状态机 | ✅ 已 verified by N2/N4 |
| Gemini CLI 迁移处理 | N4 BL-09 + §2 R6/R7 备用列 | 🟡 backlog 已写，待 builder 落地 |
| ThunderOMLX/Claude 边界 | §2 cost gate + §4.3 互斥组 | ✅ verified |
| Claude/Codex 分工 | §2 R1-R4/R9 | ✅ verified |
| 后续实现任务清单 | N4 BL-01 ~ BL-13 + task_graph N5 final-report | 🟡 待 N5 整合最终报告 |
| 所有节点 passed | N1-N3 passed, N4 reviewing, N5 pending | 🟡 进行中 |

---

## 10. 未验证 / Assumptions（必须以 `assumption` 标注后续传递）

| ID | 假设 | 来源 |
| --- | --- | --- |
| A1 | Claude opus high/xhigh 档位差异 | PRD §0 用户输入，未实测 |
| A2 | Codex GPT-5.5 可用性、配额、SDK | PRD §0，未实测；N1 验证 codex 0 profile |
| A3 | Antigravity 2.0 + Gemini 3.5 Flash 高并发吞吐 | PRD §0，未实测；N1 验证 agy v1.0.0 OAuth 超时 |
| A4 | thunderomlx-local proxy 推理质量与 proxy_model 一致性 | N1 仅校验配置，未发请求 |
| A5 | knowledge-extractor 历史失败率根因 | N1 §C 显示 5h 内 3× failed，未深挖 |
| A6 | per-backend parallelism 上限 | 基于 N1 §C 空闲槽位启发式，未压测 |
| A7 | gemini-cli `e_challenge_method` 根因 (PKCE config / CLI 回归) | N1 标 pending |
| A8 | free_memory_gb ≥ 4GB 启发式阈值 | N3 经验值，未做内存压测 |

---

## 11. 后续 Implementation DAG（next sprint 蓝图）

P0 (本 sprint 内可启动)：
- N5 final-report 节点：整合 N1-N4，产出 `monitor-reports/headless-agent-routing-replan.md`。

P0 (下一 sprint — `sprint-NEXT-routing-v2-config-gates`)：
- BL-01 profiles.json 加 `enabled_for_dispatch` 字段。
- BL-02 dispatcher 加 cost-gate + enabled_for_dispatch pre-check。

P1 (下下 sprint — `sprint-NEXT-codex-agy-onboarding`)：
- BL-03 codex profile 落地 (disabled)。
- BL-04 agy-experimenter profile 落地 (disabled)。
- BL-05 `lib/agy_adapter.py` 新建。
- BL-06 doctor.sh 加 agy probe。

P2：
- BL-07 profiles.json 加 cost_class + mutual_exclusion_group。
- BL-08 write_scope_conflict 补 R-WS-2 prefix 锁。
- BL-09 Gemini PKCE 修复或显式 deprecated。
- BL-10 status renderer 加 routing_version / safe_advance / gate 字段。

P3：
- BL-11 stale pane reap 实现。
- BL-12 v2 feature flag + shadow phase。
- BL-13 fail-rate 自动降级（knowledge-extractor）。

---

## 12. Sources & Evidence Paths

- `sprints/sprint-20260521-headless-pane-agent-routing-replan.contract.md`
- `sprints/sprint-20260521-headless-pane-agent-routing-replan.prd.md`
- `sprints/sprint-20260521-headless-pane-agent-routing-replan.N1-handoff.md` (runtime audit)
- `sprints/sprint-20260521-headless-pane-agent-routing-replan.N2-handoff.md` (role matrix)
- `sprints/sprint-20260521-headless-pane-agent-routing-replan.N3-handoff.md` (pool architecture)
- `sprints/sprint-20260521-headless-pane-agent-routing-replan.N4-handoff.md` (implementation backlog)
- `harness/config/multi-task-profiles.json` (live config baseline)
- `harness/schemas/task-graph.schema.json` (DAG schema)

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge (context inject reuse), harness-graph (task_graph schema), harness-skills (skills inventory inject via dispatch)
