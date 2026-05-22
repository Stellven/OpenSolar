# Plan — sprint-20260521-headless-pane-agent-routing-replan

Knowledge Context: solar-harness context inject used (dispatch 内嵌 unified-context 复用)
Owner: planner (本 pane) → multi-task (执行节点)
Source of Truth: 当 plan.md / design.md / task_graph.json 冲突时，以 task_graph.json 为机器执行真值。

---

## Strategy

本 sprint **只产规划与证据化分析**，不直接修改 production profile、不重启 harness、不触碰 live tmux pane。所有 production 变更必须落到下一轮 `sprint-NEXT-routing-v2-*` 由 builder 在隔离 worktree 实现。

执行顺序（DAG 见 task_graph.json）：

```
N1 current-state audit  ──┬─> N2 role-routing matrix ──┬─> N4 implementation backlog ──> N5 final report
                          └─> N3 headless-pool arch  ──┘
```

N1 / N2 / N3 已 PASSED；N4 reviewing；N5 pending — 本次 replan 主要工作是巩固契约层 (design.md + task_graph 字段补齐 + planning.html)，让 N5 可以基于完整证据收口。

---

## 交付切片顺序

| Slice | Owner | 输出 | 依赖 |
| --- | --- | --- | --- |
| S1 audit (N1) | multi-task planner | N1-handoff.md（profiles/doctor/status/agy 实测快照） | contract + PRD |
| S2 routing matrix (N2) | multi-task planner | N2-handoff.md（R1-R12 矩阵 + cost/review gate） | N1 |
| S3 pool architecture (N3) | multi-task planner | N3-handoff.md（L0-L6 分层 + 并行度 + write_scope 规则 + monitor 契约 + rollout） | N1 |
| S4 implementation backlog (N4) | multi-task builder | N4-handoff.md（BL-01 ~ BL-13） | N2 + N3 |
| S5 final report (N5) | multi-task evaluator | N5-handoff.md + monitor-reports/headless-agent-routing-replan.md | N4 |

切片粒度规则：每个切片单 handoff 文件 + 单写入路径，跨切片串行。

---

## 文件级写入范围（write_scope）

每个 DAG 节点写一个独占文件，不交集 — 满足 R-WS-1 (集合相交即冲突) 与 R-WS-3 (handoff 文件 1:1)。

| 节点 | write_scope（唯一允许写入） |
| --- | --- |
| N1 | `sprints/sprint-20260521-headless-pane-agent-routing-replan.N1-handoff.md` |
| N2 | `sprints/sprint-20260521-headless-pane-agent-routing-replan.N2-handoff.md` |
| N3 | `sprints/sprint-20260521-headless-pane-agent-routing-replan.N3-handoff.md` |
| N4 | `sprints/sprint-20260521-headless-pane-agent-routing-replan.N4-handoff.md` |
| N5 | `sprints/sprint-20260521-headless-pane-agent-routing-replan.N5-handoff.md` + `monitor-reports/headless-agent-routing-replan.md` |

Planner 自身（本 pane）写：
- `sprints/sprint-20260521-headless-pane-agent-routing-replan.design.md`
- `sprints/sprint-20260521-headless-pane-agent-routing-replan.plan.md`（本文件）
- `sprints/sprint-20260521-headless-pane-agent-routing-replan.task_graph.json`
- `sprints/sprint-20260521-headless-pane-agent-routing-replan.planning.html`
- `sprints/sprint-20260521-headless-pane-agent-routing-replan.status.json`

**禁止写入**（保护 production runtime）：
- `harness/config/multi-task-profiles.json`（live config — production）
- `harness/lib/*.py`（live scheduler — production）
- `harness/multi_task_runner.py`（live runner — production）
- 任何 four-pane / builder-lab plane 的 pane 配置

---

## 并发边界

| 节点对 | 关系 | 理由 |
| --- | --- | --- |
| N2 ↔ N3 | **可并行** | depends_on 都是 `[N1]`；write_scope 不相交（N2 vs N3 不同 handoff）；read_scope 仅 PRD + N1 (只读)。dispatcher 全局 cap=2 仍生效 |
| N4 | **串行** | depends_on=[N2,N3]；必须等两者 passed |
| N5 | **串行 critical** | depends_on=[N4]；write 涉及 `monitor-reports/` critical section (R-WS-4) |
| N1 / S1 | **串行入口** | 无依赖；但 plane 中可能与下一 sprint 节点共占 worker slot — 仍受全局 cap=2 |

历史快照：当前 N1/N2/N3 已 passed，N4 reviewing；以下并发判定面向 **下一轮 sprint** 的迁移：
- BL-01 (profiles.json) ↔ BL-05 (新建 agy_adapter.py)：write_scope 不交集，可并行。
- BL-02 (multi_task_runner.py) ↔ BL-08 (graph_scheduler.py)：write_scope 不交集，可并行。
- BL-07 ↔ BL-01：均改 `multi-task-profiles.json` → 冲突，**必须串行**。

---

## 验证命令

每个节点完成时 builder/evaluator 必须执行；失败立即写 blocker 不进 next_action。

