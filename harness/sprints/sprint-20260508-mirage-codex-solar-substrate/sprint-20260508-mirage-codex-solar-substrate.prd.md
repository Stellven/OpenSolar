---
sprint_id: sprint-20260508-mirage-codex-solar-substrate
title: Mirage As Unified Data Substrate For Codex And Solar
prd_version: 1.0
prd_author: pm_dual_sign
prd_created_at: 2026-05-08T19:30:00Z
priority: P1
lane: data-plane
handoff_to: planner
blocked_by: null
---

# PRD — Mirage As Unified Data Substrate For Codex And Solar

## 背景 / Context

Solar Harness 上一轮 sprint `sprint-20260508-mirage-unified-vfs` Round 3 PASS，落地了 `solar-harness mirage` 作为统一虚拟文件系统：5+ 个挂载点 (`/knowledge` ro, `/raw` rw, `/sprints` ro, `/solar` ro, `/cortex` ro, `/qmd`, `/drive` ro 可选)、doctor/search/exec 三件套、deny_subpaths + redact_on_read 已在 exec 层接通、统一搜索覆盖 mirage_path + qmd + solar_db 三类源、status-server 8765 暴露 mirage 段、写边界白名单 (`/raw` 唯一可写)、Drive 默认 ro 降级。

但**底座建好不等于上层用起来**：

- Codex 当前仍各自走 ad-hoc 路径 (rg/grep/find on host) 读 Knowledge 与 sprints；
- Claude pane / planner / builder / evaluator 也各自直接读 host 文件，没有统一走 mirage；
- 文档 `docs/mirage-data-substrate-codex-solar.md` 描述了目标架构但**没有强制约束**让 Codex 与 Solar runtime 真的把 mirage 当作 canonical 入口；
- 前一轮 PM 仍在 round 1 复现了 A3 sandbox 逃逸 (host `~/.zshrc` 可被 exec 读出)，虽 round 3 已修，但**adoption + governance 缺位**导致下次回归无人察觉。

本轮目标不是新做 mirage 功能，而是**推 mirage 为默认入口 + 加一层治理**让它真正成为 Codex 与 Solar 的共享数据底座。

## 用户目标 / Goals

- **G1 (统一入口)**: Codex 与 Solar runtime (planner/builder/evaluator/化身) 跨源数据访问统一从 `solar-harness mirage search/exec` 进入，不再各自直连 host 路径。
- **G2 (可观测)**: 任何人 (含监护人昊哥) 可以通过 status-server 8765 一眼看到 mirage 的健康度 (mounts/last_probe/drive_status/stale) 与 enabled 标志。
- **G3 (可控)**: 监护人通过 Solar Config UI 可以无需手工编辑 yaml 就改 mirage workspace、enable/disable、Drive 凭证等开关，且 secret 不在 UI 上显式回显。
- **G4 (边界硬约束)**: A3 sandbox 不再依赖审判官人工复跑 — 每次评估自动跑 sandbox 探针 (cat /etc/passwd / cat ~/.zshrc / 写 /knowledge)，PM/evaluator 都拦得住回归。
- **G5 (语义清晰)**: Codex 与 Solar 角色清楚知道 "什么数据走 mirage / 什么路径走专用接口" — Knowledge 写走 wiki ingest、Sprint 写走 coordinator、Config 写走 solar-config-ui，不再绕过这些接口直改。

## 用户故事 / User Stories

