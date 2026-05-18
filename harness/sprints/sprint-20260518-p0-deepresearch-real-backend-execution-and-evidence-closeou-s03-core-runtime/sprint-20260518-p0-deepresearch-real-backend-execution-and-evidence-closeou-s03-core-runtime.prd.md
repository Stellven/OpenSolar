# PRD: 核心实现与数据模型

epic_id: `epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou`
sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s03-core-runtime`
slice: `core-runtime`

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

S02 已冻结 6 个入参锚点：`S02-SCHEMA-MODEL` (model_usage.schema.json) / `S02-SCHEMA-METRICS` (execution_metrics.schema.json) / `S02-FOOTER` (footer_fields.md) / `S02-STATEMACHINE` (state-machine.md) / `S02-FALLBACK` (fallback-policy.json) / `S02-COMPAT` (compatibility-matrix.md)。Codex 已在 `/Users/sihaoli/Solar/harness/lib/research/` 下实装 `report_metrics.py` (`extract_token_usage` / `append_model_usage_event` / `parse_model_cli_output`)、`survey/backends.py` (`SurveyWriterBackend` Protocol + 4 实现)、`survey/chief_editor.py` (5 backend 路由)、`evidence/ledger.py` (sources 计数)、`explorer/log_writer.py`。S03 是 Epic 内**第一个写真实运行时代码的切片**，把 S02 契约 ground 到 Python 模块边界，且**不动 tools/ status-server/ ui/**（S04 范围）。S02 handoff 未闭环 #1 — footer 字段命名分歧 (schema `usage_source/estimated` ↔ Codex `token_usage_source/token_usage_is_estimated`) —— 必须由本切片用 schema_adapter 双向映射解决。

## 用户问题 / Problem

S02 schema 已冻结，但运行时还没有：

1. **fallback_policy 缺单一 source of truth**：4 级降级 (L1_FULL_REAL / L2_HYBRID / L3_FIXTURE / L4_TOKENIZER_DECLARED) 散落 chief_editor / backends / report_metrics 中，决策不可复现。
2. **state machine 未代码化**：S02-STATEMACHINE §4 data plane 7 状态 + 1 failed，仍只是 mermaid 图，没有可 replay 的运行时对象。
3. **schema 校验未接入**：build_model_usage_event / build_execution_metrics 写出的 JSON 没有走 jsonschema.validate，Evaluator 验收时只能 grep 字符串。
4. **字段命名分歧未消除**：Codex 旧字段 `token_usage_source` 与 S02 新命名 `usage_source` 共存，对外不一致。
5. **fallback_reason 未持久化**：S02 fallback-policy.json 定义了 4 个 enum 值，但 `report_metrics.py` 输出里没写这字段，下游 UI / Evaluator 拿不到降级原因。

不解决就 S04 集成测试无依据，S05 受控样例无法断言。

## 用户故事 / User Stories

- **作为 S03 Builder**，我希望接到一份 design.md 标明每个新模块的接口契约 + 5 个必跑单测，直接 `pytest tests/research/` 验证，不用回头问 Planner。
- **作为下游 S04 UI Builder**，我希望从 `fallback_policy.FallbackLevel` 枚举和 `state_machine.DataPlaneState` 枚举直接 import，UI 卡片状态显示不需要解析字符串。
- **作为下游 S05 Verification**，我希望本切片单测路径 `tests/research/unit/test_*.py` 和 `tests/research/integration/test_*.py` 在受控样例中 100% 跑通，不留隐性失败。
- **作为 Codex 既有调用方**，我希望本切片**只扩展字段不改签名**，旧的 `extract_token_usage()` / `append_model_usage_event()` 调用方一行不动就能继续工作。
- **作为研究员 (终端用户)**，我希望 final.md 末尾的 4 字段 (Document word count / Total token consumption / Token usage source / Token usage estimated) 在任何 fallback 等级下都准确无歧义。

## 约束 / Constraints

- **不破坏 Codex 接口**：`report_metrics.py` / `survey/backends.py` / `survey/chief_editor.py` / `evidence/ledger.py` / `explorer/log_writer.py` 的现有函数签名和返回结构**禁止改动**；新功能只通过 (a) 扩展字段 (b) 新增模块 (c) 装饰器风格扩展点 实现。
- **不动控制面**：`solar-harness wake` / `coordinator.sh` / `autopilot` / `dispatch` / `status` 任何一行都不准改；本切片仅扩展 `lib/research/` 与 `tests/research/`。
- **不消耗大额度**：单测必须用 fixture，不允许真发 Serper / Claude CLI 调用；外部 IO 全部 mock。
- **不伪装真实 token**：tokenizer 估算结果在 schema_adapter 输出中必须 `usage_source="estimated"` 且 `estimated=true`，违反即 Evaluator FAIL。
- **schema 严格校验**：`schema_adapter.validate_model_usage_line()` 与 `validate_execution_metrics()` 失败必须 raise `jsonschema.ValidationError`，禁止静默吞错。
- **写域隔离**：本切片只允许写 `/Users/sihaoli/Solar/harness/lib/research/{fallback_policy,state_machine,schema_adapter}.py` + 扩展 `report_metrics.py` + `tests/research/**`；其他路径写入即违约。
- **不提交 secret**：测试 fixture 不得包含真实 Serper key / OAuth token。

## 风险 / Risks

| RID | 风险 | 概率 | 影响 | 缓解 |
|-----|------|------|------|------|
| CR-01 | Codex 既有调用方依赖 `token_usage_source` 旧命名，本切片新增 `usage_source` 字段后旧测试漏跑导致 silent break | 中 | 高 | schema_adapter 双向映射；先跑 `pytest tests/research/` 全套基线 → 再加新字段 → 再跑回归 |
| CR-02 | jsonschema 校验抛错破坏 Codex 已通过的 `build_execution_metrics()` 调用链 | 中 | 高 | 校验只在新扩展函数中触发；旧入口保留 try/except 软断言 + warning log，下个 sprint 再切硬断言 |
| CR-03 | state machine `replay_from_jsonl()` 与活态 transition 状态不一致 (event 顺序错配) | 中 | 中 | 单测 `test_state_machine_transitions` 强制 replay 等价性断言；jsonl 写入用 append-only |
| CR-04 | fallback_policy L4 (tokenizer-declared) 决策表与 S02 fallback-policy.json 漂移 | 低 | 中 | unit test 直接读 S02 fallback-policy.json 反向校验 enum 一致 |
| CR-05 | mock 整个 `report_metrics.py` 导致测试通过但真实路径炸 | 中 | 高 | 测试纪律：只允许 mock subprocess / HTTP 外部 IO，禁止 mock 内部函数 |
| CR-06 | `parse_model_cli_output` stream-json 真实帧覆盖度不足 | 中 | 中 | 单测准备 3 类样本：claude-cli stream-json / opus JSON / 空 stdout |
| CR-07 | S04 UI 在 S03 模块尚未稳定时就 import，造成循环阻塞 | 低 | 中 | handoff.md 明示 S04 入参锚点 + 模块路径，并标 "stable from S03 N9 finalize" |

## 开放问题 / Open Questions

1. `fallback_reason` enum 是否回写到 S02 `execution_metrics.schema.json`？— 暂决策：本切片 §7 schema_adapter 内置 enum 列表 (`api_quota_exhausted` / `oauth_no_usage` / `fixture_used` / `tokenizer_estimated`)，S05 验证后回写 S02。
2. `model_usage.jsonl` 是按 sprint 一份还是全局一份？— S02 PRD 已暂定按 sprint 一份；本切片沿用，但 schema_adapter 提供 `validate_jsonl_file()` 接口为全局合并预留可能。
3. Claude CLI OAuth 模式下 `usage` 真实返回率？— S03 不验，留 S05 集成测试 (`tests/research/integration/test_real_vs_estimated_switch.py`) 真跑一次 (受控样例 max_results ≤ 3)。
4. `DeterministicSurveyWriterBackend` 是否也需走 schema_adapter？— 暂决策：是，所有 backend 返回 dict 都必须通过 `schema_adapter.normalize_to_s02()` 出 chief_editor 边界。
5. tokenizer 选型 (tiktoken vs 自实现)？— 不在本切片范围；继续用 Codex 现有 `estimated_from_model_io` 路径，S03 只确保它落 `usage_source="estimated"`。

## 架构交接 / Planner Handoff

Planner (本切片) 接到 PRD 后，必须产出以下三件套并通过 `solar-harness graph-scheduler validate` + `layers` + `doctor` 三连验：

- `*.design.md` — §2 Codex 现状对账 / §3 新增模块 / §4 字段命名统一 / §5-§7 三新模块接口 / §8 report_metrics.py 扩展点 / §9 单测覆盖矩阵 / §10 控制面接入 / §11 失败恢复 / §12 下游入参
- `*.plan.md` — DAG 节点拆解（建议 8-10 节点，分 4-5 layers，包含 codebase recon → 新模块 → 扩展点 → 测试 → handoff），含 write_scope 隔离矩阵 + 节点验收 gate (含 grep / pytest 证据命令) + 模型选择 + 失败回退路径
- `*.task_graph.json` — 节点 schema 合法、layers ≥ 3 层、必有 join gate (例如 `G_S03_RUNTIME_READY`)，每节点声明 `write_scope` 防并行冲突
- `*.planning.html` — design + plan + 关键代码示例合并渲染，size ≥ 4KB

下游 Builder 入参锁定为 design.md §3 (新增模块) / §4 (字段映射) / §5-§7 (接口) / §8 (扩展点) / §9 (测试矩阵)。breaking change 须回写本切片 design.md。

Evaluator (S05) 必须验证以下断言可执行：
- `pytest tests/research/unit/test_fallback_policy_levels.py -v` 退出 0 且覆盖 L1-L4 四级
- `pytest tests/research/unit/test_state_machine_transitions.py -v` 含 replay 等价性断言
- `pytest tests/research/unit/test_schema_adapter_compliance.py -v` 含 normalize_to_s02 round-trip 测试
- `pytest tests/research/integration/test_footer_fields_render.py -v` 含 final.md 4 字段精确文本断言
- `grep -nE "usage_source|estimated|fallback_reason" /Users/sihaoli/Solar/harness/lib/research/report_metrics.py` 命中 ≥ 3 次
- `git -C /Users/sihaoli/Solar status --short` 仅显示 `lib/research/` 与 `tests/research/` 变更

## 本切片目标

实现核心库、状态机、schema、持久化和向后兼容适配层。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou.epic.md`、`epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 核心 API 有单测覆盖
- 旧路径兼容，不破坏现有 wake/dispatch/status
- 状态变更可由元数据或事件重建

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s03-core-runtime.design.md`
- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s03-core-runtime.plan.md`
- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s03-core-runtime.task_graph.json`
- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s03-core-runtime.handoff.md`
- `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s03-core-runtime.eval.md` 或 `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s03-core-runtime.eval.json`
