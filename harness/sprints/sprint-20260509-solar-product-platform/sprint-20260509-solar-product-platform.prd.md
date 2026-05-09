# PRD — Solar Product Platform Unification

**Source**: contract `sprint-20260509-solar-product-platform`
**Priority**: P0
**Lane**: product-platform
**Handoff To**: planner
**Created**: 2026-05-09T03:05:00Z

## 背景 / Context

Solar 当前是分散组合体: Solar 主脑 + solar-harness 运行时 + ~/.agents/skills 野生技能 + ~/Knowledge 知识库 + QMD 索引 + Mirage VFS + MinerU PDF 抽取 + Solar DB 状态 + Cortex 证据库 + 多份 hook/script。各部分能跑但不构成可分发的产品: 没有干净的安装路径, 没有统一的快照/回滚, 没有秘密扫描, Skill 没有发布/评测/晋级流程, 新插件接入靠口口相传。当前部署只能在昊哥本机绑定，无法被他人下载安装、升级、自演化。

姚顺雨在 OpenAI 关于 "生成新世界的系统" 的访谈强调: 真正的 agent 系统需要可组合、可治理、可演化的能力底座，不是 prompt 拼接。Solar 也到了从手工艺过渡到产品平台的拐点。

## 用户问题 / Problem

P1 — **不能干净安装**: 没有 installer 脚本, 新人 (包括 monkey-test 容器) 无法在干净环境里搭起最小可用的 Solar。配置需要手工编辑十几个文件，出错点散落在 PATH/.zshrc/launchd/.solar/config/.claude/CLAUDE.md/skill 软链。

P2 — **秘密泄露风险**: API key/token 散落在 .env、shell history、~/.solar/config、launchd plist。无 gitleaks/secret scan，没有清晰的"已配置/未配置"展示，UI 直接渲染明文是历史遗留。

P3 — **Skill 治理空白**: Solar 已经有几十个 skill (Superpowers, gstack, solar-native, agent skills)，但没有 registry、没有版本、没有 eval pack、没有 canary/promote/rollback、没有指标。Skill 是当前能力扩展的主路径，必须升级为一等公民。

P4 — **存储职责混乱**: _raw 既当 staging 又当源、Obsidian 引用断裂、PDF 在 _raw 与 papers 间漂移、QMD index 跟实际源不一致、Drive 偶尔挂载偶尔降级、MinerU 占用主路径阻塞用户 shell。

P5 — **扩展框架缺失**: Mirage、QMD MCP、Symphony、everything-claude-code、Mermaid、SkillRetriever 都被硬塞进 Solar 主进程，没有 plugin manifest, 不知道谁能写哪条路径、谁需要 idle 限流、谁有 eval pack。

P6 — **控制面割裂**: 任务状态在 status.json + events.jsonl + Solar DB + tmux pane title + handoff/eval 文档之间漂移，pane lease 不存在，pane 容易被偷，autopilot 修复有 false positive (上次 sprint 误判 pane_busy 为 dispatch_failed 重置 status 5 次)。

P7 — **没有自演化**: 任务失败、eval 低分、新 skill candidate 无法被自动挖掘+提议+实验+回滚，全部走"昊哥手工开 sprint"的瓶颈。

## 用户目标 / Goals

G1. **可分发**: 任意干净 macOS / Linux 容器可以一条命令拉取 Solar 安装包，按向导填配置就能跑通最小可用 (planner pane + builder pane + harness)。
G2. **可升级 / 可回滚**: 新版本不会覆盖用户配置和数据；任何破坏性变更前必有 snapshot；不满意能 dry-run 回滚到指定快照。
G3. **秘密安全**: 所有 secret 集中收口；CI / git push / release 包前必跑 secret scan；UI 永不渲染明文。
G4. **Skill 是一等公民**: Skill 进入 registry，有 metric/eval/canary/promote/rollback；稳定 skill 自动同步到 Claude/Codex/agents；候选 skill 不污染默认调用。
G5. **统一存储**: `_sources` 是源, `_raw` 是 staging, Obsidian 是人可读, QMD 是索引, MinerU 是后台抽取, Solar DB 是结构化状态。Mirage 是统一访问入口。Drive 仅作冷备/可选。
G6. **可扩展**: 新开源工具 (Symphony / Everything-Claude-Code / Mermaid / Phoenix / Linear / 新 MCP) 通过 manifest 接入，声明能力/数据访问/命令/idle 安全/eval pack/rollback。
G7. **控制面收敛**: 一份权威 state DB；任务全生命周期 (PRD→Design→Plan→Dispatch→Build→Eval→KB→Closeout) 用状态机表达；pane lease 防偷；autopilot 修复 stall。
G8. **自演化**: 事件 → 失败聚类 → 改进候选 → 实验 → 评测 → 晋级或回滚；可观测、可审计。

