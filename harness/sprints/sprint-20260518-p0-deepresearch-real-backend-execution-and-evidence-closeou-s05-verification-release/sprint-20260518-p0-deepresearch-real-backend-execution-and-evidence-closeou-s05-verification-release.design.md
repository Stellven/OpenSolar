# Design — S05 验证、回归与发布证据

epic_id: `epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou`
sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s05-verification-release`
slice: `verification-release`
author: planner (solar-harness)
date: 2026-05-19
upstream: S02 design §6/§10/§12, S03 handoff (10 tests passed), S04 handoff (30 tests passed; 1 阻塞项: livework_panel.js)
Knowledge Context: solar-harness context inject used

## 1. 切片定位

S05 是 epic 的收口切片。**不写运行时代码 / 不动 `lib/` / 不动 `status-server`/`tools/`/`ui/` 主路径**，只：
1. 重跑 S03+S04 测试做底座回归
2. 修 S04 N6 阻塞项 (livework_panel.js badge-fallback 编辑被回退)
3. 加负控测试与 local-command fixture 真 usage 读取路径
4. 跑 1 个受控 DeepResearch 真实样例 (max_results<=3) + 1 个可选 survey-chief-editor claude-cli 小样
5. 收 secret-scan / 报告 / README
6. 出中文证据表 handoff 与父 epic 收口

write_scope = epic.task_graph 已固化：`tests/`, `reports/`, `README.md`。其余只读。

## 2. 验证维度矩阵

| 维度 | 要求 | 上游锚点 |
|------|------|----------|
| 回归 | `tests/research/integration/` 10 tests + `tests/ui/` 30 tests 全 pass | S03/S04 handoff |
| 负控 | schema 非法必须 raise；backend 无 usage 必须标 estimated；伪装真实 token 必须阻断 | S02 §5/§6 |
| 真实样例 | 跑 solar-deepresearch CLI max_results<=3, 产出 final.md + research_execution_metrics.json + model_usage.jsonl | PRD 必须完成 #4 |
| 真实 backend | `survey-chief-editor --backend claude-cli --model opus` 小样 (可用时);否则 local-command fixture | PRD 必须完成 #5 |
| 4 字段断言 | final.md / human_final.md / research_eval.json / report_ast.json 含 Document word count / Total token consumption / Token usage source / Token usage estimated | PRD 必须完成 #6, S02 §5.3 |
| 安全 | 不提交 API key / OAuth token / usage ledger 私密内容 | PRD 验收 #4 |
| 中文证据表 | handoff 含 7 列：搜索次数 / 来源数 / token 来源 / 字数 / 路径 / 命令 / 降级原因 | PRD 验收 #5 |
| 阻塞项闭环 | S04 N6 livework_panel.js badge-fallback 重新应用 | S04 handoff 未闭环 #1 |
| 父 epic 收口 | activation-proof + epic_status_matrix 输出 | PRD, S04 N3 |

## 3. 真实 vs Fixture 决策树（继承 S02 §10）

```
Level 1: Serper 真 + Claude CLI 真 usage  → usage_source=provider_usage_ledger, estimated=false
    ↓ SERPER_API_KEY 缺/限额
Level 2: internal_mirage + Claude CLI 真 usage → usage_source=hybrid, estimated=true (search 估算)
    ↓ Claude CLI 不返回 usage / OAuth 限
Level 3: local-command JSON fixture (受控真 usage 读路径) → usage_source=provider_usage_ledger (读取路径), 但报告 footer 必须标 "真实模型 usage 未返回" 的降级原因
    ↓ 全部不可用
Level 4: tokenizer 估算 + handoff 显式声明 "无真实 usage 数据" → usage_source=estimated, estimated=true, fallback_reason="cli_no_usage" 或 "cli_rate_limit"
```

**强制**：
- Level 3 在本 sprint **必须有测试覆盖**（PRD：至少一个测试或样例证明 provider_usage_ledger 能被 report_metrics 读取）。
- Level 1 / Level 2 在本 sprint **必须尝试**真跑一次，失败必须把原因记入 handoff，**不允许跳过**到 Level 4 假装完成。

## 4. DAG 概览（详见 plan.md）

```
Layer 1 (并行 4):
  N1 regression-tests   — pytest 重跑 S03(10) + S04(30) 测试
  N2 negative-controls  — schema 非法 / 假 usage / 缺字段 三类负控
  N3 livework-repair    — 重应用 S04 N6 livework_panel.js badge-fallback
  N4 secret-scan        — 扫描 sprints/ + reports/ 确认无 token/key 泄漏

Layer 2 (依赖 N3):
  N5 ui-proxy-curl      — 启动 status-server, curl /research/<sid>, 验证 5 新字段

Layer 3 (依赖 N1+N2+N3+N4+N5):
  N6 controlled-sample  — solar-deepresearch CLI max_results=3 受控样例
  N7 chief-editor-real  — survey-chief-editor --backend claude-cli --model opus 小样 (可用时)
  N8 fixture-realpath   — local-command JSON fixture 真 usage 读取路径测试 (PRD 强制)

Layer 4 (依赖 N6+N7+N8):
  N9 report-readme      — reports/release-evidence-{sid}.md + README.md DeepResearch 章节链接
  N10 activation-proof  — epic_status_matrix 输出 + autopilot 激活验证

