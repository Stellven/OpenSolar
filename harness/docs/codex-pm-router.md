# Codex PM Router

更新日期: 2026-05-23

## 目的

`codex-pm-router` 是 Codex 侧的 PM intake compiler。

它的职责不是替代 `solar-harness` planner，而是在进入 `solar-harness` 之前，先把用户需求规范化成三类之一：

- `short_impl`
- `full_spec`
- `research`

然后给出稳定的：

- PRD 变体
- contract 变体
- task graph 变体
- lane / priority / acceptance profile

## 组成

```text
/Users/lisihao/.codex/skills/codex-pm-router/
  SKILL.md
  templates/
  references/
  scripts/compile.sh

/Users/lisihao/Solar/harness/tools/codex_pm_router.py
```

其中：

- skill 负责 Codex 侧可安装入口和模板组织
- `codex_pm_router.py` 负责可测试的编译逻辑

## 使用方式

```bash
python3 /Users/lisihao/Solar/harness/tools/codex_pm_router.py \
  --text "fix the cache miss bug in allocator" \
  --format json
```

研究型需求：

```bash
python3 /Users/lisihao/Solar/harness/tools/codex_pm_router.py \
  --text "Analyze these papers and improve PM writing" \
  --paper "arXiv:2511.01815" \
  --paper "ICLR 2026 coding agent paper" \
  --format json
```

## 输出契约

编译器输出：

- `pm_intake`
- `classification`
- `prd_variant`
- `contract_variant`
- `dag_variant`
- `lane_hint`
- `priority`
- `acceptance_profile`
- `task_graph_skeleton`

## Solar 接口

为了接纳 Codex PM Router 输出，当前 schema 已扩展：

- `schemas/product-brief.schema.json`
  - `request_type`
  - `template_variant`
  - `pm_intake`
- `schemas/task-graph.schema.json`
  - `dag_variant`
  - `research_mode`
  - `evidence_policy`
  - `logical_operator`
  - `verifier_required`
  - `research_stage`

## 边界

- 这是 Codex 外层 intake compiler。
- `solar-harness` planner 仍然是内层 execution compiler。
- research 请求默认必须走 evidence-ledger 风格 DAG，不应降级成普通 implementation-first 流程。
