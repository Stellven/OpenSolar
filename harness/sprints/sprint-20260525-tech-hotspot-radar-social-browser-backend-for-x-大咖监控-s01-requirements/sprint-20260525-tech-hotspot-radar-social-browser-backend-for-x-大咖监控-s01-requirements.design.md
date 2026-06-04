# Design — Tech Hotspot Radar Social Browser Backend for X S01 Requirements

epic_id: `epic-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控`
sprint_id: `sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements`
slice: `requirements`
role: planner
status: planning_complete
generated_at: 2026-05-28T17:42:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
hard_dependency_blocker: `sprint-20260525-browser-agent-global-operator-cutover` (本 epic 任何实施 sprint 都不得启动直到该上游 PASS)

## 0. 切片定位

Epic 首切片 (requirements 拆解). PRD 6.6K, 10 AC, 含硬依赖 blocker (Browser Agent global physical operator). 复用其他 S01 同款 N1-N4 pattern。本切片只产规约文档, 不实施代码。

## 1. PRD → outcome 映射 (10 AC 聚合为 10 outcome)

| outcome_id | 标题 | PRD AC | 节点 |
|------------|------|--------|------|
| O1 | Backend order (browser > rss > manual > x_api optional) | AC-1, AC-3 | N1 |
| O2 | Browser physical operator 6 capabilities (open/wait/scroll/dom/screenshot/close) | AC-2 | N1 |
| O3 | Rate limiting (per-account cooldown + global concurrency=1 + jittered + exp backoff + tier1/tier2) | AC-5 | N1 |
| O4 | Data extraction (post 11 字段含 metrics + raw DOM hash + screenshot fallback + collection_backend=browser_agent) | AC-2 | N2 |
| O5 | Deduplication (canonical URL or sha256(handle+text+time)) | AC-4 | N2 |
| O6 | Downstream integration (social_posts → metrics → semantic → links → viewpoints → propagation → GitHub/YouTube/paper dispatch → Knowledge raw → AI Influence report → model_call_ledger) | AC-6, AC-7, AC-8 | N2 |
| O7 | CLI (collect-social --backend browser/auto --limit-accounts N) | AC-2 | N3 |
| O8 | WebUI/Status (7 指标: total/enabled/scanned today/ready/pending/parse fail/fallback/by backend) | (隐含) | N3 |
| O9 | Hard blocker enforcement (本 sprint 不启动实施直到 browser-agent-global-operator-cutover PASS) | AC-1 | N3 |
| O10 | Non-goals 聚合 (10 条 含不全网爬虫 / 不绕风控 / 不重复 ThunderOMLX 实例) | AC-9, AC-10 | N4 |

## 2. 4-Node DAG

```
                ┌─→ N1_backend_operator_ratelimit (O1+O2+O3)  ─┐
   (无上游) ────┼─→ N2_extraction_dedup_downstream (O4+O5+O6) ─┼─→ N4_join
                └─→ N3_cli_webui_blocker          (O7+O8+O9)  ─┘
```

3 wave-1 并行 + N4 join (含 O10 non-goals 聚合)

## 3. Stop Rules

- 不实施代码 (S01 是规约层)
- 不真跑 browser agent (上游未完成)
- 不真改 X API token (本 sprint 是规约)
- 不绕过 X 风控 / 登录限制
- 不启动第二套 Browser/DeepResearch 系统
- 不新增重复 ThunderOMLX 实例
- 不打印 secrets (X cookie / token)
- 不主动 close 父 epic
- **Hard blocker**: 本 epic 任何实施 sprint 必须等 `sprint-20260525-browser-agent-global-operator-cutover` PASS

## 4. Knowledge Context

PRD 6.6K self-contained. mirage degraded → QMD + Obsidian + Solar DB.
