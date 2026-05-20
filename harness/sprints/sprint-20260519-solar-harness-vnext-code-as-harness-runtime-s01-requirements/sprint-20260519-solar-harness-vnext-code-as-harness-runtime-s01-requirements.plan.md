# Plan — S01 需求拆解与追踪矩阵 (Code-as-Harness Runtime)

sprint_id: `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s01-requirements`
slice: `requirements`
date: 2026-05-19
Knowledge Context: solar-harness context inject used

## 1. 总体策略

**只产文档不动运行时**。Builder 接到本计划后,在 `~/.solar/harness/sprints/` 下产出 7 类 artifact (matrix / risk-register / non-goals / cannot-dispatch-to-builder / traceability-upgrade / prd.html / planning.html / handoff)。**不修改** `/Users/sihaoli/Solar/` 任何 python/typescript 代码。

write_scope 全部落在 sprints/ 目录内,与 epic.task_graph 中 S01 的 `sprints/*prd.md` + `sprints/*traceability.json` 约束兼容(本切片产物名都在此模式或同目录扩展)。

## 2. 并行 / 串行布局

```
Layer 1 (并行 5 节点 — write_scope 互不重叠):
  N1 requirements_matrix.md      — 从 design.md §2 抽 P0 O-01..O-14 + P1/P2/P3 follow-up
  N2 risk_register.md            — 从 design.md §7 抽 R-01..R-08 + owner + rollback
  N3 non_goals.md                — 从 design.md §3 抽 8 条 + 每条反例
  N4 cannot_dispatch_to_builder.md — 从 design.md §5 抽 6 类工作
  N5 prd.html                    — markdown -> html (prd.md)

Layer 2 (串行, 依赖 N1+N3+N4):
  N6 traceability_upgrade        — epic.traceability.json children[*] 加 outcomes 数组

Layer 3 (依赖 N1+N2+N3+N4+N6):
  N7 planning.html               — markdown -> html (design.md + plan.md + 4 个 artifact 合并)

Layer 4 (Gate G_S01_PLANNING, 依赖 N1..N7 全 passed):
  N8 handoff.md                  — 中文证据表 7 列 + 上游/下游/未闭环 + 命令清单 + S02 入参锚点
```

Gate `G_S01_PLANNING` = N1..N7 全 passed → N8 才能写 handoff。

## 3. 节点验收 Gate (含证据命令)

| Node | 验收 Gate | 证据命令 |
|------|-----------|----------|
| N1 | requirements-matrix.md 含 O-01..O-14 全 14 行 + F-P1/F-P2/F-P3 follow-up 段 | `grep -cE '^\| O-(0[1-9]\|1[0-4])' .../requirements-matrix.md` >= 14 |
| N2 | risk-register.md 含 R-01..R-08 全 8 行,每行含 owner + rollback 两列 | `grep -cE '^\| R-0[1-8]' .../risk-register.md` >= 8 && `grep -c 'Rollback\|rollback' .../risk-register.md` >= 8 |
| N3 | non-goals.md 含 8 条不做项,每条有反例 ("不重写 harness" 的反例 = "rewrite entire harness") | `grep -c '^## ' .../non-goals.md` >= 8 |
| N4 | cannot-dispatch-to-builder.md 含 6 类工作 (schema 设计/broker 链路/dispatcher/审批阈值/兼容层/竞态选型) | `grep -c '^## ' .../cannot-dispatch-to-builder.md` >= 6 |
| N5 | prd.html 存在,size > 4KB,含 `<html` tag + PRD §4 Functional Requirements 锚点 | `test -s .../prd.html && grep -c '<html' .../prd.html >= 1 && grep -c 'Functional Requirements\|Pkg 1' .../prd.html >= 1` |
| N6 | epic.traceability.json children 每项含非空 outcomes 数组 | `jq '[.children[] \| select((.outcomes \| length) > 0)] \| length' .../epic*.traceability.json` == 5 |
| N7 | planning.html 存在,size > 8KB,含 design + plan + 4 artifact 内容 | `grep -c 'Outcomes 拆解' .../planning.html >= 1 && grep -c '总体策略' .../planning.html >= 1 && grep -c '反例' .../planning.html >= 1` |
| N8 | handoff.md 含 5 二级段 (证据表/上游依赖/下游影响/未闭环/S02 入参锚点);中文证据表 7 列 | `grep -c '^## ' .../handoff.md` >= 5 |

