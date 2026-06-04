# Plan — S02 Architecture 切片：执行计划

epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s02-architecture`
slice: `architecture`
generated_at: `2026-05-22T06:50:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream: `S01 passed/finalized 2026-05-22T06:40:29Z`

## 1. 交付切片顺序（4 wave）

| Wave | 节点 | 类型 | 并发 | 依赖 |
|------|------|------|------|------|
| W1 | A1, A4, A6 | source-archeology / data-models / observability+failure | 3 路并行 | 无（仅 S01 矩阵 + ThunderOMLX read-only） |
| W2 | A2, A3, A5 | components / interfaces / migration | 3 路并行 | A1 (A2, A5)；A1 + A4 (A3) |
| W3 | A7 | architecture index + traceability + S03/S04/S05 handoff brief | 单节点 join | A2, A3, A4, A5, A6 |

合计 7 节点；3 layer。

## 2. 文件级写入范围（强制 write_scope）

| 节点 | 写入文件（前缀 `~/.solar/harness/sprints/<s02-sid>.`） |
|------|-------------------------------------------------------|
| A1 | `architecture.source_archeology.md` |
| A2 | `architecture.components.md` |
| A3 | `architecture.interfaces.md` |
| A4 | `architecture.data_models.md` |
| A5 | `architecture.migration.md` |
| A6 | `architecture.observability.md` |
| A7 | `architecture.index.md`, `architecture.traceability.json` |

`<s02-sid>` = `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s02-architecture`

每节点禁止写出上述以外任何路径。

**重要例外（A1 only）**：A1 节点允许 **read-only** 访问 `/Users/lisihao/ThunderOMLX/**`，用于填 N1 `[TBD-S02 read]` 标记；不允许 Write/Edit 进入 ThunderOMLX 仓库。

## 3. 并发边界

- W1 三节点 write_scope 互不重叠，可并行。
- W2 三节点同样互不重叠；W2 三节点必须等 A1 passed。A3 还需 A4 passed。
  - 实操：可以让 W2 拆为「W2a: A2, A5（A1 done 后）」+「W2b: A3（A1 + A4 done 后）」；DAG layers 自然处理。
- A7 是 join 节点，等 A2/A3/A4/A5/A6 全 passed。
- 同 pane 内禁止并发；max-parallel 建议 3。

## 4. 每节点 markdown 段落契约

每个 A1..A6 的 .md 必须包含：

1. **Outcome**（1-3 句，给出本节点交付物）
2. **Inputs From S01**（明确引用了哪些 N1..N7 + 哪些 acceptance_id）
3. **Inputs From ThunderOMLX**（仅 A1：实际读到的文件路径 + 行号区间）
4. **Architecture Decision**（本节点核心设计；表格 / BNF / 状态图 / schema 等）
5. **Conflicts / Dependencies / Degradation**（PRD 验收第 3 条要求）
6. **Owner Sprint Brief**（给 S03 / S04 / S05 的接力 1 段）
7. **Stop Rule**（本节点的边界与失败回退）
8. **Acceptance Evidence Plan**（S05 期望看到的证据样本）

A7 额外必含：

- R1..R7 + OQ1..OQ4 + NIS1..NIS10 + builder_forbidden_aggregate 全部从 S01 traceability.json 继承
- S03/S04/S05 三个接力 brief（每个 sprint 一段，含输入文件 / 期望输出 / 禁止动作 / 验证证据计划）
- `architecture.traceability.json` schema：`schema_version`、`sprint_id`、`epic_id`、`architecture_artifacts`（7 项）、`mapped_requirements`（R1..R7）、`downstream_handoff`（S03/S04/S05）、`open_questions_status`、`builder_forbidden_aggregate`、`generated_at`、`knowledge_context`

## 5. 验证命令（builder + evaluator 必跑）