- **US1**: 作为**监护人昊哥**，我打开 `http://127.0.0.1:8789/`，可以看到 "Mirage: enabled, 5 mounts ready, last probe 2 min ago"，不用 ssh 进 shell 跑 doctor。
- **US2**: 作为 **Codex 化身**，我要找一段 "OpenAI Symphony orchestration" 的引用，我跑 `solar-harness mirage search "Symphony orchestration" --json`，拿到 mirage_path + qmd + solar_db 三类源的 hits，**不用**自己 rg ~/Knowledge 再去 sqlite cortex 再去 qmd 拼三遍。
- **US3**: 作为 **planner 化身**，我要核对一个 sprint 合约现状，我直接 `mirage exec -- 'cat /sprints/<sid>.contract.md'`，**不用**记 host 绝对路径，且就算我手滑写 `/Users/sihaoli/...` 也会被拦。
- **US4**: 作为 **builder 化身**，我把整理的草稿写到 `/raw/2026-05-08/draft.md`，知道这是允许的；如果我想写 `/knowledge/concept-x.md` 会被拒，提示 "use wiki ingest"。
- **US5**: 作为**评估化身 (evaluator)**，我跑 sprint 验证时不靠肉眼，自动化脚本一并跑 sandbox 探针 + cross-source search，结果写进 eval.md 证据段。
- **US6**: 作为**监护人**，我换工作目录 (e.g. workspace_id 切换) 时，从 Solar Config UI 改一个下拉框就完成；改完 doctor 自动重跑、status 自动刷新。
- **US7**: 作为**审判官**，我读这一轮 eval.md 时能看到 "real commands executed (not status fields only)" 的证据列表，不接受 "status.json 显示 enabled 所以 PASS" 这种推断式判定。

## 功能需求 / Requirements

### R1 — Sandbox 边界自动化探针 (P0 前置门)
- 在 `tests/test-mirage-substrate.sh` 中加入**回归探针套件**：
  - 探针 P1: `mirage exec -- 'cat /Users/sihaoli/.zshrc'` → 必须 exit_code != 0 且 stderr 含 "mount not allowed" 或类似拦截语；
  - 探针 P2: `mirage exec -- 'ls /etc/passwd'` → 同上；
  - 探针 P3: `mirage exec -- 'head /Users/sihaoli/.aws/credentials'` (如不存在用 `/Users/sihaoli/.ssh/config`) → 同上；
  - 探针 P4: `mirage exec --json -- 'echo x > /knowledge/_probe.md'` → JSON 中 exit_code != 0 且 stderr 非空 (write deny);
  - 探针 P5: `mirage exec -- 'find /knowledge -name "*.md" | head -5'` → 仍然成功 (保证不是把 exec 锁死);
  - 探针 P6: `mirage exec -- 'cat /raw/$(date +%Y-%m-%d)/_probe.md'` (先 `/raw` 写一个再读) → write+read 都成功 (verify rw mount works)。
- 探针套件由 evaluator round 自动执行，结果以 JSON 段写入 eval.md。
- **门槛**: 6 个探针全部 PASS 是本 sprint 的 P0 前置条件；任何一个 FAIL 立即 round retry，不允许跳过。

### R2 — Codex/Solar 默认入口推广
- 修订 `~/.solar/harness/docs/mirage-data-substrate-codex-solar.md`：
  - 把 "推荐使用" 改为 **"Canonical entry — 必须使用"**；
  - 列出**禁用的反模式** (e.g. 化身在 prompt 中直接 rg ~/Knowledge / sqlite3 ~/.solar/solar.db / find /Users/sihaoli/.solar/harness/sprints)；
  - 给出**正例** ≥6 条覆盖：跨源搜索、读 sprint 合约、读 Knowledge 文档、读 cortex 段、读 qmd 资源、写 /raw 草稿。
- 在 `~/.solar/CLAUDE.md` 与 `~/.solar/harness/CODEX-USAGE.md` (新建或合并) 中加一条**铁律**: "Solar 角色读跨源数据，第一选择 `solar-harness mirage search/exec`；除非有专用接口 (wiki ingest / coordinator / config UI) 否则不绕过。"
- Codex pane 的 system prompt / dispatch template 中显式注入 "use mirage" 提示。

### R3 — status-server Mirage 健康面板
- `lib/symphony/status-server.py` (port 8765) 与 Solar Config UI status (port 8789) **均**在 `/api/status` 返回的 JSON 中加 `config.mirage.{enabled, workspace_id, mounts:[...], last_probe_at, drive_status, stale, qmd_indexed}` 字段。
- HTTP 面板 (HTML) 在头部加一个 "Mirage" 卡片，渲染 enabled badge、mount 列表、上次探针时间、Drive 状态、stale 警告。
- mirage 配置变更 (workspace 切换/enable/disable) 后 status 在 5s 内反映。
- `last_probe_at` 比 60s 前老 → 自动后台触发 doctor 刷新 (cooldown 30s 防 storm)。

