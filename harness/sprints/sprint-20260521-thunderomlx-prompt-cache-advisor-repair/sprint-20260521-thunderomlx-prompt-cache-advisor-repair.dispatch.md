<solar-runtime-context>
规则: 这是从 append-only session log + unified KB recall 生成的运行时投影；它是当前模型工作集，不是事实源。
pane: solar-harness:0.0 | dispatch_id: d-20260529T192833Z-678220 | session_id: sprint-20260521-thunderomlx-prompt-cache-advisor-repair

# Context Projection: sprint-20260521-thunderomlx-prompt-cache-advisor-repair
Policy: dispatch-default | Tokens: ~1766/1800 | Built: 2026-05-29T19:28:49Z

## Included Events (12)
Event IDs: a0c760b2-6b95-4826-b494-a2e4654609d9, bf14ada7-a713-44a7-ba11-0d8fe33892f4, a1218b84-d196-49f8-9f60-4455f3a0ba9a, 96f43f09-044d-4223-aaf2-bff3c2833cd7, 35427ff5-f6a5-4fd3-98b2-d60c6c3510aa, 5537e9d0-3403-4087-b47f-c9ad34cd0518, b67a271f-30ad-45ff-9a49-95bf0b46d304, 7bf3f2e5-feb1-4c7d-a3c7-54aad0be7874, b8fb3f07-7c53-4610-9d26-c1382863bffe, ac0b065b-c0ec-43c6-8d9b-e269771eaeed, 6541d30f-33a7-4053-9c20-1c3666408420, 12797803-773c-4ba4-b5f9-bdc65f4b7d68

### Event Details (redacted)
```json
{"seq": 4, "type": "activity_succeeded", "actor": "coordinator", "activity_id": "handle_passed_completed:runtime:handle_passed_completed", "payload": {"legacy_event": "handle_passed_completed", "finalized_at": "2026-05-23T14:48:14Z"}}
```
```json
{"seq": 9, "type": "state_transition", "actor": "coordinator", "activity_id": null, "payload": {"from": "", "to": "sprint-20260521-thunderomlx-prompt-cache-advisor-repair:drafting:prd_ready:planner:a6b2874e7232", "round": 1}}
```
```json
{"seq": 11, "type": "command_issued", "actor": "coordinator", "activity_id": "planner_notified:runtime:planner_notified", "payload": {"legacy_event": "planner_notified", "status": "drafting", "target": "", "round": 1}}
```
```json
{"seq": 14, "type": "activity_failed", "actor": "coordinator", "activity_id": "dispatch_failed:solar-harness:0.0:dispatch_failed", "payload": {"legacy_event": "dispatch_failed", "pane": "solar-harness:0.0", "reason": "pane_not_idle", "error": "pane_not_idle"}}
```
```json
{"seq": 16, "type": "command_issued", "actor": "coordinator", "activity_id": "dispatch_queued:runtime:dispatch_queued", "payload": {"legacy_event": "dispatch_queued", "role": "pm", "intent": "pm_prd_fix", "reason": "no_free_worker", "queue_result": "ok", "target": "", "round": 1}}
```
```json
{"seq": 18, "type": "session_started", "actor": "runtime_bridge", "activity_id": null, "payload": {"adopted_at": "2026-05-29T18:43:16Z"}}
```
```json
{"seq": 53, "type": "command_issued", "actor": "runtime_bridge", "activity_id": "legacy-status", "payload": {"status": "active", "phase": "planning_complete", "round": 0}}
```
```json
{"seq": 54, "type": "activity_started", "actor": "runtime_bridge", "activity_id": "legacy-status", "payload": {"status": "active", "phase": "planning_complete", "round": 0}}
```
```json
{"seq": 55, "type": "state_transition", "actor": "runtime_bridge", "activity_id": null, "payload": {"from": "", "to": "active", "phase": "planning_complete", "round": 0}}
```
```json
{"seq": 56, "type": "state_transition", "actor": "graph_scheduler", "activity_id": null, "payload": {"from": "active", "to": "passed", "round": 0}}
```
```json
{"seq": 57, "type": "state_transition", "actor": "graph_scheduler", "activity_id": null, "payload": {"from": "passed", "to": "passed", "round": 0}}
```
```json
{"seq": 59, "type": "state_transition", "actor": "coordinator", "activity_id": null, "payload": {"from": "", "to": "sprint-20260521-thunderomlx-prompt-cache-advisor-repair:active:planning_complete:builder_parallel:6537f3192259", "round": 1}}
```

