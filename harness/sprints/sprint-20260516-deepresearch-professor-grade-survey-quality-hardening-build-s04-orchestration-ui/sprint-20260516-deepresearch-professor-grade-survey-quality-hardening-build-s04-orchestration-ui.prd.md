# PRD: 调度、自动化与可视化

epic_id: `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build`
sprint_id: `sprint-20260516-deepresearch-professor-grade-survey-quality-hardening-build-s04-orchestration-ui`
slice: `orchestration-ui`

## 用户原始需求

DeepResearch professor-grade survey quality hardening: build pluggable package-local gates under harness/lib/research/survey only. Goal: reports must support 50k-100k word professor-level survey quality, not generic stitched summaries. Requirements: (1) source quality gate beyond URL count: canonical/high-authority distribution, primary source ratio, paper/code/official/benchmark balance, no generic example/web stuffing; (2) argument density gate: every section must contain mechanism comparison, method taxonomy, evaluation protocol, failure/negative evidence, and engineering implication where applicable; (3) controversy/反证 gate: final report must include contradiction/negative evidence matrix and use it in chapter synthesis; (4) no main architecture rewrite; everything must be package-first and pluggable; (5) agent online exploration should try multiple research directions quickly and eliminate weak directions, recording why; (6) end-to-end verification must include solar-harness runtime survey-continue sample, strict tests, and evidence artifact. Do not mark done without tests and runtime evidence.

## 本切片目标

把核心能力接入 autopilot、DAG 调度、status UI、pane 可视化和运行时证据。

## 背景 / Context

S01-S03 已锁定需求 / 架构 / 核心运行时实现：survey 包内 4 个 pluggable gate（O1 source_quality、O2 argument_density、O3 controversy_matrix、O4 exploration）+ E2E aggregator（O5 gate_report）+ explorer 子包，全部走 `survey/gates/_registry.py + survey/__init__.py` 插件注册。S03 deliverables 包含 8 个 dataclass + 4 个 gate + explorer + global_pass + runner_hook（attach-only）。但 S03 生成的 evidence artifact（distribution / density profile / contradiction matrix / elimination log / gate_report）目前**只落盘 JSON**，没有任何 CLI / pane / 用户面表面化通道；用户跑 survey-eval / survey-review / survey-compile / survey-plan 时看不到这些 gate 的判定与证据指针。

S04 任务：把 S03 已产出的 artifact **接到 survey-* CLI 表面**，并把 epic / child sprint / capability / 阻塞原因显示到 status UI / pane 输出，让"是否通过"和"为什么没过"成为可见运行时证据，而不是自然语言声明。

## 用户问题 / Problem

| 痛点 | 当前状态 | S04 后状态 |
|------|---------|-----------|
| 用户跑 `survey-eval --strict` 不知道哪个 gate 失败 | 输出只有总分数字 + 错误堆栈 | 4 个 gate 各自 verdict + 关键证据指针（distribution / density / matrix / exploration 路径） |
| 用户跑 `survey-compile` 不知道是否生成了 controversy matrix | 静默生成 JSON 文件，无 CLI 提示 | `controversy_matrix.json` 路径写入 CLI；装饰性 matrix 显式告警 |
| 用户跑 `survey-plan` 不知道探索了多少方向、淘汰原因 | 只看到最终 source_matrix，过程不可见 | `directions_proposed/eliminated/selected_count` + `elimination_log.jsonl` 路径在 CLI 输出 |
| 用户跑 `survey-review` 看不到 section 级 argument density 短板 | 只有总体 review.json | 表格化 per-section density profile + `low_density_sections` 列表 |
| autopilot 没有 capability gate hint | 派工时不知道当前 sprint 是否触发 4 gate 校验 | autopilot dispatch context 注入 4 gate readiness 摘要 |
| status UI 不展示 epic 子任务阻塞原因 | 用户只能 grep events.jsonl | `solar-harness status --epic <id>` 显示子 sprint 层 ready/blocked + 阻塞依赖 |
| pane 输出不可机器读 | 建设者声称 PASS 但无可校验事实 | gate_report.json + artifact_paths 写入 CLI 结构化输出，evaluator 可消费 |

