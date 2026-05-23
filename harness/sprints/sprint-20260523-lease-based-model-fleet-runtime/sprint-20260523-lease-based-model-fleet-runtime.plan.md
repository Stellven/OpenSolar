# Plan — Lease-based Model Fleet Runtime 执行计划

sprint_id: `sprint-20260523-lease-based-model-fleet-runtime`
generated_at: `2026-05-23T10:45:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream: task_graph validated (5 nodes / 5 layers / 0 errors / 1 advisory warning on N1 which is already passed) · N1 passed · N2 reviewing with 5 addenda

## 1. 现状（不重写 task_graph）

| Node | 状态 | gate | 产物 |
|------|------|------|------|
| N1 architecture | ✅ passed | G_ARCH | `docs/lease-based-model-fleet-runtime.md` + `.N1-handoff.md` + `.N1-addendum.md` |
| N2 schema/config | 🔄 reviewing | G_SCHEMA | 5 schema/config 文件 + `.N2-handoff.md` + 4 addenda（context-store / logical-operators / capability-token / failure-fingerprint）|
| N3 lease broker + submit | ⏳ pending | G_LEASE | 待 |
| N4 status/bridge | ⏳ pending | G_OBSERVABILITY | 待 |
| N5 final report | ⏳ pending | G_REPORT | 待 |

N2 `monitor_blocker`: "previous N2 handoff incomplete after profile/logical-operator/evidence-ledger/context-store addenda; rerun required" — builder 必须把 5 addenda 合并主 handoff，evaluator 才能 review。

DAG validate: `{"ok": true, "node_count": 5, "errors": [], "warnings": [...]}`（1 advisory warning：N1 missing package_boundary；N1 已 passed，本 sprint 不修）

## 2. 交付切片顺序

| Wave | 节点 | 备注 |
|------|------|------|
| W1 | N1 | ✅ passed |
| W2 | N2 | 合并 5 addenda 到主 handoff → reviewer pass |
| W3 | N3 | lib/{actor_runtime, actor_lease, actor_mailbox, actor_profiles, logical_operator_router, operator_score, verification_gate, evidence_ledger, context_store, capability_token, failure_fingerprint}.py + tests |
| W4 | N4 | lib/multi_task_status.py + tools/monitor_bridge.py 增强 |
| W5 | N5 | monitor-reports/lease-based-model-fleet-runtime.md |

Linear DAG（5 layers，每层 1 节点）。

## 3. 文件级写入范围（已 task_graph 钉死）

详见 task_graph.json 每节点 `write_scope`。要点：

- N2: 5 个 schema (`agent-actors / actor-hosts / logical-operators / context-store / capability-token`) + 5 个 config + 5 个 test + N2-handoff
- N3: 11 个 lib/*.py + 11 个 tests/runtime/*.py + tests/test_*.py + N3-handoff
- N4: lib/multi_task_status.py + tools/monitor_bridge.py + tests/test_actor_observability.py + N4-handoff
- N5: monitor-reports/lease-based-model-fleet-runtime.md + N5-handoff

**严格禁止 write_scope 外**：
- ThunderOMLX 任何路径
- `~/.solar/STATE.md` / epic.* / 其他 sprint artifact
- `operatord-daemon-submit-production` / `claude-operator-billing-split` 任何文件
- Solar production hook / skill / prompt 任何文件
- 现有 `physical-operators.json`（仅 schema 兼容 adapter，不修原文件）

## 4. 并发边界

- linear DAG（N1→N2→N3→N4→N5）；同 pane 1 路
- max-parallel = 1（DAG 强制）

## 5. 每节点 handoff 段落契约（per Contract §Required Evidence）

每个 N*-handoff 必须含 13 项证据：

1. files changed
2. tests run + result
3. compatibility impact
4. tmux pane identity 仅作 host metadata 证据
5. task payload 入口 mailbox 证据（不通过 keystroke）
6. lease state 含 owner/TTL/heartbeat/renew/failure 证据
7. capability/risk/cost profile schema-validated 用于 routing 测试
8. 16 logical operator schema-validated 并 mapped to bindings
9. 改 binding 改 actor 不改 DAG 节点 证据
10. OperatorScore 含 HistoricalSuccess 并可由 local evidence 更新
11. verifier decision 机器可读 + gate DONE/PASS
12. policy block destructive / secret / git push / payment / unauthorized writes
13. secrets 未打印 + remaining migration risk

## 6. 验证命令

```bash
H=/Users/lisihao/.solar/harness
SID=sprint-20260523-lease-based-model-fleet-runtime

