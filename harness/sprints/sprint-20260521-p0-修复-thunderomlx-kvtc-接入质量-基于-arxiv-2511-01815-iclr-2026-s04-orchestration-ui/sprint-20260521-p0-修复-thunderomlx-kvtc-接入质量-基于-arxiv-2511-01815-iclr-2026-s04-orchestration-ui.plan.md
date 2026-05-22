# Plan — S04 Orchestration-UI 切片：执行计划

epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s04-orchestration-ui`
slice: `orchestration-ui`
generated_at: `2026-05-22T08:55:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream: `S02 passed 2026-05-22T08:39:39Z` · `S03 active/planning_complete (soft dep on B0 errors module)`

## 1. 交付切片顺序（4 wave）

| Wave | 节点 | 类型 | 并发 | 依赖 |
|------|------|------|------|------|
| W1 | C0, C2 | kvtc_ui_gate FSM / i18n keys | 2 路并行 | 无（仅 S02 spec） |
| W2 | C1 | server.py routes (env middleware + /api/kvtc/state) | 1 路 | C0 + C2 |
| W3 | C3 | pytest tests/orchestration/ | 1 路 | C1 |
| W4 | C4 | handoff + traceability join | 1 路 | C3 |

合计 5 节点；4 layer。

## 2. 文件级写入范围（强制 write_scope）

| 节点 | 写入文件（绝对路径） | 动作 |
|------|---------------------|------|
| C0 | `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_ui_gate.py` | NEW |
| C2 | `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_ui_i18n.py` | NEW |
| C1 | `/Users/lisihao/ThunderOMLX/src/omlx/server.py` | MODIFY（仅 `/v1/cache/prompt/save` 区域 lines 2051-2215 + 新增 `/api/kvtc/state` 路由块） |
| C3 | `/Users/lisihao/ThunderOMLX/tests/orchestration/test_kvtc_ui_gate.py` | NEW |
| C4 | `~/.solar/harness/sprints/<s04-sid>.handoff.md`, `<s04-sid>.traceability.json` | NEW |

**严格禁止 write_scope 外路径**，包括：
- 任何 `src/omlx/cache/kvtc_codec.py / kvtc_calibration_store.py / kvtc_recon_gate.py / paged_ssd_cache.py / kvtc_errors.py / kvtc_tools_recalibrate.py`（S03）
- `scripts/kvtc_ab_correctness.py`（S05）
- `.github/workflows/**`（S05）
- `server.py` 非 KVTC 路由区域（lines 0-2050、2216-6431 除新增 `/api/kvtc/state` 路由块外）
- `~/.solar/STATE.md`、epic.*、S01/S02/S03 任何 artifact

## 3. 并发边界

- W1 C0 + C2 write_scope 互不重叠（新文件） → 2 路并行
- W2 C1 单节点；server.py 内部局部修改，需 surgical edit
- W3 C3 单节点
- W4 C4 单节点 join
- 同 pane 内禁止并发；max-parallel 建议 2

## 4. 每节点段落契约

每个节点 commit/handoff 必须含：

1. **Implemented**：本节点实现了哪些 acceptance（引用 N5-Ax / N7-Ax / S02-A3-API-x / S02-Schema-7）
2. **Files Touched**：diff 涉及文件 + 行数变更
3. **Decision Made**（C1 必须）：N5 默认 env=0（禁用 → 410）的决策证据
4. **Test Evidence**（C3 必须）：pytest 输出 ≥15 PASS raw 行
5. **Compat Notes**：服务端 OpenAPI / 旧客户端兼容性
6. **Stop-Rule Compliance**：明示未触碰 codec/calibration/recon_gate/ab_correctness/.github

C4 join 节点必须额外含：

- R5、R7 状态（implemented）+ R1..R4、R6 状态（仍 owned by S03/S05）
- OQ2 状态（partially_resolved → 部分 resolved：本 sprint 选定 env=0 默认禁用；H3 修复留后续）
- OQ4 状态（resolved → 实施完成：env override 已落地）
- S05 接力清单（输入文件 / 期望输出 / 禁止动作 / 验证证据计划）

## 5. 验证命令

