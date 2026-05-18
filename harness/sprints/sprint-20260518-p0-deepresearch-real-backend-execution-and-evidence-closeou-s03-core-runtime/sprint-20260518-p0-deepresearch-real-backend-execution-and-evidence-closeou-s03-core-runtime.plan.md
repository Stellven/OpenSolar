# Plan — S03 核心实现与数据模型

sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s03-core-runtime`
slice: `core-runtime`
date: 2026-05-18
upstream: S02 6 个锚点 (S02-SCHEMA-MODEL / S02-SCHEMA-METRICS / S02-FOOTER / S02-STATEMACHINE / S02-FALLBACK / S02-COMPAT)

## 1. 总体策略

把 design.md 的接口契约**ground 到 Python 模块边界**：3 个新模块 (fallback_policy / state_machine / schema_adapter) + 扩展 2 个 Codex 模块 (report_metrics / backends) + 5 单测 + handoff。**严守 §4 写域隔离**：N2/N3/N4 写新文件互不重叠；N5/N6 仅 append 字段不改签名；测试写 `tests/research/` 不动 `lib/`。

## 2. 并行 / 串行布局

```
Layer 1 (单节点, 无依赖):
  N1 codebase-recon.md  — dump 当前 lib/research/ 字段命名/函数签名/调用拓扑 (read-only)

Layer 2 (并行 3 节点, 依赖 N1):
  N2 fallback_policy.py — 4 级 FallbackLevel + decide_fallback() (design §5)
  N3 state_machine.py   — DataPlaneState + ResearchStateMachine + replay (design §6)
  N4 schema_adapter.py  — normalize/denormalize/validate_*_line (design §7)

Layer 3 (并行 3 节点, 依赖 N2+N3+N4):
  N5 report_metrics_extend.py — 扩展 build_execution_metrics() 同步写 S02 命名 (design §8)
  N6 backends_extend.py        — backends 返回 dict 加 usage_source (design §2)
  N7 unit_tests                — test_fallback_policy / test_state_machine / test_schema_adapter (design §9)

Layer 4 (单节点, 依赖 N5+N6):
  N8 integration_tests — test_real_vs_estimated_switch + test_footer_fields_render (design §9)

Layer 5 (并行 2 节点, gate G_S03_RUNTIME_READY, 依赖 N7+N8):
  N9 planning.html  — design + plan + 关键接口示例 合并渲染
  N10 handoff.md    — 中文证据表 + S04/S05 入参锚点
