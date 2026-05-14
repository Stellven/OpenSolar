# Design — Solar-Harness Live-Work Visibility · S05 Verification & Release

Sprint: `sprint-20260514-p0-…-s05-verification-release`
Epic: `epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队`
Slice: `verification-release` (Planner pass)
Author: Solar Planner
Date: 2026-05-14
Knowledge Context: solar-harness context inject used（命中 S03 accepted.md + S01 outcomes — 把 e2e / 负控 / activation-proof 明确划给本切片）

## 1. Problem Framing

S01-S04 已经把 5 outcome 拆成需求 → 架构 → 核心 lib → 路由/UI/hook：

| outcome | S01 spec | S02 arch | S03 lib | S04 接入 | **S05 验证** |
|--------|----------|----------|---------|----------|--------------|
| O1 no-active-work | outcomes.md | layer 4 | `is_idle` | `/api/idle-state` + UI 卡片 | e2e: 无 sprint → 页面"no active work" |
| O2 heartbeat + deadlock | outcomes.md | API + schema | `should_emit_heartbeat / detect_deadlock` | autopilot hook | activation-proof: 真 autopilot tick → 真 events |
| O3 PM-first PRD | outcomes.md | FSM | `intake_state_machine` | POST `/api/requirements` | e2e: 提交需求 → 新 sprint 出现 |
| O4 role next-step | outcomes.md | derived view | `resolve_role` | UI 卡片 | e2e: 每角色 next-step 渲染正确 |
| O5 transition evidence | outcomes.md | events.jsonl | 5 emit_* | UI events-tail | 回归: 5 事件类型全在 tail 可见 |

S05 是**最后一公里**：把"代码写好了"变成"用户真能看到 + autopilot 真跑出证据 + 父 epic 真允许关闭"。

## 2. Slice Boundaries

- **做**：e2e 用户流程脚本 + 负控（lib 异常 → UI 降级真验）+ activation-proof（autopilot 真接 hook 跑 ≥ 30 分钟）+ 回归报告 + 用户文档 + 父 epic close gate + 知识库 raw 写入
- **不做**：新功能、新路由、新 UI 卡片；不重写 lib；不引入新模型（仍 Sonnet）
- **不允许**：用单元测试当 activation-proof；用 mock 假数据冒充真 events；不写 raw knowledge 就声称 epic 完成

## 3. Design Goals

| Goal | Why |
|------|-----|
| **每个 outcome 有 1 条可复现 e2e** | 用户铁律：mock 测试通过 ≠ 真可用；e2e 必须真启 status-server + 真 curl + 真 grep UI |
| **activation-proof 是真的 autopilot 跑** | autopilot 主循环真 source hook、真写 events.jsonl ≥ 30 min；不是单测里 simulate |
| **负控覆盖每个降级路径** | lib 抛异常 / hook runner 死 / events.jsonl 损坏 → UI/autopilot 必须 fail-open |
| **父 epic close 是 gated** | 所有 5 children[*].*_ready=true 才允许 epic.status=closed；planner 不能手动 close |
| **knowledge raw 写入是结尾动作** | accepted.md 写完才算 finalize；后续可被 context inject 检索 |

## 4. Non-Goals

- 不替 lib 写新算法
- 不重写 S04 路由（如发现 shape 不对，回 S04 修，不在 S05 偷偷改）
- 不做性能压测（不是本 epic 目标）
- 不做安全审计（不是本 epic 目标）
- 不做 UI 美化（极简原则）

## 5. Module Map (5 节点交付物)

```text
harness/tests/livework/
├── test_e2e_user_flow.py        ← 5 outcome × happy path e2e
├── test_negative_control.py     ← 5 降级场景（lib 异常 / hook 死 / events 损坏 / shape 错 / 路由 5xx）
└── test_activation_proof_replay.py ← 用 activation-proof 写出的真 events.jsonl 重放断言

harness/autopilot/integration/
└── activation_proof.sh          ← autopilot 真接 hook 跑 ≥ 30 min 的脚本（独立可跑）

~/.solar/logs/
└── livework-activation-proof-<date>.jsonl  ← activation-proof 输出（真 events 记录）

~/.solar/reports/
└── livework-regression-<date>.md  ← pytest + coverage + e2e exit + activation-proof 摘要

~/.solar/docs/
└── livework-user-guide.md       ← 用户文档：怎么用 PM-first PRD、怎么看 status 面板、怎么读 deadlock alert

sprints/
├── <sprint>.handoff.md          ← S05 自身的 handoff（含 evaluator entry）
├── <sprint>.accepted.md         ← knowledge raw（finalize 时由 evaluator/planner 写）
└── <epic>.epic-close-gate.md    ← 父 epic close gate 决策报告（5 children 检查表）
```

## 6. Deliverables

