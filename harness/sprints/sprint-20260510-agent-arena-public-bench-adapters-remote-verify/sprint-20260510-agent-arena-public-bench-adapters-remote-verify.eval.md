# Evaluator Verdict — sprint-20260510-agent-arena-public-bench-adapters-remote-verify (Round 3)

Evaluator: solar-harness:0.3 (审判官化身)
Round: 3
Verdict timestamp: 2026-05-27T13:55:00Z
@FALLBACK_MANUAL — Skill(verify-all) not invoked; manual command-by-command verification

## 总判定: FAIL

D1 / D3 / D4 / D5 实测 PASS, 但 **D2 合约硬条件未满足**:
- 合约 D2 字面规定: `bash test-agent-arena-benchmark.sh` 必须 `PASS=20 FAIL=0`
- 实测当前 (2026-05-27 Round 3): **PASS=17 FAIL=3**
- 与 handoff 自身记录的 Round 2 数字一致, handoff 明确写明 "Round 2 PASS=17 FAIL=3 — regression in dag-node-dispatcher"

虽然 handoff 论证"regression 不在 adapter 代码内 / outside write scope", 合约语言不含此豁免, 仍属未满足。

注: Round 1 (2026-05-10) 原始 PASS=20 FAIL=0 是真实的, 当时已通过 eval。当前 sprint 在 round 3 再次评审, 原因是 graph 状态卡住; 但代码 mtime 显示 graph_scheduler.py 在 2026-05-27 01:18 新增了 prerequisite_resolver import, 导致 D2 verify 命令现在失败。

## Evidence Checked

- 合约 (`.contract.md`): D1-D5 5 条 Done, 含明确 Verify Commands; 无 D2 数值豁免条款
- handoff (`.handoff.md`, 2724B): 自检 D1 ✅ / D2 ⚠️ (Round 1 PASS=20 但 Round 2/3 PASS=17 FAIL=3) / D3 ✅ / D4 ✅ / D5 ✅
- requirement_trace.json / coverage_report.json / acceptance_verdict.json: **均不存在** (dispatch §通用步骤 step 2 列出但本 sprint 未产)
- status.json: status=reviewing / phase=implementation_complete / round=3 / handoff_to=evaluator

Session Log: solar-harness session evaluate not invoked (此 sprint 非 task_graph 驱动, 走 legacy eval-verdict 通道)

## Done 条件逐条

### D1: `benchmarks doctor` 包含 swe-bench-pro/terminal-bench/browsecomp — PASS

**实测命令**:
```
$ python3 ~/.solar/harness/lib/agent_arena_benchmark.py benchmarks doctor --json
```

**实测输出 (JSON 结构 + 关键字段)**:
- top-level keys: `['ok', 'generated_at', 'schema', 'adapters']`
- adapter 数: 8
- ids: `['swe-bench-pro', 'swe-bench', 'terminal-bench', 'browsecomp', 'osworld', 'gaia', 'webarena', 'tau-bench']`
- all status: `{'pending'}` — 没有 runner 配置, 全部诚实标 pending
- D1 contract check: swe-bench-pro ✓ / terminal-bench ✓ / browsecomp ✓

**判定**: 3 个必需 id 全部命中, 8 adapters 全部 status=pending — 满足合约。

### D2: `test-agent-arena-benchmark.sh` PASS=20 FAIL=0 — **FAIL**

**实测命令**:
```
$ bash ~/.solar/harness/tests/integrations/test-agent-arena-benchmark.sh
```

**实测尾部输出**:
```
A1 — doctor exposes agents and public benchmark adapters
  PASS: doctor exits 0
  PASS: doctor has world benchmark adapter inventory

A2 — quick arena run produces evidence-backed Solar result
  FAIL: arena exits 0
  FAIL: arena JSON proves Solar smoke suite
  PASS: arena markdown report written
  PASS: arena evidence bundle written

A3 — Hermes runtime smoke is separated from Solar capability score
  FAIL: arena with Hermes runtime still runs Solar task
  PASS: Hermes runtime boundary is honest

A4 — head-to-head ... 4/4 PASS
A5 — public benchmark adapters ... 8/8 PASS

=== Agent Arena Benchmark Test: PASS=17 FAIL=3 ===
```

**根因 (从 A2 FAIL diagnostic stack trace 提取)**:
```
File "/var/folders/.../tmp.n75NzOmCvI/lib/graph_node_dispatcher.py", line 113
  from graph_scheduler import (...)
File "/var/folders/.../tmp.n75NzOmCvI/lib/graph_scheduler.py", line 28
  from prerequisite_resolver import evaluate_prerequisite, iter_blocked
ModuleNotFoundError: No module named 'prerequisite_resolver'
```

