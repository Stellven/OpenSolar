# Plan — S02 架构设计与接口契约

sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture`
slice: `architecture`
date: 2026-05-18

## 1. 总体策略

把 design.md 的关键内容**冻结为独立的可被 grep/jq 消费的 artifact**：schema 文件、状态机 mermaid、降级矩阵 JSON、兼容性 ADR。本切片**不动 `/Users/sihaoli/Solar/` 运行时代码**，所有产出在 `~/.solar/harness/sprints/` 下。

## 2. 并行 / 串行布局

```
Layer 1 (并行 3 节点):
  N1 architecture-schemas.md/json — 三 schema 文件冻结 (design §5)
  N2 state-machine.md             — control + data plane 状态机 (design §3,§4)
  N3 compatibility-matrix.md      — Codex 既有改动兼容映射 (design §9)

Layer 2 (依赖 N1+N2+N3):
  N4 fallback-policy.md/json      — 降级 4 级路径 + 真假切换决策表 (design §6,§10)

Layer 3 (依赖 N1+N2+N3+N4):
  N5 planning.html                — design.md + plan.md + 上面 4 个 artifact 合并渲染
  N6 architecture-adr.md          — 关键架构决策记录 (ADR-001..ADR-005)

Layer 4 (依赖 N5+N6, Gate G_S02_PLANNING):
  N7 handoff.md                   — 中文证据表 + 给 S03/S04 入参锚点
```

并行 gate `G_S02_PLANNING`：N1+N2+N3+N4+N5+N6 全 passed 才允许 N7 写 handoff。

## 3. 节点验收 Gate (含证据命令)

| Node | 验收 Gate | 证据命令 |
|------|-----------|----------|
| N1 | 三 schema 文件齐 (`model_usage.schema.json`, `execution_metrics.schema.json`, `footer_fields.md`)；每个 schema 合法 JSON 或合法 markdown 表 | `jq . *.model_usage.schema.json && jq . *.execution_metrics.schema.json` 退出 0 |
| N2 | state-machine.md 含 control + data 两个 mermaid 图，且节点名与 design.md §3,§4 一致 | `grep -c '```mermaid' *.state-machine.md` >= 2 |
| N3 | compatibility-matrix.md 列出 design §9 的 6 行 Codex 模块映射 | `grep -cE '^\\| (report_metrics\\|model_usage\\|evidence/ledger\\|survey/backends\\|chief_editor\\|internal_mirage)' *.compatibility-matrix.md` >= 6 |
| N4 | fallback-policy.json 含 4 级降级 + 决策表；fallback-policy.md 含 design §6 真假切换 5 行表 | `jq '.levels \| length' *.fallback-policy.json` >= 4 && `grep -cE '^\\| (provider_usage_ledger\\|stream-json\\|tokenizer)' *.fallback-policy.md` >= 3 |
| N5 | planning.html 存在 size > 4KB，含 design + plan + schema 三段 | `grep -c '系统分层' *.planning.html` >= 1 && `grep -c '总体策略' *.planning.html` >= 1 && `grep -c 'model_usage' *.planning.html` >= 1 |
| N6 | architecture-adr.md 含 ADR-001..ADR-005 全部 5 条 | `grep -cE '^## ADR-00[1-5]' *.architecture-adr.md` >= 5 |
| N7 | handoff.md 含 5 个二级段：证据表 / 上游依赖 / 下游影响 / 未闭环项 / S03-S05 入参锚点 | `grep -c '^## ' *.handoff.md` >= 5 |

## 4. Write Scope 矩阵（并行安全）

| Node | Write Scope | Read Scope |
|------|-------------|------------|
| N1 | `sprints/*-s02-architecture.model_usage.schema.json`, `sprints/*-s02-architecture.execution_metrics.schema.json`, `sprints/*-s02-architecture.footer_fields.md` | design.md, S01 design.md §6, `/Users/sihaoli/Solar/harness/lib/research/report_metrics.py` (read-only) |
| N2 | `sprints/*-s02-architecture.state-machine.md` | design.md §3,§4 |
| N3 | `sprints/*-s02-architecture.compatibility-matrix.md` | design.md §9, `/Users/sihaoli/Solar/harness/lib/research/` (read-only ls + grep) |
| N4 | `sprints/*-s02-architecture.fallback-policy.md`, `sprints/*-s02-architecture.fallback-policy.json` | design.md §6,§7,§10 |
| N5 | `sprints/*-s02-architecture.planning.html` | design.md, plan.md, N1-N4 产物 |
| N6 | `sprints/*-s02-architecture.architecture-adr.md` | design.md, N1-N4 产物 |
| N7 | `sprints/*-s02-architecture.handoff.md` | 全部 |

**冲突检查**：N1-N6 write_scope 互不重叠 → 并行安全。N5 与 N6 依赖一致 (N1+N2+N3+N4)，可同 layer 并行。

## 5. 模型选择

- N1: `sonnet` (schema 准确性高)
- N2: `sonnet` (mermaid 语法)
- N3: `sonnet` (代码地形踏勘 → 文档)
- N4: `sonnet` (决策表)
- N5: `sonnet` (HTML 渲染)
- N6: `sonnet` (ADR 写作)
- N7: `sonnet` (中文 handoff)

## 6. 代码地形踏勘清单（N3 builder 必读，read-only）

```bash
# 现状 dump
ls /Users/sihaoli/Solar/harness/lib/research/
ls /Users/sihaoli/Solar/harness/lib/research/survey/
head -100 /Users/sihaoli/Solar/harness/lib/research/report_metrics.py
head -100 /Users/sihaoli/Solar/harness/lib/research/survey/backends.py
head -100 /Users/sihaoli/Solar/harness/lib/research/survey/chief_editor.py
head -50  /Users/sihaoli/Solar/harness/lib/research/evidence/ledger.py
grep -nE "usage|model_usage|provider_usage|estimated" /Users/sihaoli/Solar/harness/lib/research/report_metrics.py | head -20
```

**禁止修改**这些文件，只读。

## 7. HTML 渲染兜底

同 S01 plan §6：pandoc / python markdown / cmark / 最简 `<pre>` 兜底；若全不可用，写入 handoff 风险段。

## 8. 失败回退路径

- N1 schema JSON 写错 → `jq .` 验合法性后再 commit；非法立即重写。
- N3 代码地形差异 (例如字段命名不一致) → 写入 N3 文档 "现状偏差" 段，并标 AR-05 为已观测。
- N4 决策表覆盖不全 → 必须列出 4 级路径每级的 `precondition`/`action`/`postcondition`/`evidence_command`。
- N7 缺上游产物 → 阻塞 G_S02_PLANNING。

## 9. 完成定义 (DoD)

- 7 节点全 passed。
- `solar-harness graph-scheduler validate` 退出 0。
- `jq` 校验 2 个 schema JSON 文件均合法。
- handoff.md 含 §3 表所有 grep -c / jq 输出真实截断。
- status.json artifacts 含 `design`, `plan`, `task_graph`, `planning_html`, `handoff`。
- **不修改** `/Users/sihaoli/Solar/`（用 `git -C /Users/sihaoli/Solar status` 验证 working tree clean 或与开始一致）。

## 10. 与 S03/S04/S05 的入参锚点

handoff.md §5 必须明确：
- **S03 入参**：N1 三 schema + N2 data plane 状态机 + N4 fallback-policy.json + N3 兼容矩阵 + design.md §12.S03
- **S04 入参**：N1 execution_metrics.schema.json + design.md §12.S04（禁解析 markdown）
- **S05 入参**：N4 fallback-policy.json 的 4 级路径 + design.md §12.S05
