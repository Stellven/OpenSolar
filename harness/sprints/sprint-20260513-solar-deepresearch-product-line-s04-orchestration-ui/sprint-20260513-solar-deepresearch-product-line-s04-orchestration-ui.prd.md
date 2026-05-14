# PRD — 调度、自动化与可视化 (S04 orchestration-ui)

> epic_id: `epic-20260513-solar-deepresearch-product-line`
> sprint_id: `sprint-20260513-solar-deepresearch-product-line-s04-orchestration-ui`
> slice: `orchestration-ui`
> priority: `P0`
> Author: Solar PM
> Date: 2026-05-13
> Depends on: S02_architecture (must pass first); 与 S03_core_runtime 并行
> Knowledge Context: solar-harness context inject used

---

## 0. 切片定位 (Slice Framing)

S04 是 DeepResearch Product Line 的**接入层切片** —— 不负责造 research 核心 (那是 S03 core-runtime)，也不定义接口 (那是 S02 architecture)，**只负责把 S02 落地的接口 + S03 出的能力**接入 Solar-Harness 现有的 autopilot、DAG scheduler、graph-node-dispatcher、status UI 和 pane runtime，让用户能：

- 在 pane 里输入需求 → autopilot 自动判定为 research 任务 → 派给正确 role
- 在 status 面板里看到 research run 的进度 (source 数、evidence 数、claim 支持率、unsupported rate)
- pane 输出不再是"完成了"的自然语言，而是带 evidence/claim/citation 证据

S04 **不**重新定义 evidence/claim/source schema (那是 S02 的事)，**不**实现 source connector 或 claim miner (那是 S03 的事)，**不**做最终 release/regression 验证 (那是 S05 的事)。

## 1. Context / 背景

Solar-Harness 已具备以下可复用接入面：

- **autopilot**: 监听 sprint 状态 → 自动推进 PM/Planner/Builder/Evaluator 流转
- **DAG scheduler (graph_scheduler)**: 校验 task_graph 合法性 + 依赖 + write_scope 隔离 + 父级不可提前 passed
- **graph-node-dispatcher**: 按 node 生成 dispatch 文件 + 绑定 pane lease + 限制 builder 当前 node + handoff 后 reviewing
- **status UI (status-server.py 端口 8765)**: 已展示 sprint/pane/能力状态
- **pane runtime**: 每个 pane 写 events.jsonl + handoff/eval 文件
- **capability plane**: capability inference + skills inventory + scorecard + activation-proof

但 DeepResearch 产品线 (epic-20260513) 的核心能力 (Source Mesh / Evidence Ledger / Claim Ledger / ReportAST / Factuality Evaluator) 不在这套接入面上：

- autopilot 不认识 "research run"，无法自动派 researcher/evidence-miner/fact-checker/chief-editor 角色
- graph_scheduler 没有 DeepResearch DAG 模板 (R0_scope_rewrite → R11_final_export)
- status UI 不展示 research 进度 (source 数、evidence 数、unsupported rate 等)
- pane 输出靠自然语言 (builder 直接喊"完成"), 而 DeepResearch 必须以 evidence_id + span_text 为单位
- capability plane 没有 `research.*` 能力族

**用户原始需求 (epic 锚)**: 见 `epic-20260513-solar-deepresearch-product-line.epic.md`。简言之：把 Solar-Harness 从 "AI-native 研发控制面" 升级为 "AI-native 研究生产操作系统"，本切片专门解决 "接入" 这一层。

## 2. Problem Statement / 用户问题

**监护人视角的疼点**:

1. **没法启动**: 想跑深度研究只能手动写 dispatch.md，autopilot 不认 research intent，没有 `solar-harness research run` 闭环
2. **看不见进度**: 已有的 status UI (8765) 不显示 research 运行状态 — source 抓了多少、evidence 落了多少、claim 支持率怎么样、是否有 unsupported claim 卡住
3. **不敢相信 builder**: 当前 pane 输出靠自然语言 ("已完成 R0_scope_rewrite")，没有 evidence_id / span_text / source authority 之类的硬证据，监护人没法在不读源码情况下判断真假
4. **不知道阻塞**: DeepResearch 是多 pane 多角色并行，researcher pane 卡住时 chief-editor 拿不到下游信号
5. **不能并发**: 30-40 个 section 写作必须 section 级隔离 write_scope，否则两个 pane 同时写 sec01.draft.md 会撞车

**根因**: DeepResearch 核心能力 (S02/S03 出) 没和 Solar-Harness 接入面契约对齐 — 接入面不认识 research 概念，核心能力不知道怎么把 evidence 流到 status/pane。

