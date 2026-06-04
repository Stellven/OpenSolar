# PRD: 需求拆解与追踪矩阵

epic_id: `epic-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything`
sprint_id: `sprint-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything-s01-requirements`
slice: `requirements`
intent_id: `intent-20260526-185205-1d60549790` (复用 epic raw_intent，未重新捕获)
priority: `P0`
handoff_to: `planner`

## 用户原始需求

在 Mac mini 的 Claude Code 环境安装并集成 Lum1104/Understand-Anything 插件。要求只做集成不开发插件：运行 `/plugin marketplace add Lum1104/Understand-Anything` 和 `/plugin install understand-anything`；在 `/Users/lisihao/Solar` 上执行 `/understand --language zh` 生成 `.understand-anything/knowledge-graph.json`；验证 `/understand-dashboard`、`/understand-chat`、`/understand-diff`、`/understand-explain`、`/understand-onboard`、`/understand-domain`、`/understand-knowledge` 的可用性或明确阻塞；形成 handoff、安装日志、知识图路径、dashboard 访问证据，并接入 solar-harness 证据报告。不要打印 secrets，不要开发 fork，不要破坏现有 Claude Code 配置。

## 背景 / Context

- 当前 Mac mini (`lisihaodeMac-mini.local`, macOS arm64, bash 5.3.9, 4-pane Solar Harness 已在运行) 已经稳定承担 PM/Planner/Builder/Evaluator/Architect 协同；Claude Code 是这套 harness 的实际 IDE 入口。
- Lum1104/Understand-Anything 是社区插件，提供 `/understand` 系列命令，目的是把任意 repo 转成知识图 + 多视角 UI（dashboard/chat/diff/explain/onboard/domain/knowledge）。从 system-reminder 看，Claude Code 端已经识别这些命令的 skill 名称（`understand-anything:*`），但本机是否已经安装 marketplace + plugin 还未验证。
- `/Users/lisihao/Solar` 是 Solar 治理中枢的工作目录，是用户期望第一份知识图的目标 repo。
- 现状是大需求只下了一个 epic，没有 PM 切片层的可验收拆解；如果直接派 Planner/Builder，会出现“跳过 PRD schema 必填项 + 验证 7 条命令时无验收边界”的情况，因此用户用 PM persona 发起 S01 切片。

## 用户问题 / Problem

- 用户没有把这个集成任务拆成可验证的子任务、没有写明“安装失败/dashboard 起不来/某个命令缺依赖”等阻塞分支应该如何收口。
- 验收标准模糊：7 个 `/understand-*` 命令每个的“可用”意味着什么（能列出？能产出文件？能跑完一次？dashboard 必须可访问？）没有定义。
- 安全边界没固化：用户已经明确“不打印 secrets、不开发 fork、不破坏现有 Claude Code 配置”，但没有沉淀成可被 evaluator 拦截的 stop_rules。
- 缺一份 epic → 子 sprint 的 traceability 映射，导致下游 S02/S03/S04/S05 没法 join 父级 acceptance。
- 缺“Solar Harness 证据接入路径”：用户要求接入证据报告，但是接到哪个 status.json / accepted artifacts / harness handoff 没有定义。

## 用户故事 / User Stories

- **US-01 (PM 视角)**：作为 Solar 主用户，我希望本切片产出一份明确的需求拆解 + traceability，让我在批准 Planner/Builder 之前能一眼看到每个 outcome 的验收和阻塞收口方式。
  - 验收：本 PRD 包含 ≥5 个标号 outcome，每个 outcome 有 acceptance / non-goals / blocker fallback。
- **US-02 (Planner 视角)**：作为下游 Planner，我希望本切片明确告诉我 S02 架构切片要消费哪些 input、要回填什么字段，避免我重新猜 epic 意图。
  - 验收：本 PRD `## 架构交接 / Planner Handoff` 章节列出 inputs / outputs / 不在 S01 范围内但必须 S02 处理的项。
