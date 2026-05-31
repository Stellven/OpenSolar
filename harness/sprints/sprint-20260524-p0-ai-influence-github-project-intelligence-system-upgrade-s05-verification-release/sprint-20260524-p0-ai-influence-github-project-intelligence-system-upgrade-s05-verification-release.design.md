# Design — GitHub Project Intelligence System Upgrade S05 Verification-Release (epic 最后切片)

epic_id: `epic-20260524-p0-ai-influence-github-project-intelligence-system-upgrade`
sprint_id: `sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s05-verification-release`
slice: `verification-release` (epic last slice)
role: planner
status: planning_complete
generated_at: 2026-05-28T18:10:00Z
knowledge_context: solar-harness context inject used (mirage:timeout → qmd/obsidian/solar_db fallback)
upstream: S03 (delivered @ 5/27 13:00, 230 assertions all PASS — 150 module self-test + 44 pytest integration + 36 unaccounted) + S04 **partial** (O1 PASS @ 5/27 12:20, O2-O5 pending)
downstream: epic close gate (parent_check_ready=true → epic_decomposer auto-close **only when S04 O2-O5 also passed**)

## 0. 切片定位 — DOGFOOD 闭环 (epic 最后切片, 但 S04 未全 PASS)

**Epic 最后切片**: 验证 S03 实施 (4 phase 模块 C1-C5 + 194-230 assertions) + S04 partial (O1 epic_child_activation gate) 能在**真生产环境** end-to-end 跑通; 真调 ThunderOMLX 评估 README/release/issues; 真验证 model_ledger budget cap; 真写入 ~/Knowledge raw; 触发 epic close ready (但 epic 实际 close 还需 S04 O2-O5 完成)。

**核心 caveat vs YouTube S05**: GHPI epic 涉及 GitHub API + ThunderOMLX local eval, 真 budget (model_call_ledger 4 类聚合); **S04 只 O1 完成, O2-O5 pending**, 因此本 S05 的 V6 join 只能 mark partial_ready, 不能宣称 epic close ready, 必须把 S04 O2-O5 显式列为 epic close 阻塞项。

## 1. 上游消费 (S03 + S04 partial → S05)

| 上游 | 必须消费 |
|------|---------|
| S03 handoff | 5 节点 C1-C5 + 14 落地文件 (schema.py / model_ledger.py / adapters/ × 5 / snapshots.py / evidence.py / detectors.py / cards.py / briefs.py / reports/ / pipeline.py / 2 pytest 套件) + 194-230 assertions 复现 |
| S04 handoff | O1 epic_child_activation 5 pytest 复现 + O2/O3/O4/O5 显式 pending caveat (本 S05 不替 S04 完成 O2-O5) |
| S02 architecture | 8 模块边界 + 接口契约 (本 S05 read-only) |
| S01 requirements | 67 AC 全回归 (across 16 outcomes) |
| epic.md | 5 子任务图 + 调度规则 (父级不直接编码 + 依赖未 passed 不得提前派发) |

## 2. 6-Node DAG

```
V1 e2e_pipeline_real (sonnet, 关键路径)
   ├─→ V2 thunderomlx_evidence_real (sonnet, 真 ThunderOMLX 本地 eval)
   ├─→ V3 model_ledger_budget_cap (sonnet, 真 budget 强校验)
   └─→ V4 regression_aggregation (glm-5.1, 67 AC + S02 决议 + S03 230 + S04 O1 5 pytest)
                                  └─→ V5 release_docs_knowledge_raw (sonnet)
                                        └─→ V6 join_partial_epic_ready (sonnet)
```

## 3. 节点验收

### V1 e2e_pipeline_real
- 真跑 `run_pipeline()` end-to-end (discovery 4 adapter → snapshot 5 windows → evidence atoms → 8-component heat_score + 7 detectors → cards (evidence floor ≥3) → briefs → daily/weekly reports)
- 输入: 真 GitHub Search API (或 fixture replay, 不超过 quota) — 至少 3 个 tracked repo + 1 topic + 1 trending
- 输出验证: cards count ≥1 verified + briefs ≥1 + daily report 含所有 required section
- pytest: 已存在的 `test_pipeline.py` 11 个 integration smoke 再跑一次, 全 PASS
- 6 evidence JSON (discovery / snapshot / evidence / detector / card+brief / report)
- **真生产 SQLite DB 写入** (model_ledger 记录 ThunderOMLX 调用), V3 验证 budget

