# Design — DeepResearch Professor-Grade Survey Quality Hardening · S04 Orchestration-UI

Sprint: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s04-orchestration-ui`
Epic: `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build`
Slice: `orchestration-ui`
Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-graph, harness-contracts, harness-intent

## 1. Sprint Intent

把 S03 已交付的 4 gate + 1 explorer + 1 aggregator 的 evidence artifact **接到 survey-* CLI 表面**，并把 epic / child sprint / capability / 阻塞原因显示到 `status --epic` 子命令 + dispatch context hint，让评审、监护人、教授用户都能从可见运行时证据判定 PASS/FAIL，而不是靠自然语言声明。

S04 不实现新 gate 逻辑、不修改 frozen 5 module、不重写 survey-* 入口命令、不做 E2E run（S05）。

## 2. Scope Lock

### In-scope (S04 build)
- `harness/lib/research/survey/cli/` 子包（view 层）：5 个 view 模块对应 4 gate + 1 explorer
- `harness/lib/research/survey/cli/__init__.py` + `_views_registry.py`：view 插件注册（attach-only formatter）
- `survey-eval` / `survey-review` / `survey-compile` / `survey-plan` CLI 入口的 view 层 attach hook（不重写主逻辑）
- `solar-harness status --epic <id>` 子命令：展示 epic 子 sprint ready/blocked + dependency + capability 矩阵
- autopilot dispatch context capability gate hint 注入（best-effort，hint-only）
- evaluator 消费 gate_report.json 的 attach 点（read-only consumption；不改 evaluator 主流程）
- 全部单测 + fixture JSON

### Out-of-scope (其它 slice / 后续 sprint)
- 新 gate 逻辑（S03 已完成）
- 4 gate impl + explorer + aggregator + runner_hook（S03）
- E2E survey-continue sample run + strict tests + evidence artifact（S05）
- 数值阈值（S05）
- 修改 frozen 5 module 或 6 frozen file
- 修改 `survey/__init__.py` 已有导出
- watch / tail 模式 status UI（future）
- markdown CLI format 选项（YAGNI）

## 3. Planner-Locked Non-Builder Decisions

| 锁项 | 锁定值 | 锁定理由 |
|------|--------|--------|
| CLI 默认 format | `table`（终端宽 80 列默认）；`--json` 输出 dataclass.to_dict() | YAGNI markdown；保持与既有 survey-* CLI 风格一致 |
| status UI 阻塞原因来源 | 直接读 status.json `history[].blocked_by` + traceability.json `depends_on`；不缓存 | 实时一致；events.jsonl 是兜底 |
| autopilot hint 注入位置 | dispatch.md 的 `<solar-capability-context>` 节末，追加 `## Gate Readiness Hint` 子节 | 已有 capability-context schema；不新建节 |
| autopilot hint 失败策略 | fail-open：hint 计算失败 → 跳过注入，不阻塞 dispatch | 与 capability hint 现行 intent rule 一致 |
| gate_report.json 路径 | `runtime/survey-continue/<run_id>/gate_report.json`（S03 plan §5 已定） | S04 view 层从此路径读 |
| 装饰性 matrix 检测出处 | S03 O3 gate（已交付） | S04 view 只展示 warning，不重新判定 |
| view 层确定性约束 | 全部纯函数；禁 random / datetime.now / time.time / 网络 IO | 与 S03 pure_function_policy 一致 |
| view 层格式化语言 | 仅英文 + 数字 + 路径，避免 emoji / 中文 ASCII width 不一致 | CI capture 稳定；与 evaluator 既有 CLI 一致 |
| `status --epic` 默认列 | epic_id, slice, sprint_id (short), status, ready/blocked, deps_missing, target_role, capability_required | 7 列，80 列终端可容纳 |
| epic 子 sprint short_sprint_id | last segment after `-build-`（e.g. `s04-orchestration-ui`） | 可读 |

## 4. Frozen Interface Boundaries

### 5 frozen public APIs（S04 不动；只 read）
- `source_authority.check_source_authority()`
- `literature_mapping.SourceMatrix`
- `controversy.contradiction_slots` pipeline
- `chapter_review.compile_survey()`
- `chief_editor.*`

