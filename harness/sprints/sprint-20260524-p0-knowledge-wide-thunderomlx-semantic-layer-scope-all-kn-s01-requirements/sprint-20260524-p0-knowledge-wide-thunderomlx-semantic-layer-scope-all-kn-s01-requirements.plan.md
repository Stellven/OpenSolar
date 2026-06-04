# Plan — S01 Requirements & Traceability

> Sprint: `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements`
> Knowledge Context: solar-harness context inject used

## Goal
把 Epic 的用户原始大需求拆成 14 个可验收 outcomes + 5 个 "不能直派 builder" 项 + risk register；产出机器可读 traceability JSON 供 Epic 下游 4 个切片消费。本切片 **不写 runtime 代码**。

## Required Gates
- `G_PLAN`   ← S1 (planner)
- `G_IMPL`   ← S2 (S01-builder writes outcomes_matrix.md + traceability.json)
- `G_VERIFY` ← S3 (matrix completeness + 105859 实证 cross-check)
- `G_REVIEW` ← S4 (Epic-level critic: 与 105859 / 134738 / 133807 无 scope 冲突)

## Nodes

| ID | Owner | Gate | Goal | Depends | Write Scope |
|---|---|---|---|---|---|
| S1 | planner (me) | G_PLAN | design / plan / task_graph / planning.html / handoff | — | sprint-...-s01-requirements.{design,plan,task_graph,planning_html,handoff} |
| S2 | builder (doc-writer) | G_IMPL | 把 design.md §3 outcomes 表渲染到独立 `*.outcomes_matrix.md` + `*.traceability.json` | S1 | sprint-...-s01-requirements.{outcomes_matrix.md, traceability.json} |
| S3 | builder | G_VERIFY | 跑实证检查：grep 9 个 lib file 是否存在 + sqlite tables 完整 + 每个 outcome 都有 acceptance/risk/owner + traceability schema 校验 | S2 | sprint-...-s01-requirements.test_report.md |
| S4 | solar-harness | G_REVIEW | Critic：traceability JSON 与 epic.traceability.json schema 兼容 + 与 105859/134738/133807 无 scope 重写冲突 | S3 | sprint-...-s01-requirements.eval.md + review_decision.yaml |

## S2 Output Contract

### outcomes_matrix.md（人可读）
- 必含 14 个 outcome 全表，列：ID / Outcome / Acceptance / Risk / 现状 vs 105859 / 下游 owner
- 必含 "不能直派 builder" 子表（5 行）
- 必含 Epic-level Risk Register

### traceability.json（机器可读）
```jsonc
{
  "schema_version": "solar.epic.traceability.v1",
  "epic_id": "epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn",
  "produced_by_sprint": "sprint-...-s01-requirements",
  "outcomes": [
    {
      "outcome_id": "O1",
      "title": "...",
      "intake_refs": ["§Hard Requirements #1", "§Acceptance/Source coverage"],
      "acceptance": ["..."],
      "risks": [{"id":"...", "level":"...", "mitigation":"..."}],
      "current_state": "reuse-from-105859 | extend-from-105859 | epic-net-new",
      "owner_slices": ["S03_core_runtime"],   // 可多个
      "cannot_dispatch_builder_directly": false,
      "depends_on_outcomes": []
    },
    /* O2..O14 */
  ]
}
```

## Verification Commands (S3 / S4 use)

```bash
# 1. Realism check: 105859 deliverables 确实存在
for f in knowledge_ingest_registry knowledge_ingest_dispatcher knowledge_source_adapters \
         knowledge_spans knowledge_extract_json knowledge_extracted_renderer \
         knowledge_extracted_validator knowledge_qmd_indexer knowledge_ingest_health; do
  [ -f ~/.solar/harness/lib/${f}.py ] || { echo "MISSING ${f}.py"; exit 1; }
done

# 2. Registry actually built
sqlite3 ~/Knowledge/_registry/knowledge_ingest.sqlite '.tables' \
  | grep -qE "documents.*spans.*extract_jobs.*watermarks" \
  || { echo "registry tables incomplete"; exit 1; }

# 3. Matrix completeness: 14 outcomes each have acceptance + risk + owner
python3 - <<'PY'
import json, pathlib, sys
sid = "sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements"
p = pathlib.Path.home() / f".solar/harness/sprints/{sid}.traceability.json"
d = json.loads(p.read_text())
assert d["schema_version"] == "solar.epic.traceability.v1"
assert len(d["outcomes"]) >= 14, f"got {len(d['outcomes'])}"
for o in d["outcomes"]:
    assert o.get("acceptance"), f"{o['outcome_id']} missing acceptance"
    assert o.get("risks"),      f"{o['outcome_id']} missing risks"
    assert o.get("owner_slices"), f"{o['outcome_id']} missing owner"
    assert o.get("current_state") in {"reuse-from-105859","extend-from-105859","epic-net-new"}, \
        f"{o['outcome_id']} invalid current_state"
print("matrix completeness OK; outcomes=", len(d["outcomes"]))
PY

# 4. DAG validate
~/.solar/bin/solar-harness graph-scheduler validate \
  --graph ~/.solar/harness/sprints/sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s01-requirements.task_graph.json
```

## Stop Rules
- 任一 verification 命令 FAIL → 不进下一节点
- outcome matrix 任一 outcome 缺 acceptance/risk/owner → S2 不算 done
- traceability JSON 没有 `current_state` 三选一 enum → S2 不算 done
- handoff.md 不含 "上游依赖 + 下游影响 + 未闭环项" 三段 → S2 不算 done
- 任何"等价于已完成"声明无证据 → S2/S4 拒收
- 缺 verifier 决策 → 不进 DONE