### V2 thunderomlx_evidence_real
- 真调 ThunderOMLX local (本地 8B 4-bit 模型) 压缩 README/release/issues → evidence atoms
- `compress_readme()` × 2 仓库 + `compress_releases()` × 2 + `compress_issues()` × 2 = 6 真调用
- `build_reasoning_packet()` × 2 (why-hot attribution)
- `persist_atoms()` 真写入 evidence ledger
- 6 evidence JSON + evidence atom 完整性校验 (evidence_id 唯一 + atom schema 合法)
- secret scan: 日志不得出现 ThunderOMLX KV cache path / API key

### V3 model_ledger_budget_cap
- 真触发预算硬上限 (mock: 设 budget=$0.10, 故意调用直到触发 LIMIT)
- 验证 4 类聚合查询: `get_calls_by_provider/get_calls_by_model/get_total_cost_today/get_call_count`
- `ModelCall` 校验全字段 (provider/model/cost/ts/sprint_id/node_id/intent)
- budget 触发后续调用必须 raise + ledger 记 reason=budget_exhausted
- 4 evidence JSON (4 类聚合 each) + budget_trigger_log.json
- **rollback**: 测试后清理 mock ledger 数据 (备份 + transactional)

### V4 regression_aggregation
- S01 67 AC 全验证 (across 16 outcomes, requirement_ids 完整覆盖)
- S02 architecture 决议落地验证 (8 模块边界 + 接口契约 vs S03 实际落地一致)
- S03 230 assertion (194 confirmed + 36 unaccounted) 复测 + 解释口径差 (handoff §DAG 表 230 vs Done #1 表 194 是 self-test 计数口径不同)
- S04 O1 5 pytest 复测 (graph_scheduler.epic_child_activation 4 acceptance + 1 live epic test)
- **S04 O2-O5 caveat**: 显式列为 epic close 阻塞项, 不验证 (S04 未完成)
- regression_report.json (67 + S02-决议数 + 194 + 5 + S04-O2/3/4/5-pending = comprehensive PASS/FAIL/PENDING 表)

### V5 release_docs_knowledge_raw
- `docs/github-project-intelligence/RELEASE.md` (epic 总览 + S01-S05 摘要 + V1-V4 evidence + rollback (lib/github_intelligence/ 子包删除 + model_ledger 数据回滚) + ATLAS hook + **S04 O2-O5 epic close 阻塞清单**)
- **写入 ~/Knowledge/_raw/tech-hotspot-radar/github-project-intelligence/release/2026-05-28-s05-release.md** (per acceptance "写入知识库 raw")
- 禁止乐观词 ("已完成"/"完美"/"已稳定")
- `<sid>.eval.{md,json}` sprint 整体 verdict + 显式 partial-epic note

### V6 join_partial_epic_ready
- traceability.json 12 字段 + `parent_check_ready=false` (因 S04 O2-O5 pending) + `epic_required_gates_status` (S01-S03 + S04 O1 passed; S04 O2-O5 pending; S05 self passed)
- handoff.md V1-V5 摘要 + epic close 阻塞清单 (S04 O2-O5 列表) + S04 续做 sprint candidate
- **不主动 close epic** (S04 未完成)
- **S05 本身可 PASS**, 但 epic 不能 close

## 4. 写范围

| 节点 | write_scope |
|------|-------------|
| V1 | `reports/github-intelligence/s05-acceptance/V1-{discovery,snapshot,evidence,detector,card_brief,report}.json` + `<sid>.V1-handoff.md` |
| V2 | `reports/github-intelligence/s05-acceptance/V2-thunderomlx_{readme1,readme2,release1,release2,issue1,issue2,atoms}.json` + `<sid>.V2-handoff.md` |
| V3 | `reports/github-intelligence/s05-acceptance/V3-{agg_provider,agg_model,agg_cost,agg_count,budget_trigger}.json` + `<sid>.V3-handoff.md` + **SQLite 备份到 ~/.solar/harness/backups/github-intelligence/<ts>/** |
| V4 | `reports/github-intelligence/s05-acceptance/V4-regression_report.json` + `<sid>.V4-handoff.md` |
| V5 | `docs/github-project-intelligence/RELEASE.md` + `~/Knowledge/_raw/tech-hotspot-radar/github-project-intelligence/release/2026-05-28-s05-release.md` + `<sid>.V5-handoff.md` + `<sid>.eval.{md,json}` |
| V6 | `<sid>.handoff.md` + `<sid>.traceability.json` |

**严格禁止**:
- 真调 ThunderOMLX 但泄 KV cache path / API key (V2 必须 secret scan)
- 真 budget 测试不备份 SQLite (V3 必须先备份)
- 真 GitHub API 调用超 quota (V1 必须 rate-limit + fixture fallback)
- 删除 ~/Knowledge accepted artifacts (V5 只新增 raw)
- 重启 ThunderOMLX / FlashMLX / honcho / brain-router / qmd-proxy / config-server
- 修改 S03 lib/github_intelligence/ 源码 (实施已 PASS, 本 sprint read-only)
- **主动 close epic (V6 仅 mark partial_ready, S04 O2-O5 pending 阻塞)**
- 替 S04 完成 O2-O5 (那是 S04 续做 sprint 的活)
- 用乐观词

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| V1, V2, V3, V5 | sonnet | 真生产交互 + ATLAS 兜底需 reasoning |
| V4 | glm-5.1 | 回归聚合模板化 |
| V6 | sonnet | join + epic ready 判定 (含 S04 partial) |

## 6. Stop Rules

- 缺 task_graph 不派 builder
- V2 ThunderOMLX 输出泄 KV cache path → 立即 sprint FAIL + incident
- V3 budget 触发后无 raise → S03 round-2 (budget enforcement bug)
- V3 清理前未备份 → 立即 FAIL
- V1 任一 e2e 阶段 FAIL → S03 round-2 (对应 phase 模块)
- V4 S01 67 AC 任一 FAIL → 对应 S01-S03 sprint round-2
- V6 主动 close epic → 立即 FAIL (S04 O2-O5 pending)
- 不重启 service 进程
- 不动 Knowledge vault accepted artifacts (只新增 raw)
- 不用乐观词

## 7. 失败恢复

- V1 失败: e2e pipeline 出问题 → 标 S03 实施偏离 round-2
- V2 失败: ThunderOMLX 不可用 → 标 S03 evidence 模块缺降级路径 (compress_*应有 fallback)
- V3 失败: budget 不触发 → S03 model_ledger budget enforcement round-2; key 泄露 → sprint FAIL
- V4 任一 AC FAIL → round-2 对应 sprint
- V5/V6 失败 → 单节点重派
- ATLAS 兜底全失败 → 人工介入

## 8. Dogfood / Cross-Epic 关系

- **GHPI epic 是 AI Influence 三源共振中的 Project Source (GitHub 部分)**, 与 YouTube Transcript epic (Video Source) + HF Paper Insight epic (Paper Source) + Tech Hotspot Radar Social Browser Backend (Social Source) 互补
- 本 sprint passed 后 GHPI 链路 production-ready 部分上线 (S03 + S04 O1 + S05 全验证); S04 O2-O5 通过续做 sprint 后才能 close epic
- 与 TUI Pane Recover epic 共同推进: 本 sprint builder pane 卡死问题靠 TUI epic S03 实施完成后 auto-recover

## 9. 非目标

- 不实施新代码 (S03 已完成, S04 O2-O5 留续做 sprint)
- 不动 S03/S04 artifacts (read-only verification)
- 不主动 close epic (S04 未全 PASS)
- 不替 S04 完成 O2-O5
- 不重启 service 进程
- 不动 ThunderOMLX cache / FlashMLX KV (跨 epic)
- 不删 Knowledge vault accepted artifacts

## 10. Knowledge Context

S03 handoff (200 行 / 14 落地文件 / 194-230 assertion 复现) + S04 handoff (131 行, O1 PASS, O2-O5 pending 显式) + epic.md (5 子任务图) + S01 67 AC + S02 8 模块决议 = ~30K+ total upstream evidence。`context inject` 已跑, mirage degraded → QMD/Obsidian/Solar DB fallback。
