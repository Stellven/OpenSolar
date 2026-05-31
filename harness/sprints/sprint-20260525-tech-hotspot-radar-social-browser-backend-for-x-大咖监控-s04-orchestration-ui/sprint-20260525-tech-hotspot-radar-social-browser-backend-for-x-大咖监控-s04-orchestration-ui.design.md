# Design — TH Social Browser X S04 Orchestration-UI

epic_id: `epic-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控`
sprint_id: `sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s04-orchestration-ui`
slice: `orchestration-ui`
role: planner
status: planning_complete
generated_at: 2026-05-29T02:25:00Z
knowledge_context: solar-harness context inject used (mirage:timeout → qmd/obsidian/solar_db fallback)
upstream: S02 (5 A-nodes, 7 interface + 7 OQ + data model + compat) + S03 (6 C-nodes, lib/social_browser_backend_x/ + tests with mock-mode)
hard_dependency_blocker: `sprint-20260525-browser-agent-global-operator-cutover` — 真生产 dashboard 数据需 hard_blocker PASS, 本 sprint mock-mode 数据演示 OK
downstream: S05 verification-release

## 0. 切片定位

把 S03 落地核心 (lib/social_browser_backend_x/) 接入 Solar Harness autopilot + DAG 调度 + status UI + pane 可视化 + 运行时证据。复用 HF Paper Insight / YouTube / GHPI S04 同款 C1-C5 模式 (Dashboard / CLI / Config / High Model E2E plan or Autopilot integration / Traceability join), 但本 epic 特化为:
- 没有 high model (ChatGPT 5.5) 直接调用 (本 epic 仅本地 ThunderOMLX semantic extract); 因此 C4 改为 **AutopilotIntegrationPlan** 而非 high model E2E plan
- Dashboard 特化为 X 大咖监控 (200 账号 + 7 indicator + 5 backend by_backend_count + browser_ready 状态 + scan tier1/tier2)
- CLI 已在 S03 C5 落地 (collect-social subcommand), 本 sprint C2 写 CLI 命令树文档 + cron usage + legacy compat
- Config YAML 5 子段: collection (200 accounts seed + tier1/tier2) / extraction (browser fallback) / scoring (per ThunderOMLX) / output (Knowledge raw + AI Influence) / quality (3 gate)

**本 sprint 是规约层 (spec-only)**, 不实施代码, 不真跑 dashboard 数据 (mock 演示 OK)。

## 1. S02 + S03 消费 → S04 节点

| 上游来源 | S04 节点 |
|---------|---------|
| S03 C5 CLI + StatusSurface 实施 | C2 CLI 命令树 spec + C1 dashboard 数据来源 |
| S03 C4 BackendSelector + HardBlockerGuard | C3 Config UI (backend 优先级 + hard_blocker 状态展示) + C4 Autopilot 集成 |
| S02 7 interface | C1 dashboard 数据 binding (StatusSurface 7 indicator) + C2 CLI 5 backend choice |
| S02 OQ-05 Knowledge ingest 顺序 | C3 config output 子段 (raw sync + extracted async) |
| S03 mock-mode policy | C4 Autopilot 集成 (hard_blocker 状态显式展示, autopilot 自动 hold S05 until blocker passed) |

## 2. 5-Node DAG (S04 同款 C1-C5)

```
                  ┌─→ C1 dashboard_renderer_spec (sonnet)  ─┐
                  ├─→ C2 cli_command_tree_spec (glm-5.1)   ─┤
   (S03 ok) ──────┼─→ C3 config_ui_spec (glm-5.1)          ─┼─→ C5 traceability_handoff (glm-5.1, join)
                  └─→ C4 autopilot_integration_plan (sonnet) ─┘
```

Wave 1 (4 并行 write_scope 互斥): C1 / C2 / C3 / C4
Wave 2 (join): C5

## 3. C1-C5 内容大纲

### C1 dashboard_renderer_spec.md (sonnet)
- **X 大咖监控 dashboard 区域**: 200 个账号 + 7 indicator 卡片 (total/enabled/scanned_today/browser_ready/scan_state/parse_fail/fallback_count/by_backend_count)
- **HTML 模板**: 复用 visual-template CSS 变量; X 大咖监控区域嵌入 Tech Hotspot Radar 总览页 (Social Clusters 之后)
- **TUI 模板**: Rich 表格 (Top 10 active 大咖 + 各 backend 占比)
- **数据源**: `lib/social_browser_backend_x/status_surface.py` (S03 C5 落地) + `BackendSelector.last_run_status()`
- **SLO 状态行**: browser_ready (✅/⚠️/❌) + scan tier1/tier2 频率 + parse_fail rate (≥10% 红色)
- **hard_blocker caveat 显示**: 顶部 banner "Browser Agent upstream not ready, running in mock-mode"
- 验收 ≥5

### C2 cli_command_tree_spec.md (glm-5.1)
- **CLI 命令树** (基于 S03 C5 落地):
  ```
  solar-harness wiki tech-hotspot-radar collect-social \
    --backend {browser|rss|manual|x_api|auto} \
    --limit-accounts N \
    [--tier {1,2,both}]
  ```
