# Design — S02 架构设计与接口契约

epic_id: `epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou`
sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture`
slice: `architecture`
author: planner (solar-harness)
date: 2026-05-18
upstream: S01 design.md §6 接口契约

## 1. 切片定位

S01 把需求拆为 10 个 outcomes 与接口契约草案。本切片把契约**落到实际代码模块边界**：声明 control plane / data plane、状态机、失败恢复路径、观测点、与既有 Codex 实现的兼容矩阵。**不写运行时代码**，所有 schema/接口/边界以可被 S03/S04 builder 直接消费为目标。

## 2. 系统分层

```
┌──────────────────────────────────────────────────────────────────────┐
│  Control Plane (solar-harness 四 pane + autopilot + graph-scheduler) │
│  - PM/Planner/Builder/Evaluator pane 编排                            │
│  - autopilot dispatch / workflow-guard route                         │
│  - status.json / task_graph.json 状态推进                            │
└────────────────────────┬─────────────────────────────────────────────┘
                         │ dispatch + acceptance gates
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  DeepResearch Runtime (Solar/harness/lib/research)                   │
│                                                                      │
│  ┌─────────────────────┐  ┌──────────────────────┐                   │
│  │ Search Layer        │  │ Survey/Writer Layer  │                   │
│  │ sources/*.py        │  │ survey/chief_editor  │                   │
│  │ + Serper adapter    │  │ + backends.py        │                   │
│  └────────┬────────────┘  └────────────┬─────────┘                   │
│           │                            │                             │
│           ▼                            ▼                             │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Evidence + Usage Ledger (data plane)                           │  │
│  │  - evidence/ledger.py: source citations                        │  │
│  │  - explorer/log_writer.py: backend call records                │  │
│  │  - model_usage.jsonl (append-only)                             │  │
│  │  - research_execution_metrics.json (summary)                   │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Report Metrics (lib/research/report_metrics.py)                │  │
│  │  - 读取 ledger / 计算 token / 写 footer                        │  │
│  │  - usage_source ∈ {provider_usage_ledger, estimated, hybrid}   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Artifacts (sprints/{sid}/, reports/)                                │
│  final.md · human_final.md · research_eval.json · report_ast.json    │
└──────────────────────────────────────────────────────────────────────┘
```

**分层规则**：
- Control plane **只读** data plane 状态，不替它写 ledger。
- Search layer 与 Writer layer 之间 **不共享 token 计数**，各自走 ledger。
- Report metrics 是**唯一**写 footer 字段的模块（避免 4 个产物里散落计算逻辑）。

## 3. Control Plane 状态机

```
              ┌──────────┐
              │ prd_ready│ (PM 完成)
              └─────┬────┘
                    │ planner 接手
                    ▼
              ┌──────────────────┐
              │planning_complete │ (design+plan+task_graph)
              └─────┬────────────┘
                    │ workflow-guard route=builder_main
                    ▼
              ┌──────────┐    fail   ┌──────────┐
              │ building │──────────►│ reviewing│
              └─────┬────┘           └────┬─────┘
                    │ all gates pass      │ evaluator
                    ▼                     ▼
              ┌──────────┐         ┌─────────┐
              │  passed  │◄────────│ verdict │
              └──────────┘         └─────────┘
```

允许的节点状态（来自 task-graph.schema.json）：`pending | queued | assigned | dispatched | in_progress | reviewing | passed | failed | skipped`。

## 4. Data Plane 状态机（DeepResearch 单次执行）

```
        ┌──────────┐
        │  init    │
        └────┬─────┘
             │ serper key 验
             ▼
        ┌──────────┐ key 缺失/quota   ┌────────────┐
        │ searching├─────────────────►│ search_skip│
        └────┬─────┘                  └─────┬──────┘
             │ ok                           │
             ▼                              │
        ┌──────────┐                        │
        │ drafting │                        │
        └────┬─────┘                        │
             │ writer/chief_editor backend  │
             ▼                              │
        ┌──────────┐ cli usage 缺失         │
        │ metering ├─────────►estimated     │
        └────┬─────┘                        │
             │ provider_usage_ledger ok     │
             ▼                              │
        ┌──────────┐                        │
        │rendering │◄───────────────────────┘
        └────┬─────┘  写 footer 4 字段
             ▼
        ┌──────────┐
        │ finalized│  (final.md + metrics.json)
        └──────────┘
```

每个状态转移必须在 `model_usage.jsonl` 写一条记录（包括 skip/estimated 也要落痕）。

## 5. 接口契约（强制 schema）

### 5.1 `model_usage.jsonl` — append-only, JSONL

```json
{
  "ts": "2026-05-18T19:10:00Z",
  "sprint_id": "sprint-...",
  "stage": "writer|chief_editor|serper_search|estimated_fallback",
  "backend": "claude-cli|local-command|serper-http",
  "model": "claude-opus-4-7|gpt-5.4|n/a",
  "prompt_tokens": 1234,
  "completion_tokens": 567,
  "total_tokens": 1801,
  "usage_source": "provider_usage_ledger|estimated|hybrid",
  "estimated": false,
  "fallback_reason": "string|null",
  "request_id": "uuid",
  "extra": {}
}
```

约束：
- `usage_source = "estimated"` 时 `estimated=true` 必为 true，否则视为伪装真实 token。
- `fallback_reason` 在 `usage_source != "provider_usage_ledger"` 时必填。

### 5.2 `research_execution_metrics.json` / `survey_execution_metrics.json`

```json
{
  "sprint_id": "...",
  "generated_at": "ISO8601",
  "serper_calls": 0,
  "sources_count": 0,
  "backend_calls": 0,
  "total_tokens": 0,
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "usage_source": "provider_usage_ledger|estimated|hybrid",
  "estimated": false,
  "document_word_count": 0,
  "ledger_path": "relative/path/to/model_usage.jsonl",
  "ledger_lines": 0,
  "fallback_reasons": []
}
```

### 5.3 报告 footer (final.md / human_final.md / research_eval.json / report_ast.json)

```
---
Document word count: {N}
Total token consumption: {N}
Token usage source: {provider_usage_ledger|estimated|hybrid}
Token usage estimated: {true|false}
---
```

四字段缺一 Evaluator FAIL。`research_eval.json` / `report_ast.json` 用同名 key 而非 markdown footer。

## 6. 真 usage vs estimated 切换策略

| 输入 | 判定 | usage_source | estimated |
|------|------|--------------|-----------|
| backend 返回 `usage` 对象 (含 prompt/completion tokens) | 直接读 | `provider_usage_ledger` | false |
| backend 走 stream-json 含 `usage` 帧 | 累加 stream usage | `provider_usage_ledger` | false |
| backend 仅 stdout 文本 + 已知 tokenizer | 用 tokenizer 估算 | `estimated` | true |
| backend 失败/超时 | 字数 × 4/3 估算 | `estimated` | true |
| 混合：search 有 ledger / writer 无 | 各自落痕，metrics 标 hybrid | `hybrid` | true (整体) |

**禁止**：把 tokenizer 估算结果写成 `provider_usage_ledger`。S03 必须有断言测试覆盖。

## 7. 失败恢复路径

| 故障 | 检测 | 恢复 | 落痕 |
|------|------|------|------|
| Serper key 缺失 | env SERPER_API_KEY 空 | 跳过 search，state=search_skip | model_usage.jsonl 写 search_skip 记录 |
| Serper 429/超时 | HTTP status | 退避 1 次，仍失败则降级到 internal_mirage | fallback_reason="serper_quota" |
| Claude CLI 不返回 usage | parse stdout/stderr 无 `usage` 字段 | tokenizer 估算 + estimated=true | fallback_reason="cli_no_usage" |
| Claude CLI 限额 (account_limit) | stderr 含 "rate" / "limit" | 写 handoff 警告，降到 local-command fixture | fallback_reason="cli_rate_limit" |
| backend 进程 crash | exit code !=0 | 重试 1 次，仍失败则 abort，state=failed | model_usage.jsonl 写 crash 记录 |
| metrics.json 缺字段 | report_metrics validator | 重新计算并补字段，不允许半空 | fallback_reason="metrics_repair" |

## 8. 观测点（Builder 必须实现）

- `model_usage.jsonl` 必须每次 backend 调用 append 一行（含 skip/fail）。
- `research_execution_metrics.json` 每次 final render 重写。
- `~/.solar/harness/sprints/{sid}/handoff.md` 含中文证据表（搜索次数/来源数/token 来源/字数/路径/命令/降级原因）。
- Evaluator 必查 4 字段 + `model_usage.jsonl` 行数 ≥ 1。

## 9. 旧系统兼容（Codex 已有改动）

| Codex 已实现 | 现状 | S03 动作 |
|--------------|------|----------|
| `report_metrics.py` execution_metrics 字段 | 已存在 | **保留接口**，确认 footer 4 字段已写；缺则补 |
| `model_usage.jsonl` ledger | 已存在 | **保留路径**，添加 schema 校验测试 |
| `evidence/ledger.py` citations | 已存在 | 不动，作为 sources_count 数据源 |
| `survey/backends.py` backend 抽象 | 已存在 | 增加 `usage_source` 字段返回 |
| `survey/chief_editor.py` | 已存在 | 增加 `--backend claude-cli --model opus` 路径 |
| `sources/internal_mirage.py` | 已存在 | 作为 serper 降级目标 |

**兼容原则**：S03 只**扩展字段**与**补缺断言**，**不破坏**现有调用方。任何 breaking change 须先回写到本切片 design.md 的兼容矩阵并由 evaluator 审。

## 10. 降级策略

```
首选: Serper + Claude CLI usage = provider_usage_ledger
  ↓ Serper 不可用
次选: internal_mirage + Claude CLI usage = hybrid (search estimated)
  ↓ Claude CLI 不返回 usage
三选: local-command JSON fixture + 真 ledger 验证路径 + 报告标 estimated
  ↓ 全部不可用
保底: 跑 tokenizer 估算 + handoff 显式声明无真实 usage 数据
```

每一级必须独立可测；S03 单测必须覆盖前 3 级，S05 集成测覆盖至少 1 个真实级别。

## 11. 冲突 / 依赖 / 风险

| 类型 | 描述 | 缓解 |
|------|------|------|
| 冲突 | S03 改 `survey/backends.py` 与 S04 改 `tools/dispatch` 可能撞接口签名 | S03 write_scope `lib/`, S04 write_scope `tools/`, 接口冻结点 = S02 §5 schema |
| 依赖 | S03 必须先于 S04 通过 schema 验证 | epic.task_graph 已强制 S04.depends_on=[S02] (不是 S03) → S03/S04 可并行，但 join gate 在 S05 |
| 依赖 | S05 必须先消费 S03 + S04 双产物 | epic 已固化 |
| 风险 | Codex 既有改动可能与新 schema 不兼容 | S03 N1 必须先 dump 现状 schema → diff → 决策 |
| 风险 | Claude CLI usage 在 OAuth 场景下可能不返回 | §10 三选路径 + fixture 兜底 |
| 风险 | provider_usage_ledger 名称在代码中实际未必匹配 | S03 N2 必须 grep 实际命名再决定是否更名 |

## 12. 给下游 sprint 的入参

### S03 core-runtime（继承）
- 接口 schema = §5
- 状态机 = §4
- 兼容矩阵 = §9
- 降级路径 = §10
- 必须新增/扩展：`research_execution_metrics.json` schema validator、`model_usage.jsonl` JSONL 校验、4 字段 footer writer、estimated/real 切换分支测试。

### S04 orchestration-ui
- 不动 `lib/research/`，只在 `tools/` / `status-server/` / `ui/` 显示 metrics
- 必须读 §5 schema，不能解析 markdown 反推。

### S05 verification-release
- 必须跑 §10 至少前 3 级降级路径的测试
- 必须验 Evaluator 4 字段断言（S01 O-08）
- 必须验 secret-scan（S01 O-09）
- 必须中文证据表 handoff（S01 O-10）

## 13. 上游依赖 / 下游影响 / 未闭环项

- 上游：S01 design.md §6 接口契约（已闭环）。
- 下游：S03/S04 必须在本切片 schema 冻结后才能 builder dispatch。
- 未闭环：
  1. 实际代码 `survey/backends.py` 是否已有 `usage_source` 返回字段 — 由 S03 N1 dump 现状验证。
  2. `provider_usage_ledger` 命名在代码中是否一致 — S03 N2 grep 验证。
  3. Claude CLI OAuth 模式下 usage 是否返回 — S05 集成测验证。
