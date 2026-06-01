# Handoff — S03 Core-Runtime (task_graph 三分面)

sprint_id: `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s03-core-runtime`
Builder: builder_main
Round: 2

---

## Round 1 (previous builder, preserved for context)

| 文件 | 类型 | 目的 |
|------|------|------|
| `lib/task_graph_io.py` | 新建 | 三分面核心 IO 库 v1 |
| `lib/workflow_guard.py` | 修改 | triface route |
| `lib/graph_scheduler.py` | 修改 | state 同步写 |
| `tests/graph/test_task_graph_io.py` | 新建 | 26 tests |
| `tests/graph/test_workflow_guard_triface.py` | 新建 | 7 tests |

---

## Round 2: R1_state_closure_io 变更文件

| 文件 | 类型 | 目的 |
|------|------|------|
| `lib/task_graph_state_io.py` | **新建 (487 行)** | R1 核心交付。Schema-versioned spec/state/closure 三分面 I/O：empty skeleton creators、legacy backfill (extracts node_results + inline status + dispatch metadata)、event recording、atomic write、CLI entry point |
| `tests/graph/test_task_graph_state_io.py` | **新建 (28 tests)** | 完整单测：path resolution (3)、skeleton creators (2)、state I/O (3)、closure I/O (2)、legacy backfill state (4)、legacy backfill closure (4)、load_three_face (3)、mutation helpers (3)、spec immutability (1)、sprint_id extraction (3) |

---

## R1 Done 定义达成

### AC1: state/closure load-save path 存在 ✅
- `load_state()` / `save_state()` → `{sid}.task_dag.state.json` (atomic temp+replace)
- `load_closure()` / `save_closure()` → `{sid}.task_dag.closure.json` (atomic temp+replace)
- `make_empty_state()` / `make_empty_closure()` — schema-versioned skeleton creators
- 证据: `test_save_and_load_state`, `test_save_and_load_closure`, `test_atomic_write_no_tmp_leftover` 全 PASS

### AC2: legacy sprint 可回填 state skeleton ✅
- `backfill_state_from_legacy()` — 从 monolithic task_graph.json 提取 node_results、inline node status、assigned_to、dispatch_id、gate_results
- `backfill_closure_from_legacy()` — 检查 all_nodes_passed / all_required_gates_passed，满足条件时写 closed_at
- 不覆盖策略: 已有 state/closure 时返回现有值，force=True 时强制覆盖
- CLI 验证: `python3 lib/task_graph_state_io.py backfill --graph sprints/cmux-s02.task_graph.json --force` 正确提取 2 node_results
- 证据: `test_backfill_state_from_legacy` (验证 node_results, dispatch_ids, events), `test_backfill_state_does_not_overwrite`, `test_backfill_state_force_overwrites`, `test_backfill_closure_from_legacy_not_closed`, `test_backfill_closure_from_legacy_closed` 全 PASS

### AC3: 不把 runtime 状态写回 spec ✅
- State operations (`set_node_result`, `set_gate_result`, `record_event`, `save_state`) 只写 state 面，从不 touch spec 文件
- 证据: `test_state_operations_do_not_touch_spec` — 创建 spec 后执行全部 state mutations，验证 spec 文件 mtime 未变 + 内容不变

### 合约 AC 达成
- **核心 API 有单测覆盖** ✅ — 28 tests, 0 failures
- **旧路径兼容** ✅ — `task_graph_state_io.py` 是 additive 新模块，不修改任何现有文件
- **状态变更可由元数据或事件重建** ✅ — state 包含 events 数组，每个 backfill/mutation 都追加事件记录

---

## 验证命令

```bash
cd ~/.solar/harness

# R1 单测 (28 passed)
python3 -m pytest tests/graph/test_task_graph_state_io.py -v

# 现有 task_graph_io 单测回归 (26 passed)
python3 -m pytest tests/graph/test_task_graph_io.py -v

# CLI backfill 验证 (real sprint)
python3 lib/task_graph_state_io.py backfill \
  --graph sprints/sprint-20260531-cmux-多标签四分屏-tmux-状态监控工作台-s02-architecture.task_graph.json --force

# CLI load 验证
python3 lib/task_graph_state_io.py load \
  --sprint-id "sprint-20260531-cmux-多标签四分屏-tmux-状态监控工作台-s02-architecture"

# Import check
python3 -c "import sys; sys.path.insert(0,'lib'); import task_graph_state_io; print('OK')"
```

---

## 两个模块的关系

| 模块 | 职责 | API 风格 |
|------|------|---------|
| `task_graph_io.py` (Round 1) | spec/state/closure IO + MirrorCompiler + triface_parent_ready | fail-open (返回 {}), 直接读写 SPRINTS_DIR |
| `task_graph_state_io.py` (R1) | Schema-versioned state/closure IO + legacy backfill + event recording + CLI | 返回 None on missing, 支持自定义 sprints_dir, schema_version 标记, events 日志 |

R2 将统一这两个模块的消费者入口，让 workflow_guard / graph_scheduler 切换到 `task_graph_state_io` 的 `load_three_face()` 作为默认读路径。

---

## 未闭环项 (R2-R4 待办)

1. **R2**: workflow_guard + graph_scheduler 默认消费 spec/state/closure (切换到 task_graph_state_io)
2. **R3**: graph_node_dispatcher 停止依赖 inline status; closure closeout 逻辑
3. **R4**: 端到端验证 + handoff

## 残余风险

- **双模块并存**: `task_graph_io.py` 和 `task_graph_state_io.py` 有重叠 API，R2 需明确收敛策略
- **并发写 state**: atomic rename 无文件锁，极低概率竞争

