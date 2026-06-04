# Design — YouTube Transcript Epic S05 Verification-Release (epic 最后切片)

epic_id: `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构`
sprint_id: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s05-verification-release`
slice: `verification-release` (epic last slice)
role: planner
status: planning_complete
generated_at: 2026-05-28T16:35:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
upstream: S03 (passed @ 5/28 13:07, 6 acceptance reports all ok=True) + S04 (passed @ 5/27 19:25, C1-C4 spec)
downstream: epic close (parent_check_ready=true → epic_decomposer auto-close)

## 0. 切片定位 — DOGFOOD 闭环 (epic 最后切片)

**Epic 最后切片**: 验证 S03 实施 (6 模块 + 9 表 + 6 acceptance) + S04 规约 (Dashboard+CLI+Config+Premium E2E) 能在**真生产环境**跑通; 真清理 165 条污染数据; 真调 OpenAI gpt-4o-transcribe; 触发 epic close。

**核心差异 vs TUI S05**: YouTube epic 涉及真外部 API (OpenAI / yt-dlp / faster-whisper) + 真生产 SQLite DB + 真 budget ($20/day) + 真 165 污染清理。

## 1. 上游消费 (S03 + S04 → S05)

| 上游 | 必须消费 |
|------|----------|
| S03 handoff | 6 acceptance reports paths (pytest/dry-run/threshold/budget/pollution/atomicity 全 ok=True) + 3 S05 checklist (premium ASR E2E / 165 污染清理 / dashboard 真集成) |
| S04 handoff | 5-step kickoff checklist (S03 ready confirm / Dashboard 9 指标 / CLI 6 命令 / Legacy 兼容 / Premium ASR E2E 5 phase 用例) + 6 残留风险 + 3 OQ-C5 (transcript-status schema / pydantic env / config path) |
| S02 13 decisions + 4 OQ | D10 (OpenAI gpt-4o-transcribe) + D11-D13 + OQ1 (premium provider) 真生产验证 |
| S01 67 AC (16 outcomes) | R1-R16 全 67 验收 (跨 N1-N5 5 requirement docs) |

## 2. 6-Node DAG

```
V1 real_dashboard_cli_e2e (sonnet, 关键路径)
   ├─→ V2 premium_asr_real_e2e (sonnet, 真 OpenAI + budget cap)
   ├─→ V3 production_pollution_cleanup (sonnet, 真 165 清理)
   └─→ V4 regression_aggregation (glm-5.1, 67 AC + 13 决议 + 4 OQ)
                                  └─→ V5 release_docs_epic_close_prep (sonnet)
                                        └─→ V6 join_epic_close_ready (sonnet)
