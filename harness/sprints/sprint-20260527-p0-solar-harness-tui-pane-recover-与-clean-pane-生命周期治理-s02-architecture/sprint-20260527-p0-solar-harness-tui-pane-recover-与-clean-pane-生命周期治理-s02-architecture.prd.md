# PRD: 架构设计与接口契约

epic_id: `epic-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理`
sprint_id: `sprint-20260527-p0-solar-harness-tui-pane-recover-与-clean-pane-生命周期治理-s02-architecture`
slice: `architecture`
intent_id: `intent-20260527-170915-77f8774ef4` (复用 epic raw_intent，未重新捕获)
priority: `P0`
handoff_to: `planner`
status: `drafting`

## 用户原始需求

P0: Solar Harness TUI Pane Recover 与 Clean Pane 生命周期治理

背景：
当前 graph-dispatch/evaluator 仍以 Claude/GLM/Sonnet TUI pane 为主执行面。TUI 便宜、低开销、能直接使用 Coding Plan，因此继续保留。但当前 pane 会被 `Do you want to proceed?`、`Press up to edit queued messages`、权限确认、plan mode、残留 prompt 和跨任务上下文污染卡住，导致 cooldown、假并发和 evaluator 队列拖慢。

目标：
1. 保留 TUI 作为默认执行路径，不切换到 API 默认路径。
2. recover 从"cooldown 等待"升级为"自动清理确认框/queued prompt；失败后重分配或标记 respawn"。
3. 每个 pane 在完成一系列相关任务后自动执行 `/clear`，清除上下文污染。
4. clean pane 下次被使用前必须重新注入 persona、runtime policy、Solar context、capability/context prompt。
5. evaluator 支持主 Evaluator + clean lab spillover，不再因为单 pane 或 queued prompt 拖住评审队列。
6. 所有 recover/clear/reassign 行为必须写入 dispatch-ledger/model_call_ledger，便于审计。

实现要求：
- 增加 pane hygiene registry：`~/.solar/harness/run/pane-hygiene.json`。
- 增加状态：clean、dirty、running、cooling、needs_recover、needs_respawn。
- 派发前必须检查 pane hygiene；dirty pane 先 /clear，失败则跳过。
- 任务完成后按 dispatch group 或 sprint sibling 系列边界执行 /clear。
- /clear 成功判定：pane 回到空 prompt，且无 queued prompt、确认框、残留输入。
- 下次派发 clean pane 前强制重新注入 persona/runtime policy/context。
- queued prompt/proceed/permission prompt recover 成功后可继续使用；失败进入 cooldown 或 needs_respawn。
- 同批 dispatch-evals 必须避免重复选择同一 pane。
- 不允许把 cooldown 当最终修复；cooldown 只作为失败保护。
- 不允许删除用户数据、不重启 ThunderOMLX/ASR、不杀主 pane，除非明确进入 needs_respawn 且只重建该 worker pane。

验收标准（来自 epic 原始需求）：
1. 模拟 `Do you want to proceed?` 时，dispatcher 能自动确认或退出并继续派发。
2. 模拟 `Press up to edit queued messages` 时，dispatcher 能清理或重分配，不会反复撞同一个 pane。
3. builder 完成 handoff 后自动 `/clear`，并标记 clean。
4. evaluator 完成 eval.md/eval.json 后自动 `/clear`，并标记 clean。
5. clean pane 再次接任务前能看到 persona/runtime/Solar context 被重新注入。
6. dispatch-evals `--max-items 3` 能把三个 eval 分配到不同可用 pane。
7. 坏 pane 不会拖住队列；失败会写 ledger，并触发 reassign。
8. 相关 `py_compile` 和最小回归测试通过。

## 背景 / Context

- **当前痛点**：4-pane 协同（pane 0 planner opus / pane 1 builder glm-5.1 / pane 2 evaluator glm-5.1 / pane 3 architect opus）跑了几周后，频繁出现 pane 被卡在 TUI 交互（proceed prompt / queued message / permission / plan mode）→ cooldown 反复触发 → evaluator 队列累积。 chain-watcher 看到 pane busy 就不派发，假并发让 chain stop。
- **保留 TUI 是经济决定**：TUI 直接使用 Anthropic Max / GLM Coding Plan 配额（已支付），切到 API 默认路径会触发计费。
- **本切片定位**：这是 epic `epic-20260527-…-tui-pane-recover-与-clean-pane-生命周期治理` 的 **S02 architecture** 切片，上游是已 passed 的 **S01 requirements**（N1 pane_hygiene_and_recover + N2 auto_clear_and_reinject + N3 spillover_ledger_safety，共 ≥53 KB 需求文档 + 7 outcomes + 5 OQ + 7 待定决策）。S02 只产架构 / data model / API 草案 + OQ 决议，**不写实施代码**。
- **环境**：Mac mini M4 (lisihaodeMac-mini.local)，bash 5.3.9，tmux 多 pane 已稳定运行；Solar Harness coordinator + chain-watcher + graph-scheduler 已在线。