- **US-03 (Builder 视角)**：作为下游 Builder，我希望知道哪些命令是“只读集成”、哪些是“需要在 Solar repo 上写文件”，避免在错误目录污染。
  - 验收：本 PRD `## 约束 / Constraints` 明确列出可写目录、禁止目录、禁止行为。
- **US-04 (Evaluator 视角)**：作为 Evaluator，我希望从 PRD 直接抽出 stop_rules，让我可以判定 sprint passed / failed。
  - 验收：`## 范围` 中 stop_rules 完整可程序化。
- **US-05 (运维/安全视角)**：作为安全约束维护者，我希望本 sprint 留下证据证明没有打印 secrets、没有破坏 `.claude/settings.json`。
  - 验收：`## 风险 / Risks` 提到的“配置回滚证据”被列入交付物。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything.epic.md`、`epic-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。
- stop_rules:
  - 缺 `.task_graph.json` 不得派 builder。
  - 缺可复现验证不得标记 passed。
  - 发现 scope 冲突必须回写父级 traceability。
  - PRD 缺任何 7 个必需 section 不得状态推进到 planner。

## 验收标准

- **A1 — 五个 outcome 全部带验收与边界**
  - O1 安装路径已经明确：marketplace add + plugin install + `/plugin list` 自检命令、失败回退方式。
  - O2 知识图生成：`/understand --language zh` 在 `/Users/lisihao/Solar` 产出 `.understand-anything/knowledge-graph.json`，文件大小 > 0 且为合法 JSON。
  - O3 七个 `/understand-*` 命令每个有独立验收（见 ## 架构交接 表 “Command Matrix”）。
  - O4 证据接入：安装日志、`knowledge-graph.json` 路径、dashboard 访问证据写入 `~/.solar/harness/sprints/<sid>.status.json` 的 `accepted_artifacts` 或独立 handoff.md。
  - O5 安全边界：`.claude/settings.json` / `.claude/settings.local.json` 在 sprint 开始/结束的 hash 一致；安装日志不含 token / API key / OAuth code。
- **A2 — Builder 工作不能直接派**
  - 明确哪些步骤需要 Planner 重新设计 task_graph（例如 dashboard 启动卡死时的回退）。
- **A3 — Traceability map**
  - 产出父 epic 5 个 child sprint 到本 S01 acceptance 的映射，覆盖 architecture / core-runtime / orchestration-ui / verification-release。

## 非目标 / Non-Goals

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。
- 不 fork、不修改 Lum1104/Understand-Anything 上游源代码。
- 不调整 Mac mini Claude Code 全局 settings.json 中已有的 hooks / permissions。
- 不在本切片内运行 dashboard（dashboard 可达性验证留给 S04 orchestration-ui）。

## 约束 / Constraints

- **环境**：macOS arm64 (lisihaodeMac-mini.local)，bash 5.3.9 (aarch64) at `/opt/homebrew/bin/bash`，Solar Harness 4 pane 已运行；本机 Claude Code 已存在 `understand-anything:*` skill 名空间（来自 system-reminder skill 列表）。
- **路径**：所有产出必须在 `~/.solar/harness/sprints/` 或 `/Users/lisihao/Solar/.understand-anything/`；不放 `/tmp`；不放用户 home 根。
- **安全**：禁止打印 secrets / OAuth / tokens；安装命令产生的日志必须 redact 后再写进 sprint artifacts。
- **不破坏配置**：禁止覆盖 `~/.claude/settings.json`、`~/.claude/settings.local.json`、`/Users/lisihao/Solar/.claude/*` 的现有键；若插件安装会自动写入新键，必须在 PRD/handoff 留 diff 证据。
- **网络**：marketplace 添加可能要 GitHub 网络；如果网络受限必须在 PRD 留 fallback（手动 git clone Lum1104/Understand-Anything）。
- **资源**：dashboard 验证可能占用端口；S01 不分配端口，S04 决定。
- **角色边界**：PM 不写实现代码、不动 sprint status 到 `implementation`、不跳过 PRD schema。
- **API 兼容**：现有 Solar Harness CLI (`solar-harness context inject`、`session evaluate`、`intent-gateway capture`) 必须照常工作；本切片不引入 harness CLI 变更。

