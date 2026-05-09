# Implementation Plan — External Integrations Closeout

**Sprint**: sprint-20260508-external-integrations-closeout  
**Role**: planner  
**Inputs**: contract.md (D1-D10), prd.md (R1-R9, OQ1-OQ6), design.md (§1-§10)  
**Created**: 2026-05-08T15:35:00Z

## §0 总览

7 stage 串行 + 局部并行；S1 root-cause 是所有写操作的前置阻断；S2-S7 在 S1 出报告后可拆分。

```
S1 (root-cause)  ─→  S2 (schema lock)  ─┬─→  S3 (UI Tab)
                                         ├─→  S4 (upload ingest fix)
                                         ├─→  S5 (boundaries)
                                         ↓
                                   S6 (tests)  ─→  S7 (final report)
```

S2/S3/S5 互不冲突可并行；S4 依赖 S1 根因；S6 依赖 S2-S5 全部就绪；S7 是最后收口。

## §1 切片顺序与 Done 条件

### S1 — Upload ingest root-cause（P0，阻断 S4）

**Owner**: 建设者 (Sonnet 默认；不要 GLM-5.1)  
**时间盒**: 60min；超时切降级路径（见 §5 Stop Rules）  
**Write Scope**:
- `~/.solar/harness/reports/upload-ingest-rootcause-20260508.md`（新增）

**Read-only 探查范围**:
- `~/.solar/harness/lib/wiki-*`、`~/.solar/harness/lib/external-integrations-health.py`
- `~/.solar/harness/events/events.jsonl`（grep `wiki_dispatch_*`、`wiki_db_*`）
- `/Users/sihaoli/Knowledge/_raw/solar-harness/.dispatch/*.md`（已落盘的 dispatch 文件）
- 当前批次 audit JSON 实测数据

**Done 条件（必须全过）**:
- D-S1-1: 报告文件存在且 ≥ 80 行
- D-S1-2: 明确指向根因之一：`dispatch_agent_not_running` / `db_write_step_disconnected` / `db_insert_throws_silently` / `pipeline_early_failure` / `other:具体描述`
- D-S1-3: 引用 ≥ 3 条证据（events.jsonl 行号、文件 mtime、grep 命中）
- D-S1-4: 给出 S4 修复建议（修哪个文件、改什么、不改什么）

**Verify**:
```bash
test -f ~/.solar/harness/reports/upload-ingest-rootcause-20260508.md && \
  wc -l ~/.solar/harness/reports/upload-ingest-rootcause-20260508.md
grep -E '^## (Root Cause|Evidence|Fix Recommendation)' \
  ~/.solar/harness/reports/upload-ingest-rootcause-20260508.md | wc -l
# 期望 ≥ 3
```

**Rollback**: 删除报告文件即可，无副作用。

---

### S2 — Schema 冻结 + integrations probe 字段升级（D1, D9 部分）

**Owner**: 建设者 (Sonnet)  
**Write Scope**:
- `~/.solar/harness/schemas/integrations.schema.json`（新增）
- `~/.solar/harness/lib/external-integrations-health.py`（升级 mirage/symphony/owl 字段）
- `~/.solar/harness/tests/external-integrations/test_schema_health.sh`（新增）

**Done 条件**:
- D-S2-1: schema 文件存在，含 `frozen_since=2026-05-08`、`version=1.0.0`
- D-S2-2: probe 输出新字段：mirage `sdk.kind` enum、`drive.state` enum、`drive.degraded_reason`；symphony `mode` enum、`executes_builders` bool；owl status 取 `not_connected`/`experimental`/`production`
- D-S2-3: schema test 通过（`solar-harness integrations status --json | jq -e -f schema-validate`）
- D-S2-4: qmd probe 修正：installed 字段反映 `qmd` npm 全局是否真的安装（修当前 missing 误报）

**Verify**:
```bash
solar-harness integrations status --json | \
  jq -e '.integrations[] | select(.name=="strukto-ai/mirage") | .evidence.sdk.kind | tostring | test("none|solar-logical|strukto-official|fuse")'
solar-harness integrations status --json | \
  jq -e '.integrations[] | select(.name | test("symphony")) | .evidence.mode'
bash ~/.solar/harness/tests/external-integrations/test_schema_health.sh
```

**Rollback**: 还原 health.py + 删 schema 文件 + 删 test。

---

### S3 — Status UI Integrations Tab（D2, D3）

