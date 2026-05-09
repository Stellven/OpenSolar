# PRD — Solar Harness x Obsidian Wiki durable memory integration

**Source**: Codex PM research from user request + upstream repo `https://github.com/Ar9av/obsidian-wiki`
**Priority**: P1
**Lane**: delivery
**Handoff To**: planner
**Created**: 2026-05-07T21:06:02Z

## 背景 / Context

用户要把 `Ar9av/obsidian-wiki` 集成进 Solar Harness，让 Solar 的 sprint 产物、状态和长期知识能进入 Obsidian LLM Wiki。上游项目是 skill-based Obsidian knowledge framework：agent 读取 `.skills/` 指令，维护 vault 中的 `index.md`、`log.md`、`.manifest.json`、`_raw/`、`projects/`、`concepts/`、`entities/`、`skills/`、`references/`、`synthesis/`、`journal/` 等结构。

关键约束：上游 `setup.sh` 是交互式脚本，会询问 vault path、写 `~/.obsidian-wiki/config`，并把 `.skills/*` symlink 到多个 agent skill 目录。Solar 不能在自动化里直接跑交互安装，也不能覆盖用户真实 skill 目录或 vault。

## 用户问题 / Problem

Solar Harness 当前有 sprint 合约、计划、handoff、eval、events 和 HTTP status，但缺少一个安全、可复用、可查询的长期知识出口。用户希望通过 Obsidian Wiki 把 Solar 的工作结果沉淀为 durable memory，同时保持 Solar 自动化不被 Obsidian 或上游 setup 流程打断。

## 用户目标 / Goals

- 提供 `solar-harness wiki` 命令族，让用户可以非交互安装、检查状态、导出 sprint、生成 update/query 指令。
- 默认安全：不覆盖真实目录、不泄露 secrets、不要求真实用户 vault 参与测试。
- 保持 Solar Harness 主流程不变：wiki 集成是附加能力，不阻塞 coordinator、builder、evaluator。
- 让 agent 能读取 `_raw/solar-harness` 中的 sprint 原始材料，再用上游 `wiki-ingest/wiki-update/wiki-query` 技能沉淀知识。
- HTTP 状态面板能显示 Obsidian Wiki readiness，未配置时降级为 warn，而不是 fatal。

## 用户故事 / User Stories

- 作为 Solar 操作者，我可以运行 `solar-harness wiki install --vault <path>`，完成上游 repo、config、vault skeleton、skills symlink 的安全安装。
- 作为 Solar 操作者，我可以运行 `solar-harness wiki status --json`，让脚本/状态面板判断 wiki 是否 ready。
- 作为 Solar 操作者，我可以运行 `solar-harness wiki export-sprint <sid>`，把某个 sprint 的 contract/plan/handoff/eval/events 导出到 vault 的 `_raw/solar-harness/<sid>.md`。
- 作为 agent，我可以读取 `wiki update/query` 生成的 dispatch markdown，知道要对哪个 project 做增量更新或查询。
- 作为审判官，我可以用 temp vault 测试 install/status/export/update/query/safety，不污染真实用户环境。

## 功能需求 / Requirements

- `solar-harness wiki install --vault <path> [--repo <path>] [--refresh]`：非交互安装；默认 vendor clone 到 `~/.solar/harness/vendor/obsidian-wiki`；支持已有 repo；写 `~/.obsidian-wiki/config`。
- `solar-harness wiki status [--json]`：输出 repo/config/vault/skills readiness；JSON 需符合 schema。
- `solar-harness wiki export-sprint <sid> [--redact|--full]`：导出到 `$OBSIDIAN_VAULT_PATH/_raw/solar-harness/<sid>.md`；默认 redaction。
- `solar-harness wiki update [--project <path>] [--mode append|full]`：生成 agent-readable update 指令文件，不直接触碰 live tmux pane。
- `solar-harness wiki query "<question>" [--quick]`：生成 query 指令文件；空 query 必须拒绝。
- status server `/status` payload 增加 `obsidian_wiki` readiness；wiki 未配置时返回 ready=false/warn。
- 测试必须使用 `HARNESS_TEST=1`、temp vault、temp config、temp skill dirs。
- 文档必须有不少于 5 个例子。

## 验收标准 / Acceptance Criteria

- D1: `bash -n ~/.solar/harness/integrations/obsidian-wiki.sh ~/.solar/harness/solar-harness.sh` 通过。
- D2: install 在 temp vault 下创建 config、vault skeleton、安全 symlink。
- D3: status `--json` 是合法 JSON，包含 repo/config/vault/skills 字段。
- D4: export-sprint 能导出真实 sprint，包含 frontmatter、source list、redaction。
- D5: update/query 生成 agent-readable 指令文件，空 query 失败。
- D6: HTTP status server 响应包含 `obsidian_wiki` readiness。
- D7: symlink 安全测试证明不会覆盖真实目录。
- D8: docs 存在且至少 5 个使用示例。

## 非目标 / Non-Goals

- 不改写上游 `.skills/` 内容。
- 不自动打开或控制 Obsidian desktop app。
- 不默认全量导出 terminal transcript 或私密历史。
- 不引入 QMD/MCP 作为必需依赖。
- 不改变 Solar sprint 主状态机语义。

## 约束 / Constraints

- Shell + Python stdlib 优先，避免新依赖。
- 上游 `setup.sh` 只能作为行为参考，不能作为自动化直接执行路径。
- 所有真实用户目录写入必须可解释、可重复、可拒绝覆盖。
- `HARNESS_TEST=1` 下不得写真实 `~/.obsidian-wiki/config`、真实 vault、真实 skill 目录。
- Lab builders 与 main builder 不能互相覆盖；main builder 负责集成合并，不重写 lab slice。

## 风险 / Risks

- 上游 repo clone 失败会导致 skill symlink 缺失，需要 status 清晰报告并允许后续 `--refresh`。
- 多 builder 已经并行写了同名/重叠功能，main builder 需要做集成审查而不是盲目重写。
- export 默认若包含 events/contract 原文，可能泄露 token，必须默认 redaction。
- status-server 集成若 import 或 config 失败，不得影响 `/healthz`。

## 开放问题 / Open Questions

- 默认 vault 路径是否应由用户显式提供，还是允许 Solar 推荐 `~/Obsidian/Solar Wiki`。
- `wiki update/query` 后是否需要 coordinator 后续自动派 agent 处理 dispatch 文件，当前版本先只生成指令文件。
- 是否将 sprint export 后自动触发上游 `wiki-ingest`，当前版本不自动触发以避免不可控 agent 行为。

## 架构交接 / Planner Handoff

现有 planner 已产出 `sprint-20260507-obsidian-wiki.plan.md`，lab builders 已按 S1-S5 交付多个 slice。下一步不是重新规划，而是要求 main builder：

- 读取本 PRD、contract、design、plan 和四个 lab handoff。
- 集成已有 `integrations/obsidian-wiki*.sh`、`solar-harness.sh` routing、status-server、schema、docs、tests。
- 运行 D1-D8 验证命令。
- 修复冲突和缺口后写 `sprint-20260507-obsidian-wiki.handoff.md`，再将 status 推进到 `reviewing`。
