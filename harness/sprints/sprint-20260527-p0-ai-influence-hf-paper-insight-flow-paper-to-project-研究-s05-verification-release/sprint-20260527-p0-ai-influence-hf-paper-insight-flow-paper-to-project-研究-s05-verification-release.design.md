# Design — HF Paper Insight Flow S05 Verification-Release (epic 最后切片)

epic_id: `epic-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究`
sprint_id: `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s05-verification-release`
slice: `verification-release` (epic last slice)
role: planner
status: planning_complete
generated_at: 2026-05-29T01:00:00Z
knowledge_context: solar-harness context inject used (mirage:timeout → qmd/obsidian/solar_db fallback)
upstream: S03 (PASS @ 2026-05-28T19:58, collection/schema/scoring/runtime suites + auto eval sidecars) + S04 (PASS @ 2026-05-28T23:45, C1-C5 spec)
downstream: epic close gate (parent_check_ready=true → epic_decomposer auto-close, **all upstream S01-S04 passed unlike GHPI**)

## 0. 切片定位 — DOGFOOD 闭环 (epic 完整最后切片)

**Epic 完整最后切片**: 把 S03 实施 (10 层 L0-L10 + 5 评分公式 + 7 输出资产 + 4 通道 ingest) + S04 规约 (Dashboard / CLI / Config / High Model E2E plan) 在**真生产环境**跑通; 真调 5 provider API (HF / arXiv / Semantic Scholar / HF assets / GitHub); 真调 ChatGPT 5.5 Thinking high via Browser Agent (gstack browser.browse); 真生成 7 资产 + 写入 ~/Knowledge raw/extracted/QMD/graph 4 通道; 触发 epic close (与 GHPI 不同, 此 epic 全 upstream PASS, 可真正 close)。

**与 YouTube S05 vs GHPI S05 关键差异**:
- vs YouTube: 用 ChatGPT 5.5 Thinking high via Browser Agent (不是 OpenAI gpt-4o-transcribe); 7 输出资产 (不是 transcript); Knowledge ingest 4 通道 (raw/extracted/QMD/graph), 不是 SQLite pollution cleanup
- vs GHPI: epic close gate 真触发 (S04 全 PASS), V6 parent_check_ready=true; 不像 GHPI 卡 S04 O2-O5 pending

**Browser Agent 软依赖 caveat**: V2 high model E2E 通过 Browser Agent 触发 ChatGPT 5.5 Thinking high。若 Browser Agent 上游 `sprint-20260525-browser-agent-global-operator-cutover` 未 PASS, V2 必须走 fallback 路径 (per S04 C4 §failure: ChatGPT 5.5 normal 无 thinking, 或 mock packet 测试); 但 V2 仍需 PASS, 不阻塞 epic close。

## 1. 上游消费 (S03 + S04 → S05)

| 上游 | 必须消费 |
|------|---------|
| S03 handoff | 10 层 L0-L10 实施 (schema/storage/state-machine + collection/canonical/enrichment + taxonomy/scoring/packet + reasoning/compiler/store/watch) + 4 测试套件 (collection/schema/scoring/runtime) + auto eval sidecars + node verdicts + status sync |
| S04 handoff | C1 dashboard 299 行 (7 资产卡片 + HTML+TUI dual + 3 SLO) + C2 CLI 191 行 (11 subcommand + 10 flag + 4 exit code + legacy compat) + C3 config 522 行 (5 YAML + 4 routing threshold + 3 override + 4 ingest + 5 provider) + C4 high model E2E 529 行 (5 phase + 3-tier + Browser Agent + 3-hop fallback + 7 asset check) + 6 残留风险 |
| S02 D1-D5 | SQLite WAL / provider rate limits / Browser Agent reuse / YAML hot-reload / raw-first ingest ordering |
| S01 67 AC | 16 outcomes 完整回归 (PaperSnapshot/Canonical/Enrichment/Taxonomy/Signal/Evidence packet + 5 scoring + R0-R5 + 7 outputs + 11 AC) |
| epic.md | 5 子任务图 + 调度规则 |

## 2. 6-Node DAG (复用 YouTube/GHPI S05 同款 V1-V6)

