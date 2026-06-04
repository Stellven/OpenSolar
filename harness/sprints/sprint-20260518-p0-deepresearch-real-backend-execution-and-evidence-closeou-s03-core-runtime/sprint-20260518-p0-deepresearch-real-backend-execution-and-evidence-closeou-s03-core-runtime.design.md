# Design — S03 核心实现与数据模型

epic_id: `epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou`
sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s03-core-runtime`
slice: `core-runtime`
author: planner (solar-harness)
date: 2026-05-18
upstream: S02 入参锚点 (S02-SCHEMA-MODEL / S02-SCHEMA-METRICS / S02-FOOTER / S02-STATEMACHINE / S02-FALLBACK / S02-COMPAT)

## 1. 切片定位

S02 已冻结 schema / 状态机 / 降级矩阵 / 兼容矩阵。**S03 写真实运行时代码**，把契约落到 `/Users/sihaoli/Solar/harness/lib/research/` 下的 Python 模块，并补单测。**不动 `tools/` `status-server/` `ui/`**（那是 S04 切片）。

## 2. Codex 现状对账 (S02-COMPAT 锚点核验)

| 模块 | 现状 | S03 动作 |
|------|------|----------|
| `lib/research/report_metrics.py` | 已存在: `extract_token_usage`, `_discover_token_usage`, `append_model_usage_event`, `build_model_usage_event`, `parse_model_cli_output`；字段命名: `token_usage_source` / `token_usage_is_estimated` | **扩展**: 加 alias 字段 `usage_source` / `estimated` 同步写出；保留旧字段不破坏调用方 |
| `lib/research/survey/backends.py` | 已存在: `SurveyWriterBackend` Protocol + `LocalCommandSurveyWriterBackend` / `PanePacketSurveyWriterBackend` / `DeterministicSurveyWriterBackend` / `HumanPacketSurveyWriterBackend`；已调用 `append_model_usage_event` | **扩展**: backend 返回值 dict 加 `usage_source` 字段 (S02-SCHEMA-MODEL) |
| `lib/research/survey/chief_editor.py` | 已支持 `claude-cli / opus / claude / local-command / deterministic` backend | **校验**: 不动接口，只补 fallback_reason 写入路径 |
| `lib/research/evidence/ledger.py` | 已存在 sources 计数 | **不动** |
| `lib/research/survey/explorer/log_writer.py` | 已存在 | **校验**: 写出行符合 S02-SCHEMA-MODEL |
| `lib/research/sources/internal_mirage.py` | 已存在 | **不动** (作为 serper 降级目标) |

**不破坏原则**：所有改动只**扩展字段**或**新增模块**，禁止改 Codex 既有函数签名或返回结构。

## 3. 新增模块（S03 owns）

```
lib/research/
├── fallback_policy.py         (NEW)  — 4 级降级判断 (S02-FALLBACK 落地)
├── state_machine.py           (NEW)  — DeepResearch 单次执行 data plane 状态机 (S02-STATEMACHINE §4 落地)
├── schema_adapter.py          (NEW)  — token_usage_source ↔ usage_source 双向映射 + JSON Schema 校验
└── (扩展 report_metrics.py / survey/backends.py — 见 §4)
```

`tests/research/` 新增：
```
tests/research/
├── unit/
│   ├── test_schema_adapter_compliance.py     (NEW)
│   ├── test_fallback_policy_levels.py        (NEW)
│   └── test_state_machine_transitions.py     (NEW)
└── integration/
    ├── test_real_vs_estimated_switch.py      (NEW)
    └── test_footer_fields_render.py          (NEW)