| # | Deliverable | Owner Node | 关键内容 |
|---|-------------|-----------|---------|
| D1 | `test_e2e_user_flow.py` + 真 status-server fixture | N1 | 5 outcome × happy path；启 status-server ephemeral port；curl + grep UI HTML；断言 ≥ 20 |
| D2 | `test_negative_control.py` | N2 | 5 降级场景：(a) lib `is_idle` 抛 → UI 显示 "unknown"；(b) `intake_requirement` 抛 → POST 返 4xx；(c) `detect_deadlock` 抛 → hook exit 0；(d) events.jsonl 损坏 → tail 显示 "events unavailable"；(e) 路由 503 → UI 卡片显示 "degraded"；断言 ≥ 15 |
| D3 | `activation_proof.sh` + 跑 ≥ 30 分钟 + 输出 `~/.solar/logs/livework-activation-proof-<date>.jsonl` + `test_activation_proof_replay.py` 重放验证 | N3 | autopilot fixture 真接 hook；记录 heartbeat + deadlock 命中数；replay test 断言事件类型覆盖率 ≥ 4/5；运行时长 ≥ 1800s |
| D4 | `~/.solar/reports/livework-regression-<date>.md` + `<sprint>.accepted.md`（写到 knowledge raw 入口） | N4 | pytest 总断言数 + exit code + coverage 头部 + e2e 5 outcome 通过表 + activation-proof 摘要 + 知识库 raw accepted.md（供后续 context inject） |
| D5 | `~/.solar/docs/livework-user-guide.md` + `<epic>.epic-close-gate.md` + sprint `handoff.md` + 父 traceability 最终 patch `epic.gates_all_passed=true` | N5 (join) | 用户文档 ≥ 300 行（PM-first PRD 教程 + status 面板说明 + deadlock alert 解读 + FAQ）；epic-close-gate 列出 5 children × *_ready 检查表 + 允许 close 的决策；handoff 含 evaluator entry；父 traceability 仅 patch `epic.gates_all_passed` 字段 |

## 7. DAG Topology

```text
N1 e2e ───────────────┐
N2 negative control ──┤
N3 activation-proof ──┼── N5 docs + epic close gate + handoff
N4 regression report ─┘
```

Layers: `[[N1, N2, N3, N4], [N5]]`

5 节点 2 层；N1-N4 并行（write_scope 互斥）；N5 join。

**关键时间约束**：N3 activation-proof 必须真跑 ≥ 30 分钟；其他节点开发可并行，但 N5 必须等 N3 跑完才能 join。

## 8. Acceptance Contract

| # | Acceptance | 验证 |
|---|------------|------|
| A1 | `test_e2e_user_flow.py` 覆盖 5 outcome × happy path，pytest exit 0，断言 ≥ 20 | pytest |
| A2 | e2e 真启 status-server fixture（非 mock）；curl 真 HTTP + grep 真 UI HTML | grep `@mock` == 0 |
| A3 | `test_negative_control.py` ≥ 5 降级场景全过，断言 ≥ 15 | pytest |
| A4 | activation_proof.sh 真跑 ≥ 1800s（30 min），exit 0；输出 jsonl ≥ 50 行真 events | wc -l + duration log |
| A5 | activation-proof 的 events 至少 4/5 类型覆盖（heartbeat / deadlock_detected / requirement_intake / pm_drafted / role_transition） | grep event types |
| A6 | `test_activation_proof_replay.py` 重放 activation-proof jsonl，断言 ≥ 8 | pytest |
| A7 | `~/.solar/reports/livework-regression-<date>.md` 含：pytest 总断言数 + e2e 5 outcome 表 + coverage 头部 + activation-proof 摘要 | grep |
| A8 | `<sprint>.accepted.md` 写到 sprint 目录（供 mirage_path/QMD 检索），含 sprint_id + 5 outcome 验证结果 + 是否可关闭 epic | ls + grep |
| A9 | `livework-user-guide.md` ≥ 300 行，含 4 section：PM-first PRD 教程 / status 面板说明 / deadlock alert 解读 / FAQ | wc -l + grep section |
| A10 | `<epic>.epic-close-gate.md` 列出 5 children × *_ready=true 检查表 + 显式 go/no-go 决策 | grep |
| A11 | 父 traceability.json `epic.gates_all_passed=true`（仅在所有 children[*].*_ready=true 时） | jq |
| A12 | `pytest harness/tests/livework -v` 全过（S03 + S04 + S05），总断言 ≥ 130 | pytest |
| A13 | git diff: lib/livework / status-server/routes / autopilot/hooks / templates / static 均 == 0（S05 不改实现） | git diff |
| A14 | handoff 不含 "全部功能上线" / "无未闭环" 等 overclaim | grep == 0 |
| A15 | knowledge raw 写入：`<sprint>.accepted.md` 在 `sprints/` 下且能被 `context inject` 检索到（mirage_path 命中） | context inject 验 |

## 9. Stop Rules

- 任何节点修改 `lib/livework/*.py` / `status-server/routes/livework_routes.py` / `autopilot/hooks/livework_heartbeat_*` / `templates/livework_panel.html` / `static/livework_panel.js` → fail（S05 只验证，不改实现；发现 bug 必须开 followup sprint）
- e2e 用 `@mock.patch` 替代真 HTTP → fail
- activation-proof 实际跑时长 < 1800s → fail
- activation-proof 事件类型覆盖 < 4/5 → fail
- 负控未覆盖 5 降级场景 → fail
- N5 在 N1-N4 任一 pending 时 dispatched → graph_scheduler 阻断
- handoff 声称 "无未闭环项" / "全部功能上线" / "epic 完美完成" → fail
- 父 traceability `gates_all_passed=true` 在 children[*].*_ready 有 false 时被写入 → fail
- 用户文档 < 300 行 → fail（说明文档敷衍）