## 风险 / Risks

| 风险 | 影响 | 缓解 / Owner |
| --- | --- | --- |
| Lum1104/Understand-Anything marketplace 未公开或源失效 | 整个 epic 阻塞 | S02 增加 “fallback: 手动 git clone + local plugin install” 路径 / Planner |
| `/understand` 在 `/Users/lisihao/Solar` 上跑出巨大知识图，磁盘/内存爆 | Solar 工作目录损坏 | 在 S03 增加 sample-run + size cap；S01 必须把 “磁盘检查” 列为 pre-flight / Planner |
| 插件安装写入 `~/.claude/settings.json` 新键 | 破坏现有 hook 配置 | S01 要求 hash 前后对比；diff 必须人审 / Evaluator |
| dashboard 起在固定端口与现有服务冲突 | 用户其它服务掉线 | dashboard 必须 dry-run / 可换端口；S04 处理 / Builder |
| 7 个 `/understand-*` 中某条命令依赖未发布版本 | 部分 outcome 阻塞 | PRD 在 Command Matrix 中允许 “blocked-with-evidence” 作为 acceptable terminal state / PM |
| 安装日志含 GitHub OAuth code | 泄露 secrets | redact 必须在写盘前，evaluator 抽样校验 / Evaluator |
| 跨 sprint 状态漂移：S02 ~ S05 在 S01 还没 passed 时被启动 | scope 冲突 | traceability.json 中下游 `status=queued` 不许被自动激活；chain-watcher 必须 honor `depends_on` |

## 开放问题 / Open Questions

- **OQ-01**：marketplace `Lum1104/Understand-Anything` 是直接 GitHub repo 名还是已发布的 Claude Code marketplace 标识？如果是 GitHub repo，需要 confirm token / 网络要求。→ 留给 S02 Architecture 调研。
- **OQ-02**：`/understand --language zh` 是否依赖外部 LLM API？如果调用 Anthropic API，需要计费/上限策略。→ 留给 S03 Core-Runtime。
- **OQ-03**：`/understand-dashboard` 默认端口、是否本地静态站点 vs HTTP server？→ S04 必须探明再写实施任务。
- **OQ-04**：`/understand-onboard`、`/understand-explain` 等命令的输出位置是否覆盖 Solar repo 内已有 doc？需要 dry-run + diff 评估。→ S04。
- **OQ-05**：本机 Claude Code 是否已通过 `~/.claude/plugins/...` 安装过 Understand-Anything 的旧版本？需要 inventory 检查。→ S02 启动前 30 秒 pre-flight。
- **OQ-06**：证据接入是写到 `status.json.accepted_artifacts`，还是用新引入的 `solar-harness handoff` 字段？→ S05 verification 之前由 Planner 决定，但 S01 必须留 placeholder。
- **OQ-07**：dashboard 访问证据是截图还是 HTML 转 PDF？→ S04/S05 协调。

## 交付物

- `sprint-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything-s01-requirements.prd.md` (本文件)
- `sprint-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything-s01-requirements.prd.html` (人读 HTML artifact，由 PM 写)
- `sprint-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything-s01-requirements.design.md` (由 Planner 在 S02 完成)
- `sprint-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything-s01-requirements.plan.md` (由 Planner)
- `sprint-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything-s01-requirements.task_graph.json` (由 Planner)
- `sprint-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything-s01-requirements.handoff.md` (由 Planner)
- `sprint-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything-s01-requirements.eval.md` 或 `.eval.json` (由 Evaluator)

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD（含 5 个 outcome、stop_rules、约束/风险/开放问题）。
- `epic-20260526-...understand-anything.epic.md`、`.traceability.json`、`.task_graph.json`。
- 复用 intent_id：`intent-20260526-185205-1d60549790`。
- 用户原始需求文本（见 `## 用户原始需求`）。
- Mac mini 现有 Solar Harness 状态：`~/.solar/STATE.md`、`~/.solar/SPRINT-STATUS-20260502.md`、4 pane 架构 `~/.solar/docs/4-pane-architecture.md`。
- system-reminder 中已识别的 7 个 `understand-anything:*` skill 名称（dashboard / domain / knowledge / diff / explain / onboard / chat），可作为命令存在性的弱证据。