```

## 3. 节点验收

### V1 real_dashboard_cli_e2e
- `transcript-status --json` 真跑 → 9 字段全 (per S04 C2 §4.5 权威 schema)
- HTML 渲染 (visual-template CSS 变量 + 4 分组 + SLO 红/黄/绿)
- TUI 渲染 (Rich 表格 + Radar youtube_transcript 区域块嵌入 Social Clusters 之后)
- 6 CLI 真跑 dry-run: discover/acquire/process/audit/status/ab-test (每条 exit 0 + stdout schema 正确)
- Legacy 兼容: `process-transcripts --video-ids <id> --dry-run` 入队 R7 jobs (不绕过) + deprecated 字段
- 6 evidence JSON

### V2 premium_asr_real_e2e (per S04 C4 5 phase)
- **Phase 1 准备**: `SOLAR_YOUTUBE_PREMIUM_OPENAI_KEY` 注入 + grep 日志无 key (secret scan)
- **Phase 2 触发**: `should_trigger_premium()` P0 视频 + entity recall ≥70% (per OQ4)
- **Phase 3 调用**: gpt-4o-transcribe API call + youtube_premium_asr_calls ledger 7 字段
- **Phase 4 验证**: cost = $0.006 × ceil(minutes); daily budget ≤$20; quality_score 提升 vs faster-whisper
- **Phase 5 失败**: mock API 500 → retry → fallback faster-whisper large-v3 + ledger fallback_reason
- 5 evidence JSON + budget_cap_log.json

### V3 production_pollution_cleanup
- `audit-transcript-quality --repair-pollution --dry-run` 验证 165 条候选 (per N3 PRD)
- `audit-transcript-quality --repair-pollution --apply` **真生产清理** (备份 + transactional)
- 验证 transcript_status=missing AND transcript_clean 非空 count → 0
- 3 evidence JSON (count_before / count_after / backup_path)
- **rollback 命令**: 备份 SQLite + 数据回滚 SQL 写入 evidence

### V4 regression_aggregation
- S01 67 AC 全验证 (R1-R16 跨 16 outcomes)
- S02 13 决议 D1-D13 + 4 OQ (OQ1-OQ4) 落地验证
- S03 6 acceptance reports re-run + ok=True 复现
- S04 6 残留风险 + 3 OQ-C5 (per S04 handoff) 验证或转 carried-over
- regression_report.json (67+13+4+6+3 = 93 条 PASS/FAIL 表)

### V5 release_docs_epic_close_prep
- `docs/youtube-transcript/RELEASE.md` (epic 总览 + S01-S05 摘要 + V1-V4 evidence + rollback (165 数据回滚 + 6 模块删除) + ATLAS hook + OQ-C5 carried-over)
- 禁止乐观词
- `<sid>.eval.{md,json}` sprint 整体 verdict

### V6 join_epic_close_ready
- traceability.json 12 字段 + `parent_check_ready=true` + `epic_required_gates_status` (S01-S05 all passed)
- handoff.md V1-V5 摘要 + epic close checklist
- **不主动 close epic** (epic_decomposer auto)

## 4. 写范围

| 节点 | write_scope |
|------|-------------|
| V1 | `reports/youtube/s05-acceptance/V1-{transcript_status,dashboard_html,dashboard_tui,cli_*,legacy}.json` + `<sid>.V1-handoff.md` |
| V2 | `reports/youtube/s05-acceptance/V2-premium_{prep,trigger,call,verify,fallback}.json` + `<sid>.V2-handoff.md` |
| V3 | `reports/youtube/s05-acceptance/V3-{count_before,count_after,backup_path}.json` + `<sid>.V3-handoff.md` + **SQLite 备份到 ~/.solar/harness/backups/youtube/<ts>/** |
| V4 | `reports/youtube/s05-acceptance/V4-regression_report.json` + `<sid>.V4-handoff.md` |
| V5 | `docs/youtube-transcript/RELEASE.md` + `<sid>.V5-handoff.md` + `<sid>.eval.{md,json}` |
| V6 | `<sid>.handoff.md` + `<sid>.traceability.json` |

**严格禁止**:
- 真调 OpenAI 但泄 API key (V2 必须 secret scan)
- 真清理但不备份 (V3 必须先 SQLite 备份)
- 超 $20/day budget (V2 必须 budget cap 强校验)
- 删 Knowledge vault 已 accepted artifacts
- 重启 ThunderOMLX / honcho / brain-router / qmd-proxy / config-server (per N3 7 个不相关 Python 服务)
- 主动 close epic (V6 仅 mark ready)
- 修改 S03 lib 源码 (实施已 PASS)
- 用乐观词

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| V1, V2, V3, V5 | sonnet | 真生产交互 + ATLAS 兜底需 reasoning |
| V4 | glm-5.1 | 回归聚合模板化 |
| V6 | sonnet | join + epic ready |

## 6. Stop Rules

- 缺 task_graph 不派 builder
- V2 OpenAI key 泄露 → 立即 sprint FAIL + incident
- V2 budget 超 $20 → 立即 FAIL + 触发 ATLAS
- V3 清理前未备份 → 立即 FAIL
- V3 清理后 count 不为 0 → S03 round-2 (清理逻辑 bug)
- V4 任一 AC FAIL → 触发对应 sprint round-2
- V6 主动 close epic → 立即 FAIL
- 不重启服务进程
- 不动 Knowledge vault accepted artifacts
- 不用乐观词

## 7. 失败恢复

- V1 失败: 真 CLI 跑出问题 → 标 S03 接口偏离 (per OQ-C5-01) round-2
- V2 失败: OpenAI down / quota → fallback 验证 + ATLAS; key 泄露 → sprint FAIL + 撤回 key
- V3 失败: 清理 SQL 出错 → 立即 ROLLBACK + 备份回滚验证
- V4 任一 AC FAIL → round-2 对应 sprint
- V5/V6 失败 → 单节点重派
- ATLAS 兜底全失败 → 人工介入

## 8. Dogfood / Cross-Epic 关系

- **YouTube epic 是 AI Influence 三源共振中的 Influence Source (Video 部分)**, 与 HF Paper Insight Flow (Paper Source) + Social Signal Plane (Influence Source) 互补
- 本 sprint passed 后 YouTube transcript 链路真正 production-ready, 供 AI Influence digest 消费
- 与 TUI Pane Recover epic 共同推进: TUI S05 PASS 后, 本 sprint V1-V6 builder pane 卡死问题自动 detect+clear+reassign

## 9. 非目标

- 不实施新代码 (S03 已完成)
- 不动 S03/S04 artifacts (read-only verification)
- 不主动 close epic (V6 仅 mark)
- 不重启 service 进程 (per N3 7 个 non-multi_task_runner 进程)
- 不动 ThunderOMLX cache / FlashMLX KV (跨 epic)
- 不删 Knowledge vault accepted artifacts

## 10. Knowledge Context

S03 1.6K handoff + 3.8K traceability + S04 5.4K handoff + 8.9K traceability + S02 4 docs + S01 5 requirements + 6 acceptance reports = ~50K+ total upstream evidence。`context inject` 已跑, mirage degraded。
