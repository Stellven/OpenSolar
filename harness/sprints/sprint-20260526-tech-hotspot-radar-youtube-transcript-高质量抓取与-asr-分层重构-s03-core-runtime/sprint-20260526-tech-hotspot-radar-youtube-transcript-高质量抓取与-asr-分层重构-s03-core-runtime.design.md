# Design — S03 Core-Runtime 切片：YouTube Transcript 核心实施 (12 模块 + 9 表 + R8 两阶段 + 6 验收门禁)

epic_id: `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构`
sprint_id: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s03-core-runtime`
slice: `core-runtime`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-27T17:27:30Z`
knowledge_context: `solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)`
upstream: `S02 architecture passed (D1-D13, OQ1-OQ4, 14 模块 / 9 表 DDL / 14 API 签名)`
downstream: `S04 orchestration-ui (parallel) → S05 verification-release`

## 0. 切片边界（区别于 S01/S02/S04）

- **S03 是 core-runtime 实施切片**: 与 S01/S02/S04 不同, **本 sprint 必须写真实施代码**, 不再只写 markdown。
- **本 sprint 允许的写范围**:
  - `~/.solar/harness/lib/youtube/` 整个目录新建 (12 模块的 Python 代码 + 模块结构)
  - `~/.solar/harness/lib/youtube_config.py` (per D13)
  - `~/.solar/harness/lib/tech_hotspot_radar/` 现有目录的扩展 (legacy 兼容包装)
  - 数据迁移脚本: `~/.solar/harness/migrations/youtube_*.py`
  - 测试: `~/.solar/harness/tests/test_youtube_*.py`
  - SQLite DB: 测试用 `~/.solar/harness/tests/fixtures/youtube_test.db` (生产 DB 路径走 config)
  - Sprint artifacts: `<s03-sid>.handoff.md`, `<s03-sid>.traceability.json`, `<s03-sid>.B*-handoff.md` (per builder phase)
- **严格禁止**:
  - 真跑 `solar-harness wiki tech-hotspot-radar` 任何子命令 (留 S05)
  - 真调 OpenAI API (premium_escape 实施 + mock 测试; 真跑留 S05)
  - 真下载 YouTube 视频或调真 yt-dlp (audio_middleware/subtitle_discovery 实施 + mock fixture)
  - 改 S02 architecture / data_models / interfaces / OQ resolutions 文件 (有问题 → C5 记 OQ-new)
  - 触动生产数据库 (165 条污染清理只在测试 fixture DB 跑, 真生产清理留 S05)
  - 修改父 epic 任何 artifact

## 1. 上游消费（从 S02 handoff 全集复用）