## 用户问题 / Problem

- **PB-1 cooldown 反复**：单 pane 被 proceed prompt 卡住 → 调度器降级为 cooldown 等待 → 等待结束 pane 仍然 dirty → 再次失败 → 假并发。
- **PB-2 上下文污染**：同一 pane 跑了 10 个 sprint 后，persona/runtime/Solar context 漂移，新任务可能继承上一个任务的角色 / decision。
- **PB-3 队列拖慢**：evaluator 单 pane 卡住 → `dispatch-evals` 即使 `--max-items 3` 也只能撞同一个 pane。
- **PB-4 审计缺失**：现有 ledger 没记录 recover / clear / reassign 的具体原因和耗时，事后没法 root cause。
- **PB-5 S02 自身的 PRD 不完整**：之前 PRD 缺 7 个 schema 必需 section，coordinator 反复拦截 gate_prd_schema；本次修复就是为了让 S02 sprint 能正式进入 planner → builder → evaluator 流程。
- **PB-6 架构层模糊**：S01 已经定义 7 outcomes（pane-hygiene registry / 状态机 / detector / 重注入器 / spillover / ledger / 安全护栏）但没有定 control plane / data plane / 模块边界 / 存储介质 / API 签名，S03/S04 实施前必须先在 S02 定死，否则 builder 各自发明轮子。

## 用户故事 / User Stories

- **US-01 (Solar 主用户)**：作为 Solar 主用户，当我在 tmux 一个 pane 上看到 "Do you want to proceed?"，我希望调度器在 ≤5 秒内确认或绕过这个 pane，不要把整个调度链卡住。
  - 验收：S02 architecture 中 RecoverDetector 模块给出 ≤5s 检测 + 决策 SLA 草案。
- **US-02 (Planner / Architect)**：作为下游 Planner，我希望本 PRD 明确告诉我 S02 要决定哪 7 个决策点（D1-D7）和 5 个 OQ（OQ-01..OQ-05）的归属，避免我重新猜 S01 留下的边界。
  - 验收：本 PRD `## 架构交接 / Planner Handoff` 列出全部 7 决策 + 5 OQ 的归属节点（A1-A5）。
- **US-03 (Builder, 仅写规约)**：作为 S02 builder，我希望知道我只允许写 5 类 markdown / json（architecture / data_models / interfaces / OQ resolutions / traceability+handoff），不允许动 solar-harness 任何 python/sh/yaml 源码。
  - 验收：`## 约束 / Constraints` 明确列出可写文件白名单 + 严格禁止清单。
- **US-04 (Evaluator)**：作为 Evaluator，我希望本 PRD 给出可程序化的 stop_rules，让我能直接判定 sprint passed / failed。
  - 验收：`## 范围` stop_rules 完整，且与 S02 design.md §0 切片边界一致。
- **US-05 (运维/审计)**：作为 ledger 维护者，我希望本 PRD 写明所有 pane 行为必须双写 ledger（dispatch-ledger / model_call_ledger）≥6 字段，并约束 schema 在 S02 落地。
  - 验收：`## 验收标准` 含 ledger schema 字段最小集。
