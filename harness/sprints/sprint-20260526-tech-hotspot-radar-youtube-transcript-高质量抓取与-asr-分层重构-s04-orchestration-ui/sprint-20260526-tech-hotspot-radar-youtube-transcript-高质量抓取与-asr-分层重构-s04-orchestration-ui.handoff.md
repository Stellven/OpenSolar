# Handoff — S04 Orchestration-UI: YouTube Transcript Dashboard + CLI + Config + Premium E2E

sprint_id: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s04-orchestration-ui`
epic_id: `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构`
node: `C5_traceability_handoff`
generated_at: `2026-05-27T19:25:00Z`

---

## C1-C4 各产出路径与摘要

### C1 — Dashboard Renderer (R13)

**路径**: `sprints/<s04-sid>.dashboard_renderer.md`

**摘要**: 9 指标渲染规约 (HTML + TUI 双方案)，引用 visual-template.html CSS 变量体系。SLO 状态行 (P0 wait / premium ratio / premium cap) 红/黄/绿高亮。数据源 transcript-status --json。6 条验收标准。builder_eligible=conditional (需 S03 transcript-status --json)。

**节点状态**: passed

### C2 — CLI Command Tree (R14)

**路径**: `sprints/<s04-sid>.cli_command_tree.md`

**摘要**: 6 命令挂载 solar-harness wiki tech-hotspot-radar 命名空间 + legacy process-transcripts 永久保留兼容包装。退出码 0/1/2/3 统一。subcommand 路由 + cron 使用示例。5 条验收标准。builder_eligible=conditional (需 S03 CLI 框架 + R7 jobs 表)。

**节点状态**: passed

### C3 — Config UI + Radar Panel (R15 + R13)

**路径**: `sprints/<s04-sid>.config_ui_and_radar_panel.md`

**摘要**: 5 子段 Config UI 渲染草图 (pydantic v2 YoutubeConfig + 5 个 [LOCKED DEFAULT] 高亮)。env_prefix=SOLAR_YOUTUBE_ 注入路径。Radar 面板 youtube_transcript 区域块嵌入 Social Clusters 之后。4 条验收标准。builder_eligible=conditional (需 S03 youtube_config + env_nested_delimiter)。

**节点状态**: passed

### C4 — Premium ASR E2E Validation Plan

**路径**: `sprints/<s04-sid>.premium_e2e_validation_plan.md`

**摘要**: OpenAI gpt-4o-transcribe 端到端验证 5 阶段用例 (准备→触发→调用→验证→失败)。cost=$0.006/min。budget cap=$20/day 硬上限。fallback 到 faster-whisper large-v3。5 条验收标准。builder_eligible=NO (只写计划，真跑留 S05)。

**节点状态**: passed

---

## Traceability 摘要

| 指标 | 值 |
|------|-----|
| Outcome 总数 | 4 (C1..C4) |
| 全部 passed | 4/4 |
| S02 决议消费 | 5 (D10/D11/D12/D13 + OQ1) |
| S03 依赖 | 7 项接口清单 |
| Open Questions | 3 (OQ-C5-01..03, 全 owner=S03) |
| 下游 S05 验证包 | dashboard 9 指标 + CLI 6 命令 + legacy E2E + premium E2E 真跑 |

---

## S05 启动 Checklist

S05 (Verification-Release) 启动前必须完成以下步骤：

### Step 1: 确认 S03 实施就绪

- [ ] S03 `transcript-status --json` 已实现，JSON schema 与 C2 §4.5 对齐 (OQ-C5-01)
- [ ] S03 6 CLI 命令 argparse/click 框架已搭建
- [ ] S03 `youtube_config.py` pydantic v2 模块已实现 + env_nested_delimiter 已选定 (OQ-C5-02)
- [ ] S03 `premium_escape.py` 模块已实现 + 单元测试通过
- [ ] S03 `youtube_transcript_jobs` 表 DDL 已执行

### Step 2: Dashboard 9 指标验证

1. 运行 `transcript-status --json` 验证 9 指标字段全存在
2. HTML 渲染: 4 分组布局 + visual-template CSS + SLO 红/黄/绿高亮
3. TUI 渲染: Rich 表格 + Radar youtube_transcript 区域块位置正确
4. 降级: 数据源不可用时显示 "no data yet" (不是 0)
5. SLO breach 高亮不为纯文字 (必须有颜色)

### Step 3: CLI 6 命令 E2E 验证

1. `discover-transcript-tracks --limit 1 --dry-run` → exit 0, stdout schema 正确
2. `acquire-transcripts --limit 1 --dry-run` → exit 0, stdout 含 dry_run=true
3. `process-transcript-jobs --priority P0 --limit 1 --dry-run` → exit 0
4. `audit-transcript-quality --tiers` → exit 0, tier_distribution 4 级
5. `transcript-status --json` → exit 0, 9 指标 + slo_status 全字段
6. `transcript-ab-test-asr --limit 1 --dry-run` → exit 0

### Step 4: Legacy 兼容 E2E 验证

1. `process-transcripts --video-ids <id> --dry-run` → 入队 R7 jobs (不绕过)
2. stdout 旧字段 processed/failed 存在 + deprecated 字段存在
3. `--force-rerun` 重置 job status=pending

### Step 5: Premium ASR E2E 真跑 (使用真 OpenAI key + $20 budget)

1. Phase 1 准备: `SOLAR_YOUTUBE_PREMIUM_OPENAI_KEY` 注入 + grep 日志无 key
2. Phase 2 触发: `should_trigger_premium()` P0 + entity recall ≥70%
3. Phase 3 调用: gpt-4o-transcribe call + ledger 7 字段写入
4. Phase 4 验证: cost=$0.006×ceil(minutes) + budget ≤$20 + quality_score 提升
5. Phase 5 失败: mock API 500 → retry → 降级 faster-whisper + ledger fallback_reason

---

## 剩余风险

1. **OQ-C5-01**: C1/C2 transcript-status JSON schema 交叉引用 — S03 实施时以 C2 §4.5 为权威
2. **OQ-C5-02**: pydantic v2 env_nested_delimiter 未定 — 部分 env 覆盖可能静默失效
3. **OQ-C5-03**: Config 文件默认路径是草案 — S03 确认
4. **Rich 库未安装**: TUI 渲染不可用
5. **OpenAI API 变价**: $0.006/min 公式需同步
6. **25MB chunk 限制**: 长视频分片后独立计费，实际 cost 略高

---

## 禁止乐观词声明

本文档及本 sprint 所有产出中禁止使用：已修复 / 稳定 / 完美 / 无需担忧 / done / complete / implemented。

S04 为规约层，未实施任何代码。所有功能描述为规约层面。

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge (Read: C1-C4 docs + PRD + design + S02 handoff/traceability)