# A. DAG validate (已 ok)
~/.solar/bin/solar-harness graph-scheduler validate --graph $H/sprints/$SID.task_graph.json

# B. layers / ready
~/.solar/bin/solar-harness graph-scheduler layers --graph $H/sprints/$SID.task_graph.json
~/.solar/bin/solar-harness graph-scheduler ready --graph $H/sprints/$SID.task_graph.json

# C. N2 schema 齐全
for f in agent-actors actor-hosts logical-operators context-store capability-token; do
  test -f $H/config/$f.schema.json || echo "MISSING $f.schema.json"
  test -f $H/config/$f.json || echo "MISSING $f.json (except capability-token may be inline schema only)"
done

# D. N2 schema 测试
python3 -m pytest $H/tests/test_agent_actor_schema.py \
  $H/tests/test_logical_operator_schema.py \
  $H/tests/test_context_store_schema.py \
  $H/tests/test_capability_token_schema.py -q

# E. N3 lib 模块齐全
for m in actor_runtime actor_lease actor_mailbox actor_profiles logical_operator_router \
         operator_score verification_gate evidence_ledger context_store capability_token \
         failure_fingerprint; do
  test -f $H/lib/$m.py || echo "MISSING lib/$m.py"
done

# F. N3 测试套件
python3 -m pytest $H/tests/runtime/ -q
python3 -m pytest $H/tests/test_evidence_ledger.py \
  $H/tests/test_context_store_runtime.py \
  $H/tests/test_capability_token_runtime.py \
  $H/tests/test_failure_fingerprint_scoring.py \
  $H/tests/test_antigravity_placement_policy.py -q

# G. no-direct-tmux-send-keys lint
grep -nR "tmux send-keys" $H/lib/ $H/tools/ | grep -v "operatord run actor\." | grep -v "test_" \
  && echo "VIOLATION: tmux send-keys outside bootstrap" || echo "lint PASS"

# H. N4 status + monitor_bridge 含 actor 字段
~/.solar/bin/solar-harness multi-task status --no-clear 2>&1 | grep -E "actor_id|host_id|lease_state" | head -5
python3 -c "import json; d=json.load(open('$H/run/monitor-bridge/global.latest.json')); print('actor_fleet' in d, 'host_fleet' in d)"

# I. N4 测试
python3 -m pytest $H/tests/test_actor_observability.py -q

# J. N5 最终报告
test -f $H/monitor-reports/lease-based-model-fleet-runtime.md
grep -E "actor_id|lease|verification|migration" $H/monitor-reports/lease-based-model-fleet-runtime.md | head -5

# K. secrets 未打印
! grep -rE "(api[_-]?key|bearer|password|token|sk-)\s*[:=]\s*['\"][A-Za-z0-9]{8,}" \
  $H/run/agent-actors/ $H/monitor-reports/lease-based-model-fleet-runtime.md \
  $H/sprints/$SID.*.md 2>/dev/null

# L. ThunderOMLX 未碰
! git -C $H diff --name-only HEAD | grep -E "ThunderOMLX|thunderomlx"

# M. operatord-daemon / billing-split sprint 未碰
! git -C $H diff --name-only HEAD | grep -E "operatord-daemon-submit-production|claude-operator-billing-split"