| S02 决议 | S03 实施 |
|----------|----------|
| D1 (acquisition_ladder 独立模块) | B1 实施 `lib/youtube/acquisition_ladder.py` 暴露 `decide_ladder_path()` |
| D2 (CREATE TABLE IF NOT EXISTS + 4-tuple UNIQUE + migrations 表) | B2 实施 schema migration python 工具 |
| D3 (asr_router 独立 + routing table from config YAML) | B1 实施 `lib/youtube/asr_router.py` 从 config YAML 读取 |
| D4 (audio_middleware ffmpeg+VAD + 7 天 TTL WAV chunks) | B2 实施 `lib/youtube/audio_middleware.py` |
| D5 (P0/P1/P2/P3 阈值 0.80/0.60/0.35 hardcoded 入 config) | B1 实施 `lib/youtube/priority_queue.py` |
| D6 (next_retry_at 轮询 + 5 error_code backoff + 外部 cron) | B2 实施 `lib/youtube/job_scheduler.py` |
| D7 (纯 Python DDL + SQLite 队列 + audit-transcript-quality --repair-pollution) | B2 实施 storage + B2 实施 165 清理工具 |
| D8 (quality_gate inline 两阶段 + Phase 1 skip technical_term_hit_rate) | B3 实施 `lib/youtube/quality_gate.py` 两阶段 |
| D9 (vocab Pull + 周频率 sync_interval_hours=168 + sha256) | B3 实施 `lib/youtube/vocab_correction.py` |
| D10 (OpenAI gpt-4o-transcribe + youtube_premium_asr_calls 表 + SQLite WAL serialized budget check) | B3 实施 `lib/youtube/premium_escape.py` |
| D11 (dashboard JSON-only 基线; HTML/TUI 推迟 S04) | B4 实施 `lib/youtube/dashboard.py` JSON aggregation only |
| D12 (CLI 挂 solar-harness wiki tech-hotspot-radar + legacy process-transcripts 包装) | B4 实施 CLI 命令注册 + legacy compat |
| D13 (youtube_config pydantic v2 模块 + env_prefix=SOLAR_YOUTUBE_) | B1 实施 `lib/youtube_config.py` |
| OQ1 (OpenAI gpt-4o-transcribe + $0.006/min fallback faster-whisper) | B3 premium_escape 实施 |
| OQ2 (WhisperX ≤60min/10GB VRAM, >60min → faster-whisper + post-hoc clustering) | B2 audio_middleware + asr_router 实施 |
| OQ3 (R8↔R9 两阶段, Phase 1 skip + Phase 2 R9 后重算) | B3 quality_gate 实施 |
| OQ4 (R11 entity recall ≥70% 主, keyword+metadata 次, fallback 标 trigger_source) | B3 cross_source + premium_escape 实施 |

## 2. S03 内部 DAG（4 phase 严格串行 + 验收 + join）

```
B1_phase1_foundation (5 模块: subtitle_discovery / acquisition_ladder / asr_router / priority_queue / youtube_config + subtitle_tracks DDL)
    └─→ B2_phase2_middle (4: audio_middleware / job_scheduler / transcript_storage 9 表 + migrations / 165 清理工具)
          └─→ B3_phase3_application (6 模块: quality_gate 两阶段 / vocab_correction / report_eligibility / cross_source_extractor / premium_escape / 其他粘合)
                └─→ B4_phase4_interface (2: dashboard JSON / cli 6 命令 + legacy compat)
                      └─→ B5_acceptance_gates (6 验收: pytest / dry-run / threshold / budget / pollution / atomicity)
                            └─→ B6_traceability_handoff (join)
```

**为何串行**: Phase 2 audio_middleware 依赖 Phase 1 asr_router 决定的路由 schema; Phase 3 quality_gate 依赖 Phase 2 transcript_storage 表; Phase 4 dashboard 依赖 Phase 3 所有模块写入数据。

**Phase 内部并行**: 每个 Bx 节点内 builder 实施多个文件; 单节点不切分以减少 coordinator dispatch 开销 (per Solar 4-pane 经验)。

## 3. 节点写范围（互斥保证）

| 节点 | write_scope (互斥) |
|------|---------------------|
| B1 | `lib/youtube/{subtitle_discovery,acquisition_ladder,asr_router,priority_queue}.py` + `lib/youtube_config.py` + `lib/youtube/__init__.py` + migration `youtube_001_subtitle_tracks.py` + `tests/test_youtube_{subtitle_discovery,ladder,router,queue,config}.py` |
| B2 | `lib/youtube/{audio_middleware,job_scheduler,transcript_storage}.py` + migrations `youtube_00{2,3,4,5,6,7,8,9}_*.py` (9 表) + repair tool `lib/youtube/pollution_repair.py` + `tests/test_youtube_{audio,scheduler,storage,repair}.py` |
| B3 | `lib/youtube/{quality_gate,vocab_correction,report_eligibility,cross_source_extractor,premium_escape}.py` + migration `youtube_010_premium_asr_calls.py` + `tests/test_youtube_{quality,vocab,eligibility,cross_source,premium}.py` |
| B4 | `lib/youtube/{dashboard,cli}.py` + `lib/tech_hotspot_radar/_youtube_cli_wrapper.py` (legacy compat) + `tests/test_youtube_{dashboard,cli}.py` |
| B5 | `tests/conftest.py` (suite-level fixtures) + `tests/integration/test_youtube_e2e.py` + 6 验收报告 `reports/youtube/s03-acceptance/{pytest,dry-run,threshold,budget,pollution,atomicity}.json` |
| B6 | `<s03-sid>.traceability.json` + `<s03-sid>.handoff.md` + `<s03-sid>.B6-handoff.md` |

