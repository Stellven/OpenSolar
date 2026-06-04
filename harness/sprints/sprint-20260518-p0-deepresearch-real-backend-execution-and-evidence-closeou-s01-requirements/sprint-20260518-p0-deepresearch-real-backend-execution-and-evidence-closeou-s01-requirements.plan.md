# Plan — S01 需求拆解与追踪矩阵

sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s01-requirements`
slice: `requirements`
date: 2026-05-18

## 1. 总体策略

本切片**只产文档不动运行时**。Builder 接到本计划后，需在 `~/.solar/harness/sprints/` 目录下产出 6 类文件（matrix / risk-register / 升级版 traceability / prd.html / planning.html / handoff.md），无需修改 `/Users/sihaoli/Solar/` 任何代码。

## 2. 并行 / 串行布局

```
Layer 1 (并行 3 节点):
  N1 requirements_matrix.md      — 把 design.md 的 §2 outcomes 抽出独立成表
  N2 risk_register.md            — 把 design.md §7 抽出独立 + 加缓解 owner
  N4 prd.html                    — markdown -> html (prd.md)
                                  （N4 与 N1/N2 不共享 write_scope）

Layer 2 (串行, 依赖 N1):
  N3 traceability_upgrade        — 在 epic.traceability.json children[*] 加 outcomes 数组

Layer 3 (依赖 N1+N2+N3+N4):
  N5 planning.html               — markdown -> html (design.md + plan.md 合并)

Layer 4 (依赖 N5, Gate G_PLANNING):
  N6 handoff.md                  — 中文证据表 + 上游/下游/未闭环项 + 命令清单
```

并行 gate `G_PLANNING`：N1+N2+N3+N4+N5 全 passed 才允许 N6 写 handoff。

## 3. 每个节点的验收 Gate

| Node | 验收 Gate | Grep 证据命令 |
|------|-----------|---------------|
| N1 | `requirements-matrix.md` 含 O-01..O-10 全部行，且每行 ≥ 5 列 | `grep -c '^\\| O-' .../requirements-matrix.md` ≥ 10 |
| N2 | `risk-register.md` 含 R-01..R-06 全部行，每行有 owner | `grep -c '^\\| R-' .../risk-register.md` ≥ 6 |
| N3 | `epic-*.traceability.json` children 每项含 `outcomes` 数组且非空 | `jq '.children[] \| select(.outcomes \| length == 0)' .../epic*.traceability.json` 为空 |
| N4 | `*.prd.html` 存在，size > 1KB，含 `<html` tag | `test -s .../prd.html && grep -c '<html' .../prd.html ≥ 1` |
| N5 | `*.planning.html` 存在，size > 2KB，含 design + plan 两段 | `grep -c 'Outcomes 拆解' .../planning.html ≥ 1 && grep -c '总体策略' .../planning.html ≥ 1` |
| N6 | `*.handoff.md` 含「证据表」「上游依赖」「下游影响」「未闭环项」四个段 | `grep -c '## ' .../handoff.md` ≥ 4 |

## 4. Write Scope 矩阵（并行安全）

| Node | Write Scope | Read Scope |
|------|-------------|------------|
| N1 | `sprints/*-s01-requirements.requirements-matrix.md` | design.md, prd.md |
| N2 | `sprints/*-s01-requirements.risk-register.md` | design.md |
| N3 | `epic-20260518-*.traceability.json` | design.md, epic.traceability.json |
| N4 | `sprints/*-s01-requirements.prd.html` | prd.md |
| N5 | `sprints/*-s01-requirements.planning.html` | design.md, plan.md |
| N6 | `sprints/*-s01-requirements.handoff.md` | 全部上游产物 |

**冲突检查**：N1/N2/N3/N4 的 write_scope 互不重叠 → 可并行；N3 写 `epic-*.traceability.json` 是该 epic 的共享文件，与 epic 调度器不冲突（epic 调度器只读 children[*].status）。

## 5. 模型选择

- N1/N2/N4/N5/N6：`sonnet`（文档生成默认，避开 GLM 1210 历史踩坑）。
- N3：`sonnet`（JSON 升级需要 schema 准确性）。

## 6. HTML 渲染兜底

如果 builder pane 没有 `solar-harness render` 子命令，使用：

```bash
# Option A: pandoc (优先)
pandoc -f markdown -t html5 -s -o out.html in.md

# Option B: python markdown
python3 -c "import sys, markdown; print(markdown.markdown(open(sys.argv[1]).read(), extensions=['tables', 'fenced_code']))" in.md > out.html

# Option C: cmark / markdown-it
cmark in.md > out.html
```

Builder 必须三选一，如果三个都不可用，**写入 handoff.md 风险段 + 写一个最简 `<html><body>` 包裹纯文本兜底**，不能跳过。

## 7. 失败回退路径

- N3 升级 traceability.json 失败（jq 报错）→ 必须先用 `python3 -c 'import json; json.load(open(...))'` 验合法性，再写入。
- N4/N5 HTML 渲染失败 → 用 §6 Option C 兜底 + 在 handoff.md 风险段标注。
- N6 缺上游产物 → 阻塞 G_PLANNING，不允许 handoff 半截写。

## 8. 完成定义（DoD）

- 6 个节点全部 passed。
- `solar-harness graph-scheduler validate --graph <sprint>.task_graph.json` 退出码 0。
- handoff.md 含 §3 表中所有验证命令的真实输出截断（grep -c 数字 + jq 输出）。
- status.json artifacts 含 `design`, `plan`, `task_graph`, `prd_html`, `planning_html`, `handoff`。
- 不修改 `/Users/sihaoli/Solar/` 任何文件（用 git status 验证）。

## 9. 与下游 Sprint 的 handoff 锚点

handoff.md 必须含 §6 接口契约（从 design.md §6 复制）与每个 outcome 的 Owner Sprint，让 S02 architect 直接接住。
