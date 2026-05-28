# PRD: 架构设计与接口契约

epic_id: `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构`
sprint_id: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s02-architecture`
slice: `architecture`

## 用户原始需求

# Tech Hotspot Radar: YouTube Transcript 高质量抓取与 ASR 分层重构

## Intent

把当前 YouTube transcript 链路从“字幕失败后默认跑 mlx-whisper small”重构为完整的 Transcript Acquisition Ladder：

```text
L0 作者/官方上传字幕
  ↓
L1 YouTube 自动字幕
  ↓
L2 浏览器辅助字幕抓取
  ↓
L3 高质量本地 ASR
  ↓
L4 高价值视频 premium ASR
  ↓
L5 metadata-only，不阻塞日报
```

目标不是“所有视频都有 transcript”，而是：

- 高价值视频必须有高质量 transcript。
- 低价值视频不能拖垮 ASR 队列。
- 失败视频不能无限 retry。
- AI Influence 报告不能把低质量 ASR 当强证据。
- 每条 transcript 必须有来源、质量分、质量层级、版本、失败原因和可回放证据。

## Background / Current Failure

当前链路已出现严重质量事故：

- 多条英文技术视频经本地 ASR 后生成 CJK-heavy / hallucinated transcript。
- `transcript_status=missing` 但 `transcript_clean` 残留垃圾文本，导致旧 evidence pack 和报告被污染。
- 历史审计发现 165 条坏 transcript 被 requeue。
- 当前 `mlx-whisper small` 不应继续作为主要 ASR 方案，只能保留为低优先级 fallback。

本 sprint 不是调参，而是重构 transcript acquisition、ASR routing、quality gate 和 report eligibility。

## Scope

必须覆盖以下完整能力，不做 MVP 切割。

### 1. Transcript Acquisition Ladder

实现分层获取策略：

```text
L0 youtube_caption_standard
L1 youtube_caption_asr
L2 browser_caption_capture
L3 local_asr_high_quality
L4 premium_asr_top_value
L5 metadata_only
```

优先级：

1. standard en
2. standard zh / zh-Hans / zh-Hant
3. standard original language
4. standard any language
5. ASR en
6. ASR zh / original
7. browser caption capture
8. local ASR
9. premium ASR for Top P0 only
10. metadata-only

字幕存在时不得直接跑本地 ASR。YouTube ASR caption 可用时优先使用，不要因为 auto-generated 就丢弃。

### 2. Subtitle Track Discovery

新增字幕轨发现阶段，不直接下载音频。

需要支持：

- yt-dlp public subtitle discovery/download
- YouTube player caption extraction
- browser caption capture hook
- YouTube Data API captions metadata 仅作为可选/授权场景，不作为默认全网依赖

新增表：

```sql
youtube_subtitle_tracks (
  track_id TEXT PRIMARY KEY,
  video_id TEXT,
  source_backend TEXT,
  language TEXT,
  language_name TEXT,
  track_kind TEXT,
  format TEXT,
  is_auto_generated BOOLEAN,
  is_translatable BOOLEAN,
  confidence REAL,
  discovered_at DATETIME,
  download_status TEXT,
  file_path TEXT,
  error TEXT
);
```

### 3. ASR Model Router

将 `mlx-whisper small` 从主力降级为 P3 fallback only。

默认路由：

```text
caption_available_standard -> use_caption_no_asr
caption_available_asr      -> use_youtube_asr_caption
P0 + multi_speaker          -> whisperx_large_v3_diarization
P0/P1 + en/mixed/zh         -> faster_whisper_large_v3
P2                          -> faster_whisper_medium_or_large_v3_int8
P3                          -> metadata_only_or_mlx_whisper_small
```

本地 ASR 后端必须支持：

- faster-whisper large-v3
- faster-whisper distil-large-v3 for English where appropriate
- faster-whisper medium/int8 fallback
- WhisperX large-v3 + diarization for long interviews / podcasts / panels
- existing mlx-whisper small only as low-priority fallback

### 4. Audio Preprocessing

ASR 前必须统一音频预处理：

```text
download audio
  -> ffmpeg normalize
  -> mono 16kHz wav pcm_s16le
  -> loudnorm/highpass/lowpass
  -> VAD chunking
  -> ASR