## 用户故事 / User Stories

US-1 (新装): 一位新用户拿到 Solar 安装包 → 在 macOS 终端跑 `solar install` → 向导问 "用哪个模型 provider / 你的 vault 在哪 / 是否启用 Drive / API key 写入哪个 keychain" → 安装结束跑 `solar doctor` 全绿 → 跑 `solar` 进入 Solar 主脑。

US-2 (升级): 用户在 v0.4 → v0.5 升级 → installer 自动 snapshot 当前状态 → 应用差异 → 跑 smoke test → 失败时 `solar restore --dry-run` 列出会还原的文件 → 用户确认后真实 restore。

US-3 (秘密安全): 开发者 push 代码 → pre-push hook 跑 gitleaks → 拒绝任何泄露 secret 的提交。release 包构建前 audit 任何 plaintext secret 残留。Status UI 显示 "Drive: configured ✅" 而不是 token 明文。

US-4 (Skill 演化): Solar 跑了一周生成的实验 skill 在 5 个任务里 eval 高分 → 自动提到 candidate 区 → 跑 24 小时 canary → 通过指标门槛 → 自动晋级到 stable → 同步到 Claude/Codex/agents → 出问题 `solar skills rollback <id>` 即时回滚。

US-5 (PDF 抽取): 用户把 PDF 丢进 `_raw/file-uploads` → MinerU idle 抽取 → 写到 `_sources/papers/<hash>/` → Obsidian 自动生成 reference page → QMD 索引 → 用户主 shell 不被 OOM 阻塞。

US-6 (插件扩展): 开发者要把 Mermaid 接进 Solar → 写 `plugins/mermaid/manifest.yaml` → 声明 capability=diagram_render, data_access=read:_sources, commands=mermaid_render, idle_safety=light, eval_pack=mermaid_v1 → `solar plugins install` → 跑 eval → 通过则注册到 capability registry。

US-7 (控制面): 一个 sprint 卡在 dispatch_failed → autopilot 检测到 pane busy 不是 pane dead → 等 lease 释放而不是重置 status → planner 不被骚扰。

US-8 (自演化): Solar DB 累计 200 次 task → failure_miner 聚类出 "deepseek-r1 在长上下文 > 80K 时 ROC 下降" → 自动建实验切换到 gemini-2.5-pro → 验证后 promotion gate 通过 → 路由策略升级。

## 功能需求 / Requirements

FR-0 Snapshot & Restore — `solar-harness product snapshot|restore|verify`，覆盖 ~/.solar、~/.solar/harness、~/.claude/core/solar-farm 关键路径、skill registry、config 路径。manifest 含 SHA256。secret 默认不进 plaintext。restore 必须支持 --dry-run。

FR-1 Product Distribution Foundation — installer/install.sh、upgrade.sh、doctor.sh、restore.sh；config/defaults.yaml 与 .env.example；.gitignore + gitleaks.toml；docker/Dockerfile + docker/smoke-test.sh。安装向导收集 model provider、vault 路径、QMD/Drive 选项、secret 存放策略。upgrade 不覆盖用户 config/data/secrets。clean container install 跑 smoke 全绿。

FR-2 Skill Platform — skills/builtins/、skills/registry.yaml、lib/solar_skills.py、lib/skill_metrics.py、lib/skill_export.py、evals/skills/。`solar-harness skills inventory|doctor|export|eval|promote|rollback`。stable skill 安全导出/软链到 Claude/Codex/agents。candidate/canary 不进默认注入。每个 stable skill 有 eval pack 和最低分门槛。skill 调用产生 events + metrics。