## Summarized Ranges
- seq 1-3: 3 log_message events summarized
- seq 5-8: 4 log_message events summarized
- seq 10-10: 1 log_message events summarized
- seq 12-13: 2 log_message events summarized
- seq 15-15: 1 log_message events summarized
- seq 17-17: 1 log_message events summarized
- seq 19-52: 34 log_message events summarized
- seq 58-58: 1 log_message events summarized

## Dropped Ranges
- seq 60-77: budget exceeded

## Knowledge Base Hits
- [qmd] obsidian-wiki-integration.md
- [qmd] sprint-20260507-obsidian-wiki-contract.md
- [qmd] solar-harness-obsidian-wiki-integration.md
- [solar_db] solar-harness-obsidian-wiki-integration.md
- [degraded] mirage_path:no_results

## Provenance
This context is a projection over session events.
It does not modify or replace the source event log.
Total events in session: see SessionLog.replay()
</solar-runtime-context>

<!-- SOLAR_STATE_READ_PREFLIGHT -->
## 必须先读状态 (防写入 hook 卡死)

在任何 Write/Edit/handoff/eval/status 更新之前，必须先用 Claude/Codex 的 **Read 工具**读取：

`~/.solar/STATE.md`

不要用 `cat` 替代这一步；本地 `state-read-enforcer.sh` hook 只认 Read 工具标记。

如果 Write/Edit hook 仍阻断，立刻 Read 上面的 STATE 文件后重试原写入一次，不要停在“已读”等待。

---

PRD 门禁未通过：FAIL: 缺少 7 个必需 section:
  - 背景 / Context
  - 用户故事 / User Stories
  - 功能需求 / Requirements
  - 约束 / Constraints
  - 风险 / Risks
  - 开放问题 / Open Questions
  - 架构交接 / Planner Handoff。请补全 ~/.solar/harness/sprints/sprint-20260521-thunderomlx-prompt-cache-advisor-repair.prd.md，保持 status=drafting，然后更新 updated_at 触发 coordinator。

<solar-skills-context>
<!-- auto-generated by solar_skills.py at 2026-05-29T19:28:33Z -->
Solar has 1584 general skills and 38 solar-native skills.

Solar-native skills: a2a-hub, agent, agent-orchestrator, apple-calendar, banner, benchmark, browser-automation, build, clawdwork, commit, docs, email-to-calendar, fast-browser-use, mcp-builder, mode, obsidian-daily, obsidian-direct, office, office-email, office-notes, office-notion, office-reminders, office-tasks, office-trello, phase, pr, report, restore, review, save, skill-creator, skin-check, solar, solar-web, stats, status, test, webapp-testing
</solar-skills-context>

<solar-intent-context>
<!-- auto-generated by solar_skills.py at 2026-05-29T19:28:33Z -->
## Solar Intent Adapter

- intent solar-harness show_dashboard confidence=0.95
  Action: 用户请求查看 Solar 运行状况。
- hint agent-rules-books release-it confidence=0.86
  Action: 建议使用 agent-rules-books: release-it.mini。

## Intent Rules

- 这是旧 Solar intent-engine-hook.sh 的 Harness 适配层；用于 dispatch 前决策提示。
- direct intent 可以改变执行纪律；skill hint 只作为能力注入建议，不覆盖 sprint 合约。
- 命中 learned-db 规则时，优先按学习规则解释用户意图，但必须保留证据。
</solar-intent-context>

<solar-capability-context>
<!-- auto-generated by solar_skills.py at 2026-05-29T19:28:33Z -->
## Auto-selected Solar Capabilities

- ATLAS (repair.pr-cot, failure.structured_repair, routing.complexity_budget)
  Readiness: injectable_only (no executable/effective scorecard yet)
  Why: 任务涉及失败修复、hook/tool 异常、阻塞恢复或复杂度预算。
  Use: 进入 repair 模式：定位失败点，写明证据链，优先做局部修复；不要静默停住或等待人工拍板。
- Everything Claude Code (agent.inventory, command.catalog, rules.catalog, mcp.catalog)
  Readiness: injectable_only (no executable/effective scorecard yet)
  Why: 任务涉及 Claude Code 生态能力盘点、命令/规则/MCP/agent inventory。
  Use: 只读使用 vendor inventory；不要盲装 hooks 或覆盖现有 Solar 规则。