## 4. 每节点验收

### B1 (Phase 1 foundation)
- 5 模块 + 1 config + 1 DDL migration 全实施
- `subtitle_discovery` 调用 yt-dlp `--list-subs --skip-download` (real network, but rate-limited)；fallback 到 mock fixture (`tests/fixtures/yt-dlp-list-subs.json`) 当 network=off
- `acquisition_ladder.decide_ladder_path(video_id, available_tracks) → LadderPath` 单元测试
- `asr_router.route(priority, language, video_features) → ASRBackend` 6 行路由表从 config YAML 读
- `priority_queue.compute_priority_score(video) → float` 6 因子公式
- `youtube_config` pydantic v2 + env_prefix='SOLAR_YOUTUBE_' + 5 子段
- migration `youtube_001_subtitle_tracks` `CREATE TABLE IF NOT EXISTS` (per D2)
- pytest B1 套件全 pass; ≥80% line coverage 5 模块

### B2 (Phase 2 middle)
- `audio_middleware` ffmpeg loudnorm/highpass/lowpass + VAD chunking 120-300s/1.5s/1s/0.5s (mock ffmpeg in test, real binary in integration test if env=on)
- `job_scheduler` next_retry_at 轮询 + 5 error_code backoff state machine
- `transcript_storage` 9 张表 migration (含 youtube_intelligence_migrations 记录表)
- pollution repair tool dry-run 验证 COUNT=165 on test fixture DB
- audio chunks 7 天 TTL 删除策略 (per D4)
- pytest B2 套件全 pass; SQLite WAL 单事务 UPDATE 原子性测试覆盖

### B3 (Phase 3 application)
- `quality_gate` Phase 1 (6 sub-scores) + Phase 2 (R9 vocab corrected technical_term_hit_rate → final_score) 两阶段实施 (per OQ3)
- T0≥0.85 / T1≥0.70 / T2≥0.50 / T3<0.50 hardcoded
- `vocab_correction` 7 类来源 + pull ingest + sync_interval_hours=168 + sha256 (per D9)
- `report_eligibility` evidence pack JSON + T-tier 准入 + 5 validator 拒绝 (per R10)
- `cross_source_extractor` 7 类 entity (spaCy en_core_web_sm) + 4 类 cross-link + recall ≥70% (per OQ4); if recall < 70% → 标 trigger_source='fallback_no_r11'
- `premium_escape` OpenAI gpt-4o-transcribe + 7 字段 ledger + daily budget=20 USD + SQLite WAL serialized (per OQ1 + D10)
- pytest B3 套件全 pass; spaCy NER recall ≥70% 实测验证

### B4 (Phase 4 interface)
- `dashboard.aggregate() → DashboardJSON` 9 指标 JSON-only (per D11)
- `cli` 6 命令 (discover-transcript-tracks / acquire-transcripts / process-transcript-jobs / audit-transcript-quality / transcript-status / transcript-ab-test-asr) argparse
- legacy `process-transcripts` 兼容包装 (per D12) 内部调用 `process-transcript-jobs --priority P0,P1,P2`
- 退出码 0/1/2/3 统一
- pytest B4 套件全 pass