### 6 frozen files（S04 不动）
- `coordinator.sh` / `autopilot.sh` / `dispatcher.sh` / `phase-state-machine.sh` / `solar-harness.sh` / `survey/__init__.py` 既有导出

### S03 D1-D8 frozen schemas（S04 consume-only）
- `SourceQualityDistribution` / `StuffingAlert`
- `ArgumentDensityProfile` / `DimensionApplicability`
- `ContradictionMatrix` / `ClaimEvidenceLink`
- `ExplorationDirection` / `EliminationRecord` / `ExplorationRunResult`
- `GateReport`
- 全部 dataclass 含 `to_dict()` 方法（S03 已交付）

### CLI 入口（S04 attach-only，不重写）
- `solar-harness survey-eval` 主入口（attach view layer at format step）
- `solar-harness survey-review` 主入口
- `solar-harness survey-compile` 主入口
- `solar-harness survey-plan` 主入口
- `solar-harness status` 主入口（仅扩展子命令 `--epic`，不改默认行为）

## 5. Architecture Layout

```
harness/lib/research/survey/cli/
    __init__.py                  # public exports
    _views_registry.py           # view registry + register_view decorator
    source_quality_view.py       # N1: SourceQualityDistribution → CLI rows
    argument_density_view.py     # N2: ArgumentDensityProfile → per-section table
    contradiction_matrix_view.py # N3: ContradictionMatrix → CLI rows + decorative warning
    exploration_view.py          # N4: ExplorationRunResult → count summary + log path
    gate_report_view.py          # N5: GateReport → 4-gate verdict summary

harness/lib/orchestration/
    epic_status_view.py          # N6: status --epic <id> renderer
    dispatch_gate_hint.py        # N6: autopilot dispatch context hint generator

harness/cli/
    cmd_status_epic.py           # N6: register --epic subcommand for solar-harness status

tests/research/survey/cli/
    test_source_quality_view.py  # N1: ≥6 cases
    test_argument_density_view.py # N2: ≥6
    test_contradiction_matrix_view.py # N3: ≥6
    test_exploration_view.py     # N4: ≥6
    test_gate_report_view.py     # N5: ≥6
    fixtures/                    # synthetic dataclass JSON
        source_quality_pass.json
        source_quality_fail_stuffing.json
        argument_density_partial.json
        contradiction_matrix_decorative.json
        exploration_run_typical.json
        gate_report_mixed.json

tests/orchestration/
    test_epic_status_view.py     # N6: ≥4
    test_dispatch_gate_hint.py   # N6: ≥4
```

Total: ≥ 6 view tests × 5 + 4 × 2 = ≥ 38 unit tests (sprint floor ≥ 35 enforced via policy)

## 6. DAG

```text
N1 source_quality_view ──┐
N2 argument_density_view ┤
N3 contradiction_view  ──┼── N6 join: status-epic + dispatch-hint + handoff + parent patch
N4 exploration_view    ──┤
N5 gate_report_view    ──┘
```

Layers: `[[N1, N2, N3, N4, N5], [N6]]` — 5-way parallel + 1 join.

## 7. Deliverables