- Solar-Harness Runtime (harness.context_preflight, harness.intent, harness.dispatch_visibility, harness.contracts, harness.dag, harness.status, harness.model_routing)
  Readiness: injectable_only (no executable/effective scorecard yet)
  Why: 任务涉及 Solar-Harness 自身、pane、dispatch、intent engine、DAG、coordinator、status、模型路由或能力可视化。
  Use: 调用 solar-harness-runtime skill：先 context inject + intent match，再用 skills inject / intent summarize / audit / activation-proof 留证据；模型切换只用 solar-harness models 命令。

## Dispatch Rules

- 这些 capability 是自动选择的执行辅助，不替换 Solar coordinator / planner / evaluator。
- Autoresearch 只能作为 pane-level optimizer/advisor；没有用户授权、--execute、清洁/隔离工作树和 bounded max-iterations 时不得自动运行。
- 若 capability 缺失或不可用，必须 fail-open：继续完成主任务，并在 handoff 写明降级证据。
- 遇到失败、超时、hook/tool 异常时，优先触发 ATLAS structured repair，不要停在等待人工决策。
</solar-capability-context>

<solar-knowledge-context>
<solar-unified-context>
来源: Mirage + QMD solar-wiki + Obsidian Vault + Solar DB + RAGFlow(optional)
规则: 开始开发/设计/分析前，优先参考这些命中；如不足，再主动搜索 vault/qmd。
排序: synthesis/concepts/references 优先；raw 只作为证据层靠后。
- [qmd] sprint-20260507-obsidian-wiki-contract.md (qmd://solar-wiki/raw/solar-harness/artifact-ingest/20260508t155745z/harness-sprints/sprint-20260507-obsidian-wiki-contract.md): @@ -17,4 @@ (16 before, 89 after)

Add a Solar Harness integration for `Ar9av/obsidian-wiki` so Solar can configure an Obsidian LLM Wiki vault, export sprint artifacts into `_raw/`, and expose wiki install/status/update/query workflows without disrupting existing sprint automation.

## Source Facts
- [qmd] solar-harness-obsidian-wiki-integration.md (qmd://solar-wiki/references/solar-harness-obsidian-wiki-integration.md): @@ -4,4 @@ (3 before, 35 after)
created: 2026-05-12
tags: [solar-harness, obsidian-wiki, knowledge-base, integration]
source:
  - /Users/sihaoli/.solar/harness/sprints/sprint-20260507-obsidian-wiki.design.md
- [solar_db] solar-harness-obsidian-wiki-integration.md (obsidian:/Users/lisihao/Knowledge/references/solar-harness-obsidian-wiki-integration.md): 

# Solar-Harness Obsidian Wiki 集成

## 一句话

Obsidian Wiki 集成让 Solar-Harness 能安装、检查、导出、查询和桥接一个人可读的 Obsidian vault，使 sprint 产物、上传文档、ChatGPT/网页捕获和 Solar accepted artifacts 能进入长期知识库。

## 做了什么

- `solar-harness wiki install --vault <path>`：安装/配置 vault，写入 Obsidian Wiki 配置，准备 `_raw/solar-harness` staging。

- [qmd] obsidian-wiki-integration.md (qmd://solar-wiki/references/obsidian-wiki-integration.md): @@ -1,4 @@ (0 before, 23 after)
---
title: "Obsidian Wiki Integration"
category: references
tags: [alias, artifact-bridge, knowledge-graph-repair]
降级源: mirage_path:no_results
</solar-unified-context>
</solar-knowledge-context>

<!-- SOLAR_ACK_CONTRACT -->
## Dispatch ACK Contract

确认已读取本 dispatch 并开始处理后，必须立即写 ACK 文件：

`~/.solar/harness/sprints/sprint-20260521-thunderomlx-prompt-cache-advisor-repair.ack-d-20260529T192833Z-678220.json`

可直接执行：

```bash
python3 - <<'PY'
import datetime
import json
from pathlib import Path

ack_path = Path.home() / ".solar" / "harness" / "sprints" / "sprint-20260521-thunderomlx-prompt-cache-advisor-repair.ack-d-20260529T192833Z-678220.json"
ack_path.parent.mkdir(parents=True, exist_ok=True)
ack = {
    "dispatch_id": "d-20260529T192833Z-678220",
    "sid": "sprint-20260521-thunderomlx-prompt-cache-advisor-repair",
    "role": "solar-harness:0.0",
    "status": "in_progress",
    "exit_code": 0,
    "message": "dispatch read and accepted",
    "artifacts": [],
    "wrote_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
}
ack_path.write_text(json.dumps(ack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
```

后续状态更新仍按 sprint 的 status / handoff / evidence 要求执行；ACK 只证明本 dispatch 已被真实读取并接收。
