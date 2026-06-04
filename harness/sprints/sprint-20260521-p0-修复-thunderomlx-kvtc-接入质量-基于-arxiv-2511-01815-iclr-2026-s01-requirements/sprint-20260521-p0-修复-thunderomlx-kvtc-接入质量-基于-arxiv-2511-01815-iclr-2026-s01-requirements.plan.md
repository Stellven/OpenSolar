# Plan — S01 Requirements 切片：执行计划

epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements`
slice: `requirements`
generated_at: `2026-05-22T04:45:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`

## 1. 交付切片顺序

| Wave | 节点 | 类型 | 并发 |
|------|------|------|------|
| W1 (并行) | N1, N2, N3, N4, N5, N6, N7 | 文档矩阵（每节点 1 个 .md） | 7 路并行（write_scope 互不重叠） |
| W2 (join) | N8 | 聚合 N1..N7 + 父 traceability.json 写 traceability_map.md + .json | 单节点，依赖 W1 全部 passed |

## 2. 文件级写入范围（强制 write_scope）

| 节点 | 写入文件（绝对路径前缀 `~/.solar/harness/sprints/`） |
|------|------------------------------------------------------|
| N1 | `<sid>.requirements.paper_alignment.md` |
| N2 | `<sid>.requirements.calibration_key.md` |
| N3 | `<sid>.requirements.family_classifier_bypass.md` |
| N4 | `<sid>.requirements.reconstruction_gate.md` |
| N5 | `<sid>.requirements.named_prompt_cache_422.md` |
| N6 | `<sid>.requirements.ci_regression_gate.md` |
| N7 | `<sid>.requirements.ui_default_off_gate.md` |
| N8 | `<sid>.requirements.traceability_map.md`, `<sid>.requirements.traceability.json` |

`<sid>` = `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements`

每个节点禁止写出上述以外的任何路径。禁止改 ThunderOMLX 源码、禁止改 `~/.solar/STATE.md`、禁止动 epic.* 文件（包括 epic.traceability.json，N8 只生成本切片的 traceability.json 子文档供 epic 后续合并）。

## 3. 并发边界

- N1..N7 的 write_scope 文件互不重叠 → 必须并行派发（graph-scheduler 按 ready batch 调度）。
- N8 是 join 节点，必须等 N1..N7 全部 `passed` 后才 ready。
- 同一 sprint 同一 builder pane 内禁止并发 N1..N7（防止 write_scope 串行冲突）；由 graph-scheduler `batches --max-parallel` 决定（建议 3）。

## 4. 每节点产物结构（强制 markdown 段落）

每个 N1..N7 的 .md 必须包含以下段落：

1. **Outcome**：本节点交付的具体可验收物（1-3 句）
2. **Maps to PRD**：引用 PRD 中的具体段落与第几条用户要求
3. **Acceptance Matrix**：表格 = {acceptance_id, 验证方法, 期望证据形态, 下游 owner sprint}
4. **Risk Boundary**：列出"如果此需求实现错误会触发哪些用户可见 regression"
5. **Stop Rule**：列出本需求"什么情况下不允许继续派发下游 builder"
6. **Owner Sprint Brief**：给下游 sprint 的 1 段落接力说明（输入文件 / 期望输出 / 禁止动作）
7. **Acceptance Evidence Plan**：S05 verification 期望看到的证据样本（命令 / 文件 / 数字阈值）

N8 必须额外包含：

- 父 epic 8 项要求 -> N1..N7 -> 下游 sprint 的三层对照表
- 父 `epic-….traceability.json` 现状摘要（read-only 引用，禁止改写）
- 未闭环项 / open question 列表（PRD 第 7 节"开放问题"必须 1:1 出现）
- "不允许 Builder 直接派发"的事项清单（包括所有 ThunderOMLX 源码修改）

## 5. 验证命令

```bash
# A. DAG schema 校验（必须 PASS 才能进入 builder 派发）
~/.solar/bin/solar-harness graph-scheduler validate \
  --graph ~/.solar/harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements.task_graph.json

# B. ready batch 检查
~/.solar/bin/solar-harness graph-scheduler batches \
  --graph ~/.solar/harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements.task_graph.json \
  --max-parallel 3

