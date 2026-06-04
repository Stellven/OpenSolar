# Plan — S03 Core-Runtime (YouTube Transcript 核心实施切片)

gate: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s03-core-runtime:passed`
knowledge_context: solar-harness context inject used
upstream: S02 architecture passed (D1-D13, OQ1-OQ4)
downstream: S04 orchestration-ui (parallel) → S05 verification-release

## 0. 切片定位（区别于 S01/S02/S04）

S03 是 **实施切片**, 与 S01/S02/S04 不同, **必须写真代码**。Builder 在每个节点真实施 Python 模块 + SQLite migration + pytest 测试。本 sprint 的 evidence_policy.no_code=false (允许写代码), 但仍禁止真跑 yt-dlp / OpenAI / 生产 DB。

## 1. DAG (严格串行 phase + 验收 + join)

```
B1_phase1_foundation (5 模块 + 1 config + 1 migration)
    └─→ B2_phase2_middle (3 模块 + 9 migration + 165 清理工具)
          └─→ B3_phase3_application (5 模块 + 1 migration)
                └─→ B4_phase4_interface (2 模块 + legacy wrapper)
                      └─→ B5_acceptance_gates (6 验收报告)
                            └─→ B6_traceability_handoff (join)
```

**为何串行**: Phase 间数据流依赖 (audio→storage→quality_gate→dashboard)。Phase 内部 builder 一次性实施多个文件 (减少 dispatch 开销, per Solar 4-pane 经验)。

## 2. 每节点验收 (硬阈值)

| 节点 | 关键验收 |
|------|----------|
| **B1** Phase 1 foundation | 5 模块 + youtube_config 全实施 + youtube_001_subtitle_tracks migration; pytest B1 套件 pass; ≥80% line coverage; subtitle_discovery 支持 mock fixture; asr_router 从 config YAML 读路由表 (per D3); priority_queue 6 因子公式 (0.25/0.20/0.20/0.15/0.10/0.10) |
| **B2** Phase 2 middle | audio_middleware ffmpeg+VAD 实施 + chunk_length config-driven; job_scheduler next_retry_at 轮询 + 5 error_code backoff; transcript_storage 9 表 migration (含 youtube_intelligence_migrations); pollution_repair --dry-run 验证 fixture DB COUNT=165 |
| **B3** Phase 3 application | quality_gate 两阶段实施 (Phase 1 skip technical_term_hit_rate, Phase 2 R9 后重算; T0/T1/T2/T3 hardcoded); vocab_correction 7 类来源 + sha256 + sync_interval_hours=168; report_eligibility evidence pack + 5 validator 拒绝; cross_source_extractor spaCy en_core_web_sm + 实测 recall ≥70% (per OQ4); premium_escape OpenAI gpt-4o-transcribe + ledger 7 字段 + budget cap 20 USD WAL serialized |
| **B4** Phase 4 interface | dashboard 9 指标 JSON aggregation (no HTML/TUI); cli 6 命令 argparse + 退出码 0/1/2/3; legacy process-transcripts 兼容包装 (per D12) 内部调用 process-transcript-jobs |
| **B5** acceptance gates | 6 报告 (pytest / dry-run / threshold / budget / pollution / atomicity) 全 PASS; 真 SQLite 不 mock; budget concurrent 测试; 165 清理 SQL=0 |
| **B6** join | traceability.json 12 字段 (含 modules_implemented[12] / tables_created[9] / s04+s05 dependencies); handoff 含 B1-B5 摘要 + 6 acceptance 报告路径 + 剩余风险 (OQC-1..OQC-5) |

## 3. Stop Rules

- 缺 task_graph.json 不得派 builder (已满足)
- 任一 phase 验收不通过不进下一 phase
- 不真跑 `solar-harness wiki tech-hotspot-radar` 子命令
- 不真调 OpenAI / yt-dlp 真下载 / 真生产 DB
- 不动 ~/.solar/harness/lib/tech_hotspot_radar/ 现有源 (除 legacy wrapper)
- 不改 S02 artifacts (有问题 → B6 OQ-new)
- 不主动 close 父 epic
- 不放宽 R8 hard 阈值 (T0≥0.85/T1≥0.70/T2≥0.50)
- 不用乐观词

## 4. SLO

| 指标 | hard | soft |
|------|------|------|
| 12 模块实施 | < 12 → FAIL | n/a |
| 9 表 migration | < 9 → FAIL | n/a |
| 165 污染清理 (fixture DB) | SQL COUNT > 0 → FAIL | n/a |
| pytest line coverage | < 70% → FAIL | < 80% → WARN |
| spaCy NER recall (OQ4) | < 70% → FAIL (标 fallback) | < 80% → WARN |
| premium budget daily cap | > 20 USD → 立即 FAIL | n/a |
| R8 hard 阈值放宽 | > 0 → 立即 FAIL | n/a |
| 真调 OpenAI / yt-dlp 真下载 / 真生产 DB | > 0 → 立即 FAIL | n/a |

## 5. 失败恢复

- B1-B4 任一 phase FAIL: 同一节点重派; 反复失败 → ATLAS structured repair (per Solar runtime context)
- B5 验收任一 FAIL: 回到对应 B1-B4 phase 修复; 不放宽阈值
- B6 join FAIL: 诊断 phase 模块缺失/接口偏离 S02; 不擅自修 S02
- OQC-3 (spaCy recall) 不达标 → 标 trigger_source='fallback_no_r11' 继续, 不阻塞 sprint
- OQC-1 (R8 原子性) 测试失败 → 必须修, 不放过

## 6. 模型路由

| 节点 | 模型 | 理由 |
|------|------|------|
| B1-B5 | glm-5.1 | 实施代码 + 测试模板化 |
| B6 | sonnet | 跨 phase 聚合 |

## 7. 给下游接力

B6 traceability `downstream_sprint_kickoff_package`:
- **S04 (并行)** inputs: transcript-status --json schema / 6 CLI 注册点 / youtube_config pydantic / premium_escape API
- **S05 verification-release** inputs: 6 acceptance reports / premium E2E 真跑用例 (mock 实施 + 留 S05 真跑) / 165 真生产清理 / dashboard 集成测试

S03 + S04 都 passed 后 coordinator 激活 S05。

## 8. Knowledge Context

`solar-harness context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB; ATLAS / Everything Claude Code / Solar-Harness Runtime / Superpowers / solar-graph-scheduler capabilities injected。S02 5 份 artifacts (架构 547 行 + DDL 406 行 + 接口 500+ 行 + OQ 247 行 + handoff) 是本 sprint self-contained 输入。
