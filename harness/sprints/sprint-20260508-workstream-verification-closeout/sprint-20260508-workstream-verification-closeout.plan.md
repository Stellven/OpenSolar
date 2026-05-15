---
sprint_id: sprint-20260508-workstream-verification-closeout
plan_for: planner_then_builder_main
plan_version: 1
priority: P0
lane: reliability
related_prd: /Users/lisihao/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.prd.md
related_contract: /Users/lisihao/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.contract.md
related_matrix_md: /Users/lisihao/.solar/harness/reports/solar-workstream-verification-20260508.md
related_matrix_json: /Users/lisihao/.solar/harness/reports/solar-workstream-verification-20260508.json
related_fix_dispatch: /Users/lisihao/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.fix-dispatch.md
created_at: 2026-05-08T16:55:00Z
created_by: planner
---

# Verification Plan — Solar Workstream Closeout

> 这是一个**只验证 + 派最小修复**的 sprint。**禁止**新增功能、重构、或扩展任何现有 sprint 的 scope。
> 输出顺序: plan.md → 收集证据 → matrix.md/.json → fix-dispatch.md → 更新 status.json → handoff → eval.

## §0 计划要点

| 维度 | 值 |
|------|---|
| 角色 | Planner / Verification Lead |
| 类型 | Closeout reliability sprint (P0) |
| 范围冻结 | 不接受新功能 / 不重构 / 不增 scope |
| 评估方法 | artifact + verify command 双源证据；status 字段不算证据 |
| 修复哲学 | 最小修复，每条 fix 必须含 owner / write scope / verify / rollback |
| 安全边界 | fail-open / secret redaction / 不挂 $HOME / 不写真 Drive |

## §1 已完成证据收集（recon snapshot）

收集时间：2026-05-08T12:22Z（本 sprint 创建后立即跑的 read-only 探针）

### §1.1 服务面

| 服务 | 命令 | 结果 |
|------|------|------|
| status-server `/healthz` | `curl 127.0.0.1:8765/healthz` | `ok` |
| status-server `/status` | `curl 127.0.0.1:8765/status` | JSON 含 current_sprint/panes/main_screen/lab_screen/recent_events/kpi/obsidian_wiki |
| QMD MCP `/health` | `curl localhost:8181/health` | `{"status":"ok","uptime":1446}` |
| `qmd status` | CLI | 1103 indexed, **0 vectors embedded**, 1102 pending |
| `solar-harness wiki status --json` | CLI | configured=true, vault=/Users/lisihao/Knowledge, skills installed (codex/claude/agents)=true |
| `solar-harness wiki qmd-search "Solar Harness Obsidian"` | CLI | 返回 ≥1 命中 (concepts/solar-harness-obsidian-memory.md, score 0.93) |
| `solar-harness mirage doctor --json` | CLI | enabled=true, sdk.kind=none (degraded), drive.status=degraded (no creds), qmd.status=missing (probe bug), 8 mounts |
| `solar-harness wiki capture-server status` | CLI | **status=stopped** url=127.0.0.1:8788 |

### §1.2 Sprint 账本（A1 推迟到 fix-dispatch 创建工具后正式跑）

```
sprint-20260507-010946                  | passed     | E Ej H F P              | OK
sprint-20260507-obsidian-wiki           | passed     | E Ej H F P D            | OK
sprint-20260507-symphony2               | passed     | E Ej H F P              | OK
sprint-20260507-symphony3               | passed     | E Ej H F P              | OK
sprint-20260508-solar-kb-obsidian-...   | reviewing  | H P D (NO eval)         | GAP — 需补 eval (A5)
sprint-20260508-mirage-unified-vfs      | active     | P D (NO handoff-s1/s2)  | GAP — 等 builder (A6)
sprint-20260508-accepted-artifact-...   | queued     | (PRD/contract only)     | OK queued (A7)
sprint-20260508-data-plane-closeout     | queued     | (contract only, no PRD) | OK queued (但缺 PRD)
sprint-20260508-workstream-verification | drafting   | (本 sprint)              | (执行中)
```

字段含义: E=eval.md, Ej=eval.json, H=handoff.md, F=.finalized, P=plan.md, D=design.md

### §1.3 关键事件