FR-3 Unified Storage — config/storage.solar.yaml；lib/source_manifest.py、lib/solar_mirage.py、lib/qmd_adapter.py、lib/mineru_extract.py。_raw 仅 staging；canonical 在 _sources。PDF 移到 _sources/papers 并附 manifest/provenance；Mirage 暴露 /knowledge /raw /sources /papers /qmd /solar-db /cortex /sprints 与可选 /drive。MinerU 作为后台 idle 处理器。Drive 仅 mirror/cold backup，未配凭据时不能伪 ok。

FR-4 Extension Framework — plugins/<id>/manifest.yaml；schemas/plugin.schema.json + capability.schema.json；lib/capability_registry.py、lib/plugin_loader.py。新开源集成必须声明 capability/data access/commands/idle safety/eval packs/rollback。Obsidian/QMD/MinerU/Mirage/Mermaid/Symphony/Everything-Claude-Code 全部以 plugin 形式表达。`solar-harness integrations status --json` 输出 basic usable / default usable / closed loop / dead end 四级。任何 plugin 不得越权写非声明范围。

FR-5 Evolution Engine — lib/evolution_engine.py、lib/failure_miner.py、lib/eval_runner.py；evals/packs/、experiments/<id>/hypothesis.md。事件与任务结果产出 capability scorecard。失败聚类成改进候选并附证据。实验有 before/after 指标和回滚路径。promotion 必须通过 eval + 回归测试。降级时自动 demote canary/candidate。

FR-6 Control Plane — schemas/task-lifecycle.schema.json；lib/solar_state_db.py、lib/task_queue.py、lib/pane_lease.py、lib/autopilot.py。state DB 是任务、分配、租约、事件、artifact、能力的唯一权威。生命周期 PRD→Design→Plan→Dispatch→Build→Eval→KB→Closeout 状态机化。pane lease 阻止 pane stealing。autopilot 处理 handoff stall、eval stall、dispatch backlog、hook failure。重活队列支持 rate limit/retry/checkpoint/stale cleanup。

FR-7 Container Validation — Dockerfile 用受限用户、不带任何明文 secret；smoke-test.sh 在容器内跑 install→config wizard (with fake keys)→doctor→start harness→spawn planner pane→spawn builder pane→运行 1 个内置 skill→关闭。所有断点必须可观测。

FR-8 Secret Scan — gitleaks 配置 + pre-commit/pre-push hook + release 前 audit；status UI 仅 configured / missing；secret 写入 keychain 或独立 vault 路径，不入 git。

## 验收标准 / Acceptance Criteria

A1 G0 Snapshot Pass — `solar-harness product snapshot` 产出 manifest，包含 SHA256；`product restore --dry-run` 列出每个会还原的文件；secret 默认不进 plaintext copy；snapshot/restore round-trip 在临时目录通过校验。
A2 G1 Smoke Pass — 在执行任何破坏性迁移前后，`solar-harness start/status/wiki/qmd/status-server` 全绿；现有 sprint 流不破。
A3 G2 Container Pass — 干净容器一条命令安装 + fake keys 配置 + doctor 全绿 + 跑通 1 个内置 skill；不依赖任何昊哥本机私有路径。
A4 G3 Secret Scan Pass — git pre-push 钩子阻止任何 plaintext secret；release 包构建前 audit 报告 0 个 leak；status UI 仅显示 configured/missing。
A5 G4 Skill Registry Pass — 至少 5 个 builtin + 5 个 user/generated skill 进入 registry；每个 stable skill 有 eval pack 与分数；canary skill 不会被默认注入；export/promote/rollback 全部可用。
A6 G5 Storage Migration Pass — _sources 与 papers 建立完成；老 _raw PDF 全部带 checksum 复制并附 manifest，无丢失；Mirage 8 个挂点全部探测通过；QMD 索引刷新且 wiki 链接可用；Drive 在无凭据时显示 degraded 而非 ok。
A7 G6 Autopilot Pass — 注入合成 deadlock (pane busy 但 watchdog 误判 dead) → autopilot 区分 busy 与 dead 并等待 lease 而非重置 status；handoff stall / eval stall / dispatch backlog 三类故障演练通过。
A8 G7 Release Artifact Pass — 打出 release tarball；干净容器 install→upgrade→rollback round-trip 通过；checksum 一致；版本号、变更记录、ADR 链接齐全。
A9 Evolution Loop Pass — 至少跑通 1 次失败聚类 → 实验 → eval → promotion (or demotion) 闭环；scorecard 在 status UI 可见。
A10 Plugin Manifest Pass — Obsidian/QMD/MinerU/Mirage/Mermaid 五个 plugin manifest 有效；`solar-harness integrations status --json` 输出四级状态。