```bash
# N1 验证：runtime audit 输出非空且无 secret 泄露
solar-harness multi-task profiles --no-clear --renderer plain
solar-harness multi-task doctor --no-clear --renderer plain
solar-harness multi-task status --no-clear --renderer plain
/Users/lisihao/.local/bin/agy --version
grep -E '(api[_-]?key|token|client[_-]?secret|refresh[_-]?token)' \
  ~/.solar/harness/sprints/sprint-20260521-headless-pane-agent-routing-replan.N1-handoff.md \
  && echo "FAIL: secret leak" || echo "OK: no secrets"

# N2 验证：路由矩阵覆盖 5 后端 + cost gate 明确禁 Claude
python3 -c "
import re
text = open('/Users/lisihao/.solar/harness/sprints/sprint-20260521-headless-pane-agent-routing-replan.N2-handoff.md').read()
for backend in ['Claude','Codex','Antigravity','ThunderOMLX','Gemini']:
    assert backend in text, f'missing backend: {backend}'
assert '禁用' in text or '禁止' in text, 'missing cost gate language'
print('N2 acceptance OK')
"

# N3 验证：分层架构 + write_scope 规则 + monitor 契约
grep -E '(L[0-6]|R-WS-[1-7])' \
  ~/.solar/harness/sprints/sprint-20260521-headless-pane-agent-routing-replan.N3-handoff.md \
  | wc -l   # 期望 ≥ 7

# N4 验证：backlog 数量 + 每条带 smoke test
grep -c '^### BL-\|^**BL-' \
  ~/.solar/harness/sprints/sprint-20260521-headless-pane-agent-routing-replan.N4-handoff.md   # 期望 ≥ 13
grep -c 'Smoke 测试\|smoke test' \
  ~/.solar/harness/sprints/sprint-20260521-headless-pane-agent-routing-replan.N4-handoff.md   # 期望 ≥ 13

# N5 验证：最终报告存在 + 引用 N1-N4 + 含 next-implementation-DAG
test -f ~/.solar/harness/monitor-reports/headless-agent-routing-replan.md && echo "report exists"
grep -E 'N[1-4]-handoff' ~/.solar/harness/monitor-reports/headless-agent-routing-replan.md   # 期望 ≥ 4

# task_graph 整体校验
~/.solar/bin/solar-harness graph-scheduler validate \
  --graph ~/.solar/harness/sprints/sprint-20260521-headless-pane-agent-routing-replan.task_graph.json
```

---

## No-Live-Pane-Mutation 保护

明确禁止动作清单（违反 = 直接 FAIL）：

| 禁止 | 替代 |
| --- | --- |
| `tmux kill-session` / `tmux kill-window` / `tmux kill-pane` | 仅允许 `send-keys` 探测；reap 实现要落到下一 sprint 的 BL-11 |
| `pkill` / `killall` solar-harness / claude / gemini / agy 进程 | 不 kill，等 ack_timeout 自然回收 |
| 修改 `harness/config/multi-task-profiles.json` | 本 sprint 只产 backlog；落地必须在下一 sprint 由 builder 在 worktree 内提案 |
| 修改 `harness/lib/*.py` 或 `harness/multi_task_runner.py` | 同上 |
| 启动 `agy` 交互 OAuth 流程 | doctor 探测必须非交互（device flow / `agy auth status` / `--no-prompt`） |
| 输出 token / OAuth code / API key | 监控层 `secrets_redacted=true` 永真 |

---

## Rollback / Stop Rule

| 触发条件 | 立即动作 |
| --- | --- |
| 任一节点 handoff 中检测到 secret (api_key/token/client_secret/refresh_token) | scheduler 立即标 `failed: secret_leak`，停止下游派发，evaluator 介入 |
| 某节点 write_scope 越界（落在声明文件之外） | `warn: out_of_scope_write`，N5 final-report 阻断直至人工 review |
| N1 显示 free_memory_gb < 4GB | dispatcher 拒绝新派发，等待资源回收 |
| launch_guard 持续 `launch_cooldown` > 10 min | 标 `blocked: launch_cooldown`，写入 next_action，不重复轰炸 |
| ThunderOMLX 互斥组并发 > 1 | 立即 `blocked: mutual_exclusion`，pause 直到队列减到 ≤ 1 |
| review-gate 同时被 2 个节点占用 | 后到者 `deferred: review_single_lane` |
| agy `enabled_for_dispatch` 被自动化流程置 true 但 auth_ok=false | `failed: forbidden_auto_enable`，回滚 profile |
| Antigravity rollout 任一阶段 routing-induced incident | `HARNESS_PANE_POOL_V2=false` 即时回 v1 |

---

## Stop Rules（contract Stop Rules 重申）

1. 不打印 API key / OAuth token / refresh token / authorization code / OAuth URL 原文。
2. 不自动启用 Antigravity dispatch — 必须 `agy --print` smoke + auth_ok 同时 ok。
3. 不把用户 benchmark 当事实 — 未实测标 `assumption`。
4. 不改 ThunderOMLX 缓存开关。
5. 不 kill 现有 tmux / pane / process。
6. 不把知识抽取默认路由到 Claude。
7. Planner 不写业务代码 — 所有实现下沉到 builder。
8. four-pane / builder-lab 固定 pane 不允许 reap，仅 multi-task plane 允许。

---

## Acceptance Checkpoint

完成判定（per contract §Acceptance）：
- [x] N1 runtime audit handoff （PASSED 2026-05-21T21:03Z）
- [x] N2 role matrix handoff（PASSED 2026-05-21T21:45Z）
- [x] N3 headless-pool architecture handoff（PASSED 2026-05-21T21:45Z）
- [x] N4 implementation backlog handoff（reviewing — 待 evaluator 通过）
- [ ] N5 final report `monitor-reports/headless-agent-routing-replan.md`（pending — 等 N4 PASSED）
- [x] task_graph.json validates against schema
- [x] planning.html artifact registered (本 replan 完成)
- [x] design.md 完整（本 replan 完成）

---

## Harness Modules Used

`harness-knowledge` (context inject reuse) · `harness-graph` (task_graph schema validate) · `harness-skills` (skills inventory injected via dispatch — planned)