```bash
SID2=sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s02-architecture

# A. DAG schema 校验
~/.solar/bin/solar-harness graph-scheduler validate --graph ~/.solar/harness/sprints/$SID2.task_graph.json

# B. ready / layers / batches
~/.solar/bin/solar-harness graph-scheduler ready    --graph ~/.solar/harness/sprints/$SID2.task_graph.json
~/.solar/bin/solar-harness graph-scheduler layers   --graph ~/.solar/harness/sprints/$SID2.task_graph.json
~/.solar/bin/solar-harness graph-scheduler batches  --graph ~/.solar/harness/sprints/$SID2.task_graph.json --max-parallel 3

# C. 每节点段落自检
for f in ~/.solar/harness/sprints/$SID2.architecture.*.md; do
  for sec in "## Outcome" "## Inputs From S01" "## Architecture Decision" \
             "## Conflicts" "## Owner Sprint Brief" "## Stop Rule" "## Acceptance Evidence Plan"; do
    grep -q "$sec" "$f" || { echo "MISSING $sec in $f"; exit 1; }
  done
done

# D. A1 必须真的引用了 ThunderOMLX 文件（绝对路径或仓库相对路径）
grep -E "(/Users/lisihao/ThunderOMLX/|kvtc_codec\.py|kvtc_calibration_store\.py|paged_ssd_cache\.py)" \
  ~/.solar/harness/sprints/$SID2.architecture.source_archeology.md \
  | head -5  # 期望非空

# E. A7 traceability.json 自检
python3 -c "
import json
d=json.load(open('$HOME/.solar/harness/sprints/$SID2.architecture.traceability.json'))
need=['schema_version','sprint_id','epic_id','architecture_artifacts','mapped_requirements',
      'downstream_handoff','open_questions_status','builder_forbidden_aggregate']
for k in need: assert k in d, f'missing {k}'
assert len(d['architecture_artifacts'])==7
assert {x['id'] for x in d['mapped_requirements']} >= {'R1','R2','R3','R4','R5','R6','R7'}
print('OK')
"

# F. parent-check（S02 passed 后才允许 S03/S04 激活）
~/.solar/bin/solar-harness graph-scheduler parent-check \
  --graph ~/.solar/harness/sprints/epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026.task_graph.json
```

## 6. no-live-pane-mutation 保护

- 禁止 builder 调用：`tmux send-keys`、`solar-harness restart`、`solar-harness inject-prompt`、`solar-harness models switch`
- 禁止运行 `pytest` / `scripts/kvtc_ab_correctness.py` / `curl .../v1/...` / 启动 ThunderOMLX server
- 禁止 Write/Edit 任何 ThunderOMLX 仓库文件；A1 只允许 Read
- 禁止修改 `~/.solar/STATE.md`、epic.traceability.json、epic.task_graph.json、S01 任何 artifact
- 禁止真实创建 `$THUNDEROMLX_KVTC_HOME/calibration/v2/` 目录或落盘文件
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 7. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做被 FAIL 的节点
- A1 中任一 `[TBD-S02 read]` 仍留空 → 立即 FAIL（PRD 验收第 2 条「写清楚接口边界和旧系统兼容方式」依赖 A1 完整）
- A7 缺 OQ1..OQ4 状态字段 → 立即 FAIL（S01 已留 tentative_decision，S02 必须继承或调整）
- A4 任一 schema 缺版本号 → 立即 FAIL
- A3 任一 API 缺错误类层级 → 立即 FAIL
- 任何 architecture 文档使用乐观词（已修复/稳定/完美） → 立即 FAIL（S01 builder_forbidden_aggregate）
- 任何节点放宽 hard 阈值（0.02 / 0.999） → 立即 FAIL
- 父 epic.traceability.json 出现 unexpected mutation → S02 不许 passed
- PRD/contract mtime 变化 → 本 plan 作废，重跑 planner

## 8. 模型路由建议（coordinator 决定）

- A1 source archeology：`sonnet`（需要精确读源码 + 填充）
- A2 components：`sonnet`（系统抽象）
- A3 interfaces：`sonnet`（接口设计、错误类层级）
- A4 data_models：`glm-5.1`（schema 列表 + 字段表）
- A5 migration：`glm-5.1`（兼容策略 + 回滚步骤）
- A6 observability：`glm-5.1`（日志 + 指标 + 告警）
- A7 architecture index + traceability：`sonnet`（join + 全局一致性）

## 9. 时间预算

- W1 并行 3 节点：估 1 个 dispatch round 内完成（A1 较重，~20-30 min；A4/A6 ~10-15 min）
- W2 并行 3 节点：1 个 dispatch round（A3 较重）
- W3 单节点 A7：1 个 dispatch round
- S02 整体目标 3 个 dispatch round 内 passed → 解锁 S03_core_runtime（依赖）+ S04_orchestration_ui（依赖）并行

## 10. 完成定义（呼应 DoD 7 条）

1. **已完成**：design.md / plan.md / task_graph.json / planning.html 4 件齐全
2. **已完成**：task_graph.json 通过 `graph-scheduler validate`
3. **已完成**：planning.html 通过 `html_artifact.py register`
4. **未验证**：A1..A7 builder 节点尚未执行（属下一个 dispatch round）
5. **未验证**：S03/S04/S05 下游 sprint 尚未启动
6. **风险**：mirage 知识库仍降级；A1 完全依赖直接读 ThunderOMLX 仓库（不依赖检索）
7. **后续待办**：coordinator/graph-dispatch 按 task_graph 派发 → builder 产出 7 个文档 + 1 个 traceability.json → evaluator 抽检 → S02 passed → epic 激活 S03/S04 并行
