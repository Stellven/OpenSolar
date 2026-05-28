# Handoff — sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s02-architecture

Sprint: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s02-architecture`
Epic: `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构`
Generated: `2026-05-27T16:10:00Z`
Knowledge Context: solar-harness context inject used

---

## A1–A4 各产出路径 + 摘要

| 节点 | 产出路径 | 状态 | 摘要（≤100字） |
|------|---------|------|--------------|
| A1_architecture | `sprint-...-s02-architecture.architecture.md` (547行) | passed | Phase 1-4 全景图 + 15 模块划分 + control/data plane 边界 + 5 状态机 + D1-D13 全部决议 + S03/S04/S05 接力清单。 |
| A2_data_models | `sprint-...-s02-architecture.data_models.md` (406行) | passed | 9 张表 DDL 草案（含 R2/R7×4/R11/R12/R9/D2）+ 14 热路径索引 + legacy 3 阶段迁移 + 165 条污染清理 SQL + 存储估算 + PG vs SQLite 降级路径。 |
| A3_interfaces | `sprint-...-s02-architecture.interfaces.md` (500+行) | reviewing | 14 模块 Python 签名 + 6 CLI 签名+退出码+schema + legacy compat wrapper + R15 YAML 5 子段 + evidence_pack/dashboard JSON schema + 4 类事件契约 + API v1 lock + 5 S05 mock 边界。 |
| A4_open_questions_resolutions | `sprint-...-s02-architecture.open_questions_resolutions.md` (247行) | reviewing | OQ1 OpenAI gpt-4o-transcribe + OQ2 WhisperX ≤60min/10GB VRAM + OQ3 两阶段 R8↔R9 循环解法 + OQ4 entity recall ≥70%+keyword fallback + 14 blocked_by 解链。 |

---

## 13 决议摘要（D1–D13）

| Dec | 关键决议 |
|-----|---------|
| **D1** | acquisition_ladder 独立模块；暴露 `decide_ladder_path()` 接口；dispatcher 不含 ladder 逻辑 |
| **D2** | `CREATE TABLE IF NOT EXISTS` + 4-tuple UNIQUE + `youtube_intelligence_migrations` 表记录迁移历史 |
| **D3** | asr_router 独立模块；路由表编码在 config YAML，不硬编码 Python |
| **D4** | audio_middleware 封装 ffmpeg + VAD chunking；WAV chunks 7 天 TTL 后删除；不写 jobs 表 |
| **D5** | P0/P1/P2/P3 阈值（0.80/0.60/0.35）hardcoded 入 config；S04 post-launch 基于真实数据调整 |
| **D6** | `next_retry_at` 轮询调度；外部 cron（launchd）调用 CLI；不引入 daemon 或 asyncio |
| **D7** | 纯 Python DDL + SQLite 队列（无 Redis）；165 条污染清理通过 `audit-transcript-quality --repair-pollution` |
| **D8** | quality_gate inline 两阶段（per OQ3）；Phase 1 skip `technical_term_hit_rate`；Phase 2 R9 后重算 final_score |
| **D9** | vocab Pull 模型 + 周频率；sha256 版本化；ThunderOMLX 二阶校正为异步 suggested_corrections，不在 critical path |
| **D10** | OpenAI gpt-4o-transcribe（per OQ1）；独立 `youtube_premium_asr_calls` 表；SQLite WAL 串行 budget check |
| **D11** | dashboard JSON-only 作 S03 基线；HTML/TUI 推迟 S04；Tech Hotspot Radar 面板集成由 S04 实现 |
| **D12** | CLI 挂 `solar-harness wiki tech-hotspot-radar` 命名空间；legacy `process-transcripts` 保留，内部调用新 job ladder |
| **D13** | 独立 `youtube_config` pydantic v2 模块（harness/lib/youtube_config.py）；env_prefix='SOLAR_YOUTUBE_'；不改全局 config loader |

---

## 4 OQ 决议摘要（OQ1–OQ4）

| OQ | 标题 | 决议 | Owner |
|----|------|------|-------|
| **OQ1** | Premium ASR Provider | OpenAI gpt-4o-transcribe，$0.006/min；AWS/Azure/GCP 因成本高被排除；Fallback→faster-whisper large-v3 | S03 |
| **OQ2** | WhisperX GPU 内存 + 长视频 Chunking | WhisperX+diarization 限 ≤60min/10GB VRAM；>60min→faster-whisper large-v3+post-hoc clustering；阈值 config 可调 | S03 |
| **OQ3** | R8↔R9 循环依赖 | 两阶段：Phase 1 skip technical_term_hit_rate→preliminary_tier；Phase 2（T0/T1/T2）→R9 vocab correction→final_score；T3 不进 Phase 2 | S03 |
| **OQ4** | R12 触发条件 #5 Entity 召回率 | R11 entity 抽取为主触发器（recall≥70%）；keyword+metadata 为次优触发器；R11 不可用时仅用 secondary，标 trigger_source='fallback_no_r11' | S03 |

---

## S03 启动 Checklist

**前置：S02 评审通过后方可进入 S03**

### 基础层（Phase 1，解锁后续一切）

- [ ] 读取全部 S02 产出：architecture.md + data_models.md + interfaces.md + open_questions_resolutions.md + 本 handoff.md
- [ ] `subtitle_discovery` + `acquisition_ladder` 实现（L0-L5 状态机 + 10 优先级规则，per D1）
- [ ] `youtube_subtitle_tracks` DDL + 幂等 discovery（per D2，IF NOT EXISTS + INSERT OR IGNORE）
- [ ] `asr_router` routing table 从 config YAML 驱动（per D3）
- [ ] `priority_queue` 6 因子 score 计算 + P0-P3 标签（per D5，阈值 0.80/0.60/0.35）

### 中间层（Phase 2）

- [ ] `audio_middleware` ffmpeg loudnorm + VAD chunking（chunk_length config-driven，per OQ2 阈值 60min）
- [ ] `job_scheduler` next_retry_at 轮询 + 5 error_code backoff（per D6）
- [ ] `transcript_storage` 9 张表 DDL + migration pattern（per D7，python-only，无 alembic）
- [ ] 165 条坏 transcript 清理工具（`audit-transcript-quality --repair-pollution`，先 dry-run 验证 COUNT=165）

### 应用层（Phase 3）

- [ ] `quality_gate` 两阶段（Phase 1: 6 sub-scores; Phase 2: vocab-corrected technical_term_hit_rate）（per D8 + OQ3）
- [ ] `vocab_correction` pull ingest + 7 类来源 + sha256 版本化（per D9，sync_interval_hours=168 入 config）
- [ ] `report_eligibility` evidence pack JSON + T-tier 准入 + 5 validator 拒绝（per R10 + interfaces.md §5）
- [ ] `cross_source_extractor` 7 类 entity + 4 类 cross-link（per R11，spaCy en_core_web_sm 基线，验证 recall ≥70%，per OQ4）
- [ ] `premium_escape` OpenAI gpt-4o-transcribe + 7 字段 ledger + daily budget（per D10 + OQ1）
- [ ] `config_loader` youtube_config pydantic v2，5 子段，env_prefix='SOLAR_YOUTUBE_'（per D13）

### 接口层（Phase 4）

- [ ] `dashboard` 9 指标 JSON aggregation + SLO 状态行（per D11，JSON-only 基线）
- [ ] `cli` 6 命令 + legacy `process-transcripts` 兼容包装（per D12，solar-harness wiki tech-hotspot-radar 命名空间）

### S03 验收门禁（不达标不交付 S04）

- [ ] pytest suite 全 pass（no mock DB，real SQLite）
- [ ] `process-transcript-jobs --dry-run` 不写 DB
- [ ] quality_score T0≥0.85 / T1≥0.70 / T2≥0.50 / T3<0.50 hardcoded 验证
- [ ] premium budget daily cap = 20 USD，concurrent access 不超标（per OQC-4）
- [ ] 165 条污染数据清理验证 SQL 返回 0
- [ ] Phase 1/2 执行编排原子性（per OQC-1，SQLite WAL 单事务 UPDATE）

---

## S04 启动 Checklist

**前置：S03 全部验收门禁通过**

- [ ] 接 `transcript-status --json` 渲染 dashboard TUI/HTML（per D11）
- [ ] 接 `solar-harness wiki tech-hotspot-radar` 命令树（per D12）
- [ ] 接 `youtube_config` pydantic model 提供 config UI（per D13）
- [ ] 验证 premium ASR 端到端（需真 OpenAI API key，per D10）
- [ ] 接 Tech Hotspot Radar status 面板集成（9 指标 JSON + SLO）

---

## 残留风险

| 风险 ID | 描述 | 严重度 | 处理方 |
|---------|------|--------|-------|
| **OQC-1** | R8 Phase 1/2 DB 写入原子性：Phase 2 UPDATE 若部分失败，tier 可能不一致 | 高 | S03 设计 + 测试 |
| **OQC-2** | R9 vocab ingest pull 频率：7 类来源中 repo_snapshots 同步逻辑需 S03 设计，否则技术词表过期 | 中 | S03 实现 |
| **OQC-3** | R11 NER 模型（spaCy en_core_web_sm）entity recall 是否达 ≥70%：未经实测，可能需 fine-tune | 高 | S03 实测 + 选型 |
| **OQC-4** | R12 premium budget check 并发：SQLite WAL 单机足够，多 worker 场景需 S03 压测 | 中 | S03 压测验证 |
| **OQC-5** | OQ2 WhisperX 60min 阈值：来自文献估算，Mac mini M4 实际 VRAM 预算需 S03 实测校准 | 低 | S03 实测后调 config |
| **R-DB** | A3 interfaces.md 仍在 reviewing 状态：若评审发现 API 签名有误，需 S03 入场前修正 | 中 | A3 evaluator |
| **R-LEGACY** | A3/A4 reviewing 状态：若评审 FAIL，S03 启动需等重工；不允许在 S03 入场前绕过评审 | 高 | evaluator → S03 协调 |

---

## 剩余风险声明

本文件所有未验证项均标为风险或待办，不使用任何夸大完成度的措辞。遵循 task_graph.json evidence_policy.forbid_optimistic_terms 规则。

---

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge (Read scope: architecture.md + data_models.md + interfaces.md + open_questions_resolutions.md + s01-requirements.traceability.json + s01-requirements.handoff.md)