- **US-06 (Chain-watcher)**：作为自动化调度，我希望 S02 passed 之前不会被自动派 builder（S03 core-runtime 等下游不能被提前激活）。
  - 验收：stop_rules 中含 "缺 task_graph.json 不得派 builder" 且 traceability.json 保持 children S03/S04/S05 `status=queued`。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-…-生命周期治理.epic.md`、`epic-…-生命周期治理.traceability.json` 和父级 `task_graph.json`。
- 必须读取 S01 三份 requirements 文档（N1/N2/N3）和 S01 traceability + handoff。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。
- stop_rules：
  - 缺 `.task_graph.json` 不得派 builder。
  - 缺可复现验证不得标记 passed。
  - 发现 scope 冲突必须回写父级 traceability。
  - PRD 缺任何 7 个必需 section 不得状态推进到 planner。
  - S02 design.md / data_models.md / interfaces.md / open_questions_resolutions.md 任一 节缺失不得 join A5。
  - 不允许把 cooldown 当作最终修复（epic 硬约束）。
  - 不允许切换到 API 默认路径（epic 硬约束）。

## 验收标准

- **A1 设计覆盖**：control plane（dispatch / hygiene check / recover / clear 触发）与 data plane（pane-hygiene.json schema / ledger schema）必须分层；状态机覆盖 6 状态 × 全部合法转移。
- **A2 接口边界 + 旧系统兼容**：写清楚 `~/.solar/harness/run/pane-hygiene.json`、`dispatch-ledger`、`model_call_ledger` 三类 store 的接口契约和 schema；旧 coordinator / chain-watcher 不需要改字段或 API 才能继续工作（兼容策略文档化）。
- **A3 冲突 + 依赖 + 降级**：列出 S02 与 S01 / S03 / S04 的接口冲突点；说明哪个 S02 决定下放到 S03（实施）/ S04（编排），并写明每个 OQ 的 fallback。
- **A4 OQ 全部决议**：OQ-01 (持久化频率) / OQ-02 (retry 阈值) / OQ-03 (重注入频率) / OQ-04 (spillover 池规模) / OQ-05 (respawn 命令) 全部落地到 `open_questions_resolutions.md`，每个有 decision + alternatives + risk + owner（S03 或 S04）。
- **A5 决策矩阵**：D1-D7 全部落到 A1/A2/A3/A4 之一，traceability.json 含 outcome ↔ decision ↔ document 三向映射。
- **A6 Ledger schema**：dispatch-ledger / model_call_ledger 字段 ≥6（pane_id, action, reason, started_at, ended_at, result + optional error_class），同步/异步写策略明确。
- **A7 安全护栏**：4 条 epic 硬约束（不删用户数据 / 不重启 ThunderOMLX/ASR / 不杀主 pane / cooldown 不作最终修复）在 architecture.md §7 被显式承诺并对应到 enforcement 模块。
- **A8 输出齐全**：A1-A5 五份 artifact 全部存在，每份 ≥ 阈值（A1 ≥10 节 / A2 含完整 schema DDL 草案 / A3 含 ≥3 类 API 草案 / A4 含 5 OQ × {decision, alternatives, risk, owner}）。

## 非目标 / Non-Goals

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用"已完成"替代可复现证据。
- 不写 python / shell / yaml 实施代码（S02 builder 只写 markdown + JSON 草案）。
- 不动 S01 任何 artifact，也不动 epic 任何 artifact。
- 不真改 `~/.solar/harness/run/pane-hygiene.json`（S02 只产 schema 草案，实施留 S03）。
- 不真跑 `tmux send-keys` / `/clear` / pane respawn / `dispatch-evals`（S02 是规约层）。
- 不切换 TUI 到 API 默认路径。
- 不试图改写 evaluator 主流程算法（只写 spillover 编排 schema，主流程留 S04）。

## 约束 / Constraints

- **环境**：macOS arm64 (lisihaodeMac-mini.local)，bash 5.3.9 at `/opt/homebrew/bin/bash`，tmux 多 pane，Coordinator / chain-watcher / graph-scheduler 已运行。
- **可写文件白名单**（S02 builder 只能写这 5 类）：
  - `~/.solar/harness/sprints/<s02-sid>.architecture.md`（A1）
  - `~/.solar/harness/sprints/<s02-sid>.data_models.md`（A2）
  - `~/.solar/harness/sprints/<s02-sid>.interfaces.md`（A3）
  - `~/.solar/harness/sprints/<s02-sid>.open_questions_resolutions.md`（A4）
  - `~/.solar/harness/sprints/<s02-sid>.traceability.json` + `<s02-sid>.handoff.md`（A5 join）
- **严格禁止**：
  - 修改 S01 / epic 任何 artifact。
  - 修改 solar-harness 任何 python/sh/yaml 源码。
  - 真改 `~/.solar/harness/run/pane-hygiene.json` 或 ledger 实物文件。
  - 真跑 `tmux send-keys` / `/clear` / `dispatch-evals`。
- **路径**：产出只在 `~/.solar/harness/sprints/`；禁 `/tmp`、禁用户 home 根。
- **不破坏 API**：现有 `solar-harness context inject / session evaluate / intent-gateway capture` 必须照常工作。
- **角色边界**：PM 不写实现代码、不动 status 到 implementation、不跳 PRD schema；本 PRD 修复结束后保持 `status=drafting`，依赖 coordinator 重新跑 gate 并 advance。
- **TUI 经济约束**：保留 TUI 作为默认执行路径（epic G1）；不允许在 architecture 中提议默认切到 API。
- **安全/审计**：所有 pane 行为（hygiene check / clear / recover / reassign）必须双写 ledger ≥6 字段。

## 风险 / Risks

| 风险 | 影响 | 缓解 / Owner |
|------|------|--------------|
| S02 决策过粗，S03 落地时发现 schema 不可实施 | S03 builder 卡住 → epic 全停 | A2 必须给 SQLite DDL 草案 或明确选 JSONL + 并发策略；S03 启动前 30s 跑 schema dry-run / Planner |
| OQ-01 持久化频率定低 → 状态丢失；定高 → 写放大 | 状态机不可信 | A4 OQ-01 给 ≥2 alternatives + 数值实测建议 / Architect |
| 6 状态机转移不闭环（例如 needs_recover → needs_respawn 没明示） | recover 死锁 | A1 §2 必须给完整 10 条转移表（与 S01 N1 §2 对齐） / Planner |
| ledger 同步写阻塞 dispatch 关键路径 | 调度延迟 | A2 ledger 必须支持异步写 + 失败重试上限 / Planner |
| spillover 池规模与现有 5 个 lab pane 不对齐 | 撞同 pane | A4 OQ-04 必须基于现有 solar-harness:0.3 主 + lab:0.0..0.3 4 spillover 选型 / Architect |
| respawn 命令杀错 pane（杀掉主 pane / ThunderOMLX / ASR） | 系统瘫痪 | A4 OQ-05 命令必须含 pane 白名单检查 + dry-run hook / Architect |
| persona 重注入频率过高 → token 浪费 | 成本爆 | OQ-03 应选 "clean→running 时全量注入，同 session 内不重注" 轻策略 / Architect |
| coordinator 状态字段或 advance 逻辑被错误改动 | gate_prd_schema 重跑链坏 | 本切片只触发 PRD mtime，不改 coordinator / PM |
| 下游 S03/S04 在 S02 未 passed 时被 chain-watcher 提前激活 | scope 冲突 | traceability.json 保持 S03/S04 `status=queued` + chain-watcher 必须 honor depends_on / 平台 |

## 开放问题 / Open Questions

S01 已留 5 个 OQ，S02 必须在 `open_questions_resolutions.md` 全部决议；本 PRD 列出待答清单，不做决议（决议是 S02 architecture 内 A4 节点的产物）：

- **OQ-01 持久化频率**：pane-hygiene.json 写盘频率（每次状态转移 vs 定时 vs 内存缓存+atomic write）？S03 落地。
- **OQ-02 /clear retry 阈值**：retry 几次 / 每次 backoff 多少 / 升级 needs_respawn 条件？S03 落地。
- **OQ-03 persona 重注入频率**：每次派发都重注 vs clean→running 时一次性注入？S03 落地。
- **OQ-04 spillover 池规模 + 调度策略**：与现有 5 个 lab pane 对齐；round_robin / least_busy / random？S04 落地。
- **OQ-05 needs_respawn 命令选型**：tmux kill-pane + split-window + 等待 prompt 就绪信号；具体命令模板 + 白名单。S04 落地。

新发现 / S02 决议时可能新增的 OQ（暂不锁死）：
- **OQ-06**：proceed-prompt 检测器选型（tmux capture-pane 文本 parse vs claude-code json output vs 专用状态文件）？归 A1/A3。
- **OQ-07**：/clear 成功判定信号采集机制（tmux capture-pane vs 专用 ready marker）？归 A1/A3。
- **OQ-08**：ledger 引擎（SQLite / JSONL / 现有 solar.db 表扩展）？归 A2。

## 交付物

- `sprint-…-s02-architecture.prd.md`（本文件，PM 产）
- `sprint-…-s02-architecture.prd.html`（人读 HTML artifact，PM 产）
- `sprint-…-s02-architecture.design.md`（Planner 已产，对应 A1/A2/A3 设计大纲）
- `sprint-…-s02-architecture.plan.md`（Planner 产）
- `sprint-…-s02-architecture.task_graph.json`（Planner 产，含 5 节点 DAG：A1 / A2 / A3 / A4 / A5）
- `sprint-…-s02-architecture.architecture.md`（Builder A1 产）
- `sprint-…-s02-architecture.data_models.md`（Builder A2 产）
- `sprint-…-s02-architecture.interfaces.md`（Builder A3 产）
- `sprint-…-s02-architecture.open_questions_resolutions.md`（Builder A4 产）
- `sprint-…-s02-architecture.traceability.json` + `.handoff.md`（Builder A5 join 产）
- `sprint-…-s02-architecture.eval.md` 或 `.eval.json`（Evaluator 产）

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD（含 8 个 epic 验收 + 6 个用户故事 + stop_rules + 约束/风险/开放问题）。
- Epic 原始需求 + traceability.json + task_graph.json。
- S01 三份 requirements 文档：
  - `…-s01-requirements.N1_pane_hygiene_and_recover-handoff.md` + `.eval.json` (passed)
  - `…-s01-requirements.N2_auto_clear_and_reinject-handoff.md` + `.eval.json` (passed)
  - `…-s01-requirements.N3_spillover_ledger_safety-handoff.md` + `.eval.json` (passed)
- S01 traceability + handoff（≥53 KB 需求文档总量，7 outcomes，5 OQ，7 决策项）。
- Planner 已产的 design.md（10 节大纲，A1-A5 节点 DAG，已含决策矩阵 D1-D7 ↔ A 节点映射）。

### Planner 必须产出

- `*.plan.md` — 每节点 ≤8 builder task；含 wave 切分（Wave 1: A1+A4 并行；Wave 2: A2+A3 并行；Wave 3: A5 join）。
- `*.task_graph.json` — 已存在；确认 5 节点 DAG（A1 / A2 / A3 / A4 / A5）+ depends_on 完整 + 每节点的 acceptance 列表与本 PRD `## 验收标准` 对齐。
- `*.handoff.md` — 填写每 outcome / 决策 / OQ 的 owner、stop_rule 引用、accepted_artifacts 路径。

