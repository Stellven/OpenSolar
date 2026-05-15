# PRD — MinerU + Mirage Full Closure

> Sprint: sprint-20260509-mineru-mirage-closeout
> Author: planner-as-PM (degraded — brain-router 故障)
> Date: 2026-05-09

## 1. Context

Solar 集成面板 `/integrations` 当前对 **MinerU Document Explorer** 与 **Mirage Unified VFS** 标记为 `ok`，但事实上只有 Solar 自己写的 wrapper 通了，vendor 底层并未真正可用：

- **MinerU**: vendor 目录下没有可复现的 `.venv` bootstrap，doctor 命令对 venv 状态打勾纯靠 wrapper 判断；从未在用户的 `_raw/file-uploads` 上做过端到端深度抽取。
- **Mirage**: Solar 仅实现了"逻辑路径映射"层（把 `/knowledge`、`/raw`、`/sprints` 翻译成宿主绝对路径），既没安装官方 SDK，也没启用 FUSE 文件系统，Google Drive 入口完全空挂。

这是典型的"虚假繁荣"——监护人一旦真去调用任何深度功能就会 failure，但 UI 永远绿灯。

## 2. Problem Statement

**用户视角的疼点**：
- 监护人以为 MinerU 已就位 → 想抽 PDF 时发现 `solar-harness wiki mineru-doctor` 报 venv 缺失 → 信任崩塌。
- 监护人以为 Mirage 是统一文件系统 → 实际只是个路径前缀映射 → 想从 Codex 那边读时找不到 mount。
- 新 shell 启动后 QMD MCP 只绑 `127.0.0.1`，IPv6 only 的客户端连不上。
- 后台抽取/embedding 把前台 shell 卡住，监护人正常工作被打断。

**根因**: UI 标签语义不精准——`ok` 同时被用来表达"wrapper 通"和"端到端通"，没有梯度。

## 3. User Goals

| # | 目标 | 衡量 |
|---|------|------|
| G1 | 想抽 PDF 时能立即抽 | 给 2 个真实 PDF 能产出 Obsidian 引用页 |
| G2 | 想跨 source 查询时 mount 真的在 | `solar-harness mirage doctor` 全 ok |
| G3 | 状态面板讲真话 | 看 `/integrations` 知道哪能用、哪不能用、缺什么 |
| G4 | 重启后服务还在 | 关 shell 不影响 QMD MCP 双协议端口 |
| G5 | 后台任务不打断前台 | shell 永远不被嵌入式抽取/嵌入计算 hang 住 |

## 4. User Stories

- **US1**: 作为 Solar 用户（昊哥），我希望把 `_raw/file-uploads` 里的 PDF 拖给 MinerU，**以便** 自动产出带 provenance 的 Obsidian 引用页，无需手动复制粘贴。
- **US2**: 作为 Solar 用户，我希望 `/integrations` 上能一眼看出 "MinerU=basic usable / Mirage=closed loop / Drive=dead end (需要凭据)"，**以便** 快速判断今天能依赖哪个 source。
- **US3**: 作为 Solar 用户，我希望 Codex pane 里 `cat /knowledge/foo.md` 真的能读到 Knowledge 库内容，**以便** 不需要每次都给绝对路径。
- **US4**: 作为 Solar 用户，我希望关掉 Solar 主 shell 之后，QMD MCP 仍然在两套 loopback (IPv4+IPv6) 上响应，**以便** 其他 agent 进程不被波及。
- **US5**: 作为 Solar 用户，我希望长时间 PDF 抽取在后台跑，前台立即返回控制权，**以便** 我可以继续敲命令而不是等。

## 5. Functional Requirements

### FR-1 MinerU 运行时 (对应 A1)
- vendor 提供单条 bootstrap 命令产生 `.venv` + lock 文件 + 安装 report
- `solar-harness wiki mineru-doctor --json` 输出含 `venv=ok` 字段
- bootstrap 失败时报 actionable 错误（缺什么包、缺什么权限）

### FR-2 PDF 深度抽取 (对应 A2)
- 至少 2 个真实 PDF（来自 `/Users/lisihao/Knowledge/_raw/file-uploads`）端到端抽取成功
- 输出落在 Obsidian Knowledge 库 `references/` 下
- 每页生成的 markdown 含 `provenance:` frontmatter（源 PDF 路径 + 页码）
- 产出 audit report 列出 `source -> generated pages` 映射