```bash
SID4=sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s04-orchestration-ui
THUNDEROMLX=/Users/lisihao/ThunderOMLX

# A. DAG schema 校验
~/.solar/bin/solar-harness graph-scheduler validate --graph ~/.solar/harness/sprints/$SID4.task_graph.json

# B. ready / layers / batches
~/.solar/bin/solar-harness graph-scheduler ready    --graph ~/.solar/harness/sprints/$SID4.task_graph.json
~/.solar/bin/solar-harness graph-scheduler layers   --graph ~/.solar/harness/sprints/$SID4.task_graph.json
~/.solar/bin/solar-harness graph-scheduler batches  --graph ~/.solar/harness/sprints/$SID4.task_graph.json --max-parallel 2

# C. 文件齐全性
test -f $THUNDEROMLX/src/omlx/cache/kvtc_ui_gate.py
test -f $THUNDEROMLX/src/omlx/cache/kvtc_ui_i18n.py
test -f $THUNDEROMLX/tests/orchestration/test_kvtc_ui_gate.py

# D. state machine 4 状态常量
grep -E "^\s*(default_off|preview|enabled|blocked_by_gate_fail|feature_flag_off)\s*[:=]" \
  $THUNDEROMLX/src/omlx/cache/kvtc_ui_gate.py | head -10

# E. env 开关存在
grep -E "THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED|THUNDEROMLX_KVTC_UI_AB_SOURCE|THUNDEROMLX_KVTC_UI_FORCE_OFF" \
  $THUNDEROMLX/src/omlx/cache/kvtc_ui_gate.py $THUNDEROMLX/src/omlx/server.py | head -5

# F. 410 错误体含 tracking_sprint
grep -E "named_prompt_cache_save_disabled|tracking_sprint" \
  $THUNDEROMLX/src/omlx/server.py | head -3

# G. 新路由 /api/kvtc/state 注册
grep -E '"/api/kvtc/state"|@app\.get\("/api/kvtc/state"' $THUNDEROMLX/src/omlx/server.py | head -3

# H. i18n 6 个 key
grep -E "kvtc\.ui\.(state|toast)\." $THUNDEROMLX/src/omlx/cache/kvtc_ui_i18n.py | wc -l   # 期望 ≥ 6

# I. pytest 15+ cases pass
cd $THUNDEROMLX && ./venv/bin/python -m pytest tests/orchestration/ -v --tb=short

# J. 未触碰禁区
! git -C $THUNDEROMLX diff --name-only HEAD | grep -E "^src/omlx/cache/(kvtc_codec|kvtc_calibration_store|kvtc_recon_gate|paged_ssd_cache|kvtc_errors|kvtc_tools_recalibrate)\.py|^scripts/|^\.github/"

# K. server.py 修改仅限 KVTC 区域
git -C $THUNDEROMLX diff --unified=0 src/omlx/server.py | grep -E "^@@" | head -20
# 期望 hunks 均在 lines 2051-2215 或新增 /api/kvtc/state 路由块

# L. parent-check
~/.solar/bin/solar-harness graph-scheduler parent-check \
  --graph ~/.solar/harness/sprints/epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026.task_graph.json
```

## 6. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` / `solar-harness restart` / `solar-harness inject-prompt` / `solar-harness models switch`
- 禁止 `curl .../v1/cache/prompt/*`（即使 staging 复现 422，必须留给 S04 builder 在 staging 单机做，本 sprint 不真调）
- 禁止启动 ThunderOMLX server / `uvicorn` / FastAPI dev server
- 禁止真跑 `scripts/kvtc_ab_correctness.py`
- 禁止 Write/Edit 任何 S03 范围模块
- 禁止改 `~/.solar/STATE.md`、epic.traceability.json、epic.task_graph.json、S01/S02/S03 任何 artifact
- pytest 必须在 ThunderOMLX venv 内跑：`./venv/bin/python -m pytest tests/orchestration/`
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 7. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做被 FAIL 节点
- C0 缺 4 个状态常量（default_off / preview / enabled / blocked_by_gate_fail）→ 立即 FAIL
- C1 未实施 env=0 → 410 middleware → 立即 FAIL
- C1 410 错误体未含 `tracking_sprint` 字段 → 立即 FAIL
- C1 把禁用 API 状态码留为 422 → 立即 FAIL
- C2 i18n 缺任一 key（6 个）或缺任一语言 → 立即 FAIL
- C3 pytest 任一 case 失败 → S04 不许 passed
- C1 修改 server.py 非 KVTC 路由区域 → FAIL + ATLAS
- 任何文档/代码使用乐观词 → FAIL
- default UI 状态非 default_off → FAIL
- 触碰 S03 范围模块（kvtc_codec / kvtc_calibration_store / etc）→ FAIL
- PRD/contract mtime 变化 → 本 plan 作废，重跑 planner

## 8. 模型路由建议（coordinator 决定）

- C0 kvtc_ui_gate.py：`sonnet`（状态机 + env 读取 + 文件 IO + 容错）
- C2 kvtc_ui_i18n.py：`glm-5.1`（常量 dict）
- C1 server.py routes：`opus`（middleware + 新路由 + 兼容性 + surgical edit 6431 行文件）
- C3 pytest：`sonnet`（≥15 cases 精确覆盖）
- C4 handoff/traceability：`sonnet`（join + 全局一致性）

## 9. 时间预算

- W1 C0/C2 并行：~25 min（C0 较重）
- W2 C1：~45 min（最复杂，server.py surgical edit）
- W3 C3：~25 min
- W4 C4：~15 min
- S04 整体目标 3 个 dispatch round 内 passed（可与 S03 完全并行）

## 10. 完成定义（DoD 7 条）

1. **已完成**：design.md / plan.md / task_graph.json / planning.html 4 件齐全
2. **已完成**：task_graph.json 通过 `graph-scheduler validate`（0 errors / 0 warnings）
3. **已完成**：planning.html 通过 `html_artifact.py register`
4. **未验证**：C0..C4 builder 节点尚未执行
5. **未验证**：15+ pytest cases 未真跑；410 路径在 staging 未实测
6. **风险**：与 S03 软依赖（kvtc_errors module）；S04 builder 必须有 ImportError 兜底；server.py 6431 行 surgical edit 风险高
7. **后续待办**：coordinator 按 task_graph 派发 W1→W4 → builder 实施 5 节点 → pytest 15+ PASS → evaluator → S04 passed → 与 S03 一同解锁 S05