```

join gate `G_S03_RUNTIME_READY`：N2..N8 全 passed 才允许 N9/N10 收尾。

## 3. 节点验收 Gate (含证据命令)

| Node | 验收 Gate | 证据命令 |
|------|-----------|----------|
| N1 | codebase-recon.md 含 `report_metrics.py` / `backends.py` / `chief_editor.py` / `ledger.py` / `log_writer.py` 五个模块的字段表 | `grep -cE 'report_metrics\|backends\|chief_editor\|ledger\|log_writer' *.codebase-recon.md` >= 5 |
| N2 | fallback_policy.py 存在; 含 `class FallbackLevel(Enum)` + `def decide_fallback`; L1-L4 四级都定义 | `python3 -c "from research.fallback_policy import FallbackLevel; print(len(list(FallbackLevel)))"` == 4 |
| N3 | state_machine.py 存在; 含 `class DataPlaneState(Enum)` 8 状态 + `class ResearchStateMachine` 含 `transition/history/replay_from_jsonl` | `grep -cE 'INIT\|SEARCHING\|SEARCH_SKIP\|DRAFTING\|METERING\|RENDERING\|FINALIZED\|FAILED' /Users/sihaoli/Solar/harness/lib/research/state_machine.py` >= 8 |
| N4 | schema_adapter.py 存在; 含 `normalize_to_s02` / `denormalize_from_s02` / `validate_model_usage_line` / `validate_execution_metrics` | `python3 -c "from research.schema_adapter import normalize_to_s02, denormalize_from_s02, validate_model_usage_line, validate_execution_metrics"` 退出 0 |
| N5 | report_metrics.py 出现 `usage_source` 与 `estimated` 与 `fallback_reason` 三新字段, 旧字段保留 | `grep -cE 'usage_source\|estimated\|fallback_reason\|token_usage_source\|token_usage_is_estimated' /Users/sihaoli/Solar/harness/lib/research/report_metrics.py` >= 5 |
| N6 | backends.py 中至少一个 backend 返回 dict 含 `usage_source` 键; 旧返回结构不破坏 | `grep -c "usage_source" /Users/sihaoli/Solar/harness/lib/research/survey/backends.py` >= 1 |
| N7 | 3 个 unit test 文件存在并通过 pytest | `pytest tests/research/unit/test_fallback_policy_levels.py tests/research/unit/test_state_machine_transitions.py tests/research/unit/test_schema_adapter_compliance.py -q` 退出 0 |
| N8 | 2 个 integration test 通过, 含 final.md 4 字段精确文本断言 | `pytest tests/research/integration/test_real_vs_estimated_switch.py tests/research/integration/test_footer_fields_render.py -q` 退出 0 |
| N9 | planning.html 存在 size > 4KB; 含 §design + §plan + 接口示例三段 | `wc -c < *.planning.html` >= 4096 && `grep -c '系统分层\|并行 / 串行\|FallbackLevel' *.planning.html` >= 3 |
| N10 | handoff.md 含 5 个二级段: 证据表/上游依赖/下游影响/未闭环项/S04-S05 入参锚点 | `grep -c '^## ' *.handoff.md` >= 5 |

## 4. Write Scope 矩阵 (并行安全)

| Node | Write Scope | Read Scope |
|------|-------------|------------|
| N1 | `sprints/*-s03-core-runtime.codebase-recon.md` | `/Users/sihaoli/Solar/harness/lib/research/**` (read-only) |
| N2 | `/Users/sihaoli/Solar/harness/lib/research/fallback_policy.py` | S02-FALLBACK fallback-policy.json, design.md §5 |
| N3 | `/Users/sihaoli/Solar/harness/lib/research/state_machine.py` | S02-STATEMACHINE state-machine.md, design.md §6 |
| N4 | `/Users/sihaoli/Solar/harness/lib/research/schema_adapter.py` | S02-SCHEMA-MODEL, S02-SCHEMA-METRICS, design.md §7 |
| N5 | `/Users/sihaoli/Solar/harness/lib/research/report_metrics.py` (扩展字段, 不改签名) | N1, N4, design.md §8 |
| N6 | `/Users/sihaoli/Solar/harness/lib/research/survey/backends.py` (扩展返回 dict) | N1, N4, design.md §2 |
| N7 | `/Users/sihaoli/Solar/tests/research/unit/test_fallback_policy_levels.py`, `..._state_machine_transitions.py`, `..._schema_adapter_compliance.py` | N2, N3, N4 |
| N8 | `/Users/sihaoli/Solar/tests/research/integration/test_real_vs_estimated_switch.py`, `..._footer_fields_render.py` | N5, N6, fixture |
| N9 | `sprints/*-s03-core-runtime.planning.html` | design.md, plan.md, N1-N4 产物 |
| N10 | `sprints/*-s03-core-runtime.handoff.md` | 全部 |

**冲突检查**：
- N2/N3/N4 写入不同 .py 文件 → 并行安全。
- N5 (report_metrics.py) 与 N6 (backends.py) 写入不同文件 → 并行安全。
- N5/N6 与 N7 (tests/) 写入不同目录 → 并行安全。
- N9 与 N10 写不同 artifact → 并行安全。

## 5. 模型选择

- N1: `sonnet` (代码踏勘 + 写文档)
- N2-N4: `sonnet` (Python 模块, 接口严格)
- N5-N6: `sonnet` (改 Codex 模块, 不破坏现有接口要严谨)
- N7: `glm-5.1` 备选 / `sonnet` 默认 (pytest unit, 量大可降级)
- N8: `sonnet` (integration test, 含 fixture 构造)
- N9: `sonnet` (HTML 渲染)
- N10: `sonnet` (中文 handoff)

## 6. 代码地形踏勘清单 (N1 builder 必读, read-only)

```bash
ls /Users/sihaoli/Solar/harness/lib/research/
ls /Users/sihaoli/Solar/harness/lib/research/survey/
head -120 /Users/sihaoli/Solar/harness/lib/research/report_metrics.py
grep -nE "extract_token_usage|_discover_token_usage|append_model_usage_event|build_model_usage_event|parse_model_cli_output|build_execution_metrics" /Users/sihaoli/Solar/harness/lib/research/report_metrics.py
head -150 /Users/sihaoli/Solar/harness/lib/research/survey/backends.py
grep -nE "SurveyWriterBackend|LocalCommand|PanePacket|Deterministic|HumanPacket" /Users/sihaoli/Solar/harness/lib/research/survey/backends.py
head -120 /Users/sihaoli/Solar/harness/lib/research/survey/chief_editor.py
grep -nE "claude-cli|opus|local-command|deterministic" /Users/sihaoli/Solar/harness/lib/research/survey/chief_editor.py
head -60  /Users/sihaoli/Solar/harness/lib/research/evidence/ledger.py
head -60  /Users/sihaoli/Solar/harness/lib/research/survey/explorer/log_writer.py
git -C /Users/sihaoli/Solar status --short
```

**禁止修改**这些文件 (N1 阶段)；N5/N6 阶段才允许 append 字段。

## 7. HTML 渲染兜底 (N9)

同 S01/S02 plan §6/§7：pandoc → python markdown → cmark → 最简 `<pre>` 兜底；若全不可用，写入 handoff 风险段。

## 8. 失败回退路径

- **N1 现状偏差** (例如 Codex 字段命名与 design.md §2 表格不一致) → 写入 N1 文档 "现状偏差" 段, 并标 CR-01 为已观测; N4 schema_adapter 兜底双向映射。
- **N4 jsonschema 校验抛错** → 先用软断言 + warning log (try/except), 下个 sprint 切硬断言; 写入 handoff CR-02。
- **N7 pytest 失败** → 不允许跳过, 必须修到通过; 失败>2 次则 N7 单节点 ATLAS repair (deepseek-r1 诊断)。
- **N8 fixture 缺失** → 用 `tests/research/fixtures/` 准备 3 类样本: claude-cli stream-json / opus JSON / 空 stdout。
- **N9 渲染全失败** → 最简 `<pre>` 兜底+ handoff 风险段。
- **G_S03_RUNTIME_READY** 阻塞 N10 写 handoff。

## 9. 完成定义 (DoD)

- 10 节点全 passed。
- `solar-harness graph-scheduler validate` 退出 0; `layers` 输出 ≥ 5 layers; `doctor` 无 critical。
- `pytest tests/research/` 退出 0 (含 unit + integration)。
- `git -C /Users/sihaoli/Solar status --short` 仅显示 `lib/research/` (3 新文件 + 2 扩展) + `tests/research/` 变更, 无其他路径。
- handoff.md §3 表所有 grep / pytest 输出真实截断。
- status.json `artifacts` 含 `design / plan / task_graph / planning_html / handoff`。

## 10. 与 S04 / S05 的入参锚点

handoff.md §5 必须明确：
- **S04 入参**：fallback_policy 枚举 / state_machine 枚举 / schema_adapter 字段映射 / report_metrics 新增字段 (供 UI 消费)
- **S05 入参**：单测路径 `tests/research/unit|integration/` + 受控 DeepResearch 样例 (max_results ≤ 3) + footer 4 字段断言命令 + secret-scan 命令