### FR-3 QMD MCP 双协议持久化 (对应 A3)
- QMD MCP 同时绑 `127.0.0.1:8181` 和 `::1:8181`
- shell 退出后端口仍可达（launchd/独立 daemon）
- `solar-harness wiki qmd-mcp status` 同时显示两个 host 的探活结果

### FR-4 Mirage SDK/FUSE 决策 (对应 A4)
- 二选一并落 ADR：
  - **a) 装**：mirage SDK/FUSE 实际安装并跑通端到端测试
  - **b) 不装**：写 `reports/mirage-sdk-fuse-decision-2026-05-09.md` 解释为什么 Solar 逻辑 wrapper 是合理边界
- 决策证据要含 macOS 权限、内核扩展、性能基线三方面分析

### FR-5 Mirage 挂载完整性 (对应 A5)
- 必出 mounts: `/knowledge`、`/raw`、`/sprints`、`/db (Solar DB)`、`/qmd`
- Google Drive：要么真凭据挂载（OAuth flow 完成 + 测试 list 命令），要么 UI 明确标 `dead end (env var: GOOGLE_DRIVE_REFRESH_TOKEN missing)`
- `solar-harness mirage doctor --json` 给每个 mount 标 `status` + `reason`

### FR-6 状态 UI 精确标签 (对应 A6)
- `/integrations` 不再用单一 `ok` 标签，改为四档：
  - **basic usable**: wrapper 通，vendor 部分通
  - **default usable**: wrapper + vendor 默认场景通
  - **closed loop**: 全功能可用，含端到端 evaluation
  - **dead end**: 当前不可用 + 卡在哪里 + 怎么解锁
- JSON schema 测试覆盖四种标签

### FR-7 后台任务隔离 (对应 A7)
- 嵌入计算、PDF 长抽取、Drive 同步等：launchd / tmux detach / 独立 service
- 前台命令调用时立即返回 job-id，不阻塞 shell
- idle guard：用户活跃时降速或暂停（避免击穿用户工作）

## 6. Acceptance Criteria

| ID | 验收 | 验证命令 |
|---|---|---|
| A1 | venv bootstrap 可复现 | `solar-harness wiki mineru-doctor --json` 含 `venv=ok` |
| A2 | ≥2 PDF 端到端抽取 | 看 audit report：`source -> generated pages` 至少 2 行 |
| A3 | QMD MCP 双协议持久 | `solar-harness wiki qmd-mcp status` 同时显示 v4/v6 |
| A4 | Mirage SDK/FUSE 决策落 ADR | `ls reports/mirage-sdk-fuse-decision-*.md` 至少 1 文件 |
| A5 | Mirage mounts 完整 | `solar-harness mirage doctor --json` 列出 5+ mount |
| A6 | UI 用四档标签 | `/integrations` 视觉 + JSON schema test |
| A7 | 重活全后台 | launchd/tmux/service 证据 + 前台 shell 无阻塞 |

## 7. Non-Goals

- **不做** MinerU 模型自训或自定义 OCR 模型 — 用 vendor 默认 pipeline
- **不做** Mirage 写操作（只读为主，写仍走 `solar-harness mirage exec` 或 `wiki ingest`）
- **不做** Google Drive 全量索引 — 只验证 mount 可用 + 列文件
- **不做** UI 大改，仅改 `/integrations` 标签 + 状态 JSON schema
- **不做** Linux/Windows 兼容 — 只针对当前 macOS Apple Silicon 单机
- **不做** GPU 加速 — 用户机器无 NVIDIA GPU，全 CPU 路径

## 8. Constraints

- **C1 (硬件)**: macOS Darwin 24.6.0 / Apple Silicon / 无 NVIDIA GPU → MinerU 必须 CPU 可用，否则按 Stop Rule 标 unsupported
- **C2 (权限)**: macOS FUSE 需要内核扩展 + 系统授权 → 若用户未给权限，Mirage FUSE 走 ADR 路径
- **C3 (凭据)**: Google Drive OAuth 需要客户端 ID + refresh token → 缺时不强求，UI 显式 dead end
- **C4 (网络)**: QMD MCP 仅 loopback 暴露，绝不绑 0.0.0.0 → 安全边界硬要求
- **C5 (持久性)**: 重启 shell 不能影响 MCP/服务 → 必须有 launchd 或 detach 机制
- **C6 (前台体验)**: 重活不阻塞用户 shell ≥ 2 秒 → 必须后台 + idle guard
- **C7 (向后兼容)**: 不破坏 `solar-harness mirage` / `solar-harness wiki` 现有命令签名