```

## 4. 字段命名统一策略 (解决 S02 handoff 未闭环 #1)

| S02 schema 字段 | Codex 现有字段 | S03 处理 |
|-----------------|-----------------|----------|
| `usage_source` | `token_usage_source` | schema_adapter 双向映射；report_metrics 同步写两字段 |
| `estimated` | `token_usage_is_estimated` | 同上 |
| `total_tokens` | `total_tokens` | 已一致 |
| `prompt_tokens` | `prompt_tokens` / `input_tokens` | 已一致或加 alias |
| `completion_tokens` | `completion_tokens` / `output_tokens` | 已一致或加 alias |
| `fallback_reason` | (新增) | report_metrics 写 fallback_reason 字段，S02 schema 用作 enum 验证 |

**关键决策 (ADR-001 继承)**：保留 Codex 命名为内部，对外暴露 S02 命名。新代码用 S02 命名。

## 5. fallback_policy.py 接口

```python
# 落地 S02-FALLBACK fallback-policy.json
from enum import Enum
from typing import Protocol

class FallbackLevel(Enum):
    L1_FULL_REAL = 1        # Serper + Claude CLI usage
    L2_HYBRID = 2           # internal_mirage + Claude CLI usage
    L3_FIXTURE = 3          # local-command JSON fixture
    L4_TOKENIZER_DECLARED = 4   # tokenizer 估算 + handoff 显式声明

class FallbackDecision:
    level: FallbackLevel
    usage_source: str  # provider_usage_ledger | hybrid | estimated
    estimated: bool
    fallback_reason: str | None

def decide_fallback(
    serper_ok: bool,
    backend_returns_usage: bool,
    fixture_available: bool,
) -> FallbackDecision: ...
```

每个 Level 的决策必须有 unit test 覆盖 (S03 acceptance "核心 API 有单测覆盖")。

## 6. state_machine.py 接口

落地 S02-STATEMACHINE §4 data plane 状态机：

```python
class DataPlaneState(Enum):
    INIT = "init"
    SEARCHING = "searching"
    SEARCH_SKIP = "search_skip"
    DRAFTING = "drafting"
    METERING = "metering"
    RENDERING = "rendering"
    FINALIZED = "finalized"
    FAILED = "failed"

class ResearchStateMachine:
    def transition(self, to: DataPlaneState, evidence: dict): ...
    def history(self) -> list[StateTransitionEvent]: ...
    def replay_from_jsonl(self, path: Path) -> "ResearchStateMachine": ...
```

要求 (S03 acceptance "状态变更可由元数据或事件重建")：
- 每次 transition 必须 append 一行到 `model_usage.jsonl`
- `replay_from_jsonl()` 能从 jsonl 完全重建机器状态
- 单测覆盖 normal path + search_skip 分支 + failed 分支

## 7. schema_adapter.py 接口

```python
import jsonschema

S02_MODEL_USAGE_SCHEMA_PATH = "..."  # S02-SCHEMA-MODEL 路径
S02_EXECUTION_METRICS_SCHEMA_PATH = "..."  # S02-SCHEMA-METRICS

def normalize_to_s02(codex_event: dict) -> dict:
    """Codex 命名 → S02 命名"""

def denormalize_from_s02(s02_event: dict) -> dict:
    """S02 命名 → Codex 命名 (向后兼容)"""

def validate_model_usage_line(line: dict) -> None:
    """jsonschema.validate against S02 model_usage schema"""

def validate_execution_metrics(metrics: dict) -> None:
    """jsonschema.validate against S02 execution_metrics schema"""
```

要求：jsonschema 校验失败必须 raise，让测试可断言。

## 8. report_metrics.py 扩展点

扩展 `build_execution_metrics()` (现有函数) — 加同步写两套字段：

```python
def build_execution_metrics(root: Path) -> dict:
    metrics = _existing_build_logic(root)  # Codex 原逻辑
    # S03 新增: S02 命名 alias
    metrics["usage_source"] = metrics.get("token_usage_source")
    metrics["estimated"] = metrics.get("token_usage_is_estimated", False)
    metrics["fallback_reason"] = _derive_fallback_reason(metrics)
    schema_adapter.validate_execution_metrics(metrics)  # 强约束
    return metrics