```

推荐 ffmpeg 目标：

```bash
ffmpeg -i input.webm \
  -vn -ac 1 -ar 16000 \
  -af "loudnorm,highpass=f=80,lowpass=f=8000" \
  -c:a pcm_s16le \
  output.normalized.wav
```

长视频不得整段直接丢给 ASR。默认：

- chunk_length: 120s-300s
- overlap: 1.5s
- min_speech_segment: 1s
- max_silence_gap: 0.5s

### 5. Transcript Priority Queue

新增 `transcript_priority_score`：

```text
0.25 * channel_weight
+ 0.20 * video_recency_score
+ 0.20 * report_candidate_score
+ 0.15 * cross_source_score
+ 0.10 * view_velocity_score
+ 0.10 * duration_value_score
```

新增 priority：

```text
P0: 必须今天出报告的视频，允许 large-v3 / WhisperX / premium ASR
P1: 高权重频道 + 新视频 + 有跨源信号，跑 large-v3
P2: 普通高价值视频，跑 medium / large-v3 int8
P3: 低价值或多次失败，metadata-only，不烧 ASR
```

retry_queue / transcript_jobs 必须按 priority、next_retry_at、价值排序，不再 FIFO。

### 6. Retry / Failure Policy

失败不再无限重试。

错误策略：

```text
bot_check      -> 24h-72h backoff
no_caption     -> 进入 ASR 判断，不反复找字幕
asr_low_quality-> 升级模型一次；仍失败则 premium 或 metadata-only
timeout        -> 缩短音频片段重试
max_attempts   -> metadata-only / quarantined
```

新增 job ledger：

```sql
youtube_transcript_jobs (
  job_id TEXT PRIMARY KEY,
  video_id TEXT,
  job_type TEXT,
  priority TEXT,
  status TEXT,
  backend TEXT,
  attempt_count INTEGER,
  max_attempts INTEGER,
  next_retry_at DATETIME,
  error_code TEXT,
  error_message TEXT,
  created_at DATETIME,
  started_at DATETIME,
  finished_at DATETIME
);
```

### 7. Transcript Storage V2

现有 `youtube_transcripts` 需要迁移/兼容到 transcript versions。

新增或扩展：

```sql
youtube_transcripts (
  transcript_id TEXT PRIMARY KEY,
  video_id TEXT,
  source TEXT,
  language TEXT,
  is_auto_generated BOOLEAN,
  model TEXT,
  model_version TEXT,
  audio_hash TEXT,
  transcript_hash TEXT,
  raw_path TEXT,
  clean_path TEXT,
  segments_json_path TEXT,
  quality_score REAL,
  quality_tier TEXT,
  coverage_ratio REAL,
  hallucination_risk REAL,
  created_at DATETIME
);

youtube_transcript_segments (
  segment_id TEXT PRIMARY KEY,
  transcript_id TEXT,
  video_id TEXT,
  start_sec REAL,
  end_sec REAL,
  speaker TEXT,
  text_raw TEXT,
  text_clean TEXT,
  confidence REAL,
  language TEXT,
  correction_status TEXT
);

