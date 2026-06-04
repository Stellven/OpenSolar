# Design: PRD: 调度、自动化与可视化

sprint_id: `sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s04-orchestration-ui`
status: planning_complete
generated_at: 2026-05-29T15:12:39Z
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

- `O1_ready_activation_and_route` / `N/A` / `N/A` / `N/A`: 落地 epic child activation 与 orchestration route 绑定：实现 AI Influence YouTube 报告流子 sprint ready activation、route_role 归一化、dependency blocker surface 与 parent/child status projection，确保 S03/S04/S05 只能按依赖自动激活，不允许绕过 planner。外部依赖一律使用 fixture 或 mock。
- `O2_status_surface_dashboard` / `N/A` / `N/A` / `N/A`: 落地报告流 status surface 与 dashboard payload：输出 run summary、quality gate counts、group_type 分布、Browser Agent phase 状态、validator/archive 状态、blocked reason、capability usage 和 reader-facing artifact availability，并提供 status-server/dashboard 所需 JSON surface。禁止暴露 raw refs、video_id 和内部 pipeline 字段。
- `O3_pane_evidence_and_handoff` / `N/A` / `N/A` / `N/A`: 落地 pane 级可视化与运行时证据：实现 progress timeline、active phase banner、evidence ledger summary、chapter-level worklog、join-gate issues 与 handoff artifact registration，确保 pane 输出不再只是自然语言声称完成，而是能回链到 eval/handoff/status artifact。
- `O4_archive_automation_controls` / `N/A` / `N/A` / `N/A`: 落地自动化与安全控制 seam：实现 report archive queue、email/report delivery dry-run contract、ChatGPT project archive request stub、capability token / blocker banner / mock-mode policy，并保证无密钥时优雅降级、不给出假成功。所有外部动作仅做 stub、fixture 或 dry-run。
- `O5_orchestration_release_join` / `N/A` / `N/A` / `N/A`: 完成 orchestration-ui release join：汇总实现模块、status/dashboard/pane/archive seams、测试覆盖、compat 边界与未闭环项，产出 handoff 与 traceability，使 S05 能基于 S03+S04 直接搭建 verification matrix，而不是再次回到口头对齐。

## 产物边界

### Write Scope
- `/Users/lisihao/.solar/harness/lib/accepted-artifact-export.py`
- `/Users/lisihao/.solar/harness/lib/ai_influence_youtube_report/archive_controls.py`
- `/Users/lisihao/.solar/harness/lib/ai_influence_youtube_report/automation_policy.py`
- `/Users/lisihao/.solar/harness/lib/ai_influence_youtube_report/epic_projection.py`
- `/Users/lisihao/.solar/harness/lib/ai_influence_youtube_report/orchestration.py`
- `/Users/lisihao/.solar/harness/lib/ai_influence_youtube_report/pane_surface.py`
- `/Users/lisihao/.solar/harness/lib/ai_influence_youtube_report/status_surface.py`
- `/Users/lisihao/.solar/harness/scripts/tech_hotspot_radar.py`
- `/Users/lisihao/.solar/harness/status-server/research_routes.py`
- `/Users/lisihao/.solar/harness/tests/test_ai_influence_youtube_report_archive_controls.py`
- `/Users/lisihao/.solar/harness/tests/test_ai_influence_youtube_report_automation_policy.py`
- `/Users/lisihao/.solar/harness/tests/test_ai_influence_youtube_report_dashboard_payload.py`
- `/Users/lisihao/.solar/harness/tests/test_ai_influence_youtube_report_epic_projection.py`
- `/Users/lisihao/.solar/harness/tests/test_ai_influence_youtube_report_handoff_registration.py`
- `/Users/lisihao/.solar/harness/tests/test_ai_influence_youtube_report_orchestration.py`
- `/Users/lisihao/.solar/harness/tests/test_ai_influence_youtube_report_orchestration_release.py`
- `/Users/lisihao/.solar/harness/tests/test_ai_influence_youtube_report_pane_surface.py`
- `/Users/lisihao/.solar/harness/tests/test_ai_influence_youtube_report_status_surface.py`

### Read Scope
- `docs/ai-influence-youtube-report/A1-layering-failure-recovery.md`
- `docs/ai-influence-youtube-report/A2-interfaces.md`
- `docs/ai-influence-youtube-report/A3-data-model.md`
- `docs/ai-influence-youtube-report/A4-compat-migration.md`
- `sprints/epic-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收.epic.md`
- `sprints/epic-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收.task_graph.json`
- `sprints/epic-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收.traceability.json`
- `sprints/sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s03-core-runtime.design.md`
- `sprints/sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s03-core-runtime.handoff.md`
- `sprints/sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s03-core-runtime.plan.md`
- `sprints/sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s03-core-runtime.traceability.json`
- `sprints/sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s04-orchestration-ui.contract.md`
- `sprints/sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s04-orchestration-ui.prd.md`

## requirement 映射

- `O1` -> O1_ready_activation_and_route, O5_orchestration_release_join
- `O2` -> O1_ready_activation_and_route
- `O3` -> O2_status_surface_dashboard, O5_orchestration_release_join
- `O4` -> O2_status_surface_dashboard
- `O5` -> O3_pane_evidence_and_handoff
- `O6` -> O4_archive_automation_controls, O5_orchestration_release_join
- `O7` -> O4_archive_automation_controls, O5_orchestration_release_join

## 风险

- 当前 sprint 先前只有 PRD / contract / task_graph，没有稳定的 planner 视图，容易导致 workflow_guard 与 acceptance closeout 对状态理解不一致。
- review 失败应优先回退到 planner，而不是误派 builder。
- `task_graph` 中的 capability capsule 必须与 runtime operator surface 保持一致，否则后续 builder 会出现旁路执行。

## 成功标志

- 设计/计划/任务图一致并可路由到 builder_main。