```
V1 e2e_l0_l10_real_2026_05_27 (sonnet, 关键路径)
   ├─→ V2 high_model_chatgpt55_thinking_real (sonnet, 真 Browser Agent + ChatGPT 5.5 Thinking high + fallback)
   ├─→ V3 provider_breaker_ingest_4channel_regress (sonnet, 5 provider rate limit + 4 channel ordering)
   └─→ V4 regression_aggregation (glm-5.1, 67 AC + S02 D1-D5 + S03 4 suites + S04 C1-C5 + 5 OQ)
                                  └─→ V5 release_docs_knowledge_raw (sonnet, 写 raw/extracted)
                                        └─→ V6 join_epic_close_ready (sonnet, parent_check_ready=true)
```

## 3. 节点验收

### V1 e2e_l0_l10_real_2026_05_27 (per PRD AC-10 "用 2026-05-27 的 HF daily/weekly/monthly 数据跑通第一条完整闭环")
- **L0 Snapshot Collector**: 真采集 HF daily + weekly + monthly @ 2026-05-27 (3 windows), 不覆盖历史
- **L1 Canonicalizer**: arXiv ID / HF URL / title hash / authors / orgs / dedup_keys
- **L2 Enrichment**: HF metadata + arXiv + HF linked assets + GitHub + Semantic Scholar (5 provider 真调, rate-limit respected, S04 C3 §provider)
- **L3 Classifier**: PaperTaxonomy 7 字段 (domain/method/task/asset/stack_layer/maturity/research_route)
- **L4 Signal Scoring**: 5 类分数 (research_signal_score + insight_report_score + experiment_score + open_project_score + deep_research_seed_score) per PRD §评分体系 加权公式
- **L5 Evidence Packet**: PaperEvidencePacket v2 含 6 字段; Packet Gate (5 检查)
- **L6 Resonance Matcher**: R0-R5 共振等级 per PRD §三源共振; Resonance Gate (3 检查)
- **L7 High Reasoning**: 留 V2 真跑, V1 仅验证 evidence packet 准备好
- **L8 Compiler**: 7 输出资产生成 (HF Paper Insight Report + Paper Insight Cards + Three-source Resonance Seeds + AI Influence Topic Pool + Experiment Tasks + Open-source Project Briefs + Deep Research Seed Packs); Insight Gate (5 检查)
- **L9 Knowledge Store**: raw + extracted 同步写入 (per OQ-05 raw 先同步, extracted/QMD/graph 异步在 V3 验证顺序)
- **L10 Watch Trigger**: 高价值论文入队 watch / 三源共振 / deep research / 开源孵化
- pytest: S03 4 测试套件复跑 (collection/schema/scoring/runtime) 全 PASS
- 11 evidence JSON (L0..L10 each + pytest summary)

### V2 high_model_chatgpt55_thinking_real (per S04 C4 §5 phase E2E)
- **Phase 1 准备**: gstack browser.browse session 可建立; ChatGPT 5.5 Thinking high 端点可达; API key 注入但 grep 日志无 key (secret scan)
- **Phase 2 触发**: high_model_threshold=0.75 触发 full packet; 0.55-0.75 触发 compact packet; 0.40-0.55 watchlist; <0.40 raw archive; 3 override (cross_source_spike + weekly_persistence + internal_priority) 任一触发
- **Phase 3 调用**: 真调 ChatGPT 5.5 Thinking high; full packet 含 run_context + market_context + papers + required_outputs + analysis_questions (per PRD §High Model 输入格式)
- **Phase 4 验证**: 7 资产输出齐 (HF insight report 11 section + cards + seeds + topics + experiments + projects + deep-research); 不允许只复述摘要 (per AC-6); model_call_ledger 记录调用成本
- **Phase 5 失败**: Browser Agent 不可达 → fallback 1 (ChatGPT 5.5 normal 无 thinking) → fallback 2 (mock packet 测试 + 标 unverified); browser-agent-global-operator-cutover 未 PASS 时直接走 fallback 2 + 不阻塞 V2 PASS
- 5 evidence JSON (Phase 1..5)
- **rollback**: 测试 packet 写入 model_call_ledger 用专属 sprint_id 隔离, 结束 DELETE WHERE sprint_id='...s05-v2-test'