### R4 — Solar Config UI Mirage 控制面
- 在 Solar Config UI 加 **Mirage Section** ("Mirage 数据底座")：
  - 字段: enabled (toggle), workspace_id (下拉，选项来自 `state/mirage/workspaces/`), drive_credentials_path (text, secret 不回显，只显示 `***configured` 或 `not configured`), drive_default_mode (radio: ro / off);
  - 操作: "重新探测 (re-probe)" 按钮 → 调 mirage doctor；"重启 status server" 按钮 (轻量) ;
  - 改完后写 `~/.solar/config/mirage.solar.yaml` (atomic rename + backup)；
  - 不在 UI 上显式回显 Drive token 等 secret，仅显示 fingerprint (sha256 前 8 位)。
- UI 改动后 status-server 5s 内反映。
- **不允许**通过 UI 直接编辑 mounts allowlist (那是代码/yaml 的边界，UI 改太危险)。

### R5 — Drive Read-Only 与 Knowledge 写保护硬化
- `mirage exec` 写 `/drive/*` → 一律 `write denied (mode=ro)` (Drive 默认 ro，要写只能改 yaml 加 explicit override，且不暴露在 UI 上)。
- `mirage exec` 写 `/knowledge/*` → 一律 deny + 提示 "use wiki ingest pipeline"；evaluator 必须验证这条提示在 stderr 中出现。
- `mirage exec` 写 `/sprints/*` 与 `/solar/*` 与 `/cortex/*` → 一律 deny + 提示 "use coordinator / solar CLI"。
- 唯一可写 mount: `/raw/*`。

### R6 — Evaluator Real-Command 验证铁律
- 在 evaluator pane 的 verify skill 中加一条强制：**A3-A7 类断言不允许只读 status.json 字段，必须执行真实命令并把 stdout/stderr 摘要写入 eval.md**。
- evaluator 跑 sandbox 探针 (R1) + cross-source search (A2) + status curl (A3) + UI 字段写后 5s diff (A4) + write-deny 断言 (A5) 全部用 bash 真跑。
- eval.md 必须有 "Real Commands Executed" 章节，逐条列命令 + 摘要 stdout (或截断 ≤200 字)。

### R7 — Codex/Solar 语义边界 Runbook
- 新增 `~/.solar/harness/docs/mirage-runbook.md`：
  - "什么走 mirage" 表 (Knowledge 读 / Sprint 读 / Cortex 读 / QMD 读 / 跨源 search / 化身 exec) ;
  - "什么不走 mirage" 表 (Knowledge 写 / Sprint 写 / Config 写 / Drive 写) + 每条说明走哪个接口；
  - "故障应对" (mirage doctor 不通 / 探针 P1 漏拦 / status 显示 stale / Drive 401);
  - "扩展指引" (新挂载点怎么加 / 新源类型怎么接入 search)。

## 非目标 / Non-Goals

- **NG1**: 不重写 mirage 底层 (libsolar_mirage.py 已 PASS，不动)；
- **NG2**: 不在本 sprint 引入 FUSE 挂载 (macOS 不支持，logical mount mode 维持);
- **NG3**: 不打开 Drive 写权限 (即使监护人有 token，本 sprint 仅推 ro 路径);
- **NG4**: 不重写 wiki ingest / coordinator / config UI 的写路径 (它们是专用接口，本 sprint 只**指向**它们);
- **NG5**: 不做 mirage 跨机分布式 (本机 substrate);
- **NG6**: 不做 mirage 多租户 (单监护人);
- **NG7**: 不为 mirage 做查询缓存 / 索引重建优化 (search 性能调优放后续 sprint);
- **NG8**: 不替代 Cortex 知识库 (mirage 只读 cortex_sources，不替它的写路径)。

## 约束 / Constraints