### Outputs Planner 必须产出

- `*.design.md`：明确 S02-S05 之间的接口契约（特别是 `knowledge-graph.json` schema 在 S03 产出后 S04 怎么消费）。
- `*.plan.md`：把每个 outcome 拆成 ≤8 个 builder task。
- `*.task_graph.json`：节点 = builder task；边 = depends_on；含 “pre-flight” 节点（settings.json hash、磁盘、网络）。
- `*.handoff.md`：填写每个 outcome 的 owner、stop_rule 引用、accepted_artifacts 路径。

### Command Matrix (Planner 必须落地为子任务)

| 命令 | S01 acceptance（PM 切片定义） | 关键阻塞情形 | 归属 S* |
| --- | --- | --- | --- |
| `/plugin marketplace add Lum1104/Understand-Anything` | 命令返回 0，`/plugin list` 显示 marketplace 已添加；安装日志（redact 后）写入 sprint artifact | marketplace ID 无效 → 进入 OQ-01 fallback | S02 + S03 |
| `/plugin install understand-anything` | `~/.claude/plugins/...` 含该插件目录，version 字符串可读 | 网络/权限失败 → 留 evidence 后置为 blocked | S03 |
| `/understand --language zh` (在 `/Users/lisihao/Solar`) | `.understand-anything/knowledge-graph.json` 存在，size > 0，`jq` 可解析 | 占用过多磁盘/超时 → 用 sample directory 重跑 | S03 |
| `/understand-dashboard` | dashboard 可启动 + 至少一次访问截图或 curl 200 证据 | 端口冲突 / 缺依赖 → 记录 blocked-with-evidence | S04 |
| `/understand-chat` | 至少一次问答 round-trip 成功，输出可读 | LLM 配额限制 → 记 evidence 后 blocked | S04 |
| `/understand-diff` | 对 Solar repo 一个 commit 跑 diff 视图，输出文件存在 | 无 git history → 选取已知 commit | S04 |
| `/understand-explain` | 对一个目标文件跑 explain，输出在 `.understand-anything/` 或 stdout 可截取 | 文件过大 → 选小文件 | S04 |
| `/understand-onboard` | 生成 onboarding 文档至少一段，写入仓库（dry-run 优先） | 覆盖已有 README → 必须 dry-run 选项 | S04 |
| `/understand-domain` | 生成 domain graph 文件 | 缺业务逻辑 → 选 sub-package | S04 |
| `/understand-knowledge` | 生成 knowledge wiki / cluster | 重算与 `/understand` 冲突 → 串行 | S04 |

### Traceability Map (S01 → 其它子 sprint)

| 本切片 outcome | 下游 sprint | 下游必须消费的 acceptance |
| --- | --- | --- |
| O1 安装路径 + log | S02 architecture, S03 core-runtime | 把 marketplace fallback、`.claude/settings.json` diff 流程写进设计 |
| O2 知识图生成 | S03 core-runtime | 落地 sample-size guard + `jq` 验证 |
| O3 七命令矩阵 | S04 orchestration-ui | 每条命令实现 + dashboard 起停 |
| O4 证据接入 | S05 verification-release | accepted_artifacts / handoff / status.json 字段 |
| O5 安全边界 | S05 verification-release | settings hash 比对 + secret-scan |

### 不在 S01 范围、必须 S02+ 处理

- dashboard 端口策略 / 真实端口表 → S04。
- LLM 调用费用估算 + 配额开关 → S03。
- 真实运行 `/understand-*` 全套 → S04/S05。
- 写 evaluator 自动校验脚本 → S05。
- 写 builder 实际 shell 步骤 → S02 设计后 S03/S04 builder 实施。

### Knowledge Context

Knowledge Context: solar-harness context inject used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中；ATLAS / Everything Claude Code / Solar-Harness Runtime capabilities injected)。

### Harness Modules Used

Harness Modules Used: harness-knowledge (context inject), harness-intent (intent reuse, no re-capture).