```

footer 渲染同步写两套字段名 (兼容旧文档 + S02 命名)：

```
---
Document word count: {N}
Total token consumption: {N}
Token usage source: {value}
Token usage estimated: {bool}
---
```

要求：现有 final.md / human_final.md / research_eval.json / report_ast.json 必须**新增**这 4 字段（如果已存在则保留），缺一 Evaluator FAIL。

## 9. 单测覆盖矩阵 (S03 DoD)

| 测试 | 目标 | 输入 fixture |
|------|------|--------------|
| test_schema_adapter_compliance | 任何 Codex event → normalize_to_s02 → validate_model_usage_line 不抛 | Codex 已有 model_usage.jsonl 样例 |
| test_fallback_policy_levels | L1..L4 决策表覆盖 | mock serper_ok / backend_returns_usage / fixture_available 组合 |
| test_state_machine_transitions | 合法/非法 transition + replay | 构造 jsonl 序列 |
| test_real_vs_estimated_switch | backend 返回 usage → provider_usage_ledger；不返回 → estimated；混合 → hybrid | local-command + fixture |
| test_footer_fields_render | final.md 含 4 字段精确文本 | mock metrics dict |

**禁止**：测试不允许 mock 整个 `report_metrics.py`；只允许 mock 外部 IO (subprocess / HTTP)。

## 10. 控制面接入 (不破坏 wake/dispatch/status)

- S03 不动 `solar-harness wake` / `coordinator.sh` / `autopilot`。
- 仅扩展 `lib/research/` 与 `tests/research/`。
- `model_usage.jsonl` 写入路径与 Codex 原路径一致 (`sprints/{sid}.model_usage.jsonl` 或 `survey_chief_editor_backend.json` 同目录)。

## 11. 失败恢复 (运行时层面)

| 故障 | 检测 | 恢复 |
|------|------|------|
| schema_adapter 校验失败 | jsonschema.ValidationError | 抛错让 caller 决策；不静默吞 |
| state machine 非法 transition | RuntimeError | 抛错；不允许 jsonl 行残留 |
| fallback_policy 输入不一致 | assert | 测试覆盖每个分支 |

## 12. 给下游 sprint 的入参

### S04 orchestration-ui 入参（继承）
- 新增 module `fallback_policy.py` / `state_machine.py` / `schema_adapter.py` — UI 可读它们的状态/级别枚举显示
- `report_metrics.py` 新增字段 `usage_source` / `estimated` / `fallback_reason` — UI 可消费

### S05 verification-release 入参
- 单测路径：`tests/research/unit/test_*.py`, `tests/research/integration/test_*.py`
- 必须跑：受控 DeepResearch 样例 (max_results=3) + survey-chief-editor claude-cli 小样
- 必须验：4 footer 字段断言 + secret-scan

## 13. 风险

| 风险 | 缓解 |
|------|------|
| Codex 既有调用方依赖旧字段命名 | schema_adapter 双向映射；旧字段保留 |
| schema 校验抛错破坏 Codex 已通过测试 | 先跑 `pytest tests/research/` 全套；新增字段不动旧字段 |
| Claude CLI OAuth 真不返回 usage | fallback_policy L2/L3 兜底；S05 验证集成 |
| state machine 状态泄露 (replay 不一致) | 单测覆盖 replay 等价性 |
| 新增模块与 Codex 命名空间冲突 | 用 `from research.fallback_policy import ...` 避开 |

## 14. 上游依赖 / 下游影响 / 未闭环项

- 上游：S02 6 个入参锚点（schema 2 + footer + state-machine + fallback + compat）。
- 下游：S04 UI 读新增模块枚举；S05 跑受控样例 + 单测全套。
- 未闭环：
  1. Claude CLI OAuth 真 usage 返回情况 — 由 S05 集成测验证。
  2. fallback_reason enum 在 S02 schema 中未约束 — 由本切片 §7 决定具体 enum 值后回写 S02 schema 或本设计。
  3. `parse_model_cli_output` 真实 stream-json 解析覆盖度 — 由本切片单测验证。