- **C1 (前置门)**: R1 sandbox 探针 6 项必须先全 PASS，才能开始评估其他 Acceptance；evaluator 在 round 中**首先**跑 R1，FAIL 立即 retry 不动其他。
- **C2 (写白名单)**: 所有 mirage 写路径白名单仅 `/raw/*`，新增需修改 `lib/solar_mirage.py` + `config/mirage.solar.yaml` 双签 (PR 必须经 PM 复核)。
- **C3 (读边界)**: 读路径必须做 mount-prefix 校验 (round 1 P0 教训)，禁止 host absolute path 落到 dispatcher。
- **C4 (UI 不暴露 secret)**: Solar Config UI Mirage Section 显示 Drive 凭证时只能显示 fingerprint (sha256[:8]) 或 "configured/not configured"，绝不回显 token/path 全文。
- **C5 (status 一致性)**: 8765 与 8789 两个 status server 都必须暴露 mirage 段，字段名/语义一致 (避免文档分裂)。
- **C6 (atomic 写配置)**: UI 改 mirage.solar.yaml 必须 backup → tmpfile write → fsync → atomic rename，禁止 in-place 覆盖 (避免 UI 崩溃留下半文件)。
- **C7 (不破坏 unified-vfs)**: 任何对 lib/solar_mirage.py 的改动必须保 round 3 PASS 的 33/33 测试不退化；改完跑全套 + R1 探针。
- **C8 (Codex 入口推广不强制)**: 新 docs 与 CODEX-USAGE.md 是 **soft enforcement** (文档 + dispatch prompt 注入)，不在 mirage CLI 层强制 user-agent 检测；监护人有意手动跑 rg/find 不会被拦 (避免误伤)。

## 风险 / Risks

| RK | 描述 | 缓解 |
|----|------|------|
| RK1 | 探针 P1-P3 在 round 3 验收时被 builder "测试针对性补丁" 绕过 (只防探针 5 条 path，没真正修 dispatcher) | evaluator 探针不固定 path，引入随机 host 文件 (e.g. `/private/etc/hosts`) 抽测；PM 在 round 3 自验 ≥1 条新 path |
| RK2 | status-server 8765 与 8789 两份代码漂移 (一边加了字段一边没加) | R3 验收时 curl 两个 endpoint diff 字段集，必须 superset/subset 关系成立 |
| RK3 | Solar Config UI 改 mirage 配置后 atomic rename 失败 (磁盘满 / 权限) 留下半文件 | C6 强制 backup + tmpfile + rename；UI 改完 5s 内 doctor re-probe，失败回滚到 backup |
| RK4 | Drive credentials 在 UI 上手滑回显 (违反 C4) | UI 渲染层强制只能渲染 fingerprint，单元测试断言 "drive_credentials_path" 字段不出现在 HTML 响应 |
| RK5 | 化身 (Codex/Claude pane) 仍然用旧习惯直连 host 路径，新文档 G1 落不下来 | dispatch template 显式注入 "use mirage"；PM 在 round 3 sample 检查最近 3 个化身 dispatch 的引用是否含 mirage |
| RK6 | mirage doctor 在 mounts 卷膨胀时 (qmd 大量文件) 慢 → status 8765 阻塞 | R3 last_probe 后台异步触发，cooldown 30s；探针 timeout 5s 否则降级 stale=true |
| RK7 | runbook (R7) 写完没人读 | 在 dispatch template 与 PM brief 中引用 runbook 章节锚 (e.g. `mirage-runbook.md#what-goes-via-mirage`) |
| RK8 | UI 加 Mirage Section 与现有 Symphony / Wiki Section 排版冲突 | UI 改动走 design-review skill，render snapshot 对比 |
| RK9 | evaluator real-command 跑 5+ 真命令导致 round 时长翻倍 | 探针套件 timeout 总和 ≤30s；evaluator 用 `--timeout 5` 限制每条 |
| RK10 | C8 soft enforcement 长期被绕过，半年后 mirage 又退化为可选 | 在 weekly-report.sh 加 metric "mirage usage ratio" (近 7 天 dispatch 含 mirage 关键词数 / 总数)，<60% 触发警告 |

## 开放问题 / Open Questions

