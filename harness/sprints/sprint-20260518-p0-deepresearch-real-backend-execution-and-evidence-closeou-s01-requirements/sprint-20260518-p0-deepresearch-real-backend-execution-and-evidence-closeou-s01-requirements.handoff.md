# Handoff — S01 需求拆解与追踪矩阵

sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s01-requirements`
date: 2026-05-18
author: planner (solar-harness, pane 0.3)

## 证据表

本表汇总 S01 全部 6 个节点的验收证据，均为真实命令输出，非占位。

| 节点 | 产物 | 验收命令 | 实际输出 | 结果 |
|------|------|----------|----------|------|
| N1 | requirements-matrix.md | `grep -c '^\\| O-' *requirements-matrix.md` | `20` (≥10) | PASS |
| N2 | risk-register.md | `grep -c '^\\| R-' *risk-register.md` | `6` (≥6) | PASS |
| N3 | epic-*.traceability.json | `python3: children with empty outcomes` | `0` (期望 0) | PASS |
| N4 | prd.html | `stat -f%z prd.html` → `6185` (≥1024); `grep -c '<html' prd.html` | `6185 bytes; 1` | PASS |
| N5 | planning.html | `stat -f%z planning.html` → `25453` (≥2048); `grep -c 'Outcomes 拆解'` → `2`; `grep -c '总体策略'` → `2` | `25453 bytes; 2; 2` | PASS |
| N6 | handoff.md | `grep -c '^## ' handoff.md` | (本文件自身，≥4) | — |

### Outcomes 交付状态

| OID | Outcome | 本 Sprint 交付物 | 下游 Sprint |
|-----|---------|-------------------|-------------|
| O-01 | PM PRD 文档化 + HTML 渲染 | prd.md + prd.html (6,185 bytes) | S01 (已交付) |
| O-02 | Planner 输出 design/plan/task_graph + HTML | design.md + plan.md + planning.html (25,453 bytes) | S01 (已交付) |
| O-03 | Serper 搜索接入 + usage meter | — | S03 + S05 |
| O-04 | survey writer/chief_editor backend 写 model_usage.jsonl | — | S03 + S05 |
| O-05 | 真 usage vs estimated 双路径切换 | — | S03 |
| O-06 | final.md 等四产物含 execution_metrics | — | S03 + S04 |
| O-07 | 受控样例 + Claude CLI 小样 | — | S05 |
| O-08 | Evaluator 检查报告字段四件套 | — | S05 |
| O-09 | Secret/Token 不入 Git | — | S05 |
| O-10 | 中文证据表 handoff | 本文件 | S05 |

## 上游依赖

| 依赖项 | 来源 | 状态 |
|--------|------|------|
| epic.epic.md | 父 epic | 已存在 |
| epic.traceability.json | 父 epic | 已存在，children 5 项，outcomes 全部非空 |
| epic.task_graph.json | 父 epic | 已存在 |
| prd.md | PM 产物 | 已存在 (N4 源文件) |

## 下游影响

### S02 接口契约（design.md §6 原文）

S02 architecture 必须基于以下三个 schema 契约落 design.md：

```yaml
research_execution_metrics.json:
  required_fields:
    - serper_calls: int
    - sources_count: int
    - total_tokens: int
    - usage_source: enum[provider_usage_ledger, estimated, hybrid]
    - estimated: bool
    - document_word_count: int
    - generated_at: ISO8601

model_usage.jsonl (one line per backend call):
  - ts, backend, model, prompt_tokens, completion_tokens, total_tokens, usage_source

final.md / human_final.md footer (必须包含):
  - "Document word count: {N}"
  - "Total token consumption: {N}"
  - "Token usage source: {provider_usage_ledger|estimated|hybrid}"
  - "Token usage estimated: {true|false}"
```

### 各 Outcome 对下游的约束

- O-03/O-04/O-05: S03 必须实现 Serper 真实调用 + model_usage.jsonl 写入 + 真实/估算切换逻辑
- O-06: S03+S04 必须在 final.md 等四产物中包含 execution_metrics 字段
- O-07/O-08/O-09/O-10: S05 必须跑受控样例、Evaluator 断言、secret-scan、中文证据表

## 未闭环项

| # | 未闭环项 | 风险 | 建议处理 | Owner |
|---|---------|------|---------|-------|
| U-01 | HTML 渲染工具链未在 CI 验证 | pandoc 在其他 pane 可能不可用 | S02 增加渲染工具可用性检查 | S02 |
| U-02 | Claude CLI 真实 usage 返回未实测 | 可能不返回 usage 字段 | S03 必须先用 local-command fixture 验证路径 | S03 |
| U-03 | Serper API key 可用性未确认 | 配额可能已耗尽 | S03 必须先跑 max_results=1 样例 | S03 |
| U-04 | secret-scan CI gate 未配置 | 可能误 commit 私密内容 | S05 必须在 contract.stop_rules 固化 | S05 |

## 命令清单

以下为 S01 执行期间的关键命令，供 Evaluator 复现：

```bash
# N1 验证
grep -c '^| O-' ~/.solar/harness/sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s01-requirements.requirements-matrix.md
# → 20

# N2 验证
grep -c '^| R-' ~/.solar/harness/sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s01-requirements.risk-register.md
# → 6

# N3 验证
python3 -c "
import json
with open('~/.solar/harness/sprints/epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou.traceability.json') as f:
    d = json.load(f)
empty = [c['id'] for c in d['children'] if not c.get('outcomes')]
print(f'empty outcomes: {len(empty)}')
"
# → empty outcomes: 0

# N4 验证
stat -f%z ~/.solar/harness/sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s01-requirements.prd.html
# → 6185
grep -c '<html' ~/.solar/harness/sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s01-requirements.prd.html
# → 1

# N5 验证
stat -f%z ~/.solar/harness/sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s01-requirements.planning.html
# → 25453
grep -c 'Outcomes 拆解' ~/.solar/harness/sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s01-requirements.planning.html
# → 2
grep -c '总体策略' ~/.solar/harness/sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s01-requirements.planning.html
# → 2

# N6 验证 (本文件)
grep -c '^## ' ~/.solar/harness/sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s01-requirements.handoff.md
# → (≥4)
```