| ID | Owner | Owns (write_scope, exclusive) | Goal |
|----|-------|-------------------------------|------|
| D1 | N1 | `survey/cli/source_quality_view.py` + `tests/.../test_source_quality_view.py` + `fixtures/source_quality_*.json` | 把 SourceQualityDistribution → CLI 行（canonical_coverage / primary_ratio / stuffing_alerts）|
| D2 | N2 | `survey/cli/argument_density_view.py` + `tests/.../test_argument_density_view.py` + `fixtures/argument_density_*.json` | 把 ArgumentDensityProfile → per-section table + low_density_sections 列表 |
| D3 | N3 | `survey/cli/contradiction_matrix_view.py` + `tests/.../test_contradiction_matrix_view.py` + `fixtures/contradiction_matrix_*.json` | 把 ContradictionMatrix → CLI 摘要 + 装饰性矩阵 WARNING（≥ N claim 无 negative ref → 装饰）|
| D4 | N4 | `survey/cli/exploration_view.py` + `tests/.../test_exploration_view.py` + `fixtures/exploration_run_*.json` | 把 ExplorationRunResult → `proposed/eliminated/selected` count + elimination_log path |
| D5 | N5 | `survey/cli/gate_report_view.py` + `tests/.../test_gate_report_view.py` + `fixtures/gate_report_*.json` | 把 GateReport → 4-gate verdict 表 + artifact_paths 列表 |
| D6 | N6 | `survey/cli/__init__.py` + `survey/cli/_views_registry.py` + `harness/lib/orchestration/epic_status_view.py` + `harness/lib/orchestration/dispatch_gate_hint.py` + `harness/cli/cmd_status_epic.py` + `tests/orchestration/*.py` + handoff.md + traceability patch | 注册 5 view + status --epic 子命令 + autopilot dispatch hint + join handoff + 父 traceability `children[3].orchestration_ui_ready=true` |

## 8. Acceptance Contract

| ID | Condition |
|----|----------|
| A1 | N1-N6 6 节点 evaluator verdict 全部 PASS |
| A2 | `survey/cli/` 子包存在且含 6 .py 文件（含 `_views_registry.py` + 5 view） |
| A3 | 5 view 文件每个：含 1 个 `format_*(dataclass) -> str` 函数 + 1 个 `to_dict(dataclass) -> dict` 函数；纯函数（无 IO、无 random、无 datetime.now） |
| A4 | `_views_registry.py` 暴露 `register_view(name)` 装饰器 + `VIEW_REGISTRY` dict；5 view 通过 decorator 注册 |
| A5 | `survey/__init__.py` 既有导出条目数量不减少（diff check） |
| A6 | `harness/lib/orchestration/epic_status_view.py` 含 `render_epic_status(epic_id) -> str` + 列：epic_id, slice, sprint_id_short, status, ready/blocked, deps_missing, target_role, capability_required |
| A7 | `harness/lib/orchestration/dispatch_gate_hint.py` 含 `inject_gate_hint(dispatch_context: str, sprint_id: str) -> str`；fail-open（异常时返回原 context 不抛错） |
| A8 | `harness/cli/cmd_status_epic.py` 注册 `solar-harness status --epic <id>` 子命令；不动既有 `status` 命令默认行为 |
| A9 | 总单测数 ≥ 35（实际 ≥ 38 per design.md §5）；运行 `pytest tests/research/survey/cli/ tests/orchestration/` 全 PASS |
| A10 | view 层全部输入为 S03 dataclass 实例或 fixture JSON；禁止 import requests/urllib/httpx/openai/anthropic |
| A11 | view 层 / orchestration 模块禁止使用 `@mock.patch` / `MagicMock`（grep 检查） |
| A12 | view 层 / orchestration 模块禁止使用 `random.` / `datetime.now` / `time.time` / `uuid.uuid4`（grep 检查） |
| A13 | N6 仅 patch `children[3].orchestration_ui_ready=true`；schema_version + children 顺序 + 长度未变（jq 检查） |
| A14 | S03 D1-D8 已交付的 dataclass 公共 API 未被 S04 修改（grep + diff） |
| A15 | `survey-eval` / `survey-review` / `survey-compile` / `survey-plan` 入口主文件未修改（diff check）；attach 通过 view 注册 |
| A16 | handoff.md 含 `s05_can_start: true` + 不声明 epic 完成 + 不声明 E2E ready |
| A17 | handoff.md 列出 5 view × 1 CLI = 5 surfacing pair + status --epic + dispatch hint = 至少 7 surfacing entry |

## 9. Stop Rules

