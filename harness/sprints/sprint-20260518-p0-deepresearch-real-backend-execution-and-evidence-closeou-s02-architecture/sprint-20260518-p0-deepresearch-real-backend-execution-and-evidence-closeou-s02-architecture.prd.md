# PRD: 架构设计与接口契约

epic_id: `epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou`
sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture`
slice: `architecture`

## 用户原始需求

P0: DeepResearch real-backend execution and evidence closeout

背景：Codex 已直接在 Solar repo 中实现了 DeepResearch report execution metrics 与 model_usage.jsonl ledger 支持，但这不是完整的 solar-harness 四 pane 执行闭环。请 solar-harness 自己按 PM -> Planner -> DAG Builder -> Evaluator 路径验证并收口，不允许只依赖 Codex 手工改动结论。

目标：让 DeepResearch 能用高质量搜索与真实 writer/chief_editor backend 生成可审阅报告，并在报告与 JSON artifact 中明确写出本次执行总 token 消耗数和产生的文档字数。

必须完成：
1. PM 输出 PRD，并生成 prd.html。
2. Planner 输出 design.md、plan.md、task_graph.json，并生成 planning.html。
3. Builder 基于当前 /Users/sihaoli/Solar 代码验证以下链路：
   - Serper 搜索能被 DeepResearch 使用，并记录 usage meter。
   - survey writer/chief_editor backend 会写 model_usage.jsonl。
   - 如果 backend 返回真实 usage JSON/stream-json/stdout/stderr，final metrics 使用 provider_usage_ledger。
   - 如果 backend 不返回真实 usage，只能标记 estimated，不能伪装为真实 token。
   - final.md / human_final.md / research_eval.json / report_ast.json 包含 execution_metrics。
4. 必须运行一个受控 DeepResearch 样例，不要消耗大额度；max_results <= 3。
5. 如果可用，跑 survey-chief-editor --backend claude-cli --model opus 的小样；若 Claude CLI 或账户限制导致无法拿真实 usage，必须把错误、fallback 与估算标记写入 handoff。
6. Evaluator 必须检查报告末尾是否包含 Document word count、Total token consumption、Token usage source、Token usage estimated。

验收标准：
- status.json artifacts 里可追踪 prd_html/planning_html。
- 产物目录包含 final.md、research_execution_metrics.json 或 survey_execution_metrics.json、model_usage.jsonl（真实 backend 路径可用时）。
- 至少一个测试或样例证明 provider_usage_ledger 能被 report_metrics 读取；如果真实 Claude CLI 不提供 usage，则用受控 local-command JSON fixture 验证真实 usage 读取路径，并明确标注真实模型 usage 未返回。
- 不要把 API key、OAuth token、usage ledger 私密内容提交到 GitHub。
- 最终 handoff.md 用中文给出证据表：搜索次数、来源数、token 来源、文档字数、报告路径、测试命令、失败/降级原因。

## 背景 / Context

S01 已把用户原始大需求拆为 10 个可验收 outcomes (O-01..O-10) 与接口契约草案 (research_execution_metrics.json / model_usage.jsonl / final.md footer)。Codex 在 `/Users/sihaoli/Solar/harness/lib/research/` 下已实装 `report_metrics.py`、`survey/chief_editor.py`、`survey/backends.py`、`evidence/ledger.py`、`explorer/log_writer.py` 五个模块，但缺统一的 schema 冻结点与降级矩阵，导致后续 S03 builder 无所适从。S02 本切片就是把契约 ground 到这些实际模块边界。

## 用户问题 / Problem

DeepResearch 当前不能可靠区分"真 token usage"与"估算 usage"：

1. 真假 token 切换策略散落各处，缺单一 source of truth。
2. final.md / human_final.md / research_eval.json / report_ast.json 四个产物的 footer 字段未冻结。
3. Claude CLI OAuth 模式下 usage 是否返回未知，缺降级路径。
4. Serper 缺 key / quota 满时无统一兜底，可能把估算伪装成真实。

不解决就会让 Evaluator 无法用一致断言验收，等于本 Epic P0 目标失效。

## 用户故事 / User Stories

- **作为研究员**，我希望读完 final.md 末尾就能确认本次 token 是否真实，不被估算数字误导。
- **作为 Evaluator (审判官)**，我希望 4 字段断言一律可执行 (`grep "Token usage source:"` 等)，不用逐个产物自己猜算。
- **作为 S03 Builder**，我希望接到一份冻结 schema + 状态机 + 降级矩阵的 design.md，按图施工即可，不再回头问 Planner。
- **作为 S04 UI Builder**，我希望从 `research_execution_metrics.json` 单一 schema 读 metrics，不需要解析 markdown 反推。
- **作为 S05 Verification**，我希望降级 4 级路径每级都有可复现测试，secret-scan 在 CI 中固化。

## 约束 / Constraints

- **不破坏**现有 Codex 改动：保留 `report_metrics.py` / `model_usage.jsonl` / `evidence/ledger.py` 现有接口，只扩展字段。
- **不消耗大额度**：S03/S05 受控样例 `max_results ≤ 3`，单次 backend 调用 ≤ 1 次。
- **不伪装真实 token**：tokenizer 估算结果必须 `usage_source="estimated"` 且 `estimated=true`，违反即 Evaluator FAIL。
- **不提交 secret**：Serper key / OAuth token / usage ledger 私密内容不入 Git，CI 必须有 secret-scan。
- **本切片不写代码**：只产架构文档 (design/plan/task_graph)，运行时代码由 S03/S04 实现。
- **schema 一旦冻结**：S03/S04 不得 breaking change，必须回写到本切片 design.md §9 兼容矩阵。

## 风险 / Risks

| RID | 风险 | 概率 | 影响 | 缓解 |
|-----|------|------|------|------|
| AR-01 | Codex 现有 `report_metrics.py` 与新 schema 字段命名冲突 | 中 | 中 | S03 N1 先 dump 现状 → diff → 决策；本切片 §9 列出已知字段 |
| AR-02 | Claude CLI OAuth 模式下 `usage` 真不返回 | 高 | 中 | §10 降级三选 (tokenizer/fixture/handoff 显式声明) |
| AR-03 | Serper key 在 CI 中泄漏 | 低 | 高 | secret-scan gate (S01 O-09) |
| AR-04 | S03 与 S04 同时改 backend 接口签名冲突 | 中 | 中 | write_scope 隔离：S03→`lib/`, S04→`tools/status-server/ui/` |
| AR-05 | provider_usage_ledger 命名在代码中实际不一致 | 中 | 低 | S03 N2 grep 验证 |
| AR-06 | Evaluator 跳过 4 字段断言 | 中 | 高 | contract.stop_rules 固化 4 字段必查 |

## 开放问题 / Open Questions

1. `survey/backends.py` 是否已有 `usage_source` 返回字段？— 由 S03 N1 dump 验证。
2. Claude CLI 在 OAuth (tmux pane Sonnet) 模式下 stream-json 是否携带 usage 帧？— 由 S05 集成测验证。
3. `internal_mirage` 是否能完全替代 Serper 作为 search 降级？— 由 S05 控制样例验证。
4. `model_usage.jsonl` 是按 sprint 一份还是全局一份？— 暂按 sprint 一份 (放 `sprints/{sid}.model_usage.jsonl`)，S03 可推翻并回写本 PRD。
5. footer 四字段是否需在 `report_ast.json` 中用结构化字段而非 markdown？— 本切片 §5.3 已决策用同名 key (S03 实现确认)。

## 架构交接 / Planner Handoff

Planner (本切片) 接到 PRD 后，必须产出以下三件套并通过 graph-scheduler validate：

- `*.design.md` — §2 分层 / §3-§4 状态机 / §5 schema / §6 真假切换 / §7 失败恢复 / §9 兼容矩阵 / §10 降级
- `*.plan.md` — DAG 节点拆解 (含 §5 schema 冻结为独立 architecture-schemas.md) + write_scope 隔离
- `*.task_graph.json` — 节点 schema 合法、layers 至少 2 层、必有 join gate

下游 Builder (S03/S04) 入参锁定为 design.md §5/§7/§9/§10。breaking change 须回写本切片 design.md。

Evaluator (S05) 必须验证以下断言可执行：
- `grep "Token usage source:" final.md && grep "Token usage estimated:" final.md` 出错则 FAIL
- `jq '.usage_source' research_execution_metrics.json` 返回 enum 之一
- `wc -l model_usage.jsonl` ≥ 1

## 本切片目标

基于需求矩阵产出系统分层、接口、数据模型、兼容策略和迁移方案。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou.epic.md`、`epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 设计覆盖 control/data plane、状态、失败恢复和观测
- 写清楚接口边界和旧系统兼容方式
- 列出冲突、依赖和降级策略

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.design.md`
- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.plan.md`
- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.task_graph.json`
- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.handoff.md`
- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.eval.md` 或 `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.eval.json`
