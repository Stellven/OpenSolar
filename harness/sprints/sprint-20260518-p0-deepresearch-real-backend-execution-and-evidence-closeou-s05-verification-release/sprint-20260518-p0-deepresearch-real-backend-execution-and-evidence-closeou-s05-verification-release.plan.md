# Plan — S05 验证、回归与发布证据

sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s05-verification-release`
slice: `verification-release`
date: 2026-05-19
Knowledge Context: solar-harness context inject used

## 1. 总体策略

S05 = 验证 + 收口。**不写运行时代码**（lib/research/、status-server、tools/、ui/、core/ 主路径都不动）。

允许写入：
- `~/.solar/harness/sprints/<sid>.*` （本切片自己的产物）
- `/Users/lisihao/Solar/tests/` （仅加测试，不改既有测试逻辑）
- `/Users/lisihao/Solar/harness/status-server/static/livework_panel.js` （**仅 N3 重应用 S04 N6 被回退的编辑**）
- `/Users/lisihao/Solar/reports/` （样例输出 + release-evidence 报告）
- `/Users/lisihao/Solar/README.md` （仅添加 DeepResearch 章节引用）
- `/Users/lisihao/Solar/tests/fixtures/` （local-command JSON fixture）

禁止：
- 改 `/Users/lisihao/Solar/harness/lib/research/`
- 改 `/Users/lisihao/Solar/harness/status-server/*.py` 与 `tools/*.py`
- 改 `/Users/lisihao/Solar/core/ui/dashboard.ts`
- 提交 API key / OAuth token / model_usage.jsonl 私密内容到 git

## 2. 并行 / 串行布局

```
Layer 1 (并行 4 节点 — write_scope 不重叠):
  N1 regression-tests   [read-only]
  N2 negative-controls  [tests/research/integration/test_negative_controls.py]
  N3 livework-repair    [harness/status-server/static/livework_panel.js]
  N4 secret-scan        [sprints/*.secret-scan.txt]

Layer 2 (依赖 N3):
  N5 ui-proxy-curl      [sprints/*.ui-proxy-curl.txt]

Layer 3 (依赖 N1+N2+N3+N4+N5):
  N6 controlled-sample  [reports/deepresearch-sample-{sid}/]
  N7 chief-editor-real  [reports/survey-chief-editor-sample-{sid}/]
  N8 fixture-realpath   [tests/research/integration/test_local_command_fixture.py, tests/fixtures/local_command_usage.json]

Layer 4 (依赖 N6+N7+N8):
  N9 report-readme      [reports/release-evidence-{sid}.md, README.md]
  N10 activation-proof  [sprints/*.activation-proof.md]

Layer 5 (Gate G_S05_RELEASE, 依赖 N1..N10 全 passed):
  N11 handoff           [sprints/*.handoff.md]
```

Gate `G_S05_RELEASE` = N1..N10 全 passed → N11 才能写 handoff。

## 3. 节点验收 Gate (含证据命令)

| Node | 验收 Gate | 证据命令 |
|------|-----------|----------|
| N1 | `pytest tests/research/integration/ tests/ui/ -q` 退出 0；两套总数 >= 40 (S03 10 + S04 30) | `cd /Users/lisihao/Solar && python3 -m pytest tests/research/integration/ tests/ui/ -q` |
| N2 | 3 类负控测试全 pass: schema 非法 raise / backend 无 usage 强制 estimated=true / 缺 footer 字段被 evaluator 命中 | `cd /Users/lisihao/Solar && python3 -m pytest tests/research/integration/test_negative_controls.py -q` (>=3 passed) |
| N3 | `wc -l harness/status-server/static/livework_panel.js` >= 130 且 `grep -cE 'badge-fallback\|formatStateTransition\|formatResearchMetrics' static/livework_panel.js` >= 3 | `cd /Users/lisihao/Solar && wc -l harness/status-server/static/livework_panel.js && grep -cE 'badge-fallback\|formatStateTransition\|formatResearchMetrics' harness/status-server/static/livework_panel.js` |
| N4 | `secret-scan.txt` 文件存在；扫描结果 `MATCHES=0` 或所有命中已在 handoff 风险段标注 | `grep -rEn '(AIza\|sk-\|hf_\|ghp_\|xoxb-\|api[_-]?key|oauth_token)' ~/.solar/harness/sprints/sprint-20260518-p0-deepresearch* /Users/lisihao/Solar/reports/ 2>/dev/null | tee ${sid}.secret-scan.txt; echo MATCHES=$(wc -l < ${sid}.secret-scan.txt)` |
| N5 | curl /research/<sid> 返回 200 + JSON 含 5 字段 (`usage_source`/`estimated`/`fallback_reason`/`state`/`fallback_level`)；或 fallback 单元测试覆盖 4 级映射 | `python3 harness/tools/solar-status-server.py & sleep 2; curl -s localhost:<port>/research/${sid} | jq 'has("usage_source") and has("estimated") and has("fallback_reason") and has("state") and has("fallback_level")'` |
| N6 | reports/deepresearch-sample-{sid}/ 含 final.md + research_execution_metrics.json + model_usage.jsonl；final.md 含 4 footer 字段精确文本；max_results <= 3 | `cd /Users/lisihao/Solar && python3 -m harness.lib.research.cli --topic "<受控 topic>" --max-results 3 --out reports/deepresearch-sample-${sid}/; grep -c 'Document word count\\|Total token consumption\\|Token usage source\\|Token usage estimated' reports/deepresearch-sample-${sid}/final.md` >= 4 |
| N7 | reports/survey-chief-editor-sample-{sid}/ 含 final.md + survey_execution_metrics.json；real path: usage_source=provider_usage_ledger；fallback path: usage_source=estimated + fallback_reason 明确 | `cd /Users/lisihao/Solar && python3 -m harness.lib.research.survey.chief_editor --backend claude-cli --model opus --topic "<受控>" --out reports/survey-chief-editor-sample-${sid}/ 2>&1 | tee reports/survey-chief-editor-sample-${sid}/run.log; jq '.usage_source, .estimated, .fallback_reason' reports/survey-chief-editor-sample-${sid}/survey_execution_metrics.json` |
| N8 | test_local_command_fixture.py 至少 2 test 覆盖: ①真 usage JSON → usage_source=provider_usage_ledger / estimated=false；②fixture 无 usage 字段 → 必须 raise 或 estimated=true | `cd /Users/lisihao/Solar && python3 -m pytest tests/research/integration/test_local_command_fixture.py -v` (>=2 passed) |
| N9 | release-evidence-{sid}.md 含 8 段: 概要 / 测试结果 / 真实样例 / fixture 路径 / 4 字段 / secret-scan / 降级原因 / 未闭环；README.md 含 deepresearch 章节锚点 | `grep -c '^## ' /Users/lisihao/Solar/reports/release-evidence-${sid}.md` >= 8 && `grep -c 'deepresearch\\|DeepResearch' /Users/lisihao/Solar/README.md` >= 1 |
| N10 | activation-proof.md 含 epic_status_matrix 输出 + 父 epic 5 子 sprint 全 passed | `solar-autopilot-monitor --epic-status-matrix --epic epic-20260518-... 2>&1 \| tee sprints/${sid}.activation-proof.md; grep -c 'passed' sprints/${sid}.activation-proof.md` >= 5 |
| N11 | handoff.md 含 5 二级段 (证据表 / 上游依赖 / 下游影响 / 未闭环项 / 父 epic 收口)；证据表 7 列 | `grep -c '^## ' sprints/${sid}.handoff.md` >= 5 |

## 4. Write Scope 矩阵（并行安全）

| Node | Write Scope | Read Scope |
|------|-------------|------------|
| N1 | （只读） | `/Users/lisihao/Solar/tests/research/integration/`, `/Users/lisihao/Solar/tests/ui/` |
| N2 | `/Users/lisihao/Solar/tests/research/integration/test_negative_controls.py` | `harness/lib/research/{schema_adapter,fallback_policy,report_metrics}.py` (只读) |
| N3 | `/Users/lisihao/Solar/harness/status-server/static/livework_panel.js` | sprint-20260518-...s04-orchestration-ui.N6-handoff.md (重应用参考) |
| N4 | `sprints/${sid}.secret-scan.txt` | `sprints/` + `/Users/lisihao/Solar/reports/` |
| N5 | `sprints/${sid}.ui-proxy-curl.txt` | N3 产物, harness/status-server/research_routes.py (只读) |
| N6 | `/Users/lisihao/Solar/reports/deepresearch-sample-${sid}/` | harness/lib/research/cli.py (只读) |
| N7 | `/Users/lisihao/Solar/reports/survey-chief-editor-sample-${sid}/` | harness/lib/research/survey/chief_editor.py (只读) |
| N8 | `/Users/lisihao/Solar/tests/research/integration/test_local_command_fixture.py`, `/Users/lisihao/Solar/tests/fixtures/local_command_usage.json` | harness/lib/research/schema_adapter.py (只读), N6/N7 产出 |
| N9 | `/Users/lisihao/Solar/reports/release-evidence-${sid}.md`, `/Users/lisihao/Solar/README.md` | N1..N8 全部 |
| N10 | `sprints/${sid}.activation-proof.md` | epic.task_graph.json, status.json |
| N11 | `sprints/${sid}.handoff.md` | 全部 |

**冲突检查**：N1..N10 write_scope 互不重叠（N1 只读；N2 vs N8 测试文件不同名；N3 vs N9 写不同目录）→ 并行安全。

## 5. 模型选择

| Node | 模型 | 理由 |
|------|------|------|
| N1 | sonnet | 直接跑 pytest 解析输出 |
| N2 | sonnet | 写测试（schema 边界） |
| N3 | sonnet | UI/JS 重实现（badge-fallback 4 级） |
| N4 | sonnet | grep regex 设计 |
| N5 | sonnet | curl + jq 验证 |
| N6 | sonnet | 调 CLI 受控样例 + 解析产物 |
| N7 | sonnet | 调 CLI + 处理 OAuth/限额 fallback |
| N8 | sonnet | fixture 构造 + jsonschema 测试 |
| N9 | sonnet | 中文报告 + README 章节 |
| N10 | sonnet | epic_status_matrix 输出处理 |
| N11 | sonnet | 中文 handoff 证据表 |

## 6. 真实 vs Fixture 强制规则（PRD #3 #4 #5）

- **N6 必须真跑** solar-deepresearch CLI（max_results<=3）。如果 Serper key 不可用，**必须**降级到 internal_mirage 真跑一次，不允许跳过到纯 fixture。
- **N7 必须尝试** survey-chief-editor --backend claude-cli --model opus。失败必须把 stderr + fallback 写入 handoff，**不允许**假装通过。
- **N8 必须用 fixture 验证 real-usage 读取路径**（PRD 强制：至少一个测试或样例证明 provider_usage_ledger 能被 report_metrics 读取）。
- **任何节点的产物 footer 含 estimated=true 但 usage_source=provider_usage_ledger** → 立即 FAIL（伪装真实 token，design §6 明令禁止）。

## 7. 安全约束（PRD 验收 #4）

- N4 secret-scan 是硬卡点。命中 API key / OAuth token / 完整 usage ledger 私密内容 → handoff 风险段强制标注，**N9 release-evidence 必须显式声明清理动作或留 follow-up**。
- 报告引用 `model_usage.jsonl` 路径时，**不嵌入完整内容**，只贴 head/tail 摘要 + 行数。
- N7 OAuth 失败的 stderr 如含 token 片段，先脱敏再写 handoff。

## 8. HTML 渲染兜底

planning.html / prd.html 渲染优先级：pandoc → python markdown → cmark → 最简 `<pre>` 兜底。若全失败，写入 handoff 风险段并仍标 N5 节点 passed（artifact 退化路径）。

## 9. 失败回退路径

- N1 失败 → 区分 S03 vs S04 失败源；S03 失败回写到 S03 followup（不在本 sprint 修），handoff 标 "回归失败"；S04 失败由本 sprint N3 / N5 收。
- N5 status-server 起不来 → 改单元测试覆盖 `_derive_fallback_level` 4 级映射（fixture 路径），handoff 注明 curl 未验证。
- N6 + N7 双双失败 + N8 fixture 通过 → 本 sprint 不能 passed (PRD #4 必须真跑受控样例)；写 followup sprint。
- N4 发现泄漏 → 阻塞 G_S05_RELEASE 直到用户决定处理方式。

## 10. 完成定义 (DoD)

1. N1..N11 全 passed
2. `solar-harness graph-scheduler validate` 退出 0
3. handoff.md 中文证据表 7 列每行有真实命令输出截断
4. 至少一个产物（N6 或 N7）含 4 footer 字段精确文本
5. N8 测试 ≥ 2 passed，覆盖真 usage 读路径
6. secret-scan 通过或泄漏已被标注
7. status.json artifacts 含 `design`, `plan`, `task_graph`, `planning_html`, `prd_html`, `handoff`
8. **未修改** `harness/lib/research/`, `harness/status-server/*.py`, `tools/*.py`, `core/ui/dashboard.ts`（用 `git -C /Users/lisihao/Solar diff --name-only` 验证）

## 11. 与父 epic 收口

- 父 epic `epic-20260518-...closeou` 在 N11 handoff passed 后由 evaluator 触发关闭。
- N10 必须产出 `epic_status_matrix`，5 子 sprint 全 `passed`：S01_requirements ✓ / S02_architecture ✓ / S03_core_runtime ✓ / S04_orchestration_ui ✓ / S05_verification_release (本 sprint, 待 passed)。