**Owner**: 建设者 (Sonnet) 或 探索派 (g3) — 选可读性更好的  
**Write Scope**:
- `~/.solar/harness/lib/status-server/`（新增 `/integrations-view` handler + HTML template）
- `~/.solar/harness/tests/external-integrations/test_endpoint_view.sh`（新增）
- `~/.solar/harness/tests/external-integrations/test_p95_no_regression.sh`（新增）

**禁止动**: `/status` 主页 handler、主页 HTML（避免拖慢 P95）

**Done 条件**:
- D-S3-1: `curl http://127.0.0.1:8765/integrations-view` 返回 200 + HTML
- D-S3-2: HTML 含 7 个 integration 名称（grep 7 条全命中）
- D-S3-3: HTML 含 4 个 badge color（绿/黄/红/灰）+ purpose 一句话
- D-S3-4: `/status` P95 引入新 view 前后波动 ≤ 5%（采样 50 次）
- D-S3-5: `/integrations-view` 首字节 ≤ 200ms

**Verify**:
```bash
curl -fsS -o /tmp/iv.html -w "%{http_code} %{time_starttransfer}\n" \
  http://127.0.0.1:8765/integrations-view
grep -c -E 'obsidian-wiki|MinerU|mermaid|symphony|mirage|owl|drive' /tmp/iv.html
bash ~/.solar/harness/tests/external-integrations/test_p95_no_regression.sh
```

**Rollback**: 删 view handler + 测试文件，不影响主页。

---

### S4 — Upload ingest fix + reconciliation（D4, D5）

**Owner**: 建设者 (Sonnet)；**前置**: S1 报告 PASS  
**Write Scope**:
- 由 S1 报告决定的具体文件（dispatch agent 入口 / db-writer 模块）
- `~/.solar/harness/lib/wiki-audit-uploads.*`（升级 per-file state + blocker 字段）
- `~/.solar/harness/lib/wiki-backfill-uploads.*`（兜底命令）
- `~/.solar/harness/tests/external-integrations/test_audit_uploads.sh`（新增）

**Done 条件**:
- D-S4-1: 跑 backfill 后，最新批次 `20260508T131337Z` 满足 `qmd.found==total && vault.found==total && solar_db.found==total && dispatch.pending==0` ；**或** per-file blocker 字段完整（无 unknown，每条 missing/partial 都有具体原因）
- D-S4-2: audit JSON 中 per-file state 字段取值集合 ⊆ `{full, qmd_only, vault_only, db_only, partial:qmd+vault, partial:qmd+db, partial:vault+db, missing}`
- D-S4-3: missing/partial 文件的 `blocker` 字段非空且 ⊆ `{dispatch_pending, dispatch_failed, parse_error, oversized, unsupported_format, db_write_failed, unknown}`

**Verify**:
```bash
solar-harness wiki backfill-uploads --batch 20260508T131337Z --json > /tmp/bf.json
solar-harness wiki audit-uploads --batch 20260508T131337Z --json > /tmp/au.json
jq '.data.qmd, .data.vault, .data.solar_db, .data.dispatch' /tmp/au.json
jq '[.data.pages.files[].state] | unique' /tmp/au.json
bash ~/.solar/harness/tests/external-integrations/test_audit_uploads.sh
```

**Stop Rule（强制兑现）**: 一次 backfill 后 `solar_db.found` 仍为 0 → 立即停手 + 写降级报告（per-file blocker）+ 升级监护人。**禁止循环重试**。

**Rollback**: backfill 命令是幂等读 / 受控写（只写 _raw/ 和 DB），失败可通过 sqlite 删除 batch 标记的 row 回退。

---

### S5 — Mirage / Symphony / OWL 边界 UI 措辞修订（D6, D7, D8）

**Owner**: 建设者 (Sonnet) — 与 S3 可并行  
**Write Scope**:
- `~/.solar/harness/lib/status-server/` 中所有提到 mirage/symphony/owl 的人类可读文案
- `~/.solar/harness/lib/external-integrations-health.py` 的 `purpose` 字段
- 不动 mermaid 文案

**Done 条件**:
- D-S5-1: status-server 任何页面/JSON 文案不含"Symphony 在跑 builder" / "Drive mounted" / "OWL connected"，除非对应 enum 字段为真
- D-S5-2: mirage UI 在 `drive.state!=connected` 时显式标注"逻辑挂载（非真实 Drive）"
- D-S5-3: OWL 显示文案明确为"未连接（如需提级须新 sprint）"

**Verify**:
```bash
# 反例搜索：以下命令必须 0 命中
grep -r "Symphony.*runs.*builder\|Drive.*mounted\|OWL.*connected" \
  ~/.solar/harness/lib/status-server/ || echo "PASS: no false claims"
curl -fsS http://127.0.0.1:8765/integrations-view | \
  grep -E "logical mount|not connected"
```

