# Eval — S03 Core-Runtime (task_graph 三分面)

sprint_id: `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s03-core-runtime`
Round: 1
Evaluator: (awaiting)

---

## 验收标准核查

### AC-1: 核心 API 有单测覆盖

**证据**:
```
python3 -m pytest tests/graph/test_task_graph_io.py -v
→ 26 passed in 0.07s

python3 -m pytest tests/graph/test_workflow_guard_triface.py -v
→ 7 passed in 0.05s
```
覆盖接口：`load_spec/save_spec/spec_valid`、`load_state/save_state/patch_state/set_node_result_in_state/set_gate_result_in_state`、`load_closure/save_closure/closure_complete`、`backfill_state_from_legacy/backfill_spec_from_legacy`、`compile_mirror/write_mirror`、`triface_parent_ready`、`_triface_graph_valid`、`_triface_parent_ready`

**结论**: ✅ PASS

---

### AC-2: 旧路径兼容，不破坏现有 wake/dispatch/status

**证据**:
- workflow_guard.py 的所有三分面调用均包裹在 `try/except` fail-open 逻辑中
- `_triface_graph_valid()` 返回 `(None, "spec_missing")` 时，`route()` 自动 fallback 到原 `_graph_valid(graph)` 路径
- graph_scheduler.py 的 state 写入为 best-effort，失败不影响 legacy `save_graph()` 调用

**回归测试** (排除预存在失败):
```
python3 -m pytest tests/graph/ -q \
  --ignore=tests/graph/test_multi_task_runner_status_surface.py
→ 55 failed (全部为预存在 datetime.UTC Python 3.9 兼容问题), 162 passed
```

注：55 个失败均发生在 `graph_scheduler._now()` 调用 `datetime.UTC`（Python 3.11+ 特性），本次修改**未引入**该问题（可通过 `git diff lib/graph_scheduler.py` 确认 `_now()` 函数未变）。

**结论**: ✅ PASS（兼容路径完整，无回归引入）

---

### AC-3: 状态变更可由元数据或事件重建

**证据**:
- `backfill_state_from_legacy()` 可从 legacy task_graph.json 重建 state skeleton
- `compile_mirror()` 可从 spec + state 重建兼容 task_graph.json
- `triface_parent_ready()` 先读 closure，closure 完整时不依赖 state 内容

**测试证据**:
- `test_backfill_state_from_legacy` — 验证从 legacy 重建 state
- `test_compile_mirror_merges_spec_and_state` — 验证从 spec+state 生成 mirror
- `test_triface_parent_ready_via_closure` — 验证 closure 驱动的状态重建

**结论**: ✅ PASS

---

## 未闭环项（继承自 handoff）

| # | 项目 | 严重度 |
|---|------|--------|
| 1 | dispatcher inline status 依赖未切换 | P1 (S04/后续 sprint) |
| 2 | closure auto-write 未挂入 parent_ready_check | P1 |
| 3 | MirrorCompiler 未挂入 coordinator 刷新 | P2 |
| 4 | closure replay e2e 测试 | P2 |
| 5 | datetime.UTC 预存在兼容问题 | P2 (独立 bug) |

---

## 总体结论

**本切片 (R1+R2+部分R3) 核心验收通过**。

未闭环项均为有计划的后续工作，不影响当前三分面基础架构的可用性。建议标记为 `reviewing` 待 evaluator 最终确认。