## 非目标 / Non-Goals

N1. 不重写 Claude Code、Codex、tmux、Mirage、QMD、MinerU 内核，只做集成与治理。
N2. 不替换现有 solar-harness 协调器 / coordinator.sh，只在控制面增加 lease 与 state DB；coordinator 内部状态可逐步迁移。
N3. 不引入 Kubernetes、Elixir/OTP 等重型 orchestrator；保持 bash + python + sqlite + jsonl 技术栈。
N4. 不强制接 Linear / Jira；保留可选 plugin。
N5. 不做云端 SaaS 化；优先单机产品；多机后续再说。
N6. 不在本 sprint 完成所有 candidate skill 的 eval pack 编写；只完成框架与示例。
N7. 不替换 ~/.claude 目录结构；只通过 export 同步稳定 skill。

## 约束 / Constraints

C1. 总工作量分多个独立 slice，单 slice 不超过单个 builder session 可消化的范围。
C2. 不允许在 G0 通过前做任何破坏性迁移 (移动 PDF、重命名 _raw、改 launchd 主入口)。
C3. 禁止在容器测试中引用昊哥本机私有路径；docker 测试必须在干净 image 内自包含。
C4. 禁止 plaintext secret 进入 git / log / status UI / release tarball。
C5. 所有重活 (QMD embed, MinerU 抽取, paper reingest, eval pack 大批量执行) 必须 background + idle + rate limit；不得阻塞 user shell。
C6. 不能破坏当前 solar-harness start/status/wiki/qmd/status-server 路径。
C7. Skill 既要进 product 分发也要可被 Claude/Codex/agents 安全调用；不允许只有 ~/.agents/skills 野生形态。
C8. 任何 plugin 越权写非声明 scope = 立即拒载并告警。
C9. Mirage 失败回退到 native FS read-only，不做 silent error。
C10. 所有状态变更必须留 audit (status.history, events.jsonl, state DB)。

## 风险 / Risks

R1 (高): 存储迁移误删 PDF — 缓解: G0 snapshot 强制；移动改为 copy + checksum + retain symlink；migrate 命令带 --dry-run 强制审视；任何缺失 checksum 的文件不动。
R2 (高): Skill export 软链覆盖用户自有 skill — 缓解: skill_export.py 必须保留备份、检测冲突、产出 diff；用户可选择 keep-mine / overwrite / namespace；默认 namespace 隔离。
R3 (中): 容器 clean install 在 macOS 与 Linux 之间漂移 — 缓解: docker 用 Linux base，本机 macOS install 用相同 install.sh 但分支处理 brew vs apt；smoke test 跑两套。
R4 (中): coordinator 现有逻辑被破坏 — 缓解: 新 lease/state DB 通过 adapter 注入，旧 status.json/events.jsonl 不动；先双写后切读。
R5 (中): autopilot 误判 pane_busy 为 pane_dead 仍未修 — 缓解: lease 引入 + busy 心跳信号 + dispatch_failed 三态扩展 (no_pane / busy / dead) + 重置前必须 cross-check tmux 与 hook 时间窗。
R6 (中): Drive 凭据缺失下伪 ok — 缓解: integrations status 强制四级；Drive 没有凭据 → degraded 并显示需要的 env var/UI action。
R7 (低): plugin 框架过度设计阻碍开发速度 — 缓解: manifest schema 先支持最小字段，逐步演化；不要求一次接入所有现有集成。
R8 (低): evolution engine 误自动晋级劣化 skill — 缓解: 新 skill 默认仅 candidate；promotion 必须双 gate (eval pass + regression pass)；degradation 自动 demote。
R9 (中): secret scan 漏检遗留 token — 缓解: gitleaks 配置开放规则；release audit 在干净 worktree 重扫；status UI 严格白名单。
R10 (低): MinerU 占主进程导致 OOM — 缓解: 后台 launchd 服务 + idle 触发 + 内存上限 + 触发条件 user-shell-load < threshold。