**Rollback**: 单文件 git checkout 即可。

---

### S6 — 测试覆盖（D9 完整）

**Owner**: 建设者 (Sonnet)；**前置**: S2-S5 全部就绪  
**Write Scope**:
- `~/.solar/harness/tests/external-integrations/`（汇总，已包含 S2-S4 各自测试）
- `~/.solar/harness/tests/external-integrations/run-all.sh`（聚合 runner）

**Done 条件**:
- D-S6-1: tests/external-integrations/ 下 ≥ 5 个测试脚本
- D-S6-2: `run-all.sh` 一键跑全部，全 PASS
- D-S6-3: 任一测试失败 exit code 非 0

**Verify**:
```bash
ls ~/.solar/harness/tests/external-integrations/*.sh | wc -l   # ≥ 5
bash ~/.solar/harness/tests/external-integrations/run-all.sh && echo OK
```

**Rollback**: 删除测试目录，不影响生产代码。

---

### S7 — Final Report（D10）

**Owner**: 建设者 (Sonnet) 或 综合官 (gpt-4o) — 文档写作选擅长综合的  
**Write Scope**:
- `~/.solar/harness/reports/solar-open-source-integrations-audit-20260508-final.md`（新增，不覆盖原 audit）

**Done 条件**:
- D-S7-1: 报告 ≥ 200 行
- D-S7-2: 含 §1 七态最终表 / §2 上传入库前后对照 / §3 reconciliation 抽样 / §4 边界措辞修订 / §5 遗留 conflicts（每条带 owner + next action） / §6 链回原 audit
- D-S7-3: §5 conflicts 列表里每条 next action 有具体 sprint 提议 id 或"无"明示

**Verify**:
```bash
test -f ~/.solar/harness/reports/solar-open-source-integrations-audit-20260508-final.md
wc -l ~/.solar/harness/reports/solar-open-source-integrations-audit-20260508-final.md
grep -c -E '^## §' ~/.solar/harness/reports/solar-open-source-integrations-audit-20260508-final.md   # ≥ 6
```

**Rollback**: 删除文件。

## §2 文件级写入范围（白名单，绝对路径）

允许写：
```
~/.solar/harness/schemas/integrations.schema.json                                      [S2]
~/.solar/harness/lib/external-integrations-health.py                                   [S2,S5]
~/.solar/harness/lib/status-server/                                                    [S3,S5]
~/.solar/harness/lib/wiki-audit-uploads.*                                              [S4]
~/.solar/harness/lib/wiki-backfill-uploads.*                                           [S4]
~/.solar/harness/lib/(由 S1 根因报告决定的具体修复点)                                  [S4]
~/.solar/harness/tests/external-integrations/                                          [S2-S6]
~/.solar/harness/reports/upload-ingest-rootcause-20260508.md                           [S1]
~/.solar/harness/reports/solar-open-source-integrations-audit-20260508-final.md        [S7]
~/.solar/harness/sprints/sprint-20260508-external-integrations-closeout.handoff.md     [收尾]
~/.solar/harness/sprints/sprint-20260508-external-integrations-closeout.status.json    [收尾]
```

禁止写：
```
任何 sprint 的 contract.md
~/.solar/harness/trajectories/
/Users/sihaoli/Knowledge/concepts/
/Users/sihaoli/Knowledge/canonical/
~/.config/google-oauth.json 等凭据文件
~/.solar/harness/vendor/mermaid-viewer/         (mermaid 是 ok，不动)
任何 live tmux pane (no-live-pane-mutation)
其他 active sprint 的工作目录 (mirage / accepted-artifact / data-plane-closeout)
```

## §3 并发边界

| 阶段 | 可并行 | 必须串行 |
|------|--------|----------|
| S1 | — | 单线程，60min 时间盒 |
| S2/S3/S5 | 可并行（不同文件） | — |
| S4 | — | 依赖 S1 根因 |
| S6 | — | 依赖 S2-S5 |
| S7 | — | 收尾，独立 |

并行执行时 Builder 必须用 disjoint write set；同一 builder pane 一次只跑一个 stage（避免 GLM 1210 重派后 race）。

## §4 No-Live-Pane-Mutation 保护

- 禁止 `tmux send-keys` 到任何 live pane（solar-harness:0、solar-harness-lab:0）
- 禁止 `tmux kill-session`、`kill-pane`、`kill-server`
- 禁止 `~/.solar/harness/coordinator.sh stop|restart`
- 禁止 touch `.coordinator.pid`、`.coordinator.log` 之外的协调器状态文件
- 重启 status-server 必须走 `solar-harness status-server reload`，不直接 kill

