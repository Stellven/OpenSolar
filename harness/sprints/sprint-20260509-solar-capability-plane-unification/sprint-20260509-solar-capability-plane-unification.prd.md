# PRD — Solar Capability Plane Unification

**Source**: codex-manual-2026-05-09  
**Priority**: P0  
**Lane**: reliability  
**Handoff To**: builder_main  
**Created**: 2026-05-09T00:30:27Z

## 背景 / Context

Solar 现在已经形成三层分裂：`/Users/sihaoli/Solar` 保存原始架构、skills、agents、rules；`/Users/sihaoli/.solar` 保存运行数据和数据库；`/Users/sihaoli/.solar/harness` 是真实 live orchestration。`solar-harness.sh` 又演化成 2790 行总控脚本，直接分发到 coordinator、pane launcher、wiki、mirage、qmd、symphony、autopilot、Everything Claude Code 等子系统。

当前最大缺口不是能力不存在，而是能力没有统一进入执行面。Builder pane 被派发时通常只收到 `读取并执行 <dispatch.md>`，不会自动知道可用 skills、MCP 状态、KB context，也不会知道任务应该优先使用哪些 Solar 原生 skill。状态面板也无法回答“这个 pane 实际可用什么”。

## 用户问题 / Problem

1. `solar-harness` 和 `Solar` 已经事实分离，Solar 原架构里的 38 个 skills 没有被系统性提取、注册、注入。
2. `~/.agents/skills`、`~/.claude/skills`、`~/.codex/skills`、`~/Solar/skills`、vendor skills 多套并存，缺少统一 inventory/doctor。
3. 第三方模型 pane 使用 empty MCP，主 builder 使用 full tools；用户看不到每个 pane 实际 tool/MCP/skill 能力。
4. dispatch 前没有自动解析任务需要的 skill 和 KB context，导致 builder 重复摸索或完全不用知识库。
5. `solar-harness.sh` 内部存在重复 `case` 分支和不可达代码，缺少依赖图命令，维护成本持续上升。

## 用户目标 / Goals

- 用户运行 `solar-harness skills inventory` 可以看到全量 skills 来源、数量、冲突、可用性。
- 用户运行 `solar-harness skills doctor` 可以知道每个 pane 真实可用的 skill/MCP/context。
- coordinator 每次派发前自动把任务相关 skills 和 KB context 注入 dispatch 文件，不再只发裸指令。
- status UI 显示每个 pane 的 persona、model、MCP 模式、top skills、KB context 状态。
- 用户运行 `solar-harness graph` 可以输出 harness 依赖图，覆盖代码、skills、MCP、Markdown/schema/vendor。
- 从 `/Users/sihaoli/Solar` 原架构提取可复用 skills，并以安全方式纳入 harness inventory，不覆盖用户现有 skill。

## 用户故事 / User Stories

- 作为用户，我想知道 pane0/pane1/pane2/pane3 分别有什么能力，这样不用猜它们为什么不会用某个 skill。
- 作为 builder，我收到 dispatch 时就能看到“本任务推荐 skills + KB hits + MCP/tool 限制”，不用再主动问人。
- 作为 evaluator，我能验收 dispatch 是否真的带上了 skill/context，而不是只看到 status 里写“已集成”。
- 作为维护者，我能用 `solar-harness graph --format mermaid` 看清 `solar-harness.sh` 指向哪些脚本、skills、MCP、MD。
- 作为系统 owner，我能看到 Solar 原始 skills 哪些可直接用、哪些冲突、哪些需要迁移。

## 功能需求 / Requirements