## 开放问题 / Open Questions

OQ-1. installer 脚本运行时是否假设有 Homebrew / apt？两套脚本还是统一 detector + 分支？建议: 统一 install.sh 内做 OS detection + manager dispatch，并提供 fallback 手册。
OQ-2. secret 存放策略默认值: macOS keychain vs file-with-mode-600 vs 1Password CLI？建议: macOS 默认 keychain，Linux 默认 file 600，可配置 1Password。
OQ-3. skill registry 是 yaml + sqlite 双写还是单存 sqlite？建议: yaml 是用户可读源，sqlite 是查询索引；启动时 yaml → sqlite materialize。
OQ-4. plugin 沙盒策略: process 级隔离 vs scope-checked 调用？建议: 第一阶段 scope-checked + audit log；process 隔离作为后续 R&D。
OQ-5. evolution engine 的实验是否需要金丝雀流量分流？建议: skill canary 用调用比例分流；其他 capability 用 shadow execution + diff。
OQ-6. release 渠道: GitHub Release tarball + brew tap vs 自建 cdn？建议: 起步 GitHub Release + checksum；brew tap 后续。
OQ-7. state DB 迁移路径: 直接 sqlite 新表 vs 复用 cortex schema？建议: 独立 schema (solar_state.db)，不要污染 cortex；通过 adapter 双写过渡。
OQ-8. autopilot 心跳信号源: pane title? hook log? coordinator events? 建议: 统一改为 events.jsonl 标记 pane_heartbeat，并带 ttl。
OQ-9. 容器 clean install 是否包含 Claude/Codex 二进制？建议: 不包含；installer 检测到容器环境跳过 LLM CLI，仅验证 harness 自身路径。
OQ-10. Mirage Drive 离线缺凭据时的 UI 文案规范？建议: degraded badge + tooltip 列出需要的 env var + 链接到配置 wizard。

## 架构交接 / Planner Handoff

Planner 必须产出三份文档:

1. **Architecture Design** — 用至少 6 张组件图覆盖: (a) state DB schema 与生命周期状态机；(b) skill platform 流水线 (registry / package / export / metrics / eval / canary / promote / rollback)；(c) plugin manifest schema 与 capability registry；(d) storage layer (Mirage 八挂点 + _sources 规范 + MinerU idle 抽取流水)；(e) evolution engine (events → fail mining → experiment → promotion gate)；(f) installer / upgrade / rollback / snapshot 数据流。每个组件给出文件路径、数据结构、JSON schema 草案。

2. **Implementation Plan** — 切分为不重叠的 builder slice。建议:
   - S0 Snapshot/Restore Foundation (D0) — 必须最先、阻塞门槛
   - S1 Installer + Doctor + Container + Secret Scan (D1, FR-7, FR-8)
   - S2 Skill Platform (D2)
   - S3 Storage & Data Access (D3, MinerU idle 重活分项)
   - S4 Extension Framework (D4)
   - S5 Evolution Engine (D5)
   - S6 Control Plane (D6)
   - S7 Release Tooling + ADR (G7, ADR template)

   每个 slice 必须列: 写范围 (paths)、读范围、依赖、Done 条件、与 G0–G7 的对应、回滚动作、stop 触发、idle 安全。slice 之间禁止写交集。

3. **Dispatch Plan & Risk Register** — 哪个 slice 给哪个 builder（Sonnet / GLM-5 / GPT-5 codex），哪些 slice 可以并行；G0 通过前禁止任何 D1-D6 的破坏性写动作；列举 R1-R10 的具体缓解 owner 与触发器；列首 Gate Checklist (G0 必通过项)。

Planner 不可越界写代码；不可启动 builder；不可触碰 live tmux pane。完成后 status.phase 推到 `planning_complete`，并把 PRD/design/plan 三份产物路径写入 handoff 文件。