# N. parent / chain 检查
~/.solar/bin/solar-harness graph-scheduler parent-check --graph $H/sprints/$SID.task_graph.json 2>&1 || true
```

## 7. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` 除 `operatord run <actor_id>` bootstrap
- 禁止 `solar-harness restart` / `solar-harness inject-prompt` / `solar-harness models switch`
- 禁止 kill / restart 任何现有 pane（无显式用户授权）
- 禁止改 `~/.solar/STATE.md` / epic.* / 其他 sprint artifact
- 禁止 block 或 rewrite `operatord-daemon-submit-production` / `claude-operator-billing-split` 任何文件
- 禁止 ThunderOMLX 任何修改
- 禁止 secrets 落盘任何 handoff / ledger / log
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 8. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做 FAIL 节点
- N2 五 addenda 未合并主 handoff → reviewer FAIL（monitor_blocker 已标）
- N3 任一具名 lib 模块缺失 → FAIL
- N3 OperatorScore 公式不含 HistoricalSuccess / 不可由 local evidence 更新 → FAIL
- N3 writer == verifier 测试不拒绝 → FAIL
- N3 capability token 默认允 secret / git push / 无限制 network → FAIL
- N3 premium actor 接 BULK_DOC_EDIT / TRIVIAL_RENAME / GREP_SCAN 测试不拒绝 → FAIL
- N4 status / monitor bridge 未含 actor_id / host_id / host_type / lease_state / billing_pool → FAIL
- N4 任一字段 emit prompt body / raw key / token / cookie / secret → FAIL
- DAG code 任何位置直调 `tmux send-keys` 传 task payload → FAIL + ATLAS
- pane index 当 durable scheduler key 写入 schema/test → FAIL
- writer 与 verifier 同一 actor 通过 critical PASS → FAIL
- 任何节点改 ThunderOMLX 路径 → FAIL + ATLAS
- 任何节点 block / rewrite `operatord-daemon-submit-production` / `claude-operator-billing-split` → FAIL + ATLAS
- 任何 handoff / ledger / log 含 secret 字面值 → FAIL + 立即删除
- 任何文档/代码用乐观词 → FAIL
- PRD/contract mtime 变化 → 本 plan 作废，重跑 planner

## 9. 模型路由建议（per task_graph preferred_operator_classes）

- N1 DeepArchitect + ResearchSynthesis（已 passed）
- N2 Implementation
- N3 Implementation + RootCauseDebug
- N4 Implementation + Verifier
- N5 Verifier (high)

## 10. 时间预算

- N1 已完成
- N2 reviewing → 合并 addenda → review pass：~30 min
- N3 11 模块 + 11 测试 + 多 acceptance：~3-4 hours
- N4 status + bridge + tests：~1 hour
- N5 final report：~1 hour
- 整 sprint 目标 1-2 个 dispatch round 内 passed（高复杂度）

## 11. 完成定义（DoD 7 条 + Contract §Done）

1. **已完成**：design.md / plan.md / planning.html 3 件（task_graph.json 已就位，本 plan 不重写）
2. **已完成**：task_graph.json validate ok（5/5/0/1 advisory）；N1 passed
3. **已完成**：planning.html 注册
4. **未验证**：N2 五 addenda 合并待 reviewer；N3/N4/N5 未启动
5. **未验证**：13 项 evidence 全集未由 evaluator 复跑
6. **风险**：
   - writer = verifier 漏检（plan §8 stop rule）
   - tmux send-keys 漏到 DAG path（plan §8 + lint）
   - secret 落盘 ledger（plan §8 + scrub）
   - premium actor 被批量耗（plan §8 cost gate）
   - parallel sprint 被误 block（plan §7 显式护航）
7. **后续待办**：
   - N2 builder 合并 5 addenda → reviewer PASS
   - N3 builder 实施 11 lib + 11 test
   - N4 builder 增强 status/bridge
   - N5 builder 产 monitor-reports/lease-based-model-fleet-runtime.md
   - evaluator 跑 §6 验证 A..N 全 PASS → sprint passed
   - PM 决定是否开下一 sprint（provider adapter 迁移 backlog）