youtube_asr_runs (
  asr_run_id TEXT PRIMARY KEY,
  video_id TEXT,
  transcript_id TEXT,
  backend TEXT,
  model TEXT,
  model_size TEXT,
  compute_type TEXT,
  audio_duration_sec REAL,
  processing_time_sec REAL,
  gpu_used BOOLEAN,
  input_audio_path TEXT,
  output_path TEXT,
  quality_score REAL,
  cost_estimate REAL,
  created_at DATETIME
);
```

必须保留 legacy compatibility，让现有报告/semantic pipeline 不直接崩。

### 8. Transcript Quality Gate

新增 `transcript_quality_score`：

```text
0.25 * source_quality
+ 0.20 * asr_confidence
+ 0.15 * language_consistency
+ 0.15 * technical_term_hit_rate
+ 0.10 * timestamp_stability
+ 0.10 * hallucination_risk_inverse
+ 0.05 * coverage_ratio
```

质量层级：

```text
T0 >= 0.85  high quality, 可进入报告核心证据
T1 >= 0.70  usable, 可进入摘要和趋势判断
T2 >= 0.50  weak, 只能进入 watchlist，报告标 weak
T3 <  0.50  unusable, metadata-only，不进入语义证据
```

source_quality 默认：

```text
standard caption: 1.0
YouTube ASR caption: 0.75
browser caption capture: 0.70
faster-whisper large-v3: 0.70
WhisperX large-v3: 0.75
premium ASR: 0.85
mlx-whisper small: 0.35
metadata-only: 0.0
```

必须检测：

- 重复句子过多
- 长静音段生成长文本
- compression_ratio 异常
- no_speech 段有大量文字
- 语言/script 与视频元数据明显不符
- 技术名词密集错写
- CJK-heavy hallucinated transcript，但不要把它简单称为“中文”

### 9. Technical Vocabulary Correction

新增技术词表修正层，来源：

- GitHub repo names
- Hugging Face paper/model names
- model names
- company names
- YouTube channel names
- social clusters
- topic tags

示例词：

```text
MCP, Claude Code, Codex, Cursor, vLLM, Triton, MLX, Qwen,
DeepSeek, Kimi, Gemini, Gemma, LlamaIndex, LangChain,
CrewAI, PyTorch, CUDA, TPU, H100, Blackwell, RAG,
context engineering, agent memory, Chrome DevTools MCP
```

修正规则：

- raw transcript 不覆盖。
- clean transcript 可做低风险修正。
- 每个修正保留 diff。
- 低置信修正进入 suggested_corrections，不覆盖原文。
- ThunderOMLX/Qwen3.6 可做二阶段校正，但不能补内容。

### 10. Report Eligibility

AI Influence 报告必须按 transcript tier 使用素材：

```text
T0/T1 -> 可进入核心分析
T2    -> 补充观察，标注 weak transcript
T3    -> 只能用标题/简介/频道/metadata，不能引用具体内容
```

Evidence pack 必须包含：

```json
{
  "video_id": "string",
  "transcript_id": "string",
  "quality_tier": "T1",
  "segment_refs": [
    {
      "start_sec": 812.5,
      "end_sec": 845.2,
      "text": "string",
      "confidence": 0.82
    }
  ]
}
```

报告 validator 必须拒绝：

- T3 transcript 进入核心证据
- missing/failed transcript 携带残留 transcript_clean
- source_quality 低但未标 weak
- 计划引用的视频被质量门踢掉后仍写作
- raw low-quality ASR 被当成 strong evidence

### 11. Cross-source Extraction Hook

Transcript accepted 后必须触发实体抽取：

- repo names
- paper titles
- model names
- product names
- company names
- people
- technical terms

创建跨源链接：

```text
youtube_video -> canonical_entity
youtube_segment -> github_repo
youtube_segment -> paper
youtube_segment -> model
```

这要为 GitHub/Social/YouTube 跨源共振服务。

### 12. Premium ASR Escape Hatch

只给 Top 5%-10% 高价值视频使用 premium ASR。

触发条件：

- 视频进入 AI Influence report plan
- 频道 tier 高
- 关联 GitHub/HF paper/social cluster
- 本地 ASR 质量低但视频热度高
- 长访谈中出现重要人物或关键技术事件

必须记录：

- provider
- model
- cost
- file chunks
- transcript_id
- quality_score
- model_call_ledger

### 13. Dashboard / Status

Tech Hotspot Radar status/UI 必须展示：

- subtitle tracks discovered
- accepted transcripts by source/tier
- pending jobs by P0/P1/P2/P3
- failed jobs by error_code
- ASR model success rate
- quality score distribution
- metadata-only count
- report-eligible count
- premium ASR cost

## CLI Requirements

新增/增强 CLI：

```bash
solar-harness wiki tech-hotspot-radar discover-transcript-tracks --limit N
solar-harness wiki tech-hotspot-radar acquire-transcripts --limit N
solar-harness wiki tech-hotspot-radar process-transcript-jobs --priority P0,P1 --limit N
solar-harness wiki tech-hotspot-radar audit-transcript-quality --tiers
solar-harness wiki tech-hotspot-radar transcript-status --json
solar-harness wiki tech-hotspot-radar transcript-ab-test-asr --limit 10
```

`process-transcripts` legacy 命令必须继续可用，但内部走新 job ladder。

## Config Requirements

新增 config：

```yaml
youtube:
  transcript_acquisition:
    ladder_enabled: true
    default_policy: subtitle_first
    metadata_only_after_failures: true

  subtitle_tracks:
    backend_order: [yt_dlp, browser_caption_capture, youtube_api_optional]
    language_priority: [en, en-US, en-GB, zh, zh-Hans, zh-Hant, original, any]

  asr:
    default_backend: faster_whisper
    mlx_whisper_small_enabled: false
    mlx_whisper_small_policy: p3_fallback_only
    faster_whisper:
      models:
        p0: large-v3
        p1: large-v3
        p2: medium
      compute_type: float16_or_int8_float16
      beam_size: 5
      vad_filter: true
      condition_on_previous_text: false
    whisperx:
      enabled: true
      model: large-v3
      diarization: true

  transcript_quality:
    min_report_core_tier: T1
    allow_weak_in_watchlist: true
    reject_t3_from_semantics: true

  premium_asr:
    enabled: false
    provider: openai
    models: [gpt-4o-transcribe, gpt-4o-transcribe-diarize]
    max_daily_cost_usd: 20