- **退出码** 0/1/2/3 统一 (per S03 C5)
- **cron usage 示例**: tier1 每 6h / tier2 每 24h (per S02 A1 RateLimiter)
- **legacy compat**: 旧 `collect-social --x-api-token <T>` 路径仍保留 (per S02 A3 phase 1+2 兼容)
- **dry-run mode**: `--dry-run` 不真跑 lease, 仅打印 plan
- 验收 ≥5

### C3 config_ui_spec.md (glm-5.1)
- **YAML config 5 子段** (per S02 A2 + A3):
  1. `collection`: 200 accounts seed + tier1/tier2 separation + global_concurrency=1
  2. `extraction`: browser fallback (lease + rate + screenshot path)
  3. `scoring`: ThunderOMLX semantic (reuse socket, no new instance)
  4. `output`: Knowledge raw + AI Influence report (per OQ-05 raw sync + extracted async)
  5. `quality`: 3 gate (Packet/Insight/Resonance) — 本 epic 复用 HF Paper Insight 同款 gate
- **hot-reload**: atomic write/rename, 不重启
- **rollback env**: `SOLAR_SOCIAL_BROWSER_BACKEND_DISABLE=1` (per S02 A3)
- **per-provider config**: browser_agent (mock fixture path / lease timeout) / rss feed list / manual_curated import path / x_api token (optional)
- 验收 ≥4

### C4 autopilot_integration_plan.md (sonnet)
- **替代 HF Paper / YouTube S04 中的 high_model_e2e_plan** (本 epic 无 ChatGPT 5.5 调用)
- **Autopilot 集成**:
  - chain-watcher: 检测到 hard_blocker (browser-agent-global-operator-cutover:passed) 自动 unblock S05 真 e2e
  - graph-scheduler dispatch: S05 V1 真 e2e 节点的 `required_node_id=sprint-20260525-browser-agent-global-operator-cutover` `required_node_status=passed`
  - autopilot tick: tier1 大咖 P0 每 6h 触发, tier2 每 24h
- **5-phase autopilot flow** (per S02 A1 RateLimiter + per_account_cooldown):
  - Phase 1 prep: lease 可申请 + HardBlockerGuard 通过
  - Phase 2 trigger: 进入 ready_accounts (cooldown 已过)
  - Phase 3 call: BrowserLeaseClient 6 op (open/wait/scroll/dom_extract/screenshot/release)
  - Phase 4 verify: PostExtractor 11 字段 + DedupQueue + social_posts insert
  - Phase 5 failure: 5 failure mode (lease_fail/login_required/parse_fail/rate_429/dom_change) → 各自 fallback path
- **本节点只写 plan, 不真启 autopilot** (留 S05)
- 验收 ≥5

### C5 traceability_handoff.md (glm-5.1, join)
- traceability.json 12 字段 + S05 启动包
- S05 启动包 checklist (5 测试矩阵):
  1. DASHBOARD: 真渲染 + 7 indicator 验证
  2. CLI: 5 backend + 4 exit code 真跑
  3. CONFIG: 5 YAML 子段 hot-reload + rollback flag
  4. AUTOPILOT: tier1/tier2 调度真触发 (mock-mode)
  5. **HARD_BLOCKER_TRUE_E2E**: hard_blocker PASS 后才能跑 V1 真 e2e
- S01 10 outcomes + S02 5 A-nodes + S03 6 C-nodes 全回归
- 5 OQ-C5 carried-over (本 sprint 新发现) — 留 S05 跟踪

## 4. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| C1 | sonnet | dashboard X 大咖特化 + hard_blocker banner 需 reasoning |
| C2 | glm-5.1 | CLI 命令树模板化 |
| C3 | glm-5.1 | YAML config 5 子段填空 |
| C4 | sonnet | Autopilot 集成 + 5-phase + HardBlockerGuard 触发需 reasoning |
| C5 | glm-5.1 | traceability + handoff 模板化 |

## 5. Stop Rules

- 不实施代码 (本 sprint 是规约层)
- 不真跑 browser_agent (hard_blocker 未 PASS)
- 不真启 autopilot (本 sprint C4 只写 plan, 留 S05)
- 不真渲染 dashboard 数据 (mock 演示 OK)
- 不绕 X 风控 / 登录
- 不启第二套 Browser / DeepResearch
- 不新起 ThunderOMLX 实例
- 不打印 cookie/token/session
- 不主动 close 父 epic
- 不绕 planner 直派 builder
- 不用乐观词

## 6. 与 S03 / S05 接力

- S03 完成 → 本 sprint 消费 S03 7 interface (S03 ok 才能 dispatch 本 sprint)
- 本 sprint passed → S05 V1-V6 启动 (V1 真 e2e 仍需 hard_blocker PASS)
- S05 启动包必须含: 4 测试矩阵 (DASHBOARD/CLI/CONFIG/AUTOPILOT) + 1 hard_blocker gate (V1 真 e2e)

## 7. Knowledge Context

S03 6 C-node design + handoff (lib/social_browser_backend_x/ 子包) + S02 5 A-node (7 interface + 7 OQ) + S01 4 N-node (10 outcomes) + PRD (10 AC + 7 indicator) + contract = self-contained。mirage degraded → QMD/Obsidian/Solar DB fallback。