如果改动需要 status-server 重启，必须在 handoff.md 里明示并由监护人手动确认。

## §5 Stop Rules（强制兑现）

| 条件 | 动作 |
|------|------|
| S1 60min 仍未定位根因 | 写降级路径报告（接受 0/N）+ 标 D4 为 "blocked, escalate" |
| S4 一次 backfill 后 solar_db.found=0 | 立刻停手 + per-file blocker + 升级监护人；禁止循环重试 |
| S3 P95 退化 > 5% | 回滚 view handler + 改为 lazy-load 或独立端口 |
| 任意 stage 触碰 live pane | 立即 abort + 写 incident note + 升级监护人 |
| 写 scope 越界 | builder 自动 abort；evaluator git diff 检测发现也算 fail |

## §6 Verification Commands（汇总，eval 抽样源）

来自 contract.md "Verification Commands" 7 条 + plan 新增 ≥ 5 条：

```bash
# Contract D1-D8 / R1-R7
solar-harness integrations status --json
solar-harness integrations status --json --refresh
curl -fsS http://127.0.0.1:8765/integrations | python3 -m json.tool
solar-harness wiki audit-uploads --batch 20260508T122047Z --json
solar-harness mirage doctor --json
solar-harness wiki qmd-status
solar-harness symphony status

# Plan 新增
curl -fsS http://127.0.0.1:8765/integrations-view | head -50
solar-harness wiki audit-uploads --batch 20260508T131337Z --json | jq '.data.solar_db'
bash ~/.solar/harness/tests/external-integrations/run-all.sh
test -f ~/.solar/harness/reports/upload-ingest-rootcause-20260508.md
test -f ~/.solar/harness/reports/solar-open-source-integrations-audit-20260508-final.md
```

evaluator 必须从上述 12 条中抽样 ≥ 3 条复现 + git diff 比对 §2 white list 越界。

## §7 Rollback 矩阵

| Stage | 单 stage 回滚 | 全 sprint 回滚 |
|-------|---------------|----------------|
| S1 | 删 report 文件 | 同左 |
| S2 | git checkout health.py + 删 schema + 删 test | 同左 |
| S3 | git checkout status-server + 删 view test | 同左 |
| S4 | sqlite 删 batch row + git checkout wiki-* | 同左 |
| S5 | git checkout 文案 | 同左 |
| S6 | 删 tests/external-integrations/ | 同左 |
| S7 | 删 -final.md | 同左 |

整体 rollback 不影响线上 active sprint（mirage / accepted-artifact / data-plane-closeout）。

## §8 Builder 模型选择

| Stage | 推荐模型 | 备选 | 不要用 |
|-------|----------|------|--------|
| S1 (root-cause) | 审判官 (deepseek-r1) | 稳健派 (gemini-2.5-pro) | GLM-5.1 |
| S2 (schema) | 建设者 (Sonnet) | 稳健派 | GLM-5.1 |
| S3 (UI) | 建设者 (Sonnet) | 探索派 (gemini-3-pro) | GLM-5.1 |
| S4 (ingest fix) | 建设者 (Sonnet) | 审判官 | GLM-5.1 |
| S5 (boundaries) | 建设者 (Sonnet) | 综合官 (gpt-4o) | GLM-5.1 |
| S6 (tests) | 建设者 (Sonnet) | 闪电侠 (gemini-3-flash) | GLM-5.1 |
| S7 (report) | 综合官 (gpt-4o) | 创想家 (deepseek-v3) | GLM-5.1 |

依据：MEMORY 教训 — GLM-5.1 已踩 4 次坑，默认切 Sonnet。

## §9 Definition of Done（整体）

- D1-D10 全 PASS（contract.md acceptance）
- §6 12 条 verify command 全可复现
- evaluator eval verdict=PASS（独立复现 ≥ 3 条 + git diff 检查）
- 写 scope 无越界
- §5 stop rules 未触发，或触发后已升级处理
- handoff.md 含 "## 变更文件" / "## Done 达成" / "## 验证方法" 三段
- status.json 终态 status=passed, phase=done

## §10 Post-Plan 收尾步骤

按 dispatch.md 步骤 7：
1. 状态机 status: drafting → active
2. phase: prd_ready → planning_complete
3. handoff_to: planner → builder_main
4. history append: planner_plan_completed
5. 不触发协调器主动派发；由协调器轮询 mtime 自然接管