**根因定位 (一行修复)**:
- `tests/control_plane/test-graph-node-dispatcher.sh` 行 21-29 把 lib/*.py 拷贝到 tmp 目录:
  - 包含: graph_scheduler.py / graph_node_dispatcher.py / task_queue.py / pane_lease.py / solar_skills.py / capability_effects.py / resource_telemetry.py / solar_db.py / model_registry.py
  - **缺失**: `prerequisite_resolver.py` (存在于 `/Users/lisihao/.solar/harness/lib/prerequisite_resolver.py`, 11183 bytes, mtime 2026-05-26 13:32)
- `graph_scheduler.py:28` 含 `from prerequisite_resolver import evaluate_prerequisite, iter_blocked` (Round 1 之后引入的新依赖, graph_scheduler.py mtime 2026-05-27 01:18)
- 当 sub-test 在 tmp 目录加载 graph_scheduler.py 时, 缺失模块 → ModuleNotFoundError → A2/A3 整段 arena 跑挂 → 3 FAILs

**判定**: 合约要求 PASS=20 FAIL=0, 实测 PASS=17 FAIL=3 — 不满足。

### D3: 缺少真实 runner 时 adapter status=pending, 不能伪造 — PASS

- D1 doctor 实测: 8 adapters 全部 `status=pending`, `configured=false`, 含明确 reason `XXX_CMD not set and none of <bin> found`
- D2 A5 section (8/8 PASS) 含明确 assertion: "missing runner reports pending without fake score" + "pending adapter does not claim benchmark result"
- 反伪造路径完整 — 即使 A2/A3 FAIL, 反伪造仍工作正常

### D4: handoff 包含关键 stdout 和结论 — PASS (borderline)

- 文件存在 (2724 bytes, mtime 2026-05-27 08:56)
- 含 Verification Commands 段
- 含 D1-D5 结论摘要
- 含 Known Risks 明确披露 D2 回归
- 但: 未粘贴**完整** stdout (只是结论摘要), 与合约 D4 "粘贴关键 stdout 和结论" 边界接近但未违反

### D5: status=reviewing — PASS

- status.json: `status=reviewing / phase=implementation_complete / round=3 / handoff_to=evaluator`
- 状态正确

## Requirement coverage

合约 5 条 Done, 当前覆盖:
- D1 / D3 / D4 / D5: 已 verified PASS
- D2: **partial → missing** (合约硬条件未满足, 缺失项已识别根因)
- missing 未清零

## Architecture Guard Compliance

- 本 sprint dispatch 无 graph package_boundary 声明 (legacy 非 task_graph 驱动)
- 修改源代码受 Constraints 约束: "不要修改源代码, 除非测试失败且必须修复"
- D2 当前确属"测试失败且必须修复"场景, 合约允许 builder 修复
- **handoff 错误地把 prerequisite_resolver fix 标为 "outside write scope"** — 合约 Constraint 明文允许测试失败时修复源码, builder 拒修是误读合约

## Risks

1. **Round 3 仍未满足 D2** — 此 sprint 已循环 3 轮。Round 1 (2026-05-10) 真实 PASS=20 FAIL=0, Round 2/3 因 graph_scheduler.py 引入 prerequisite_resolver 依赖后未同步 test fixture 而 regression。
2. **handoff 论证"outside write scope"误读合约** — 合约 Constraint 明文允许测试失败修复, 不应回避。
3. **requirement_trace.json / coverage_report.json / acceptance_verdict.json 缺失** — dispatch §通用步骤要求读取这 3 个文件; 本 sprint 没有产出, 表明 trace pipeline 未启动。

## Required Fixes

1. **修复 test fixture** — 在 `tests/control_plane/test-graph-node-dispatcher.sh` 行 21-29 拷贝段添加:
   ```
   cp "$HARNESS_DIR_REAL/lib/prerequisite_resolver.py" "$TMPDIR_TEST/lib/prerequisite_resolver.py"
   ```
2. **重跑 D2 verify command** — `bash ~/.solar/harness/tests/integrations/test-agent-arena-benchmark.sh`, 须 PASS=20 FAIL=0
3. **更新 handoff** — 粘贴新的 PASS=20 FAIL=0 实测输出, 删除"outside write scope"措辞 (合约 Constraint 允许此类必要修复)

## next_round_capsule_diff

### changed_facts

- D1: 实测 8 adapters with ids ['swe-bench-pro','swe-bench','terminal-bench','browsecomp','osworld','gaia','webarena','tau-bench'], all status=pending — **PASS** (与 handoff D1 自检一致)
- D2: 实测 PASS=17 FAIL=3 — **FAIL** (合约硬条件 PASS=20 FAIL=0 未满足)
- D2 根因精确定位: tests/control_plane/test-graph-node-dispatcher.sh:21-29 缺 `cp prerequisite_resolver.py`; graph_scheduler.py:28 的 import 是 Round 1 之后新增依赖
- D3: 反伪造路径 8/8 PASS (A5 section 全绿) — **PASS**
- D4: handoff 含结论但 stdout 是摘要不是 raw paste — borderline PASS
- D5: status=reviewing — **PASS**

### new_risks

- 此回归不是首次出现 (handoff Known Risks §1 早已识别), 但 Round 2/3 都未修复 — 说明 builder 在 "outside write scope" 判断上卡住
- 真正阻塞: builder 自我设限 (test fixture 修复被认为越界), 而非技术难度
- 一旦修了 fixture, 这个 sprint 在 5 分钟内能闭合

### updated_next_action

Builder 下一轮的最小修复指令 (具体到文件:行):

1. **打开** `/Users/lisihao/.solar/harness/tests/control_plane/test-graph-node-dispatcher.sh`
2. **定位** 行 21-29 cp 段 (拷贝 lib/*.py 到 tmp dir)
3. **添加** 一行 (建议插在第 29 行 model_registry.py 拷贝之后):
   ```
   cp "$HARNESS_DIR_REAL/lib/prerequisite_resolver.py" "$TMPDIR_TEST/lib/prerequisite_resolver.py"
   ```
4. **跑测** `bash ~/.solar/harness/tests/integrations/test-agent-arena-benchmark.sh`, 期望 `=== Agent Arena Benchmark Test: PASS=20 FAIL=0 ===`
5. **更新 handoff** — 删除 "Round 2 re-verification PASS=17 FAIL=3" 段, 改为 "Round 3 PASS=20 FAIL=0", 粘贴新输出尾部 + Known Risks §1 标"测试 fixture 已补齐 prerequisite_resolver cp"
6. **重派 evaluator** 复跑 D1-D5

修复后预期 sprint 一轮闭合; 当前 Round 3 verdict 必须 FAIL 以触发该最小修复。