## 3. User Goals / 用户目标

| # | 目标 | 衡量 |
|---|------|------|
| G1 | 一条命令启动 research run | `solar-harness research run --brief "..." --target-chars 100000` 触发完整 DAG 派工 |
| G2 | autopilot 自动识别 research intent | dispatch 含 research 关键词时, autopilot 自动派给 researcher pane, 不需人工拍板 |
| G3 | status UI 显示 research 真实状态 | `/integrations` 或 `/research/<sid>` 显示 source/evidence/claim/unsupported 五个指标 |
| G4 | pane 输出带 evidence 证据 | builder handoff 必须含 `evidence_ids[]`, 没有就 evaluator fail |
| G5 | section 级并发不撞车 | 5 个 section 并行写, 0 次 write_scope 冲突 |
| G6 | 阻塞原因可视化 | status UI 标 "blocked: waiting for S03_core_runtime.evidence_ledger" |

## 4. User Stories / 用户故事

- **US1**: 作为监护人 (昊哥)，我希望在 pane 里输 `solar-harness research run --brief "LLM agent training survey" --target-chars 50000`，**以便** 自动展开 R0→R11 全套 DAG，不用手写 task_graph。
- **US2**: 作为 PM, 我希望写完 research_brief.md 后，autopilot 自动识别 "research" intent 把 sprint 派给 researcher pane (不是普通 builder)，**以便** 用对的角色干对的活。
- **US3**: 作为监护人, 我希望在 `/status` 面板看到 "research-sid-xxx: 23 sources / 451 evidence / 89 claims / unsupported_rate=4.2%", **以便** 一眼判断研究是否健康。
- **US4**: 作为 fact-checker, 我希望 builder handoff 必须列 `evidence_ids[]` + `unsupported_claim_count`, **以便** 直接基于证据 audit, 不用反向猜 builder 是不是糊弄我。
- **US5**: 作为 chief-editor, 我希望 30 个 section 并行写时, graph_scheduler 自动隔离 `sections/ch01/sec01.*` vs `sections/ch01/sec02.*` 的 write_scope, **以便** 不会两个 pane 同时改一个文件。
- **US6**: 作为监护人, 我希望 researcher pane 卡在 source fetch 超时时, status UI 立刻显示 "blocked: arxiv timeout", **以便** 知道该手动介入还是再等。
- **US7**: 作为评估者, 我希望看 R8_section_fact_check 节点 handoff 时, 看到 `citation_span_accuracy / unsupported_claim_rate / source_authority_score` 三个数, **以便** 决定是否 pass 节点。

## 5. Functional Requirements / 功能需求

### FR-1 Autopilot research intent 识别 (对应 A1)
- autopilot intent engine 加 `research.run` 规则: dispatch 含 "research/调研/综述/深度报告/factuality" 关键词时, 自动识别为 research intent, score >= 0.7 时不询问监护人
- intent 命中后, autopilot 自动派给 researcher pane 而非通用 builder pane
- 失配时降级为普通 builder, 写 `autopilot_degraded_to_builder` 事件

### FR-2 DeepResearch DAG 模板 (对应 A2)
- 在 `harness/lib/research/graph/templates/` 下提供 `deepresearch.template.json`, 含 R0_scope_rewrite → R11_final_export 12 节点
- `solar-harness graph-scheduler validate templates/deepresearch.template.json` 必须 pass
- 节点 write_scope 自动隔离: `sections/chXX/secYY.*` 路径前缀按节点 ID 拆分, 5 个并行 section 0 冲突
- `solar-harness research run` 命令展开模板成具体 task_graph 写入 `<sid>.task_graph.json`

### FR-3 Pane evidence 输出约定 (对应 A3)
- builder handoff schema 加必填字段:
  - `evidence_ids[]` — 本节点产出/引用的 evidence 列表 (空数组允许, 但缺字段 fail)
  - `claim_count` — 本节点新增 claim 数
  - `unsupported_claim_count` — 本节点产出 claim 中无 evidence 支撑的条数
- evaluator 默认拒收 handoff 缺这三字段的 dispatch (除非节点声明 `requires_evidence: false`)
- 输出走 `<sid>.<node>-handoff.md` 已有路径, 不新增文件

### FR-4 Status UI 研究面板 (对应 A4)
- status-server.py 加路由 `/research/<sid>` (HTML + JSON 双输出)
- 展示字段: `source_count`, `evidence_count`, `claim_count`, `unsupported_rate`, `citation_span_accuracy`, `current_node`, `blocked_reason`
- 数据源: `<sid>.sources.jsonl` / `<sid>.evidence.jsonl` / `<sid>.claims.jsonl` (S03 产出)
- 缺数据时显式标 "pending: S03_core_runtime not yet delivered evidence_ledger"