## 用户故事 / User Stories

- **US-1（教授用户）**：作为学术综述作者，我跑 `solar-harness survey-eval <run> --strict` 后能直接看到 4 个 gate 的 PASS/FAIL 状态、违规章节列表与证据 artifact 路径，不需要 grep JSON 文件。
- **US-2（教授用户）**：作为学术综述作者，我跑 `survey-compile <run>` 后看到 controversy matrix 是否生成、是否为装饰性矩阵（claim 全无 negative evidence 引用 = 装饰），并被显式告警。
- **US-3（教授用户）**：作为综述方向探索者，我跑 `survey-plan <question>` 后能在终端看到 `Directions explored: 12 → eliminated: 8 → selected: 4` + elimination_log 路径，了解 explorer 在做什么。
- **US-4（建设者 / 评审）**：作为评审，跑完 sprint 后能从 `survey-eval --strict --json` 拿到 `gate_report.json` 结构化输出，并把 `artifact_paths` 喂给下游可视化或自动化（CI），不再靠"建设者声明 PASS"。
- **US-5（监护人 / 主脑）**：作为 epic 监督者，跑 `solar-harness status --epic <id>` 能立刻看到 5 个子 sprint 的 ready / blocked / dependency / capability 矩阵，知道阻塞在哪一层；如果某子 sprint 因 capability 缺失停住，能定位到具体 capability。
- **US-6（建设者）**：作为 builder，dispatch context 注入的 gate readiness 摘要可以告诉我"此 sprint 需要 O3 controversy_matrix gate 通过"，让我在写代码时主动检查而不是等评审打回。

## 约束 / Constraints

- **不重写主架构**：不修改 `coordinator.sh` / `autopilot.sh` / `dispatcher.sh` / `phase-state-machine.sh` / `solar-harness.sh` / `survey/__init__.py` 已有导出（S01 frozen 列表）。
- **不动 S03 frozen 实现**：S03 提交的 4 gate impl + explorer + runner_hook + global_pass 不修改公共 API，S04 只消费。
- **CLI attach-only**：所有 survey-* CLI 增强通过 formatter/view 层注入，不重写 `survey-eval` / `survey-review` / `survey-compile` / `survey-plan` 入口逻辑；状态判断仍走 S03 gate 输出。
- **包内规则**：CLI view 实现必须落在 `harness/lib/research/survey/cli/` 子包，避免污染主 CLI 命令空间。
- **status UI attach-only**：epic 子 sprint 状态展示通过 `solar-harness status --epic` 子命令新加，不修改既有 `status` 命令默认行为。
- **autopilot 注入只读 hint**：dispatch context 的 capability gate hint 必须 best-effort、失败不阻塞，符合"capability hint 不覆盖合约"intent rule。
- **纯函数 view 层**：所有 view 层格式化函数必须确定性（同输入恒同输出），不得引入 random / datetime.now / time.time / 网络 IO。
- **无 mock**：所有单测用 fixture JSON / 真实 dataclass 实例，禁止 `@mock.patch` / `MagicMock`。
- **模型默认 Sonnet**：所有节点 `preferred_model = sonnet`（GLM 1210 已踩 5 次）。

## 风险 / Risks