### V3 provider_breaker_ingest_4channel_regress (per S04 C3 + S02 D2 + OQ-05)
- **5 provider rate-limit + circuit breaker** (per S04 C3 §5 provider limits): HF / arXiv / HF assets / Semantic Scholar / GitHub 各自 rate cap 验证; 强制超限触发 breaker open; cooldown 后 half-open → closed
- **4 ingest channel ordering** (per OQ-05): raw 同步 → extracted 异步 → QMD 异步 → graph 异步; 验证 raw 先于其他 3 channel 写入完成 (timestamp diff > 0)
- **YAML hot-reload** (per S02 D4): 5 YAML subsection (collection / enrichment / scoring / output / quality) 修改 → atomic write/rename → 不重启进程; 4 routing threshold 修改后立即生效
- **3 gate** 真验证: Packet Gate (5 检查 fail 阻断) + Insight Gate (5 检查 fail 阻断) + Resonance Gate (3 检查 fail 阻断)
- 8 evidence JSON (5 provider + 4 channel ordering + hot-reload + 3 gate)

### V4 regression_aggregation
- S01 67 AC 全验证 (cross 16 outcomes, requirement_ids 完整覆盖)
- S02 D1-D5 决议落地验证 (SQLite WAL + 5 provider limit + Browser Agent reuse + YAML hot-reload + raw-first ingest)
- S03 4 测试套件 (collection / schema / scoring / runtime) 复跑全 PASS
- S04 C1-C5 spec 兑现度验证 (C1 7 asset cards + C2 11 subcommand + C3 5 YAML + C4 5 phase + C5 traceability)
- **S04 6 残留风险** 逐条评估 (per S04 handoff §Remaining Risks):
  1. High model E2E spec-only → V2 已转 real ✅
  2. Config hot-reload race → V3 hot-reload 验证 ✅
  3. Provider breaker spec-only → V3 已转 real ✅
  4. Knowledge ingest latency SLO → V1 L9 + V3 4 channel 已验证
  5. Browser Agent fallback under quota stress → V2 Phase 5 已测
  6. No production rollout without runtime validation → V5 release notes 显式标注
- **5 OQ follow-ups** (per S04 §S05 Kickoff 5) 落地状态
- regression_report.json (67 + 5 + 4 + 5 + 6 + 5 = 92 条 PASS/FAIL 表)