### FR-5 Capability Plane research 能力族 (对应 A5)
- `solar-harness skills inventory` 必须包含:
  - `research.source.search`
  - `research.evidence.extract`
  - `research.claim.mine`
  - `research.citation.verify`
  - `research.report.compile`
- 每个能力跑 `capability_activation_proof.py` 必须出 `ok / warn / pending`, 不允许 fake ok
- doctor 命令 `solar-harness research doctor` 报告每个 connector 健康度

### FR-6 阻塞原因传递 (对应 A6)
- graph_scheduler 节点 ready check 失败时, 把 blocker 写到 `<sid>.status.json` 的 `blocked_by[]` 和 `blocked_reason`
- status UI 直接展示, 不靠 grep events.jsonl 反推
- 解锁后 (依赖 passed) 自动写 `unblocked_at` 时间戳

### FR-7 CLI 命令路由 (对应 A7)
- `solar-harness research <subcmd>` 子命令族至少含 `run / plan / status / doctor` 四条
- `status --json` 输出可被 status UI 直接消费 (与 FR-4 共用 schema)
- 缺 S03 能力时, 子命令返回 actionable error: "research subcmd requires evidence_ledger from S03; current=pending"

## 6. Acceptance Criteria / 验收标准

| ID | 验收 | 验证命令 |
|----|------|----------|
| A1 | autopilot 识别 research intent | 模拟 dispatch 含 "调研 LLM agent 训练综述", autopilot intent 命中 `research.run`, score≥0.7 |
| A2 | DAG 模板可校验可展开 | `solar-harness graph-scheduler validate templates/deepresearch.template.json` pass + `solar-harness research run --dry-run` 输出合法 task_graph.json |
| A3 | Builder handoff 必带 evidence 字段 | 缺 `evidence_ids[]` 字段的 handoff 被 evaluator 拒收, 写 `eval_failed_missing_evidence_schema` 事件 |
| A4 | `/research/<sid>` 显示 6 指标 | curl status-server `/research/<sid>` HTML 含 6 个指标占位 (S03 未到位时显示 pending) |
| A5 | capability_activation_proof 含 research.* | `solar-harness integrations activation-proof --json` 5 个 `research.*` 条目, 状态非 fake ok |
| A6 | 阻塞原因可视化 | 创建依赖未满足的 child node, status.json 含 `blocked_by[]` 非空 + `blocked_reason` 字符串 |
| A7 | CLI 4 子命令可用 | `solar-harness research run/plan/status/doctor --help` 均不报 unknown command |

每条 acceptance 都要有可复现验证证据 (命令 + 输出 + 时间戳), 不接受 "刚跑过缓存通过"。

## 7. Non-Goals / 非目标

- **不**实现 evidence/claim/source 任何 schema 或存储 (那是 S02 + S03 的事)
- **不**实现 source connector (arxiv/openalex/github/jina 等) — S03 负责
- **不**实现 factuality evaluator 算法 (S03 + S05 负责), 本切片只暴露指标到 UI
- **不**重写 graph_scheduler / graph-node-dispatcher 公共 API, 只在模板和 schema 层面扩展
- **不**做 final report 编译 (那是 S03 + S05 联合负责)
- **不**做最终回归测试 + release 证据 (那是 S05)
- **不**做 UI 大改, 只在 status-server.py 加 `/research/<sid>` 路由
- **不**做 OS 级隔离或 sandbox 改造 (前序 sprint 已闭环)

## 8. Constraints / 约束

- **C1 (依赖)**: 本切片实现强依赖 S02 architecture 出口的 `EvidenceItem / Claim / ReportSection` schema 接口契约, **不能在 S02 未 passed 前 dispatch builder**
- **C2 (隔离)**: graph_scheduler write_scope 隔离规则不可破坏, section 级写权限按 `sections/chXX/secYY.*` 路径前缀切分
- **C3 (向后兼容)**: 不破坏现有 `solar-harness graph-scheduler / autopilot / status` 命令签名, 只能增 subcommand 或字段
- **C4 (前台体验)**: research run 必须立即返回 sid + dry-run 输出, 不阻塞 pane (与 mineru 长任务一样, 后台 detach)
- **C5 (假 ok 红线)**: 任何接入面 (autopilot/dispatcher/status/capability) 报 `ok` 时必须有真证据 (activation proof / evidence count > 0), 否则只能 `warn / pending`
- **C6 (Stop Rules 继承)**: 父 epic 5 条 Stop Rules 在本切片继续生效 — 单 prompt 长报告 / 无 evidence 的 claim / 父 sprint 提前 passed / 静默降级 / 单 builder 写十万字, 均触发 fail
- **C7 (无 OS 容器)**: 不引入 Docker/seatbelt/chroot, 复用现有 SandboxHand (前序 sprint 已就位)