### B5 (acceptance gates)
- pytest suite 全 pass (no DB mock, real SQLite in tests/fixtures/youtube_test.db)
- `process-transcript-jobs --dry-run` 不写 DB
- quality_score 阈值 hardcoded 验证 (T0/T1/T2/T3 边界值测试)
- premium budget daily cap=20 USD 并发不超标测试 (per OQC-4)
- 165 条污染清理实测验证 SQL 返回 0 (test fixture DB)
- Phase 1/2 执行编排原子性测试 (per OQC-1 SQLite WAL 单事务 UPDATE)
- 6 验收报告落盘 `reports/youtube/s03-acceptance/`

### B6 (join handoff/traceability)
- traceability.json 12 字段 (含 modules_implemented[12] / tables_created[9] / migrations_applied[10] / s04_dependencies / s05_dependencies)
- handoff.md 含 B1-B5 摘要 + 验收报告路径 + S04/S05 启动 checklist + 剩余风险 (OQC-1..OQC-5)

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| B1, B2, B3, B4 | glm-5.1 | 实施代码量大但模式化 (per S02 决议)，省钱 |
| B5 | glm-5.1 | 测试 + 验证脚本 |
| B6 | sonnet | 跨 phase 聚合 + S04/S05 接力 reasoning |

## 6. Stop Rules

- 缺 task_graph.json 不得派 builder (本 sprint 已满足)
- 缺可复现验证不得标记 passed
- 任一 phase 验收不通过, 不得进下一 phase
- 不真跑 `solar-harness wiki tech-hotspot-radar` 任何子命令
- 不真调 OpenAI API (mock 测试 + 留 S05 真跑)
- 不真下载 YouTube 视频 (mock fixture 优先)
- 不动生产 DB (清理只在 test fixture DB)
- 不改 S02 任何 artifact (有问题 → B6 OQ-new)
- 不主动 close 父 epic
- 不放宽 R8 hard 阈值 (T0≥0.85/T1≥0.70/T2≥0.50)
- 不用乐观词

## 7. SLO

| 指标 | hard | soft |
|------|------|------|
| 12 模块实施 | < 12 → FAIL | n/a |
| 9 表 DDL migration | < 9 → FAIL | n/a |
| 165 条污染清理实测 | SQL COUNT > 0 → FAIL | n/a |
| pytest line coverage | < 70% → FAIL | < 80% → WARN |
| spaCy NER recall (OQ4) | < 70% → FAIL (标 fallback) | < 80% → WARN |
| premium budget daily cap | > 20 USD → 立即 FAIL | n/a |
| R8 hard 阈值放宽 | > 0 → 立即 FAIL | n/a |
| 真调 OpenAI/yt-dlp/真生产 DB | > 0 → 立即 FAIL | n/a |

## 8. 失败恢复

- B1 失败 → 单 phase 重派, 不进 B2
- B2/B3 失败 → 同一节点重派; 若反复失败 → ATLAS structured repair
- B4 失败 → 不进 B5
- B5 验收任一 FAIL → 回到对应 B1-B4 修复
- B6 失败 → 诊断哪个 phase 模块缺失/接口偏离 S02; 不擅自修 S02

## 9. 非目标

- 不写实施代码以外的内容 (B1-B5 必须真代码; 不是 markdown spec)
- 不真跑 yt-dlp / faster-whisper / WhisperX / OpenAI / solar-harness 命令
- 不动生产数据库
- 不改 S02 artifacts
- 不主动 close epic
- 不用乐观词
- 不放宽阈值
- 不实施 S04 范围 (dashboard HTML/TUI / radar 面板集成 / premium E2E 真跑 / config UI)

## 10. 给下游接力

- B6 traceability `downstream_sprint_kickoff_package`:
  - **S04 (与本 sprint 并行)** inputs: `transcript-status --json` 输出 schema / 6 CLI 命令注册点 / youtube_config pydantic model / premium_escape 模块接口
  - **S05 verification-release** inputs: 6 acceptance reports / premium E2E 用例 (B3 实施了 mock, 留 S05 真跑) / 165 真生产清理 / dashboard HTML/TUI 集成测试

S03 + S04 都 passed 后 coordinator 激活 S05。
