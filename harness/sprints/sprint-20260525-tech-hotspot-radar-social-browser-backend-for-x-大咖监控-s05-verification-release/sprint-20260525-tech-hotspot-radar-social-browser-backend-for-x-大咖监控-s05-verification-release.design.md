# Design: PRD: 验证、回归与发布证据

sprint_id: `sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s05-verification-release`
status: planning_complete
generated_at: 2026-05-29T13:42:00Z
source_of_truth: compiled PRD / contract / task_graph

## 目标

- 将编译型需求推进为可执行 planner contract。

## 设计原则

- Requirement IR / compiled contract 仍是事实源，planner 产物只做执行视图。
- 不绕过 `task_graph.json` 直接派 builder。
- 每条 requirement / acceptance 都必须能映射到节点和验证门。
- capability capsule 与 logical operator 绑定必须保留，不能在 planner 层丢失。

## 执行面分层

- **Planning layer**: `S1` 锁定实现边界与文件范围。
- **Implementation layer**: `S2` 做受约束实现，严格限制在声明写范围。
- **Verification layer**: `S3` 输出测试与证据。
- **Review layer**: `S4` / `S5` 负责 verifier 决策与 rollout note。

## 逻辑算子 / capsule 绑定

- `V1_browser_smoke_cli_status` / `N/A` / `N/A` / `N/A`: 基于已完成的 S03 core-runtime 与 S04 kickoff package，执行首轮真实 smoke：验证 collect-social CLI 入口、BackendSelector auto/browser 路径、StatusSurface 7 指标 JSON、browser hard-blocker 已 passed 时的 gate 行为，并产出首批 evidence JSON 与 V1 handoff。允许在 verification scope 内补最小测试/可观察性代码，但不得引入新的付费依赖。
- `V2_collection_dedup_semantic_knowledge` / `N/A` / `N/A` / `N/A`: 围绕 browser-collected social posts 验证数据落盘与后处理：同账号重复扫描 dedup、生效的 local semantic extract/ledger/Knowledge raw 入队，以及 failed account 不扩散到整批。若需要，仅允许补本地 queue/ledger 证据，不引入 premium 模型调用。
- `V3_dashboard_config_autopilot_matrix` / `N/A` / `N/A` / `N/A`: 根据 S04 kickoff package 真实验证 dashboard/config/autopilot 三条矩阵：dashboard 指标与 blocker banner、config hot-reload 与 rollback flag、autopilot mock-mode tier1/tier2 调度与 chain-watcher unblock 语义。允许补最小 dashboard/status 观测实现，但不主动关父 epic。
- `V4_regression_negative_controls` / `N/A` / `N/A` / `N/A`: 聚合回归与负控：对齐 S01 10 outcomes、S02 5 A-nodes、S03 6 C-nodes、S04 C1-C5 kickoff package，并新增 no-x-api default、no extra Browser system、no extra ThunderOMLX instance 三类负控证据。
- `V5_release_docs_closeout_prep` / `N/A` / `N/A` / `N/A`: 编写 release docs / eval / closeout prep：总结 V1-V4 证据、记录 rollback、列出 5 条 OQ-C5 carried-over 的最终去向，并为父 epic 保留未闭环项说明。不得主动 close 父 epic。
- `V6_join_epic_close_ready` / `N/A` / `N/A` / `N/A`: 聚合 V1-V5，写最终 handoff 与 traceability，标记 parent_check_ready 条件，但不主动 close 父 epic；父 epic 关闭仍由 epic_decomposer / projection closeout 处理。

## 产物边界

