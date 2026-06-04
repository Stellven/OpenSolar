# Handoff — sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s01-requirements

## N1..N5 各产出路径 + 摘要

### N1 (acquisition_ladder) — R1, R2
- 产出: `*.requirements.acquisition_ladder.md` (343 行)
- 摘要: L0–L5 ladder 状态机 + 10 项优先级矩阵 + youtube_subtitle_tracks 14 字段 schema + 多后端 discovery 顺序。AC-R1×5 + AC-R2×4，共 9 条验收。字幕存在禁止跑 ASR 硬规则。builder_eligible=false，S02 先定状态机实现位置。

### N2 (asr_and_audio) — R3, R4
- 产出: `*.requirements.asr_and_audio.md` (328 行)
- 摘要: 6 行 ASR 路由表 (caption_std / caption_asr / P0_multi / P0P1 / P2 / P3) 全覆盖 + ffmpeg loudnorm/highpass/lowpass + VAD chunking 4 默认值。mlx-whisper small 仅 P3 fallback。distil-large-v3 英文可选。AC-R3×5 + AC-R4×4，共 9 条验收。builder_eligible=false，S02 先定路由表实现位置 + audio 中间件边界。

### N3 (queue_retry_storage) — R5, R6, R7
- 产出: `*.requirements.queue_retry_storage.md` (404 行)
- 摘要: priority_score 6 项公式 (0.25/0.20/0.20/0.15/0.10/0.10) + P0–P3 标签 + non-FIFO 排序 + 5 error_code backoff 状态机 + 4 张表 schema (youtube_transcripts/segments/asr_runs/jobs) 全字段语义 + legacy 3 阶段迁移 + 165 条污染数据清理。AC-R5×4 + AC-R6×4 + AC-R7×4，共 12 条验收。builder_eligible=false，S02 先定 schema 迁移工具 + 队列实现 + backoff 调度器。

### N4 (quality_vocab_eligibility) — R8, R9, R10, R11
- 产出: `*.requirements.quality_vocab_eligibility.md` (376 行)
- 摘要: quality_score 7 项公式 + T0–T3 阈值 + 8 backend source_quality 映射 + 6 类检测器 + 7 类 vocab 来源 + raw 不覆盖约束 + 5 项 validator 拒绝码 + evidence pack JSON + 7 类实体抽取 + 4 类 cross-link。AC-R8×5 + AC-R9×4 + AC-R10×4 + AC-R11×4，共 17 条验收。builder_eligible=false，S02 先定 score 实现位置 + vocab ingest + 循环依赖解法。

### N5 (premium_dashboard_cli_config) — R12, R13, R14, R15
- 产出: `*.requirements.ops_and_interface.md` (462 行)
- 摘要: 5 premium 触发条件 + 7 字段 ledger + max_daily_cost_usd=20 + Top 5-10% 限定 + 9 dashboard 指标 + 6 CLI 命令签名 + legacy 兼容 + youtube YAML 5 子段 + 5 关键默认值。AC-R12×5 + AC-R13×5 + AC-R14×5 + AC-R15×5，共 20 条验收。builder_eligible=false，S02 先定 CLI 入口 + config loader + premium ledger 物理 schema。

## Traceability 摘要

| 指标 | 值 |
|------|-----|
| outcome 总数 | 16 (R1..R16) |
| P0 占比 | 12/16 (75%) |
| P1 占比 | 3/16 (18.75%) |
| P2 占比 | 1/16 (6.25%) |
| builder_eligible=true | 1 (R16 non-goals 聚合) |
| builder_eligible=false | 15 |
| 阻塞 outcome (blocked_by 非空) | 14/16 |
| 总验收条件数 | 67 条 |
| Open Questions | 4 (OQ1..OQ4) |

## S02 启动 Checklist

S02 architecture sprint 启动前必须完成以下步骤：

1. **读取 R1..R16 全部 requirements docs** (N1..N5 五个 markdown 文件)
2. **读取本 traceability.json** — 理解 outcome_dependency_matrix 和 open_questions
3. **按依赖拓扑排序产出**:
   - Phase 1: R1/R2/R3/R5 (基础层: ladder + subtitle + ASR router + priority queue)
   - Phase 2: R4/R6/R7/R8 (中间层: audio prep + retry + storage + quality gate)
   - Phase 3: R9/R10/R11/R12/R15 (应用层: vocab + eligibility + cross-source + premium + config)
   - Phase 4: R13/R14 (接口层: dashboard + CLI)
4. **必须回答的 S02 决策项** (按 R-id):
   - R1: ladder 状态机实现位置 (独立模块 vs 嵌入 job dispatcher)
   - R2: youtube_subtitle_tracks DDL + discovery 幂等策略
   - R3: ASR 路由表实现位置 + distil-large-v3 en 默认策略
   - R4: audio 中间件模块边界 + chunking 产物生命周期
   - R5: priority 阈值标定方法 (历史数据推导 vs 硬编码初始值)
   - R6: backoff 调度器 (cron / asyncio / next_retry_at 轮询)
   - R7: schema 迁移工具 (alembic vs 直接 DDL) + 队列实现 (SQLite / Redis / heapq)
   - R8: score 实现位置 (pipeline step vs post-processor) + R9 循环依赖解法
   - R9: 词表 ingest 流 (push vs pull, 频率) + ThunderOMLX 二阶校正 critical path
   - R12: premium provider 选型 + ledger 物理 schema (独立 vs 合并 asr_runs)
   - R13: dashboard 渲染栈 (HTML / TUI / JSON-only)
   - R14: CLI 入口宿主 (独立 solar-cli vs solar-harness wiki 子命令)
   - R15: config loader 模块边界 (独立 youtube_config vs 扩展全局 config)
5. **产出 S02 artifacts**:
   - `architecture.md` — 系统架构 + 模块划分 + 状态机设计
   - `data_models.md` — DDL 草案 + 外键 + 索引
   - `interfaces.md` — 内部 API 签名 + CLI + config schema

## Open Questions (4 条)

| OQ | Topic | Owner | Status |
|----|-------|-------|--------|
| OQ1 | Premium ASR provider 选择 (OpenAI / AWS / Azure / Google) | S02 | open |
| OQ2 | WhisperX diarization 长视频 GPU 内存预算 | S02 | open |
| OQ3 | R8 technical_term_hit_rate 与 R9 词表循环依赖解法 | S02 | open |
| OQ4 | R12 触发条件 #5 entity 抽取召回率保障 | S02 | open |

## 禁止乐观词声明

本文档不使用 `task_graph.forbid_optimistic_terms` 定义的保留词来描述实施进度。所有 15 个 `builder_eligible=false` 的 outcome 仍处于需求规约阶段，未进入实施。