- `sprint-20260508-mirage-unified-vfs.events.jsonl` 有 `manual_dispatch_reroute` (severity=warn) at 14:35: GLM API 400 code=1210，S1 从 lab pane 重路由到主屏 builder
- `sprint-20260508-solar-kb-obsidian-autouse.events.jsonl` 有 **3 次 `dispatch_failed`** in 5 分钟内 (12:18-12:23)
- `recent_events` 末段全是 `test-hooks-*` 合成 sprint 的 hook_failed (severity=warn) — 这是测试夹具在污染 status 信号

### §1.4 Pane 现状

```
solar-harness:0  PM/Planner/Builder/Evaluator (active/active/active/active)
  - Builder pane assignment=mirage-unified-vfs，artifact=missing  ← 仍在写代码
  - PM pane artifact=present
  - Planner/Evaluator artifact=N/A（正常，planner 写 plan，evaluator 写 eval，无独立 artifact tracker）

solar-harness-lab:0  4 lab builders (active/idle/idle/active)
  - 全部 assignment 为空，但 artifact 字段还指向 obsidian-wiki-lab/* (历史污染)
```

## §2 验证矩阵生成步骤

### Step 1 — 写 plan.md ✅ (本文件)

### Step 2 — 生成 matrix.md / matrix.json

按 A1-A10 逐条评估：

| AC | Workstream | 评估方法 | 来源证据 |
|----|------------|---------|----------|
| A1 | Sprint Ledger | inline scan 9 sprints + (fix) 创建 verify-workstream-ledger.py 工具 | filesystem + status.json |
| A2 | Obsidian Wiki | wiki status + qmd-search | CLI ok |
| A3 | QMD/MinerU | qmd status + 8181/health | 1103/0 → WARN |
| A4 | Status Server | /healthz + /status keys + recent_events 噪声分析 | 服务 ok，但 test-hooks 噪声需过滤 |
| A5 | Solar KB Autouse | check eval.md/eval.json existence + 跑 contract A1-A7 | **PENDING** — eval 缺失 |
| A6 | Mirage VFS | doctor + handoff-s1/s2 检查 | doctor ok，**handoff 缺失** |
| A7 | Accepted Artifact | contract + status JSON valid | OK queued |
| A8 | Capture Server | capture-server status + _raw dir | **WARN** — server stopped, _raw ok |
| A9 | Pane Orchestration | tmux list-panes + status panes | tmux ok，但 lab artifact 字段陈旧 |
| A10 | Fix Dispatch | 由本计划生成 fix-dispatch.md | (输出) |

输出：
- `/Users/lisihao/.solar/harness/reports/solar-workstream-verification-20260508.md` (人读)
- `/Users/lisihao/.solar/harness/reports/solar-workstream-verification-20260508.json` (机读)

### Step 3 — 生成 fix-dispatch.md

只对 warn/error/pending 派工。预期任务：

| Fix | Owner | 优先级 | Block 关系 |
|-----|-------|--------|-----------|
| F1 — 创建 verify-workstream-ledger.py | builder_main | P0 | 无 |
| F2 — Solar KB autouse 跑契约 A1-A7 + 写 eval.md/eval.json | evaluator | P0 | 无 |
| F3 — Mirage S1/S2 builder 等 handoff 落盘 + 不重启已运行 builder | observer | P1 | 等 GLM/Sonnet 完成 |
| F4 — recent_events 过滤 test-hooks-* 合成 sid | builder_main | P2 | 无 (status-server 小改) |
| F5 — capture-server 决策（启动 vs 文档化为可选） | builder_main | P2 | 无 |
| F6 — data-plane-closeout 缺 PRD 补齐 | codex_pm | P3 | 无 |
| F7 — lab pane artifact 字段陈旧（指向旧 obsidian-wiki-lab）清理 | builder_main | P3 | 无 |
| F8 — mirage doctor `qmd.status=missing` 但 qmd 实际可用，probe 修正 | builder_main (mirage S1 后续) | P2 | 等 S1 完成 |

### Step 4 — 更新 status.json

成功条件分支：
- 如 fix-dispatch 非空 → status=active, phase=verification_matrix_ready, handoff_to=builder_main
- 如全部 PASS/WARN 且无需修复 → status=active, phase=verification_matrix_ready, handoff_to=evaluator