## 9. Risks / 风险

| # | 风险 | 触发条件 | 缓解 |
|---|------|----------|------|
| R1 | S02 architecture 接口契约延迟 | S02 sprint 卡 reviewing > 24h | 本切片设占位 schema (mock interface), 等 S02 真 passed 再切换; 切换前 capability_activation_proof 显式 `pending: waiting_s02` |
| R2 | autopilot intent 误判 | research 关键词在普通工程 sprint 出现 (e.g. "research codebase") | intent score 阈值 0.7 + 显式 `research.run` 规则只命中 `research run/调研报告/深度综述` 等强信号词 |
| R3 | section 并发 write_scope 撞车 | 30 节点并行, 写权限设计漏 | 模板里每节点 write_scope 强制 `sections/chXX/secYY.*` 唯一前缀, graph_scheduler validate 出非法 DAG 时直接 fail fast |
| R4 | status UI 显示假数据 | S03 没出 evidence_ledger, UI 强行展示空表 → 监护人误以为 0 evidence | UI 缺数据时显式 "pending: S03 dependency", 不显示 0 |
| R5 | Builder 绕过 evidence 字段 | handoff 不写 evidence_ids 但写 "evidence_in_text" | evaluator 用 schema 校验, 不接受字段名变体 |
| R6 | Capability activation proof 假 ok | research.* 能力还没实装就标 ok | proof 必须 grep evidence dir 含至少 1 条产物, 否则降级 warn |
| R7 | 与 S05 验证职责重叠 | S04 写了端到端测试, S05 再写一遍 | 本切片只写接入层 smoke (intent 命中/schema 校验/UI 渲染), 不写 evidence/claim 算法回归 (S05 范围) |
| R8 | 接入层改动反向破坏现有 sprint 流转 | autopilot intent 规则改动误命中老 sprint | 加 intent 命中日志 + dry-run 回归 5 个历史 sprint, 0 误命中才可 merge |

## 10. Open Questions / 开放问题 (给 Planner / 架构师)

1. **research intent 关键词清单是否要支持监护人扩展?** 默认硬编码 vs 走 `~/.solar/config/research-intent-keywords.json` 配置文件 — 后者更灵活但增加维护面。
2. **status UI 路径**: `/research/<sid>` vs `/sprints/<sid>?lens=research` 哪种好? 前者独立路由更清晰, 后者复用现有 sprint 视图减少新代码。
3. **DeepResearch DAG 模板放哪?** `harness/lib/research/graph/templates/` (按本切片范围 in S04 写) vs `harness/templates/dag/deepresearch.json` (架构层放 by S02). 取决于 S02 是否落地 templates 目录。
4. **section 级 write_scope 切分粒度**: `sec` 级 (每节单独) vs `ch` 级 (章级共享)? 前者并发度高但 graph 节点数爆炸 (30 节点 → 30+ writer dispatch), 后者降并发但节点数收敛 (12 节点)。
5. **Builder handoff 缺 evidence 字段时如何降级?** 硬 fail (节点 eval failed) vs 软降级 (warn + 自动 patch evidence_ids=[])? 影响 builder 迁移成本。
6. **autopilot 派 researcher pane**: 复用现有 builder pane (lease 标 role=researcher) vs 起新 pane (独立 pane 角色)? 影响 pane 资源开销。
7. **capability_activation_proof 5 条 research.\* 的 proof 路径**: 完整跑一次 mini research run vs 静态 grep 接口实现存在? 前者更真但慢, 后者快但可能假 ok.
8. **CLI `solar-harness research` 命名冲突**: 是否与现有命令冲突? 需要 architect 提前 grep 子命令空间。

## 11. 架构交接 / Planner Handoff

Planner 需要把本切片拆成 **4-5 条 builder slice**, 推荐依赖顺序:

1. **N1 — Autopilot research intent 路由** (FR-1)
   - 改 autopilot intent engine 加 `research.run` 规则
   - 加 dry-run 回归: 5 个历史 sprint 测 0 误命中
   - 出口: `solar-autopilot dry-run --dispatch test-research-brief.md` 命中 research.run, score>=0.7

