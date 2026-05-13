# PRD — Tool Plane Sandbox Default Routing

Sprint: `sprint-20260513-tool-plane-sandbox-default-routing`
Priority: P0
Lane: reliability
Date: 2026-05-13
Author: Solar PM (knowledge context: solar-harness context inject used)

> Restored 2026-05-13 21:30Z from planner memory snapshot — original file deleted during 21:01-21:11 contract-patrol churn; content matches eval.json acceptance_results.

## Background

Local disposable runtime v2 已就位：`SandboxHand` 支持 argv + write-guard 双模式，evidence 写到 sandbox 外，dispose 后 workspace 清零。Activation proof 当前 11/11 PASS。两条用户触发链路已默认走 SandboxHand：

- `solar-harness mirage exec`（data-plane shell）
- Ruflo / Claude Flow runtime smoke（help/version/mcp_help）

但 `solar-harness-local-disposable-sandbox-assessment-20260513.md` 自评里仍有三个 warn：`default all-tool routing`、`OS-level FS isolation`、`network egress policy`。本 sprint 只动第一条「默认路由」，**不**触碰 OS 级容器化和网络 egress —— 它们留给 v3。

## Goal

把更多**用户触发的 tool/data-plane 调用**默认路由到 `SandboxHand`，并通过 activation proof + 回归测试锁死，不允许回退到裸 host 执行。控制面（tmux/ssh/rsync/launchctl/status server/test runner）**不在**本轮范围。

## User Stories

- 作为用户，我跑任何 user-triggered 工具命令时，默认会经过 SandboxHand：argv 模式 + workspace 隔离 + write-guard + evidence file。
- 作为 evaluator，我可以从 activation proof 看到「哪些路径已 sandbox 化、哪些是显式排除、哪些 pending」，没有被「假 ok」糊弄。
- 作为 Solar 维护者，我能从 `reports/tool-plane-sandbox-routing/inventory.{json,md}` 一眼看清剩余 `subprocess.run` 调用点的分类（tool/data/control/test/background）。
- 作为下游 sprint planner，我能从 closeout 文档拿到「下一批安全迁移目标」清单，不用从头扫代码。

## Scope

### In Scope

- R0 inventory：对 `lib/`、`tools/`、`tests/` 下剩余 `subprocess.run` 调用点做分类清单，输出 JSON + Markdown，并镜像到 `_raw`。
- R1 QMD / data-search 链路分析：能 sandbox 化的（CLI/search/status）走 SandboxHand；前台 embed 这种长跑 worker **必须**保留为 background，**不**强行进 sandbox smoke。
- R2 Document extraction / MarkItDown 上传链路：smoke 路径若能 sandbox 化则迁移，否则 activation proof 显式标 warn/pending（**不**假 ok）。
- R3 activation proof + status UI：迁移路径回退到裸 host 时必须 fail；status UI 暴露迁移工具的 sandbox 路由状态。
- R4 closeout：写 _raw 收官文档，列已迁移 / 显式排除 / pending 三栏，给 evaluator 出 readiness report。

### Out of Scope（本 sprint 显式不做）

- 路由 `tmux`、`ssh`、`rsync`、`launchctl`、status server 进程控制、test runner 编排 —— 它们是 control-plane side-effect，不能 sandbox。
- 前台跑长 QMD embedding（成本爆炸）。
- 全 kernel-level 隔离（chroot/seatbelt/docker）—— 留给 v3。
- 网络 egress allowlist/denylist —— 留给 v3。

## Constraints

- 不修改 `SandboxHand` 公共 API，复用现成 argv + write_guard_roots 能力。
- 每条迁移路径必须留下 `executor=sandbox`、`execution_mode=argv`、`evidence_file` 三件证据，否则 activation proof 拒收。
- 不允许 builder 自宣 passed，必须由 evaluator 复核 activation proof 输出。
- 不许 builder 改写 contract scope；如确需扩 write_scope，写 scope-change note 到 node handoff，不要直接越界。

## Risks

- **Regression**：迁移到 sandbox 后旧调用方可能拿不到原 env/cwd —— 缓解：每条迁移都要附带 `tests/` 回归，证明旧契约还能跑。
- **假 ok 倾向**：previous round Builder 容易把没真跑的路径标 ok。缓解：activation proof 严格区分 `ok / warn / pending`，acceptance 明确写「不允许 fake ok」。
- **QMD embed 误踩前台**：QMD embed worker 长跑，前台 sandbox 化会卡。缓解：R1 acceptance 第一条就锁死「no foreground qmd embed is run」。
- **MarkItDown 凭据泄漏**：document extraction 路径若涉及外部 API，secret 必须走 secret_refs + redact。缓解：R2 acceptance 显式要求 evidence 里没明文凭据。