- ❌ 写 .ts / .js / .sh / .sql 文件 → fail
- ❌ 修改 frozen 5 module 或 6 frozen file → fail
- ❌ 修改 S03 D1-D8 dataclass 公共 API → fail
- ❌ 修改 `survey/__init__.py` 已有导出 → fail
- ❌ 修改 survey-eval / survey-review / survey-compile / survey-plan / status 主入口（不含新增 --epic 子命令）→ fail
- ❌ view 层 import requests/urllib/httpx/openai/anthropic → fail
- ❌ 使用 random. / datetime.now / time.time / uuid.uuid4 → fail
- ❌ 使用 @mock.patch / MagicMock → fail
- ❌ 任何节点测试数 < 6（N6 ≥ 8 due to orchestration coverage） → fail
- ❌ N6 之前任何节点动 parent traceability → fail
- ❌ handoff 声称 epic 完成 / E2E 已验证 / S05 已就绪 → fail
- ❌ autopilot dispatch hint 抛异常阻断主流程 → fail（必须 fail-open）

## 10. Routing Policy

- 全节点 `preferred_model = sonnet`（GLM 1210 已踩 5 次，禁 GLM）
- 禁止 builder 使用 webfetch / web search / 网络写
- prerequisites（强制 blocks_until）：
  - `sprint-20260516-…-s01-requirements:passed`
  - `sprint-20260516-…-s02-architecture:passed`
  - `sprint-20260516-…-s03-core-runtime:passed`
- 上游必读 read_scope：
  - `sprints/…-s01-requirements.outcomes.md`
  - `sprints/…-s01-requirements.non-builder-boundary.md`
  - `sprints/…-s02-architecture.handoff.md`
  - `sprints/…-s02-architecture.{source-quality,argument-density,contradiction-matrix,exploration,gate-report}-arch.md`
  - `sprints/…-s03-core-runtime.handoff.md`
  - `harness/lib/research/survey/schemas.py`（S03 扩展后的 dataclass 列表）
  - `harness/lib/research/survey/gates/_registry.py`（S03 注册接口）

## 11. Observability

- `survey-eval --strict` 输出含 4 gate verdict（PASS/FAIL）+ artifact_paths（4 路径）+ failed_sections（如有）
- `survey-eval --strict --json` 输出含 `gate_report` 完整 dict（key: gates, artifact_paths, summary）
- `survey-compile` 输出在生成 contradiction_matrix 时打印 `[gate:controversy] matrix=<path> (decorative=<bool>)`
- `survey-plan` 输出含 `[gate:exploration] proposed=N eliminated=M selected=K log=<path>`
- `survey-review` 输出含 per-section density profile 表格 + `low_density_sections` 列表
- `solar-harness status --epic <id>` 输出含 7 列 + 阻塞依赖摘要
- autopilot dispatch context 注入的 hint 写入 dispatch.md 末尾 `## Gate Readiness Hint`

## 12. Failure Modes

| FM | 原因 | 处理 |
|----|------|------|
| FM-1 | S03 gate 输出 schema 字段错位 | view 函数 raise `KeyError`；测试中由 fixture 触发并 catch 写 expected fail |
| FM-2 | gate_report.json 不存在 | view 层显示 `[gate_report: missing]`，不抛错 |
| FM-3 | autopilot hint 计算失败 | catch all → 返回原 dispatch context；写 stderr warning（不阻塞） |
| FM-4 | status --epic 收到无效 epic_id | 返回 `epic not found` + 现有 epic 列表，exit code 2 |
| FM-5 | CLI 输出宽度溢出 | 默认 truncate 列宽 + 加 `...`；提示 `--json` |
| FM-6 | controversy_matrix 装饰性检测漏报 | view 显示 `decorative=unknown`，不强制告警（依赖 S03 gate 判定）|

## 13. Exit Criteria (Sprint passed)

- A1-A17 17 条 acceptance 全过
- 6 节点 evaluator verdict 全 PASS
- 父 traceability `children[3].orchestration_ui_ready=true`（schema_version + children 顺序 + 长度未变）
- handoff.md 含 `s05_can_start: true`、不声称 epic 完成
- view 层 + orchestration 模块 ≥ 35 unit test pass

## 14. Out of Scope（再次明示）

- E2E survey-continue 实际跑（S05）
- gate 数值阈值（S05）
- 新增 gate 逻辑（S03 已闭合）
- watch / tail status UI（future）
- markdown CLI format（YAGNI）
- 修改 evaluator 主流程（仅 read gate_report.json，read-only）

Knowledge Context: solar-harness context inject used