| 风险 | 影响 | 缓解 |
|------|------|------|
| S03 gate 输出 schema 微调 | S04 view 层字段错位 | 严格只引用 S03 dataclass + to_dict()，不假设字段；CI 在 S03 schema 变更时 fail-fast |
| autopilot dispatch context 注入路径过深 | 性能开销 | hint 只追加摘要 JSON 节 ≤ 2KB，不阻塞 dispatch |
| status UI 改动溢出到既有 `status` 命令 | 影响其它 sprint | 走 `--epic` 子命令，不动既有命令行为 |
| epic 子 sprint 阻塞原因展示与 events.jsonl 不一致 | 用户决策被误导 | 直接从 status.json + events.jsonl 实时计算，不缓存 |
| CLI 输出宽度溢出 | 终端可读性差 | 默认 80 列，超长走 `--json` |
| S03 builder 实际 schema 字段 ≠ planner spec | S04 view 编译 fail | S04 节点 prerequisites 强制 `S03:passed`；spec-ahead 时仅引用 design.md 字段名（不依赖具体值） |
| pane evidence 落地接入既有 evaluator | hook 冲突 | gate_report.json 写入约定路径 `runtime/survey-continue/<run>/gate_report.json`，evaluator 主动 read |

## 开放问题 / Open Questions

- Q1 — CLI 是否需要 `--format markdown/json/table` 三选项？默认 table。**Planner Lock**：默认 table；`--json` 已有约定；不加 markdown 选项（YAGNI）。
- Q2 — status UI `--epic` 是否需要 watch / tail 模式？**Planner Lock**：S04 不做 watch；future 工作。
- Q3 — autopilot dispatch hint 是否注入 builder pane 提示文本？**Planner Lock**：仅注入 dispatch.md context 节，不改 pane 命令文本。
- Q4 — gate_report.json 路径是否走 evidence_pack 索引？**Planner Lock**：写入 evidence_pack.gate_report_path 字段（S03 已 reserved），不另起新索引文件。
- Q5 — 装饰性 controversy matrix 检测是否在 view 层还是 gate 层？**Planner Lock**：检测逻辑在 S03 O3 gate（已在 S03 plan），view 层只展示 warning。
- Q6 — S03 未交付前 S04 builder 是否能动手？**Planner Lock**：禁止；task_graph 设 `dependency_policy.blocks_until: [S02:passed, S03:passed]`。
- Q7 — survey-plan 是否需要新增 `--show-eliminated` 标志？**Planner Lock**：不需要；默认输出 count + log 路径，详情用户自查 jsonl。

## 架构交接 / Planner Handoff

下游建设者（Builder Main）必须遵守以下交接：

| 项 | 交接内容 |
|----|---------|
| 入口模块 | `harness/lib/research/survey/cli/` 新建子包；不动 `survey/__init__.py` 现有导出 |
| 入口命令 | `survey-eval --strict` / `survey-review` / `survey-compile` / `survey-plan` / `solar-harness status --epic <id>` 五处 surfacing |
| 上游依赖 | S03 deliverables D1-D7（dataclass + 4 gate + explorer + aggregator + runner_hook）必须 passed；通过 `dependency_policy.blocks_until` 强制 |
| Frozen API | S01 列出的 5 frozen module 公共 API + 6 frozen file + S03 D1-D8 公共 dataclass 全部不可改 |
| 写范围 | 每节点 `write_scope` 严格互斥（见 task_graph.json）；不允许跨节点写同一文件 |
| 测试基准 | 每节点 ≥ 6 unit test；sprint 总 ≥ 35 unit test |
| 输出标准 | view 层全部纯函数（输入 dataclass / dict，输出 str / dict），无 IO 副作用 |
| 模型路由 | 全节点 `preferred_model=sonnet`，禁止 GLM 1210 系列 |
| Stop rules | 写 .ts/.js/.sh 文件 / 写网络 IO 代码 / 修改 frozen API / 用 @mock.patch / 输出含 datetime.now → fail |
| 父级追踪 | N6 join 仅 patch `children[3].orchestration_ui_ready=true`，schema_version + children 顺序长度不变 |
| 未闭环项 | 真正的 E2E 跑 survey-continue 用 sample run + strict tests 由 S05 完成；S04 只做 CLI surfacing + status UI + dispatch hint |
| 不可声称 | S04 不得声明 "epic complete" / "E2E verified" / "S05 ready" |