## 9. Risks

| # | 风险 | 触发条件 | 缓解 |
|---|------|----------|------|
| R1 | MinerU venv 安装链长，pip 依赖冲突 | bootstrap 报 dependency conflict | 用 `uv` 或锁定 wheel；若硬冲突则按 Stop Rule 标 unsupported |
| R2 | macOS FUSE 需要重启或解锁 SIP，用户不愿 | 安装 FUSE 时弹系统授权对话框 | 默认走 ADR 路径，FUSE 仅作 opt-in |
| R3 | QMD MCP 双绑端口冲突 | `::1:8181` 已被其他进程占用 | doctor 检测占用方 + 给 actionable 错误 |
| R4 | Drive OAuth 需要浏览器交互，无法纯 CLI 完成 | 用户未配 refresh token | 显式 degraded，UI 给"点这里去配"按钮指引 |
| R5 | 后台抽取偷跑磁盘 IO 影响系统响应 | 大 PDF + 用户活跃 | idle guard：检测用户活跃则降并发到 1 |
| R6 | 状态 UI 标签改动破坏第三方消费方（Codex 读 JSON） | 已有调用方依赖 `status=ok` 字符串 | 加 `status_legacy` 字段保留旧值；6 周后弃用 |
| R7 | 现在标 ok 的集成被改回 dead end，监护人体感倒退 | UI 一上线立即出现红 | 同步发 changelog 解释"现在的红是真的红，比假绿更值得信任" |

## 10. Open Questions (给 Planner / 架构师)

1. **MinerU 是否完全走 vendor 默认 pipeline？** 还是要为常见学术 PDF 做后处理 patch（公式/表格）？— 答案影响 FR-2 是否要包"质量校验" 子 slice。
2. **Mirage FUSE 决策的截止时间？** 如果架构师决定保留 wrapper，ADR 是单文档还是要走 Solar 现有 ADR 流程（INFRA-ADR 编号）？
3. **Status UI 四档标签是否要支持 per-component？** 例如 MinerU 整体 `basic usable` 但 PDF 抽取 `closed loop`，是要扁平展开还是嵌套？
4. **QMD MCP 持久化方案选 launchd 还是 tmux session？** launchd 更"系统级"，tmux 更"易调试"——架构师偏好？
5. **后台任务的"idle guard"靠什么信号？** macOS 的 `ioreg` HID idle、tmux pane 活跃、还是 shell history mtime？
6. **Drive degraded 路径是否要写"假数据"占位？** 还是直接 404？— 影响 UI 渲染策略。

## 11. 架构交接 / Planner Handoff

架构师需要把本 sprint 拆成 **4 条独立 builder slice**，按依赖顺序：

1. **Slice S1 (MinerU 运行时)**: vendor `.venv` bootstrap + lock + doctor JSON 增 `venv=ok` 字段。出口闸：`solar-harness wiki mineru-doctor --json` 在 fresh shell 通过。
2. **Slice S2 (PDF 端到端抽取)**: 复用 S1 venv，跑 ≥2 个真实 PDF 抽取 → Obsidian + provenance + audit report。依赖 S1。
3. **Slice S3 (Mirage 决策 + 挂载)**: SDK/FUSE 决策 ADR → 落地 5 个 mount + Drive 凭据探活 + degraded UI。可与 S1/S2 并行。
4. **Slice S4 (状态 UI + 后台隔离)**: `/integrations` 四档标签改造 + JSON schema test + 重活后台化（launchd/tmux）+ idle guard。**必须最后做**，因为标签改动依赖前 3 个 slice 真实状态。

每个 slice 必须独立可 evaluate，evaluator 在 fresh shell 重跑探针，不接受"刚跑过缓存通过"。

跨 slice 共用约束：所有 doctor/status 命令更新必须先于 UI 标签变更（避免 UI 撒谎）。