2. **N2 — DAG 模板 + graph_scheduler 校验** (FR-2)
   - 在 `harness/lib/research/graph/templates/` 创建 `deepresearch.template.json`
   - graph_scheduler 加模板展开命令 `--expand-template`
   - 出口: `validate templates/deepresearch.template.json` pass + section 级 write_scope 隔离测试 5 并发 0 冲突

3. **N3 — Handoff evidence schema** (FR-3) ∥ N4
   - 改 builder handoff schema 加 `evidence_ids[] / claim_count / unsupported_claim_count` 三字段
   - evaluator 加 schema 校验, 缺字段拒收
   - 出口: 故意提交缺字段 handoff, evaluator 写 `eval_failed_missing_evidence_schema` 事件

4. **N4 — Status UI research 面板** (FR-4 + FR-6) ∥ N3
   - status-server.py 加 `/research/<sid>` 路由 + JSON schema
   - 阻塞原因 (`blocked_by[] / blocked_reason`) 标准化写入 status.json
   - 出口: curl `/research/<sid>` 返回 6 指标; 人造阻塞 child node, UI 显示 blocked_reason

5. **N5 — Capability plane + CLI 路由** (FR-5 + FR-7)
   - capability inference 加 5 条 `research.*` 能力族 + activation_proof 校验真证据
   - CLI 加 `solar-harness research run/plan/status/doctor` 4 子命令
   - 出口: `solar-harness skills inventory --json | grep research.` 输出 5 条 + `research doctor` 给每个 connector 真状态

并行规则: N3 ∥ N4 可并行 (write_scope 不冲突); N5 依赖 N1+N2; N1 是入口, 优先做。

每个 N 必须独立 evaluator review, 不允许 contract-patrol 直接标 passed (吸取 sprint-20260513-tool-plane-sandbox followup F4 教训)。

跨切片共用约束:
- 所有改动必须先有 dry-run 回归证明不破坏现有流转, 再合入
- capability_activation_proof 状态 (ok/warn/pending) 必须真实, 不允许接入层为了通过 gate 强标 ok
- 等 S02 architecture 真 passed 后才能锁定 evidence/claim/source schema 字段, 在此之前用 placeholder + TODO 标记

---

## 附录 A — Epic 上下文 (参考材料, 不在本切片实现范围)

> 以下内容来自 `epic-20260513-solar-deepresearch-product-line.epic.md`, 仅作为背景参考。S04 不实现这些内容; 它们是 S02/S03/S05 的范围。

### A.1 DeepResearch 核心缺口 (epic-level, 非 S04 实现)

- **Source Mesh**: Web/Academic/Preprint/DOI/Patent/Code Repo/Standards/Dataset/Company/Internal — S03 实现, S04 只接入
- **Evidence Ledger**: `EvidenceItem / Claim / ClaimEvidenceLink / CitationSpan / Contradiction / EvidencePack` 一等公民 — S02 定义 schema, S03 实现存储, S04 只接 UI
- **ReportAST**: `Report / Chapter / Section / Subsection / ClaimBlock / EvidenceBlock / ...` — S02 + S03 实现
- **Factuality Evaluator**: `unsupported_claim_rate / citation_span_accuracy / ...` 七指标 — S03 算, S04 只展示
- **Source Intent Classifier**: 判断需求需要哪类源 — S03 实现

### A.2 运行产物 (epic-level 全套, S04 只接入)

```
<sid>.research_brief.md / research_plan.json / source_matrix.json
<sid>.sources.jsonl / evidence.jsonl / claims.jsonl / contradictions.jsonl
<sid>.report_ast.json / sections/ / chapters/ / final.md / bibliography.json
<sid>.research_eval.json
```

S04 范围: 把这些产物名标准化, 让 status UI 知道去哪读; 不负责生产它们。

### A.3 DAG 模板节点清单 (epic-level)

`R0_scope_rewrite / R1_source_matrix / R2_external_search / R3_fetch_extract / R4_claim_mining / R5_contradiction_hunt / R6_report_ast / R7_section_writing_batch / R8_section_fact_check / R9_chapter_compile / R10_global_consistency / R11_final_export`

S04 范围: 把这 12 节点写进 `deepresearch.template.json` 让 graph_scheduler validate 过; 不实现每个节点的具体逻辑 (那是 S03)。

### A.4 Epic Stop Rules (继承)

- 不允许把 DeepResearch 做成单 prompt
- 不允许没有 evidence span 的 claim 进入 final report
- 不允许 parent sprint 在 evidence/claims/fact-check gates 未过前 passed
- 不允许 Source Mesh connector 失败时静默降级为模型自说自话
- 不允许十万字报告写入单个 builder 节点

---

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-intent, harness-skills, harness-graph