- **OQ1**: status server 8765 (Symphony) 与 8789 (Solar Config UI) 长期是否保留两个？还是 8789 收编 8765？(本 sprint 维持双跑，统一推后续 sprint，但 mirage 段双 expose)
- **OQ2**: Codex pane (pane 3 codex-bridge) 的 dispatch 模板是否要无条件注入 "use mirage" 提示？还是仅在 task-type ∈ {research, audit, cross-source} 时注入？(默认: 无条件，研究阶段如果 token 涨幅 > 5% 再降级到条件注入)
- **OQ3**: mirage workspace_id 切换时，化身的内存中是否要 invalidate 上次 search cache？(目前 search 无 cache，未来加 cache 时需考虑)
- **OQ4**: Drive ro 默认是否需要监护人在 Solar Config UI 显式同意一次才生效？(默认: 安装即 ro，不需要点同意；override 到 rw 才需要二次确认)
- **OQ5**: R6 real-command 验证铁律是否回溯应用到所有历史 sprint 的 evaluator？(默认: 只对**未来** sprint 生效，历史 sprint 不重审)
- **OQ6**: runbook (R7) 写在 docs/ 还是 wiki/concepts/？(默认: docs/，因为是 Solar Harness 内部 runbook 不入 Knowledge wiki)

## 验收标准 / Acceptance Criteria

| # | 验收点 | 验证命令 (evaluator 必跑) | Pass 标准 |
|---|--------|---------------------------|-----------|
| **A1** | Sandbox 探针套件 (R1) 6/6 PASS | `bash ~/.solar/harness/tests/test-mirage-substrate.sh` (新增) | `probes_passed=6 probes_failed=0`；JSON 段在 eval.md |
| **A2** | 跨源搜索 ≥2 source classes (R2 验证 mirage 仍可用) | `solar-harness mirage search "Solar Harness Obsidian" --json` | `len(hits) > 0` 且 `set(hit.source_type for hit in hits)` ≥ 2 |
| **A3** | status-server 8765 + 8789 都暴露 mirage 段 (R3) | `curl -fsS http://127.0.0.1:8765/api/status` 与 `curl -fsS http://127.0.0.1:8789/api/status` | 两份 JSON 均含 `config.mirage.{enabled, workspace_id, mounts, last_probe_at}` |
| **A4** | Solar Config UI 可改 mirage 字段 (R4)，secret 不回显 | curl UI HTML 抓 Mirage Section + 改 workspace 下拉 → 5s 内 status 反映 | HTML 不含 drive token 全文 (只含 fingerprint)；改后 `config.mirage.workspace_id` 变更 |
| **A5** | 写边界硬化 (R5)：/raw 可写其余全 deny | `mirage exec --json -- 'echo x > /knowledge/_a5.md'`；`> /sprints/_a5.md`；`> /solar/_a5.md`；`> /cortex/_a5.md`；`> /drive/_a5.md`；`> /raw/$(date +%Y-%m-%d)/_a5.md` | 前 5 条 exit_code != 0 + stderr 含 deny 提示；最后一条 exit_code == 0 |
| **A6** | Real-command 铁律 (R6)：eval.md 含 "Real Commands Executed" 章节 | grep -q "Real Commands Executed" eval.md | 章节存在且至少列 6 条命令 |
| **A7** | Runbook (R7) 与默认入口文档 (R2) 落地 | `ls ~/.solar/harness/docs/mirage-runbook.md` + `grep -q "Canonical entry" ~/.solar/harness/docs/mirage-data-substrate-codex-solar.md` + `grep -q "use mirage" ~/.solar/CLAUDE.md` | 三处引用都存在 |

## 架构交接 / Planner Handoff

### 切片建议 (3 切片，对齐 acceptance 与依赖)