# C. 每节点 .md 段落自检（builder 自验 + evaluator 抽检）
for f in ~/.solar/harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements.requirements.*.md; do
  for sec in "## Outcome" "## Maps to PRD" "## Acceptance Matrix" "## Risk Boundary" "## Stop Rule" "## Owner Sprint Brief" "## Acceptance Evidence Plan"; do
    grep -q "$sec" "$f" || { echo "MISSING $sec in $f"; exit 1; }
  done
done

# D. N8 traceability.json schema 自检（必须含 children + open_questions + not_in_scope）
python3 -c "
import json, sys
p='$HOME/.solar/harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements.requirements.traceability.json'
d=json.load(open(p))
for k in ['schema_version','sprint_id','epic_id','requirements','open_questions','not_in_scope']:
    assert k in d, f'missing {k}'
assert len(d['requirements'])==7
print('OK')
"

# E. parent-check（确认本 sprint passed 后才允许 epic 关闭 S02）
~/.solar/bin/solar-harness graph-scheduler parent-check \
  --graph ~/.solar/harness/sprints/epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026.task_graph.json
```

## 6. no-live-pane-mutation 保护

- 本计划禁止 builder 调用：`tmux send-keys`、`solar-harness restart`、`solar-harness models switch`、`solar-harness inject-prompt`。
- 本计划禁止 builder 调用任何 ThunderOMLX CLI / HTTP API（`curl :…/v1/cache/prompt/*`、`pytest`、`scripts/kvtc_ab_correctness.py`）。
- 本计划禁止 builder 修改 `~/.solar/STATE.md`、epic.traceability.json、epic.task_graph.json（这是 epic_decomposer 的所有权）。
- 若 builder 触发上述任意一项，evaluator 必须 FAIL 并标 `stop_rule_violation`。

## 7. Rollback / Stop Rule

- 任一节点 evaluator FAIL → status 回到 `planning_complete`，builder 重做被 FAIL 的节点；不允许"打补丁 + 继续推进"。
- N8 缺 open_questions 段落 → 立即 FAIL（PRD 第 7 节"开放问题"必须显式被携带）。
- 若 PM PRD 变更（`<sid>.prd.md` mtime 变化 + raw_request_chars 变化），本 plan 作废，需重跑 planner。
- 若发现父 epic `traceability.json` 缺项（例如 S02..S05 中任一 status 为非 `queued/active/passed`），N8 必须把该缺项写入 `requirements_blocking_epic`，且本 sprint 不许标 passed。
- 任一节点检测到 N0 范围外的写入企图（例如 builder 试图写 `/Users/lisihao/ThunderOMLX/...`）→ evaluator 立即 FAIL + 触发 ATLAS structured repair。

## 8. 模型路由建议（仅参考，coordinator 决定）

- N1（论文对齐审计）：`opus` 或 `sonnet-4.6`（需要 paper-grade 抽象）
- N2/N3/N4（计算/格式相关需求）：`glm-5.1`（成本敏感，文档型任务足够）
- N5/N7（API / UI 需求）：`glm-5.1`
- N6（CI 矩阵）：`glm-5.1`
- N8（join + traceability）：`opus`（需要 epic 全局视角）

## 9. 时间预算

- N1..N7 并行 wave：估 1 个 dispatch 周期内完成（每节点 ~5-15 分钟）
- N8 join：1 个 dispatch 周期
- S01 整体目标在 2 个 dispatch round 内 passed → 解锁 S02 architecture

## 10. 完成定义（呼应 DoD 7 条）

1. 已完成：design.md / plan.md / task_graph.json / planning.html 4 件齐全
2. 已完成：task_graph.json `graph-scheduler validate` PASS
3. 已完成：planning.html 通过 `html_artifact.py register`
4. 未验证：N1..N8 builder 节点尚未执行（属下一个 dispatch round）
5. 未验证：S02..S05 下游 sprint 尚未启动
6. 风险：mirage 知识库降级，依赖 qmd/obsidian fallback；后续如再降级可能影响 N1 论文对齐审计
7. 后续待办：builder pane 拿到本 task_graph 后按 W1→W2 顺序产出 8 个矩阵文件 → evaluator 抽检 → status passed → epic 激活 S02