Layer 5 (Gate G_S05_RELEASE, 依赖 N1..N10 全 passed):
  N11 handoff           — 中文 7 列证据表 + 上游/下游/未闭环/父 epic 收口
```

## 5. 接口冻结点（不可破坏）

| 来源 | 接口/产物 | 冻结说明 |
|------|-----------|---------|
| S02 | `model_usage.schema.json` / `execution_metrics.schema.json` / `footer_fields.md` | schema 字段名 = `usage_source` / `estimated` / `fallback_reason` |
| S02 | `fallback-policy.json` 4 级 | N6/N7/N8 命中级别须能映射到 L1..L4 |
| S03 | `harness.lib.research.fallback_policy.FallbackLevel` (L1..L4) + `decide_fallback()` | N2/N8 测试导入此模块，不得改名 |
| S03 | `harness.lib.research.schema_adapter.normalize_to_s02` / `validate_model_usage_line` / `validate_execution_metrics` | N2 负控用 jsonschema.ValidationError 断言 |
| S03 | `harness.lib.research.report_metrics.build_execution_metrics` + footer 4 字段精确文本 | N6/N7/N8 必须读 footer 文本 |
| S04 | `research_routes.build_research_payload` + `_derive_fallback_level` | N5 curl 校验 5 新字段 |
| S04 | `solar-runtime-soak --check_research_footer_fields` | N6/N7 用此命令校 4 字段 |
| S04 | `solar-autopilot-monitor --epic-status-matrix` | N10 用此输出做父 epic 收口证据 |

## 6. 失败恢复

| 节点 | 故障 | 恢复 | 落痕 |
|------|------|------|------|
| N3 | 重应用 livework_panel.js 失败 | 重新实现 badge-fallback-L1/L2/L3/L4 + formatStateTransition + formatResearchMetrics 三函数（**不要** git checkout 旧版本，因为旧版本就是被回退的版本） | handoff fallback_reason="ui_reimpl" |
| N5 | status-server 启动失败 | 用 fixture 单元测试 `_derive_fallback_level` 4 级映射 + curl 失败原因写入 handoff | handoff fallback_reason="status_server_unreachable" |
| N6 | Serper 不可用 (key/quota) | 切 internal_mirage，记 fallback_reason="serper_quota" | model_usage.jsonl 含 search_skip 行 |
| N6 | DeepResearch CLI 失败 | 最多重试 1 次，仍失败则把错误 stderr 写入 handoff，不假装通过 | handoff "未闭环" 段 |
| N7 | Claude CLI 不返回 usage / OAuth 限 | 切 local-command JSON fixture (复用 N8 fixture) 并在 footer 标注 fallback_reason="cli_no_usage" 或 "cli_rate_limit" | handoff 显式标注 "真实模型 usage 未返回" |
| N8 | fixture 构造失败 | **禁止跳过**（PRD 强制 #5）；重写 fixture 直到通过 | 阻塞 G_S05_RELEASE |
| N4 | 发现 secret 泄漏 | 立即阻塞，写 handoff 风险段，**不要**自己删（用户决定怎么处理） | 阻塞 G_S05_RELEASE |

## 7. 上游依赖 / 下游影响 / 未闭环项

### 上游依赖（必须 passed）
- S03_core_runtime: passed (2026-05-19T12:35:55Z)
- S04_orchestration_ui: passed (2026-05-19T12:35:55Z, 含 1 阻塞项)

### 下游影响
- 父 epic `epic-20260518-...closeou` 在 S05 passed 前不能关闭（已在 epic.task_graph activation_policy 固化）
- 父 epic 关闭后才能开新 DeepResearch 相关 sprint

### 未闭环项（继承自上游，本切片必须收口）
1. S04 N6 阻塞: `livework_panel.js` 89 行 vs 期望 138 行 — **N3 必须重新应用**
2. S04 #2 server.ts proxy curl 未验证 — **N5 必须 curl 验证**
3. S03 #3 L4 (TOKENIZER_DECLARED) 集成测试未覆盖 — **N2/N8 任一节点必须补**
4. PRD #5 Claude CLI usage 在 OAuth 模式下是否返回未知 — **N7 实测**

## 8. 验收（DoD）

- N1..N11 全 passed
- `solar-harness graph-scheduler validate --graph <task_graph>` exit 0
- handoff.md 含中文 7 列证据表，每行有真实命令输出（grep -c / pytest 行数）
- `final.md` / `human_final.md` / `research_eval.json` / `report_ast.json` 含 4 footer 字段（N6 / N7 / N8 任一路径产出至少 1 套）
- secret-scan 报告无泄漏，或泄漏已写入 handoff 风险段
- status.json artifacts 含 `design`, `plan`, `task_graph`, `planning_html`, `prd_html`, `handoff`
- **不修改** `/Users/sihaoli/Solar/harness/lib/research/` 主路径运行时代码 (允许仅在 `tests/` 加测试 + `static/livework_panel.js` 重应用 N6 + `reports/` + `README.md`)

## 9. 给下游（无）

S05 是 epic 末节点。下游 = 父 epic 关闭 + 知识库 raw 归档。