本次必为前者（多个 GAP 已识别）。

### Step 5 — Handoff（推迟到 fix 完成后）

写 `handoff.md` 由 builder_main 在 fix-dispatch 完成后生成，含：
- F1-F8 完成证据
- 重新跑 A1-A10 verify 命令的结果
- evaluator 接收点

### Step 6 — Eval（推迟到 handoff 后）

由 evaluator 写 `eval.md`，最终 verdict=PASS/FAIL。

## §3 写入边界

### §3.1 本 sprint 允许写入

| 文件 | 创建/修改 | 责任人 |
|------|----------|--------|
| `sprint-20260508-workstream-verification-closeout.plan.md` | create | planner ✓ |
| `reports/solar-workstream-verification-20260508.md` | create | planner ✓ |
| `reports/solar-workstream-verification-20260508.json` | create | planner ✓ |
| `sprint-20260508-workstream-verification-closeout.fix-dispatch.md` | create | planner ✓ |
| `sprint-20260508-workstream-verification-closeout.status.json` | update | planner ✓ |

### §3.2 严禁触碰

- **任何**正在运行的 builder pane（main_screen.2, lab_screen.0/3）正在写的文件
- `sprint-20260508-mirage-unified-vfs.lib/*` —— S1/S2 builder 仍在写
- `sprint-20260508-solar-kb-obsidian-autouse.lib/*` —— P0 builder 仍在写（即使 dispatch_failed）
- `~/.claude/hooks/*` —— P0 sprint 拥有
- 真实 Google Drive
- `/Users/lisihao/Knowledge/concepts/`、`/Users/lisihao/Knowledge/projects/` 等正式 wiki 页
- 整个 `/Users/lisihao`（不可挂载）

### §3.3 Fix-dispatch 派工时也必须遵守 §3.2

每条 fix 的 "Write Scope" 字段会精确列出允许触碰的文件。

## §4 Stop Rules

- 评估器**禁止**在没跑 verify 命令的情况下 PASS
- **禁止**用 status 字段当证据
- **禁止**任何 fix 写入真 Google Drive
- **禁止**任何 fix 挂 `/Users/lisihao`
- **禁止**测试写 temp 路径之外（除 `/Users/lisihao/Knowledge/_raw` 显式 smoke test）
- **禁止**在本 closeout 报告产出之前启动新 feature sprint
- 遇到 plan mode 卡住 / GLM 1210 / coordinator 不派发 → 列入 fix-dispatch，**不**自己补救

## §5 Master-Brain 升级条件

| 触发 | 升级动作 |
|------|----------|
| Solar KB autouse 评估真的 FAIL（不是 missing eval） | master brain 决策是否回滚 P0 设计 |
| Mirage S1/S2 builder 24h 内仍无 handoff | master brain 决策切换 builder 模型 / 重派 |
| capture-server 启动会污染 wiki | master brain 决策是否文档化为人工触发 |
| 任何 fix 触发安全边界 stop rule | master brain 立即停 + 重新规划 |

## §6 Definition Of Done

- [ ] plan.md 落盘（本文件）✓
- [ ] matrix.md + matrix.json 落盘 (Step 2)
- [ ] fix-dispatch.md 落盘 (Step 3)
- [ ] status.json 更新到 active/verification_matrix_ready/builder_main (Step 4)
- [ ] 每条 A1-A10 有 status (PASS/WARN/PENDING/FAIL) + artifact + verify cmd
- [ ] 每条 fix 有 owner / write scope / verify / rollback
- [ ] 没有任何 fix 越过 §3.2 边界
- [ ] handoff + eval 在 fix 完成后由后续 builder/evaluator 写

## §7 后续 sequence

```
[本 sprint planner]
   │
   ├─→ plan.md (本文件) ✓
   ├─→ matrix.md/.json (下一步)
   ├─→ fix-dispatch.md
   └─→ status.json: status=active, phase=verification_matrix_ready, handoff_to=builder_main
        │
        └─→ [builder_main]  按 fix-dispatch 跑 F1-F8
              │
              └─→ [evaluator] 重跑 A1-A10 → eval.md/eval.json → PASS/FAIL
                    │
                    └─→ finalized
```