### 7 决策 ↔ A 节点归属（来自 design.md §2，PRD 锁定）

| Dec-id | 主题 | OQ 关联 | 落入文档 |
|--------|------|---------|----------|
| D1 | pane-hygiene.json 完整物理 schema + 字段定义 + 默认值 | OQ-01 | A2 |
| D2 | 6 状态转移完整规则 + retry 阈值 + cooldown 时长 + 升级路径 | OQ-02 | A1 + A4 |
| D3 | proceed-prompt 检测器实现方式 | (新, OQ-06) | A1 + A3 |
| D4 | /clear 成功判定信号采集机制 | (新, OQ-07) | A1 + A3 |
| D5 | persona-reinject 模板源路径 + 重注入频率 | OQ-03 | A1 + A4 |
| D6 | ledger 字段 schema + 存储引擎 + 同步/异步写 | (新, OQ-08) | A2 |
| D7 | spillover 调度策略 + 池规模 | OQ-04 | A1 + A4 |
| D8 | needs_respawn 重建命令 + 白名单 | OQ-05 | A4 |

### 5 OQ 决议归属（PRD 锁定）

| OQ | 主题 | Owner（决议落地）| 实施 Owner |
|----|------|------------------|-------------|
| OQ-01 | pane-hygiene.json 持久化频率 | S02 A4 | S03 |
| OQ-02 | /clear retry 阈值 | S02 A4 | S03 |
| OQ-03 | persona 重注入频率 | S02 A4 | S03 |
| OQ-04 | spillover 池规模 + 调度策略 | S02 A4 | S04 |
| OQ-05 | needs_respawn 命令选型 | S02 A4 | S04 |

