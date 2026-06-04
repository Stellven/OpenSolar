# Plan — DeepResearch Professor-Grade Survey Quality Hardening · S04 Orchestration-UI

Sprint: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s04-orchestration-ui`
Epic: `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build`
Slice: `orchestration-ui`
Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-graph, harness-contracts, harness-intent

## 1. DAG (6 nodes, 2 layers)

```text
N1 source_quality_view ──┐
N2 argument_density_view ┤
N3 contradiction_view  ──┼── N6 join: status-epic + dispatch-hint + handoff + parent patch
N4 exploration_view    ──┤
N5 gate_report_view    ──┘
```

Layers: `[[N1, N2, N3, N4, N5], [N6]]` — 5-way parallel + 1 join.

## 2. Node-by-Node Execution

| Node | Goal | Write Scope (exclusive) | Depends | Gate |
|------|------|-------------------------|---------|------|
| N1 | 实现 `source_quality_view.py`：把 S03 `SourceQualityDistribution` → CLI 行（canonical_coverage / primary_ratio / stuffing_alerts）+ JSON dict + 6 unit test + fixture | `harness/lib/research/survey/cli/source_quality_view.py`, `tests/research/survey/cli/test_source_quality_view.py`, `tests/research/survey/cli/fixtures/source_quality_pass.json`, `tests/research/survey/cli/fixtures/source_quality_fail_stuffing.json` | — | G1 |
| N2 | 实现 `argument_density_view.py`：把 S03 `ArgumentDensityProfile` → per-section table + `low_density_sections` 列表 + JSON dict + 6 unit test + fixture | `harness/lib/research/survey/cli/argument_density_view.py`, `tests/research/survey/cli/test_argument_density_view.py`, `tests/research/survey/cli/fixtures/argument_density_partial.json`, `tests/research/survey/cli/fixtures/argument_density_full.json` | — | G2 |
| N3 | 实现 `contradiction_matrix_view.py`：把 S03 `ContradictionMatrix` → CLI 摘要 + 装饰性 matrix WARNING + JSON dict + 6 unit test + fixture | `harness/lib/research/survey/cli/contradiction_matrix_view.py`, `tests/research/survey/cli/test_contradiction_matrix_view.py`, `tests/research/survey/cli/fixtures/contradiction_matrix_decorative.json`, `tests/research/survey/cli/fixtures/contradiction_matrix_active.json` | — | G3 |
| N4 | 实现 `exploration_view.py`：把 S03 `ExplorationRunResult` → `proposed/eliminated/selected` count + elimination_log path + JSON dict + 6 unit test + fixture | `harness/lib/research/survey/cli/exploration_view.py`, `tests/research/survey/cli/test_exploration_view.py`, `tests/research/survey/cli/fixtures/exploration_run_typical.json`, `tests/research/survey/cli/fixtures/exploration_run_high_kill.json` | — | G4 |
| N5 | 实现 `gate_report_view.py`：把 S03 `GateReport` → 4-gate verdict 表 + artifact_paths 列表 + JSON dict + 6 unit test + fixture | `harness/lib/research/survey/cli/gate_report_view.py`, `tests/research/survey/cli/test_gate_report_view.py`, `tests/research/survey/cli/fixtures/gate_report_all_pass.json`, `tests/research/survey/cli/fixtures/gate_report_mixed.json` | — | G5 |
| N6 | join：注册 5 view + `status --epic` 子命令 + autopilot dispatch hint + handoff + 父 traceability patch | `harness/lib/research/survey/cli/__init__.py`, `harness/lib/research/survey/cli/_views_registry.py`, `harness/lib/orchestration/epic_status_view.py`, `harness/lib/orchestration/dispatch_gate_hint.py`, `harness/cli/cmd_status_epic.py`, `tests/orchestration/test_epic_status_view.py`, `tests/orchestration/test_dispatch_gate_hint.py`, `sprints/…s04-orchestration-ui.handoff.md`, `sprints/epic-…traceability.json` | N1, N2, N3, N4, N5 | G6 |

## 3. Parallelism

- N1-N5 ∥ 5-way：每个写独立 view + tests + fixtures，write_scope 互斥；只读 S02 arch spec + S03 schemas / dataclass
- N6 join：必须等 5 个 view 全部 passed 后才能开始（5 view 注册 + status epic + dispatch hint + handoff matrix）
- 5-way batch 同时派 5 builder pane 略激进；建议 2 + 3 拆批（见 §4），避免 pane 资源饿死

## 4. Dispatch Batches

| Batch | Nodes | Trigger | 备注 |
|-------|-------|---------|------|
| B1 | N1, N2, N3 | S03 passed + status=active 后立即派发 | 3 个最熟的 view（schema 已稳） |
| B2 | N4, N5 | B1 中任意 ≥ 1 passed 后派发 | N5 aggregator view 引用最多 |
| B3 | N6 | N1-N5 全部 G1-G5 passed | join 单 pane |

如 pane 资源充足，B1+B2 可合并为单 batch 5-way；graph_scheduler `layers ready` 自动决定。

## 5. Per-Node Acceptance

### N1 — source_quality_view.py
- `format_source_quality(dist: SourceQualityDistribution) -> str` 函数存在并纯函数
- `to_dict_source_quality(dist: SourceQualityDistribution) -> dict` 函数存在
- 输出含 `canonical_coverage` / `primary_ratio` / `stuffing_alerts_count`（至少 3 字段）
- `@register_view("source_quality")` 装饰器 wired（N6 完成 registry 后由 N1 验证）
- ≥ 6 unit test：fixture-pass / fixture-stuffing / empty / boundary / json-output / table-output
- 禁止 import requests/urllib/httpx/openai/anthropic（grep 检查）
- 禁止使用 random / datetime.now / time.time / uuid.uuid4（grep 检查）
- 禁止 @mock.patch / MagicMock（grep 检查）

### N2 — argument_density_view.py
- `format_argument_density(profile: ArgumentDensityProfile) -> str` + `to_dict_argument_density()`
- 输出含 per-section density table + `low_density_sections` 列表
- 输出含 5 维度 column（mechanism / taxonomy / evaluation / failure / engineering）
- ≥ 6 unit test：partial-coverage / full-coverage / single-section / empty / json-output / table-output
- 其它同 N1（禁 import / 禁 mock / 纯函数）

### N3 — contradiction_matrix_view.py
- `format_contradiction_matrix(matrix: ContradictionMatrix) -> str` + `to_dict_contradiction_matrix()`
- 输出含 `total_claims / claims_with_negative / decorative` 字段
- 装饰性检测取 matrix.is_decorative 字段（S03 已计算）；view 不重判
- 装饰性 → 输出 `[WARN] decorative matrix: <claims_no_neg>/<total>`
- ≥ 6 unit test：decorative / active / single-claim / boundary / json-output / table-output
- 其它同 N1

### N4 — exploration_view.py
- `format_exploration(result: ExplorationRunResult) -> str` + `to_dict_exploration()`
- 输出含 `proposed_count / eliminated_count / selected_count / elimination_log_path`
- ≥ 6 unit test：typical / high-kill / no-elimination / single-direction / json-output / table-output
- 其它同 N1

### N5 — gate_report_view.py
- `format_gate_report(report: GateReport) -> str` + `to_dict_gate_report()`
- 输出含 4 gate verdict 行（O1-O4）+ artifact_paths 列表 + summary verdict
- ≥ 6 unit test：all-pass / mixed / all-fail / missing-gate / json-output / table-output
- 其它同 N1

### N6 — join + registry + status epic + dispatch hint + handoff + traceability
- `survey/cli/__init__.py` 暴露 5 view 函数 + VIEW_REGISTRY
- `survey/cli/_views_registry.py` 暴露 `register_view(name)` 装饰器 + `VIEW_REGISTRY: dict[str, callable]`
- 5 view 通过 `from survey.cli import VIEW_REGISTRY; len(VIEW_REGISTRY) == 5` 验证
- `harness/lib/orchestration/epic_status_view.py` 含 `render_epic_status(epic_id) -> str`，列：epic_id / slice / sprint_id_short / status / ready_or_blocked / deps_missing / target_role / capability_required
- `harness/lib/orchestration/dispatch_gate_hint.py` 含 `inject_gate_hint(dispatch_context: str, sprint_id: str) -> str`；fail-open（异常→返回原 context；写 stderr warning）
- `harness/cli/cmd_status_epic.py` 注册 `--epic <id>` 子命令到 `solar-harness status`；不动既有 `status` 命令默认行为
- ≥ 4 + 4 unit test（orchestration / dispatch hint 各 ≥ 4）
- handoff.md 含 7 surfacing entry（5 view + status-epic + dispatch-hint）
- handoff.md 含 `s05_can_start: true` + 不声称 epic 完成 + 不声称 E2E ready
- 父 traceability `children[3].orchestration_ui_ready=true`；schema_version + children 顺序 + 长度未变（jq 检查）

## 6. Routing Policy

- 所有节点 `preferred_model=sonnet`（GLM 1210 已踩 5 次）
- 禁止 builder webfetch / web search / 网络写
- 上游证据源（必须 read_scope）：
  - `sprints/…-s01-requirements.outcomes.md`
  - `sprints/…-s01-requirements.non-builder-boundary.md`
  - `sprints/…-s02-architecture.handoff.md`
  - `sprints/…-s02-architecture.source-quality-arch.md`
  - `sprints/…-s02-architecture.argument-density-arch.md`
  - `sprints/…-s02-architecture.contradiction-matrix-arch.md`
  - `sprints/…-s02-architecture.exploration-arch.md`
  - `sprints/…-s02-architecture.gate-report-arch.md`
  - `sprints/…-s03-core-runtime.handoff.md`
  - `harness/lib/research/survey/schemas.py`（S03 扩展后的 dataclass 列表）
  - `harness/lib/research/survey/gates/_registry.py`
- 上游 prerequisites 必须 passed：S01 + S02 + S03

## 7. Stop Rules

- 写 .ts / .js / .sh / .sql 文件 → fail
- 修改 frozen 5 module 或 6 frozen file → fail
- 修改 S03 D1-D8 dataclass 公共 API → fail
- 修改 `survey/__init__.py` 已有导出 → fail
- 修改 survey-eval / survey-review / survey-compile / survey-plan / status 主入口 → fail
- view 层 import requests/urllib/httpx/openai/anthropic → fail
- 使用 random / datetime.now / time.time / uuid.uuid4 → fail
- 使用 @mock.patch / MagicMock → fail
- 任何节点测试数 < 6（N6 ≥ 8）→ fail
- sprint 总测试数 < 35 → fail
- N6 之前任何节点动 parent traceability → graph_scheduler 阻断
- handoff 声称 "epic 完成" / "E2E 已验证" / "S05 已就绪" → fail
- autopilot dispatch hint 抛异常阻断主流程 → fail（必须 fail-open）

## 8. Exit Criteria (Sprint passed)

- N1-N6 6 节点 evaluator verdict 全部 PASS
- D1-D6 6 deliverable 齐备且 cross-consistent
- 父 `epic-…traceability.json` `children[3].orchestration_ui_ready=true`（schema_version + children 顺序未变）
- A1-A17 17 条 acceptance 全过（design.md §8）
- 全部测试 pass：`pytest tests/research/survey/cli/ tests/orchestration/` ≥ 35 passed

## 9. Evaluator Entry Points

- 看 design.md §8 Acceptance Contract（A1-A17）
- grep 5 view 文件存在 + `format_*` / `to_dict_*` 函数签名
- pytest 跑 ≥ 35 test pass
- jq `.children[3].orchestration_ui_ready == true` + `.schema_version == "solar.epic.traceability.v1"` + `len(.children) == 5`
- diff S03 D1-D8 dataclass 公共 API（无变更）
- diff `survey/__init__.py` 既有导出（无新增 - 行）
- grep view 层 import requests/urllib/httpx/openai/anthropic（无）
- grep view 层 random / datetime.now / time.time / uuid.uuid4（无）
- grep view 层 @mock.patch / MagicMock（无）

## 10. Out of Scope

- E2E survey-continue 实际跑（S05）
- gate 数值阈值（S05）
- 新增 gate 逻辑（S03 已闭合）
- watch / tail status UI（future）
- markdown CLI format 选项（YAGNI）
- 修改 evaluator 主流程

## 11. Current Status

- status: drafting → active（本次 planner pass 完成后翻）
- phase: prd_ready → planning_complete
- handoff_to: planner → builder_parallel
- target_role: planner → builder_main
- artifacts: design.md ✓ / plan.md ✓ / task_graph.json ✓
- prerequisites: S01:passed ✓ / S02:passed ✓ / S03:passed (blocks_until enforced)