## 10. Parallelism & Write Scope

- **N1**: `harness/tests/livework/test_e2e_user_flow.py`
- **N2**: `harness/tests/livework/test_negative_control.py`
- **N3**: `harness/autopilot/integration/activation_proof.sh`, `harness/tests/livework/test_activation_proof_replay.py`, `~/.solar/logs/livework-activation-proof-<date>.jsonl`（write-once 数据日志）
- **N4**: `~/.solar/reports/livework-regression-<date>.md`, `sprints/sprint-20260514-…-s05-verification-release.accepted.md`
- **N5**: `~/.solar/docs/livework-user-guide.md`, `sprints/epic-20260514-…-epic-close-gate.md`, `sprints/sprint-20260514-…-s05-verification-release.handoff.md`, `sprints/epic-20260514-…traceability.json` (`epic.gates_all_passed` field only)

write_scope 完全互斥。所有 N1-N5 都**不写 lib/routes/templates/hooks**（S05 stop rule）。

## 11. Model Routing

- 所有节点 `sonnet`（GLM 1210 已 5 次 + 验证准确性）
- 禁止 worker webfetch / web search
- 测试 fixture：用真 HTTP server + 真 events.jsonl + tmp_path；禁 `@mock.patch` / `unittest.mock`
- activation-proof 用真 autopilot fixture（可用 systemd-like 轻量进程）

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| activation-proof 30 min 跑不完阻塞 N5 | 节点并行：N1/N2/N4 不等 N3；N3 独立跑；N5 join 时检查 N3 已完成 |
| e2e 在 CI 环境状态不稳（ephemeral port 冲突） | fixture 用 `socket.bind(('',0))` 取空闲端口 + cleanup 必跑 |
| activation-proof 事件类型不全（如 PM 流没触发） | activation_proof.sh 主动触发 5 类事件（模拟用户提交、模拟空闲、模拟死锁），不是被动等 |
| 用户文档 ≥ 300 行变水文 | N5 文档分 4 section（教程 / 面板 / 告警 / FAQ），每 section 用 acceptance 验 |
| 父 epic gate 误判 close（漏检 children） | epic-close-gate.md 必须 jq 5 个 children 字段，硬编码检查表 |
| S05 期间发现 lib bug 想偷偷改 | stop rule + git diff 验；发现 bug 开 followup sprint（在 handoff 中列） |
| activation-proof jsonl 写到生产 events.jsonl 污染 | activation_proof.sh 用独立 `~/.solar/logs/livework-activation-proof-<date>.jsonl`，不写主 events.jsonl |

## 13. Knowledge Context Usage

- `solar-harness context inject` 已执行：命中 S03 accepted.md（确认 e2e/UI 归 S05）+ S01 outcomes（5 outcome 唯一来源）
- S04 handoff.md 是本切片输入：5 路由 curl 示例 + 4 dom-id + autopilot 1 行集成指令
- knowledge raw 入口：`sprints/<sid>.accepted.md` 是 mirage_path 检索目标；写到此处后 context inject 可命中

## 14. Handoff Plan

N5 完成后，handoff.md 必须含：

- 5 outcome × 验证类型 × 通过结果矩阵
- activation-proof 摘要（运行时长 / 事件总数 / 类型覆盖率 / 异常数）
- 用户文档入口：`~/.solar/docs/livework-user-guide.md`
- epic-close-gate 决策结果（go / no-go）
- 已知未闭环项（即使 epic close 也要明确列：UI 权限/i18n、deadlock auto re-dispatch、性能压测、安全审计）
- followup sprint 建议（如 S05 期间发现的 lib bug 列在此）
- `evaluator_can_review: true` + `epic_can_close: true | false`（基于 gate 结果）

## 15. Epic Close Gate 决策模板

```markdown
# Epic Close Gate — epic-20260514-…

## Gate Check (5 children)
- [ ] children[0] s01-requirements.outcomes_ready=true
- [ ] children[1] s02-architecture.architecture_ready=true
- [ ] children[2] s03-core-runtime.core_runtime_ready=true
- [ ] children[3] s04-orchestration-ui.orchestration_ui_ready=true
- [ ] children[4] s05-verification-release.verification_ready=true

## Verification Evidence
- e2e: pytest exit 0, 5 outcome × happy path passed
- negative-control: 5 降级场景全过
- activation-proof: 真跑 <duration>s, 事件 <count>, 覆盖 <ratio>
- regression report: ~/.solar/reports/livework-regression-<date>.md
- user docs: ~/.solar/docs/livework-user-guide.md (≥ 300 行)

## Decision: GO | NO-GO
（仅在 5 个 checkbox 全部 ✅ 且 evidence 完备时填 GO）
```