```

## Acceptance Criteria

### P0 Completion

1. 新增 subtitle_tracks / transcript_jobs / transcript_versions / segments / asr_runs / quality_checks ledger。
2. 默认流程优先使用 standard caption / YouTube ASR caption。
3. 本地 ASR 默认不再使用 mlx-whisper small。
4. faster-whisper large-v3 可用于 P0/P1。
5. WhisperX large-v3 + diarization 对长访谈/播客可路由。
6. ASR 前做 ffmpeg normalize + chunking。
7. transcript_quality_score / quality_tier 入库。
8. retry_queue / transcript_jobs 按 priority 调度，不再 FIFO。
9. 多次失败进入 metadata-only。
10. AI Influence evidence pack 只允许 T0/T1 核心证据，T2 只能 weak，T3 拒绝。
11. 旧污染状态 `transcript_status=missing` 但 `transcript_clean` 非空必须被迁移/清理。
12. 单测覆盖字幕优先、ASR 路由、质量门、metadata-only、报告准入。

### P1 Completion

1. Browser caption capture 接入 Browser Agent operator。
2. 技术词表 correction layer。
3. Cross-source entity extraction hook。
4. transcript quality dashboard。
5. ASR A/B test command。

### P2 Completion

1. Premium ASR escape hatch。
2. 25MB chunk upload handling。
3. premium ASR cost ledger。
4. local vs premium ASR quality comparison。

## Non-goals

- 不追求所有视频都有 transcript。
- 不对低价值视频全量跑 large-v3。
- 不绕过 YouTube 访问限制。
- 不把 LLM 摘要伪装成 transcript。
- 不覆盖 raw transcript。
- 不让低质量 ASR 进入核心报告证据。

## Suggested Sprint Name

`sprint-tech-hotspot-youtube-transcript-quality-ladder`

## 本切片目标

基于需求矩阵产出系统分层、接口、数据模型、兼容策略和迁移方案。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构.epic.md`、`epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 设计覆盖 control/data plane、状态、失败恢复和观测
- 写清楚接口边界和旧系统兼容方式
- 列出冲突、依赖和降级策略

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s02-architecture.design.md`
- `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s02-architecture.plan.md`
- `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s02-architecture.task_graph.json`
- `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s02-architecture.handoff.md`
- `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s02-architecture.eval.md` 或 `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s02-architecture.eval.json`
