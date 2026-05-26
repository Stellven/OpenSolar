# 交接 — Solar-Harness功能开发 / 2026-05-25

## 核心架构纠偏
Browser Agent 不是 Deep Research OS 的私有外部能力层。Browser Agent 必须是 solar-harness 全局 Physical Operator Fleet 的一等执行资源，可被任意 DAG / logical_operator 调度。Deep Research OS 只是它的高价值消费方之一。

禁止：不允许 Deep Research OS 私有调用 Browser Agent；不允许另起第二套 Browser/DeepResearch 系统；不允许 DAG 硬编码 model=gemini/chatgpt；不允许日志写 cookie/token/OAuth/header/session secret。

## 已完成
1. RawIntent 编译路由 bug 已修复并 push：`b4dd6cf8 Fix RawIntent compiler routing for operator specs`，branch `codex/capsule-proof-adapter-runtime`。
2. Browser Agent Research Operators sprint 已推进：N1/N2/N3/N4 passed；N5/N7 reviewing；N6/N8 pending。
3. 新增全局 Browser Agent cutover 需求单和 graph，明确 Browser Agent 是 global physical operator，Deep Research OS 是 consumer。

## 当前 Browser Agent sprint
Graph: `/Users/lisihao/.solar/harness/sprints/sprint-20260525-browser-agent-research-operators.task_graph.json`

```text
N1 passed     需求/架构设计
N2 passed     registry/schema/logical_operator config
N3 passed     async job protocol + mock/dry-run adapter
N4 passed     session/auth broker + capability-token policy + secret scrub
N5 reviewing  routing/fallback + monitor bridge observability
N6 pending    focused tests/lint gate
N7 reviewing  playbook / re-login / evidence ledger docs
N8 pending    final verification + rollout report
```

验证证据：N2 246 passed；N3 18 passed + runtime 91 passed；N4 14 passed + runtime 99 passed。

N5/N7 已有 handoff，待独立验证后 mark passed。

## Global cutover sprint
Addendum: `/Users/lisihao/.solar/harness/sprints/sprint-20260525-browser-agent-research-operators.global-operator-addendum.md`
Requirements: `/Users/lisihao/.solar/harness/sprints/sprint-20260525-browser-agent-global-operator-cutover.requirements.md`
Graph: `/Users/lisihao/.solar/harness/sprints/sprint-20260525-browser-agent-global-operator-cutover.task_graph.json`

当前状态：
```text
N1 failed  因 Claude/Sonnet quota limit
N2 pending
N3 pending
N4 pending
N5 pending
N6 pending
```

N1 失败原因：
```text
You've hit your limit · resets May 27 at 1am (America/Toronto)
backend=claude-cli model=sonnet exit_code=1
```

这说明 quota-aware fallback 仍有 bug：N1 是只读审计任务，不应该卡死在 Sonnet quota 上，应该 fallback 到 Gemini/Antigravity/local auditor。

## 当前 dirty files
```text
M harness/config/actor-hosts.json
M harness/config/agent-actors.json
M harness/config/logical-operators.json
M harness/config/logical-operators.schema.json
M harness/config/physical-operators.json
M harness/lib/capability_token.py
M harness/lib/logical_operator_router.py
M harness/lib/multi_task_runner.py
M harness/lib/operator_runtime.py
M harness/lib/operator_score.py
M harness/tests/conftest.py
M harness/tests/runtime/test_logical_operator_router.py
M harness/tests/test_logical_operator_schema.py
M harness/tests/test_operator_status_observability.py
M harness/tests/test_schemas.py
M harness/tools/monitor_bridge.py
?? harness/docs/browser-agent-operator-playbook.md
?? harness/lib/browser_job_runtime.py
?? harness/tests/runtime/test_browser_agent_operator.py
?? harness/tests/runtime/test_browser_fallback_observability.py
?? harness/tests/runtime/test_browser_security_policies.py
```

不要提交，直到 N5/N7/N6/N8 都验证完。

## 接手执行顺序
1. 验证 N5/N7 handoff，跑相关 tests，通过后 mark passed。
2. 启动 N6，完成测试/lint gate。
3. 启动 N8 final verification，生成 rollout report。
4. 统一 commit/push 当前 Browser Agent sprint。
5. 修复/重派 global cutover N1：不要用 Sonnet，改用 Antigravity/Gemini/local evaluator fallback。
6. N1 pass 后推进 N2-N6，实现 Browser Agent global cutover。

## 必查命令
```bash
cd /Users/lisihao/Solar
git status --short --branch
/Users/lisihao/.solar/bin/solar-harness multi-task status --no-clear --renderer plain
python3 - <<'PY'
import json, pathlib
for name in ['sprint-20260525-browser-agent-research-operators','sprint-20260525-browser-agent-global-operator-cutover']:
 p=pathlib.Path(f'/Users/lisihao/.solar/harness/sprints/{name}.task_graph.json')
 print('GRAPH', name)
 d=json.loads(p.read_text())
 for n in d.get('nodes',[]): print(n.get('id'), n.get('status'), n.get('updated_at'), n.get('goal'))
PY
```

当前问题：Browser Agent Research Operators 主线还没 final；Global cutover N1 因 Sonnet quota failed；reviewing 自动 closeout 机制不可靠。
下一步：验证 N5/N7 -> 推 N6/N8 -> 收口提交 -> 修 global cutover N1 fallback -> 推进 N2-N6。