## 4. Write Scope 矩阵（并行安全）

| Node | Write Scope | Read Scope |
|------|-------------|------------|
| N1 | `sprints/{sid}.requirements-matrix.md` | design.md, prd.md |
| N2 | `sprints/{sid}.risk-register.md` | design.md §7 |
| N3 | `sprints/{sid}.non-goals.md` | design.md §3, prd.md §8 |
| N4 | `sprints/{sid}.cannot-dispatch-to-builder.md` | design.md §5 |
| N5 | `sprints/{sid}.prd.html` | prd.md |
| N6 | `sprints/{epic}.traceability.json` | design.md §4, epic.traceability.json |
| N7 | `sprints/{sid}.planning.html` | design.md, plan.md, N1-N4 |
| N8 | `sprints/{sid}.handoff.md` | 全部 |

**冲突检查**:N1..N5 写不同文件名 → 并行安全。N6 写 epic.traceability.json 是该 epic 共享文件,但 epic 调度器只读 children[*].status 字段,不会跟 N6 的 outcomes 字段冲突。

## 5. 模型选择

| Node | 模型 | 理由 |
|------|------|------|
| N1-N4 | sonnet | 中文表格 + 抽取 |
| N5 | sonnet | markdown → html (pandoc/python-markdown) |
| N6 | sonnet | JSON 编辑需要准确性 (jq + python json.load 验) |
| N7 | sonnet | 合并 markdown → html |
| N8 | sonnet | 中文证据表 + 多上游聚合 |

## 6. HTML 渲染兜底

Builder 必须三选一:

```bash
# Option A: pandoc
pandoc -f markdown -t html5 -s -o out.html in.md

# Option B: python markdown
python3 -c "import sys, markdown; print(markdown.markdown(open(sys.argv[1]).read(), extensions=['tables', 'fenced_code']))" in.md > out.html

# Option C: cmark
cmark in.md > out.html
```

三个都不可用时,**写入 handoff 风险段 + 用最简 `<pre>` 包裹纯文本兜底**,不允许跳过。

## 7. 失败回退路径

- N1..N4 表格列对不齐 → 必须先用 `awk -F '|' 'NF<5'` 检查每行列数,补齐再写入。
- N6 升级 traceability.json 失败 (json 非法) → 必须先用 `python3 -c 'import json; json.load(open(...))'` 验合法性。
- N5/N7 HTML 渲染失败 → §6 Option C 兜底 + handoff 风险段标注。
- N8 缺上游产物 → 阻塞 G_S01_PLANNING,不允许 handoff 半截写。

## 8. 完成定义 (DoD)

1. N1..N8 全 passed (8 节点)
2. `solar-harness graph-scheduler validate --graph <task_graph>` exit 0
3. handoff.md §3 表所有 grep/jq 命令真实输出截断 (不允许占位)
4. status.json artifacts 含 `design`, `plan`, `task_graph`, `planning_html`, `prd_html`, `requirements_matrix`, `risk_register`, `non_goals`, `cannot_dispatch_to_builder`, `traceability_upgraded`, `handoff`
5. **不修改** `/Users/sihaoli/Solar/` 任何文件 (用 `git -C /Users/sihaoli/Solar status` 验证)
6. P0 outcomes (O-01..O-14) 全部映射到至少一个 child sprint
7. P1/P2/P3 outcomes 全部归类 follow-up,不进本 epic task_graph

## 9. 与下游 Sprint 的入参锚点

N8 handoff.md §5 必须明确:

- **S02 architecture 入参**:design.md §6 接口契约骨架 (action_contract / event / broker_coverage) + risk-register.md R-02/R-03 选型决策 + cannot-dispatch-to-builder.md #1/#2/#6
- **S03 core runtime 入参**:S02 design.md (待 S02 产出) + O-03/O-04/O-05/O-07/O-09
- **S04 orchestration_ui 入参**:O-06/O-08 + risk-register.md R-04/R-06/R-08
- **S05 verification_release 入参**:全部 outcomes 的可复现验证命令 + risk-register.md R-07

## 10. 资源与时间

- 估时:N1-N4 各 0.5h (4 节点并行 = 0.5h),N5 0.3h (并行),N6 0.4h,N7 0.4h,N8 0.5h
- 总墙钟 ≈ 2-3h (有并行)
- builder pane 1 个即可 (无重 IO)