- R1: 新增 `solar-harness skills inventory [--json|--markdown]`，扫描 `~/.agents/skills`、`~/.claude/skills`、`~/.codex/skills`、`~/Solar/skills`、`~/.solar/harness/vendor/*`。
- R2: 新增 `solar-harness skills doctor [--json]`，输出各 skill root 可读性、重复 skill、缺失 SKILL.md、vendor pending、Solar 原 skill 可迁移性。
- R3: 新增 `solar-harness skills inject --sid <sid> --instruction-file <path>`，基于 PRD/contract/dispatch 文本选择 top skills，并追加 `<solar-skills-context>` 与 `<solar-knowledge-context>` block。
- R4: 修改 `coordinator.sh dispatch_to_pane()`，在发送短指令前对 instruction file 执行一次 idempotent inject；失败 fail-open 但必须 emit warning event。
- R5: 新增 `solar-harness graph [--json|--markdown|--format mermaid]`，自动生成 live dependency graph，不依赖手写报告。
- R6: 清理 `solar-harness.sh` 中重复/不可达 `mirage`、`data-plane` case 分支，保持 CLI 行为兼容。
- R7: 修改 `pane-launcher.sh` 或 persona banner，启动时显示 persona、model、MCP mode、skill root summary、KB context mode。
- R8: 修改 status-server UI/API，新增 pane capability card，展示每个 pane 实际可用 skill/MCP/context。
- R9: 提取 `/Users/sihaoli/Solar/skills` 的 38 个原生 skills，写入 inventory，并标注 `usable | conflict | stale | needs_migration`。
- R10: 所有新增命令必须有 tests，且不能打印 token、API key、secret。

## 验收标准 / Acceptance Criteria

- A1: `solar-harness skills inventory --json` 返回 JSON，包含至少 5 个 source root、总数、重复项、Solar 原生 38 skills。
- A2: `solar-harness skills doctor --json` 返回 overall 状态，并列出 pane capability，包括 main builder full tools、lab builder empty MCP。
- A3: `solar-harness skills inject --sid <test> --instruction-file <file>` 对同一文件重复运行不会重复插入 block。
- A4: coordinator 真派发路径会调用 inject；测试能证明 dispatch 文件包含 `<solar-skills-context>` 和 `<solar-knowledge-context>`。
- A5: `solar-harness graph --json` 包含 `solar-harness.sh -> pane-launcher.sh -> persona-config.sh`、wiki、mirage、symphony、autopilot、vendor 节点。
- A6: `solar-harness graph --format mermaid` 输出合法 Mermaid graph，不需要人工维护。
- A7: `solar-harness.sh` 不再有重复 top-level `mirage)` 或 `data-plane)` case。
- A8: status UI `/status` 或 `/api/status` 能展示 pane skills/MCP/context summary。
- A9: `pane-launcher.sh --print-config lab-builder` 能显示 MCP empty mode；main builder 显示 full tools。
- A10: 测试覆盖新增命令和注入逻辑；bash/python 静态检查通过。

## 非目标 / Non-Goals

- 不重写 coordinator。
- 不强制安装 Everything Claude Code live hooks。
- 不把所有 skills 自动 symlink 到所有 runtime。
- 不改变现有模型路由策略。
- 不把第三方网关 pane 改成 full MCP。
- 不引入外部网络依赖。

## 约束 / Constraints

- 必须 fail-open：skill/context 注入失败不能阻断 P0 派发，但必须写 warn event。
- 必须 idempotent：同一个 dispatch 文件多次 inject 不得重复 block。
- 必须保密：输出中不得包含 `ZHIPU_AUTH_TOKEN`、`ANTHROPIC_AUTH_TOKEN`、`DEEPSEEK_API_KEY`。
- 必须兼容当前 `solar-harness` CLI。
- 状态 UI 不能显示千行原始 JSON；必须是用户可读 summary。

## 风险 / Risks

- RISK1: 直接改 `dispatch_to_pane()` 可能影响所有派发路径。缓解：只在发送前做小型 wrapper，失败 fail-open。
- RISK2: skill 数量过大，inventory 慢。缓解：缓存 summary 到 `state/skills-inventory.json`，doctor 可快速读缓存。
- RISK3: skill 推荐误判。缓解：推荐只作为 context，不强制 builder 使用。
- RISK4: 清理重复 case 误删行为。缓解：先用 graph/test 捕获 CLI 分支，再做最小删除。

## 开放问题 / Open Questions

- OQ1: Solar 原生 skill 是否要复制到 `~/.claude/skills`，还是只进入 inventory？默认只 inventory，不覆盖。
- OQ2: status UI 展示 top skills 几个？默认 6 个。
- OQ3: KB context 命中为空时是否插入空 block？默认插入 degraded/empty summary，便于 evaluator 验收。

## 架构交接 / Planner Handoff

直接进入 builder_main。实现建议 4 个切片：

- S1 `lib/solar_skills.py` + CLI `skills inventory/doctor/inject`。
- S2 coordinator dispatch 注入 + tests。
- S3 `lib/harness_graph.py` + CLI `graph` + 重复 case 清理。
- S4 pane banner/status-server capability UI + Solar 原 skills 提取报告。