### Write Scope
- `docs/social-browser-backend-x/RELEASE.md`
- `reports/social-browser-backend-x/s05-acceptance/V1-cli_auto.json`
- `reports/social-browser-backend-x/s05-acceptance/V1-cli_browser.json`
- `reports/social-browser-backend-x/s05-acceptance/V1-hard_blocker_gate.json`
- `reports/social-browser-backend-x/s05-acceptance/V1-pipeline_smoke.json`
- `reports/social-browser-backend-x/s05-acceptance/V1-status_surface.json`
- `reports/social-browser-backend-x/s05-acceptance/V2-dedup.json`
- `reports/social-browser-backend-x/s05-acceptance/V2-failure_isolation.json`
- `reports/social-browser-backend-x/s05-acceptance/V2-knowledge_raw.json`
- `reports/social-browser-backend-x/s05-acceptance/V2-model_call_ledger.json`
- `reports/social-browser-backend-x/s05-acceptance/V2-semantic_pipeline.json`
- `reports/social-browser-backend-x/s05-acceptance/V3-autopilot_mock.json`
- `reports/social-browser-backend-x/s05-acceptance/V3-config_reload.json`
- `reports/social-browser-backend-x/s05-acceptance/V3-dashboard.json`
- `reports/social-browser-backend-x/s05-acceptance/V3-unblock_idempotency.json`
- `reports/social-browser-backend-x/s05-acceptance/V4-negative_controls.json`
- `reports/social-browser-backend-x/s05-acceptance/V4-regression_report.json`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s05-verification-release.V1-handoff.md`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s05-verification-release.V2-handoff.md`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s05-verification-release.V3-handoff.md`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s05-verification-release.V4-handoff.md`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s05-verification-release.V5-handoff.md`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s05-verification-release.eval.json`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s05-verification-release.eval.md`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s05-verification-release.handoff.md`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s05-verification-release.traceability.json`

### Read Scope
- `docs/social-browser-backend-x/C1-dashboard-renderer-spec.md`
- `docs/social-browser-backend-x/C3-config-ui-spec.md`
- `docs/social-browser-backend-x/C4-autopilot-integration-plan.md`
- `docs/social-browser-backend-x/RELEASE.md`
- `harness/lib/social_browser_backend_x/**`
- `harness/scripts/tech_hotspot_radar.py`
- `harness/state/tech-hotspot-radar/**`
- `harness/tests/test_hard_blocker_guard.py`
- `harness/tests/test_pipeline_mock.py`
- `harness/tests/test_social_browser_backend_x.py`
- `reports/social-browser-backend-x/s05-acceptance/**`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements.traceability.json`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s02-architecture.traceability.json`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s03-core-runtime.handoff.md`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s04-orchestration-ui.handoff.md`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s04-orchestration-ui.traceability.json`
- `sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s05-verification-release.V5-handoff.md`

## requirement 映射

- `R1` -> V4_regression_negative_controls
- `R10` -> V3_dashboard_config_autopilot_matrix, V4_regression_negative_controls, V5_release_docs_closeout_prep, V6_join_epic_close_ready
- `R2` -> V1_browser_smoke_cli_status
- `R3` -> V1_browser_smoke_cli_status
- `R4` -> V2_collection_dedup_semantic_knowledge
- `R5` -> V2_collection_dedup_semantic_knowledge
- `R6` -> V2_collection_dedup_semantic_knowledge
- `R7` -> V2_collection_dedup_semantic_knowledge
- `R8` -> V1_browser_smoke_cli_status, V2_collection_dedup_semantic_knowledge, V3_dashboard_config_autopilot_matrix
- `R9` -> V1_browser_smoke_cli_status, V3_dashboard_config_autopilot_matrix, V4_regression_negative_controls

## 风险

- 当前 sprint 先前只有 PRD / contract / task_graph，没有稳定的 planner 视图，容易导致 workflow_guard 与 acceptance closeout 对状态理解不一致。
- review 失败应优先回退到 planner，而不是误派 builder。
- `task_graph` 中的 capability capsule 必须与 runtime operator surface 保持一致，否则后续 builder 会出现旁路执行。

## 成功标志

- 设计/计划/任务图一致并可路由到 builder_main。