### Outcome ↔ 下游 sprint 映射（PRD 锁定）

| S01 Outcome | S02 主消费节点 | 下游实施 sprint |
|-------------|----------------|------------------|
| O1 Hygiene Registry + 6 状态机 | A1 + A2 | S03 |
| O2 3 类 prompt 检测器 | A1 + A3 | S03 |
| O3 /clear 触发链 + 成功判定 | A1 + A3 | S03 |
| O4 persona/runtime/Solar context 重注入 | A1 + A4 | S03 |
| O5 evaluator spillover + --max-items 3 不撞同 | A1 + A4 | S04 |
| O6 dispatch-ledger / model_call_ledger 双写 ≥6 字段 | A2 | S03 + S04 |
| O7 4 条安全护栏 | A1 + A4 | S04 + S05 |

### 不在 S02 范围、必须 S03+ 处理

- 真实写入 / 读取 `~/.solar/harness/run/pane-hygiene.json`（S03）。
- 真跑 `tmux send-keys` / `/clear` / pane 状态机的实施代码（S03）。
- evaluator 主流程 + dispatch-evals 编排实施（S04）。
- 6 状态机的 unit test + 端到端回归（S05）。
- `py_compile` + 最小回归测试（S05）。
- 4 安全护栏的 enforcement 实施（S04 + S05）。

### Knowledge Context

Knowledge Context: solar-harness context inject used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中；ATLAS / Everything Claude Code / Solar-Harness Runtime capabilities injected)。

### Harness Modules Used

Harness Modules Used: harness-knowledge (context inject), harness-intent (intent reuse intent-20260527-170915-77f8774ef4, no re-capture)。