| Slice | Deliverables | Acceptance 覆盖 | 依赖 |
|-------|--------------|-----------------|------|
| **S1: 边界硬化 (P0 前置)** | D1 探针套件 `tests/test-mirage-substrate.sh` (R1 全部) ；D2 评估流程改 — evaluator 在 round 启动后**首先**跑探针 (R6 部分) ；D3 写边界提示文案补全 (R5 deny stderr 文案统一 "use wiki ingest" / "use coordinator" / "use solar CLI") | A1, A5 (写部分), A6 (部分) | 无 (在 unified-vfs 之上) |
| **S2: 可观测 + 可控** | D4 status-server 8765 加 mirage 段 (R3) ；D5 Solar Config UI 8789 加 mirage 段 + Mirage Section 控制面 (R3+R4) ；D6 last_probe 后台刷新 (cooldown 30s) | A3, A4 | S1 (因 R6 evaluator 流程改了要先稳) |
| **S3: 推广 + 治理** | D7 修订 `mirage-data-substrate-codex-solar.md` 改 "Canonical entry" + 反模式表 (R2) ；D8 新建 `mirage-runbook.md` (R7) ；D9 修订 `~/.solar/CLAUDE.md` + 新建/合并 `CODEX-USAGE.md` 加 "use mirage" 铁律 (R2) ；D10 dispatch template 注入 "use mirage" (R2 + RK5) ；D11 weekly-report 加 mirage usage metric (RK10) | A2, A6 (完整), A7 | S1 (确保推荐的入口已经是硬约束的) |

### 验证顺序约束

evaluator round 必须按以下顺序跑，任何一步 FAIL 立即 retry，不评估后续：
1. **A1 (R1 探针)** — 前置门，6/6 必须 PASS；
2. **A5 (写边界)** — sandbox 写侧验证；
3. **A3 (status 8765+8789)** — 可观测；
4. **A4 (UI)** — 可控；
5. **A2 (跨源 search)** — mirage 主功能未退化；
6. **A7 (docs)** — 文档落地；
7. **A6 (Real Commands chapter)** — 元验收，evaluator 自身遵守了铁律。

### 必须复用的现有基础设施

- `lib/solar_mirage.py` (round 3 PASS 的实现，**不重写**)；
- `lib/mirage_search.py` (search 引擎)；
- `lib/mirage_events.py` (event log)；
- `config/mirage.solar.yaml` (workspace 配置，UI 写入此文件)；
- `state/mirage/` (探针快照 + workspace state)；
- `lib/symphony/status-server.py` (8765, 加 mirage 段，参考 sprint solar-kb-obsidian-autouse 修对了文件)；
- Solar Config UI 8789 (找 server 入口加 Mirage Section)；
- `tests/test-mirage-unified-vfs.sh` (既有 33/33，本 sprint 不动它，新增独立的 substrate 探针套件)。

### 必须解决的 OQ (planner 在 plan.md 中明确选择)

- OQ2 (dispatch 注入策略) → planner 在 plan.md 中选 "无条件注入" 或 "条件注入"，给依据；
- OQ4 (Drive ro 是否需要二次确认) → planner 选默认即 ro 还是 UI 二次确认；
- OQ6 (runbook 位置) → planner 确认 docs/ 而非 wiki/concepts/。

### 不允许做的事

- **不重写** lib/solar_mirage.py (NG1)；
- **不开** Drive 写权 (NG3)；
- **不引入** FUSE (NG2)；
- **不绕过** wiki ingest / coordinator / config UI 的写路径 (NG4)。

### 触发升级到 PM 的情况

- 探针 P1-P6 在 builder 实现后仍 FAIL 2 round → PM 介入 finding；
- C4 (secret 不回显) 失守 → PM 立即 finding + P0 retry；
- weekly-report mirage usage ratio < 60% (本 sprint 完成后 30 天) → PM 复盘是否要把 C8 改为 hard enforcement。

## 文档完整性 (Definition of Done)

- [x] 背景 / Context
- [x] 用户目标 / Goals (G1-G5)
- [x] 用户故事 / User Stories (US1-US7)
- [x] 功能需求 / Requirements (R1-R7)
- [x] 非目标 / Non-Goals (NG1-NG8)
- [x] 约束 / Constraints (C1-C8)
- [x] 风险 / Risks (RK1-RK10)
- [x] 开放问题 / Open Questions (OQ1-OQ6)
- [x] 验收标准 / Acceptance Criteria (A1-A7)
- [x] 架构交接 / Planner Handoff (3 切片 + 验证顺序 + 复用基础设施 + OQ resolution + 禁止事项 + 升级触发)

PRD 完成，handoff_to: planner，等 planner 在 plan.md 中切片落地。