## DoD (Definition of Done)

- [ ] D1 R0 inventory 输出三件套：`inventory.json` + `inventory.md` + `_raw/tool-plane-sandbox-routing-inventory-20260513.md`，每个 `subprocess.run` 调用点都被分类到 5 类之一（tool_plane / data_plane / control_plane / test_only / background_worker），并写明「下一批安全迁移目标」。
- [ ] D2 R1 QMD / data-search 路径：至少一条 CLI/search/status 路径迁移到 SandboxHand 并附 evidence_file；或者明确报告「该路径暂不安全迁移」+ 写 activation proof pending/warn（**禁止** fake ok）。
- [ ] D3 R2 Document extraction 路径：smoke 路径 sandbox 化 + 小文本/markdown fixture 回归通过；或者明确标 not applicable。MarkItDown 能力保持可注入但不假报已执行。
- [ ] D4 R3 activation proof：跑 `solar-harness integrations activation-proof --json`，输出包含本轮所有迁移路径的 sandbox 证据；任意一条迁移路径若被改回裸 host，proof 必须 fail。
- [ ] D5 R3 status UI：`/status` 或对应 report 能看到本轮迁移的 tool sandbox route 状态。
- [ ] D6 回归测试全绿：`test-hands-runtime.sh`、`test-status-capability-health-projection.sh`、`test-mirage-substrate.sh`、`test-mirage-unified-vfs.sh`、`tests/plugins/test-ruflo-integration.sh` 全过。
- [ ] D7 R4 closeout：`_raw/tool-plane-sandbox-default-routing-closeout-20260513.md` + `reports/tool-plane-sandbox-routing/closeout.{md,json}`，三栏齐全（migrated / excluded-with-reason / pending-with-next-step），父级 readiness report 注明 evaluator 是否可入审。

## Required Verification

```bash
python3 -m py_compile \
  ~/.solar/harness/lib/hands_runtime.py \
  ~/.solar/harness/lib/solar_mirage.py \
  ~/.solar/harness/lib/ruflo_adapter.py \
  ~/.solar/harness/lib/capability_activation_proof.py

bash ~/.solar/harness/tests/runtime/test-hands-runtime.sh
bash ~/.solar/harness/tests/test-status-capability-health-projection.sh
bash ~/.solar/harness/tests/test-mirage-substrate.sh
bash ~/.solar/harness/tests/test-mirage-unified-vfs.sh
bash ~/.solar/harness/tests/plugins/test-ruflo-integration.sh
solar-harness integrations activation-proof --json
```

## Stop Rules（红线，碰即 fail）

- 任何 `tmux`/`ssh`/`rsync`/`launchctl`/status server lifecycle/test runner orchestration 被改成走 `SandboxHand` —— 立即停。
- 前台触发长 QMD embedding —— 立即停。
- 声称「完整 kernel 隔离」—— 立即停（当前边界是 local process sandbox + 策略/证据）。
- write_scope 越界但没写 scope-change note —— 立即停。

## Deliverables

- `reports/tool-plane-sandbox-routing/inventory.{json,md}`
- `reports/tool-plane-sandbox-routing/qmd-route.{json,md}`
- `reports/tool-plane-sandbox-routing/document-route.{json,md}`
- `reports/tool-plane-sandbox-routing/closeout.{json,md}`
- `reports/capability-activation-proof-latest.json`（更新）
- 更新后的 `lib/qmd_adapter.py` / `lib/mirage_search.py` / `lib/wiki-upload-*.py` / `lib/capability_activation_proof.py` / `lib/symphony/status-server.py`
- 更新后的回归测试（按 task_graph write_scope 列举）
- `_raw/solar-harness-local-disposable-sandbox-assessment-20260513.md`（追加本轮进展）
- `_raw/tool-plane-sandbox-default-routing-closeout-20260513.md`

## Handoff

PM PRD 完成 → 移交 **Planner**（不是 Builder）。
Planner 已有 `plan.md` + `task_graph.json`（R0→R1+R2→R3→R4 五节点），需根据本 PRD 复核 acceptance 是否对齐，必要时补丁 task_graph，再触发 graph-scheduler 派工。

Knowledge Context: solar-harness context inject used