### V5 release_docs_knowledge_raw
- `docs/hf-paper-insight/RELEASE.md` (epic 总览 + S01-S05 摘要 + V1-V4 evidence + rollback (lib/hf_paper_insight/ 子包 + model_call_ledger 数据回滚) + ATLAS hook + 7 output asset 路径)
- **写入 ~/Knowledge/_raw/hf-paper-insight/release/2026-05-29-s05-release.md** (per AC + 切片目标 "写入知识库 raw")
- **同步写入 ~/Knowledge/extracted/hf-paper-insight/2026-05-27/** (per L9, 7 资产真生成)
- **QMD 索引**: by_date/by_topic/by_method/by_asset_type/by_resonance_level/by_projectability/by_deep_research_value (per PRD §QMD 索引目录)
- 禁止乐观词
- `<sid>.eval.{md,json}` sprint 整体 verdict

### V6 join_epic_close_ready
- traceability.json 12 字段 + **parent_check_ready=true** (与 GHPI 不同, 全 upstream PASS)
- epic_required_gates_status (S01-S04 all passed; S05 self passed)
- handoff.md V1-V5 摘要 + epic close checklist + cross-epic 三源共振完成状态
- **不主动 close epic** (epic_decomposer auto-close, V6 仅 mark ready)
- AI Influence cross-epic dependency: HF Paper (Paper Source) + YouTube (Video Source) + GHPI (Project Source) + TH Social X (Social Source) 四源矩阵, 本 sprint 完成 Paper Source

## 4. 写范围

| 节点 | write_scope |
|------|-------------|
| V1 | `reports/hf-paper-insight/s05-acceptance/V1-L0..L10.json` (11) + `<sid>.V1-handoff.md` |
| V2 | `reports/hf-paper-insight/s05-acceptance/V2-phase_{prep,trigger,call,verify,fallback}.json` (5) + `<sid>.V2-handoff.md` |
| V3 | `reports/hf-paper-insight/s05-acceptance/V3-{provider_5,channel_4,hot_reload,gate_3}.json` (8) + `<sid>.V3-handoff.md` |
| V4 | `reports/hf-paper-insight/s05-acceptance/V4-regression_report.json` + `<sid>.V4-handoff.md` |
| V5 | `docs/hf-paper-insight/RELEASE.md` + `Knowledge/_raw/hf-paper-insight/release/2026-05-29-s05-release.md` + `Knowledge/extracted/hf-paper-insight/2026-05-27/{report,cards,seeds,topics,experiments,projects,deep-research}.md` (7) + `<sid>.V5-handoff.md` + `<sid>.eval.{md,json}` |
| V6 | `<sid>.handoff.md` + `<sid>.traceability.json` |

**严格禁止**:
- 真调 ChatGPT 5.5 Thinking 但泄 API key (V2 必须 secret scan)
- 真调 5 provider API 但超 rate limit (V1+V3 必须 rate respect)
- 把 HF ranking 当结论 (per PRD 边界 + AC-6 不允许只复述摘要)
- 把 YouTube 低质 transcript 当强证据 (per PRD 边界 + youtube_match=gated)
- 删除 ~/Knowledge accepted artifacts (V5 仅新增)
- 重启 ThunderOMLX / FlashMLX / honcho / brain-router / qmd-proxy / config-server
- 修改 S03 lib/hf_paper_insight/ 源码 (实施已 PASS, 本 sprint read-only)
- **主动 close epic** (V6 仅 mark parent_check_ready=true, decomposer auto)
- 使用乐观词

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| V1, V2, V3, V5 | sonnet | 真生产 + 5 phase E2E + 8 provider/channel/gate + Knowledge ingest 需 reasoning |
| V4 | glm-5.1 | 回归聚合模板化 |
| V6 | sonnet | join + epic ready 判定 (含 4 源共振 cross-epic) |

## 6. Stop Rules

- 缺 task_graph 不派 builder
- V2 ChatGPT 5.5 Thinking API key 泄露 → 立即 sprint FAIL + incident
- V1+V3 任一 provider 超 rate limit → 立即 sprint FAIL + breaker open 验证
- V1 11 layer 任一 FAIL → S03 round-2 (对应 layer)
- V2 high model 输出仅复述摘要 → V2 FAIL (per AC-6)
- V3 4 channel ordering raw 非首 → S03 round-2 (ingest ordering bug)
- V3 hot-reload race condition → S03 round-2 (atomic write bug)
- V4 任一 AC FAIL → round-2 对应 sprint
- V6 主动 close epic → 立即 FAIL (decomposer auto)
- 不重启 service 进程
- 不动 Knowledge accepted artifacts
- 不用乐观词

## 7. 失败恢复

- V1 失败: L0-L10 任一层出问题 → 标 S03 round-2 (对应 layer)
- V2 失败: Browser Agent 不可用 → fallback 2 (mock packet + unverified 标注); ChatGPT 5.5 quota → fallback 1 (normal 无 thinking)
- V3 失败: provider rate limit 超 → S04 C3 round-2 (limit 配置错); channel ordering 错 → S03 round-2
- V4 任一 AC FAIL → round-2 对应 sprint
- V5/V6 失败 → 单节点重派
- ATLAS 兜底全失败 → 人工介入

## 8. Dogfood / Cross-Epic 关系

- **HF Paper Insight epic 是 AI Influence 四源共振中的 Paper Source**, 与:
  - YouTube Transcript epic (Video Source) — S05 进行中
  - GitHub Project Intelligence epic (Project Source) — S05 进行中 (S04 partial blocking close)
  - TH Social Browser X epic (Social Source) — S02 architecture 完成, 等 hard_blocker
- 本 sprint passed → Paper Source production-ready, 供 AI Influence digest 消费 + 三源共振 R0-R5 计算
- 与 TUI Pane Recover epic 共同推进: TUI S05 PASS 后, 本 sprint V1-V6 builder pane 卡死问题自动 detect+clear+reassign

## 9. 非目标

- 不实施新代码 (S03 已完成, S04 spec 已就位)
- 不动 S03/S04 artifacts (read-only verification)
- 不主动 close epic (decomposer auto)
- 不重启 service 进程
- 不动 ThunderOMLX cache / FlashMLX KV
- 不删 Knowledge vault accepted artifacts
- 不把 HF ranking 当结论
- 不把 YouTube 低质 transcript 当强证据

## 10. Knowledge Context

S03 handoff (concise but verified: 4 suite + auto sidecar) + S04 handoff (7K, C1-C5 全 PASS + 6 残留风险 + 3 OQ-C5 + 5 S05 kickoff) + S02 design (5 OQ 决议) + S01 67 AC (16 outcomes) + PRD 11 AC + 10 layer + 7 assets + 5 scoring + 4 routing + 5 provider + 4 ingest + 3 gates = ~50K+ upstream evidence。`context inject` 已跑, mirage degraded → QMD/Obsidian/Solar DB fallback。
