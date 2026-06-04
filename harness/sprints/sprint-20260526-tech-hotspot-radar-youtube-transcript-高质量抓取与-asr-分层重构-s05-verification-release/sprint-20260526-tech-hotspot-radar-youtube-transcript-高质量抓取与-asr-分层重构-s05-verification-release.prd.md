# PRD: 验证、回归与发布证据

epic_id: `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构`
sprint_id: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s05-verification-release`
slice: `verification-release`

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

建立端到端测试、负控、回归报告、文档和验收证据，防止半截完成。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构.epic.md`、`epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 单测、集成测、负控和 activation-proof 全部可复现
- 父 epic 不能在所有 required gate 通过前关闭
- 产出最终 handoff/eval/report 并写入知识库 raw

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s05-verification-release.design.md`
- `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s05-verification-release.plan.md`
- `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s05-verification-release.task_graph.json`
- `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s05-verification-release.handoff.md`
- `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s05-verification-release.eval.md` 或 `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s05-verification-release.eval.json`

---

## 背景 / Context

- 上游 epic `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构` 已经把 YouTube transcript 链路从"字幕失败默认跑 mlx-whisper small"重构为完整 6 层 **Transcript Acquisition Ladder** (L0 标准字幕 → L1 YouTube ASR → L2 浏览器抓取 → L3 本地高质 ASR → L4 premium ASR → L5 metadata-only)，并新增 13 个 P0 范围 + 3 P1 + 4 P2 能力（字幕轨发现、ASR Model Router、Audio Preprocessing、Priority Queue、Retry/Failure Policy、Storage V2、Quality Gate、Technical Vocabulary Correction、Report Eligibility、Cross-source Hook、Premium ASR Escape Hatch、Dashboard、CLI/Config）。
- 历史质量事故已记录：英文技术视频 ASR 出 CJK-heavy / hallucinated transcript；`transcript_status=missing` 但 `transcript_clean` 残留垃圾文本污染 evidence pack；165 条坏 transcript 被 requeue。
- 本切片 **S05 verification-release** 是 epic 5 个子 slice 的最后一站（S01 requirements / S02 architecture / S03 core-runtime / S04 orchestration-ui / **S05 verification-release**）。S05 任务**不是再造功能**，而是建立端到端测试 / 负控 / 回归报告 / 文档 / 验收证据，防止上游 4 个 slice "半截完成"。
- 状态：sprint 已 `active / phase=planning_complete / handoff_to=builder_main`，V1_real_dashboard_cli_e2e builder 已 dispatch；coordinator 当前把 sprint 拉回 `drafting/prd_ready` 仅为 gate_prd_schema 触发的回溯。本切片即修复 PRD schema，不动 builder 实施。

## 用户问题 / Problem

- **PB-1 epic 半截完成的风险**：4 个上游 slice (S01-S04) 各自交付 acceptance，但没有 end-to-end 验证证明 13 个 P0 能力 + ladder + retry + quality gate 能合在一起跑通。
- **PB-2 旧污染状态需要清理**：`transcript_status=missing` 但 `transcript_clean` 非空的旧数据必须被迁移或清空，否则报告会继续引用垃圾 evidence（epic Acceptance 第 11 条）。
- **PB-3 单测覆盖不齐**：epic 第 12 条 acceptance 要求"字幕优先、ASR 路由、质量门、metadata-only、报告准入"五大场景单测；本切片必须验收单测真存在且全绿。
- **PB-4 负控（negative test）缺失**：必须证明 T3 transcript 进不了核心证据 / missing+clean 残留被拒 / source_quality 低未标 weak 被拒 / T3 视频被踢后报告不写它 / raw low-quality ASR 不当 strong evidence — 5 条 reject 规则要负控。
- **PB-5 回归报告 / activation-proof 缺**：epic 已交付 4 slice 实施，但没有"重启后端到端跑一次确认全链路 alive"的 activation proof。
- **PB-6 PRD schema 7 节缺失**：coordinator gate_prd_schema 把 sprint 拉回 drafting；本切片即修复入口。

## 用户故事 / User Stories

- **US-01 (Epic 主导 / Tech Hotspot Radar 维护者)**：作为 epic 主导，我希望 S05 跑出 13 个 P0 + 5 个负控 + 旧数据迁移 + activation-proof 的端到端证据，否则我不签 epic done。
  - 验收：本 PRD §验收标准 + epic acceptance P0 第 1-12 条 + §1 Transcript Acquisition Ladder + §6 Retry/Failure + §8 Quality Gate + §10 Report Eligibility 全部端到端 pass。
- **US-02 (Builder / V1 dashboard CLI e2e)**：作为 V1 builder，我已收到 `V1_real_dashboard_cli_e2e-dispatch.md`，任务是真跑 dashboard / CLI / 端到端流水，留可复现命令和输出。
  - 验收：`<sid>.V1_real_dashboard_cli_e2e-dispatch.md` + physical-plan 已就位；builder pane 跑完后写 V1 handoff 含真实命令 + stdout 摘要 + ledger 行数证据。
- **US-03 (Evaluator)**：作为 evaluator，我需要逐条核对 12 条 P0 acceptance + 5 条负控 + 旧数据迁移证据；任一缺失视为 FAIL。
  - 验收：eval.md / eval.json 含逐项 PASS/FAIL/SKIP + 引用 V1 handoff 的命令行号。
- **US-04 (AI Influence 报告消费者)**：作为下游 AI Influence 报告生成者，我希望 evidence pack 永远只引用 T0/T1 核心证据 / T2 weak 标注 / T3 拒绝，**不会再看到** CJK-hallucinated transcript 进核心 evidence。
  - 验收：epic §10 Report Eligibility 5 条 reject 规则 + S05 负控测试用例。
- **US-05 (Data 维护)**：作为数据维护，165 条旧坏 transcript + `missing+clean` 残留必须被一次性迁移/清理；本切片留迁移证据（前后行数差）。
  - 验收：epic Acceptance 第 11 条 + S05 V1 handoff 含 cleanup 命令 + 前后行数对比。
- **US-06 (Cost 控制 / Premium ASR)**：作为 cost 控制，Premium ASR 只允许 Top 5%-10% 视频 + 触发条件齐全 + 含 `max_daily_cost_usd: 20` 上限；本切片验证 cost ledger 真存在。
  - 验收：epic §12 Premium ASR Escape Hatch + S05 negative test 防止低价值视频走 premium。
- **US-07 (PM / Coordinator)**：作为 coordinator，本 PRD 通过 gate_prd_schema 不再循环。
  - 验收：本切片即修复，`validate.sh prd` → PASS。

## 约束 / Constraints

- **环境**：macOS arm64 (lisihaodeMac-mini.local) / bash 5.3.9 / Solar Harness 4-pane / ThunderOMLX 8002（不在本 sprint scope，但 §9 二阶段校正可调）/ faster-whisper / WhisperX / yt-dlp。
- **路径白名单**（S05 verification 只允许写）：
  - `<sid>.V1_real_dashboard_cli_e2e-handoff.md` (V1 builder 写)
  - `<sid>.design.md` + `<sid>.plan.md` + `<sid>.task_graph.json` (Planner 已写)
  - `<sid>.handoff.md` + `<sid>.eval.md/.json` (后续节点写)
  - 报告 `~/.solar/harness/monitor-reports/youtube-transcript-asr-refactor-verification-release.md`
  - PM 本切片仅写 `<sid>.prd.md` + 重渲染 `<sid>.prd.html` + ACK
- **不实施新功能**：epic 13 P0 + 3 P1 + 4 P2 已在 S01-S04 实施；S05 不重做。
- **必须 end-to-end 真跑**：不允许"unit test 过了就算 done"；S05 必须有 dashboard / CLI / 流水线在真实数据上的 activation proof。
- **不删 raw transcript**：epic Non-goals 明示 "不覆盖 raw transcript"；S05 cleanup 只动 `transcript_clean` / `transcript_status` 一致性。
- **secrets**：API key / YouTube Data API token / Premium ASR provider key 不打印 / 不进 ledger；redact 在写盘前。
- **保留 legacy compatibility**：`process-transcripts` 等老命令必须继续可用（内部走新 job ladder）；不破坏现有 AI Influence 报告 / semantic pipeline。
- **mlx-whisper small 只允许 P3 fallback**：epic §3 ASR Model Router 已降级；S05 必须验证 default config `mlx_whisper_small_enabled: false`。
- **Premium ASR 默认 disabled + cost 上限**：`max_daily_cost_usd: 20` 必须 enforce；超额 reject + alert。
- **不绕过 YouTube 访问限制**：epic Non-goals 明示；bot_check 24h-72h backoff 强制。
- **不让 LLM 摘要伪装成 transcript**：epic Non-goals。
- **父 epic 不能在所有 required gate 通过前关闭**：本 PRD §验收标准 第 2 条强制。
- **PM 角色边界**：不写代码 / 不动 design / plan / task_graph / V1 dispatch / builder pane；本 PRD 修复后保持 status。

## 风险 / Risks

| 风险 | 影响 | 缓解 / 状态 |
|------|------|--------------|
| S01-S04 单独 PASS 但合并跑 e2e 不通 | epic 半截完成 | V1_real_dashboard_cli_e2e builder 正在跑；S05 必须 end-to-end activation proof |
| 旧污染状态 (`missing` + `clean` 非空) 未清理 → 报告继续被毒化 | AI Influence 报告失真 | epic Acceptance 第 11 条 + S05 V1 handoff 含 cleanup + 前后行数证据 |
| 负控 5 条 reject 规则任一不强制 | T3/raw low-quality 偷渡进核心 evidence | epic §10 Report Eligibility 5 条 + S05 negative test 必须 PASS |
| 单测覆盖不齐（字幕优先 / ASR 路由 / 质量门 / metadata-only / 报告准入 5 大场景） | 回归无保障 | epic Acceptance 第 12 条 + S05 单测验收 |
| 165 条旧坏 transcript 残留 | 历史数据继续污染 | S05 V1 cleanup + ledger 行数证据 + spot-check 5 条样本人审 |
| Premium ASR 误开 / 超额 | $$ 烧 | `max_daily_cost_usd: 20` enforce + cost ledger + S05 negative test "low-value 视频走 premium 被 reject" |
| mlx-whisper small 还在主路径用 | CJK hallucination 复发 | epic §3 + config `mlx_whisper_small_policy: p3_fallback_only` + S05 验证 default config |
| Browser caption capture 接入 Browser Agent 操作泄漏 cookie | secrets 事故 | redact + cookie 不入 ledger / log |
| Quality Gate 数值（T0≥0.85 / T1≥0.70 / T2≥0.50）calibration 不准 | 误踢/误放 | epic §8 已固定权重；S05 收集真实数据后留 OQ 给 calibration sprint |
| Dashboard 跑不起来或显示假数据 | 操作员失盲 | V1 dispatch 已要求真跑 dashboard + 截图/curl 证据 |
| CLI 6 个新命令任一不可用 | 操作链断 | V1 handoff 必须含 6 命令真跑 + stdout 摘要 |
| pane_not_idle / builder 阻塞 | V1 卡住 | TUI Pane Recover sprint 协同（events 显示历史有 pane busy 情况） |
| PRD schema 缺 → coordinator 拉回 drafting | 链路循环 | 本切片即修复 ✅ |

## 开放问题 / Open Questions

- **OQ-01** Quality Gate 数值（T0≥0.85 / T1≥0.70 / T2≥0.50）的 calibration：是否需要在跑过 ≥500 transcript 后做 A/B 调权重？**Owner**：未来 calibration sprint。
- **OQ-02** Premium ASR provider 是否仅 OpenAI gpt-4o-transcribe？还是需要兼容多家（Deepgram / AssemblyAI / Speechmatics）？**Owner**：epic 后续 sprint。
- **OQ-03** WhisperX large-v3 + diarization 在 Mac mini 上的实际 throughput 多少？长访谈 (≥60min) 跑得动吗？**Owner**：V1 builder 在 e2e 跑时顺便测。
- **OQ-04** Technical Vocabulary Correction 词表从哪里增量更新？GitHub trending / HF top papers / 手工维护？**Owner**：未来 ops sprint。
- **OQ-05** 165 条旧坏 transcript 是 hard delete 还是 quarantine 表？影响历史追溯。**Owner**：data governance sprint。
- **OQ-06** `youtube-api-optional` 默认 off；什么时候开（需 YouTube Data API quota / OAuth 授权）？**Owner**：未来 expansion sprint。
- **OQ-07** Cross-source Extraction Hook 命中实体后写到哪个表？epic §11 列了链接类型但未指明 schema。**Owner**：跨源 schema 设计 sprint。
- **OQ-08** Browser caption capture 是用 Playwright / Chrome DevTools MCP / 还是 Browser Agent operator？epic §2 列了"browser caption capture hook"但未定 backend。**Owner**：browser agent sprint。

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD（epic 原始 13 P0 + 3 P1 + 4 P2 完整 scope + 本切片 7 schema 必需 section）。
- 上游 epic 文档：
  - `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构.epic.md`
  - `epic-...-.traceability.json`
  - 父级 `task_graph.json`
- 上游 4 个 slice 产物（S01 requirements / S02 architecture / S03 core-runtime / S04 orchestration-ui）— S05 必须读它们的 handoff / eval 才能做 end-to-end 验证。
- 本切片已有产物（**PM 不动**）：
  - `<sid>.contract.md`
  - `<sid>.design.md` (Planner 已产)
  - `<sid>.plan.md` (Planner 已产)
  - `<sid>.planning.html`
  - `<sid>.task_graph.json` (Planner 已产)
  - `<sid>.V1_real_dashboard_cli_e2e-dispatch.md`（已派 builder）
  - `<sid>.V1_real_dashboard_cli_e2e-physical-plan.json`

### V1_real_dashboard_cli_e2e Builder 任务 (已 dispatch)

- 真跑 dashboard / CLI 6 个新命令 / 端到端流水线在真实数据上。
- 留可复现命令 + stdout 摘要 + ledger 前后行数证据。
- 跑 5 大场景单测 + 5 条负控规则。
- 跑 165 条旧坏 transcript cleanup + spot-check 5 条样本人审。
- 验证 Premium ASR `max_daily_cost_usd: 20` enforce。
- 验证 default config `mlx_whisper_small_enabled: false`。
- 顺便测 WhisperX large-v3 + diarization 在 ≥60min 长访谈上的 throughput（OQ-03）。

### 5 条负控规则（V1 必须显式 negative test）

1. T3 transcript 进入核心证据 → reject
2. missing/failed transcript 携带残留 transcript_clean → reject
3. source_quality 低但未标 weak → reject
4. 计划引用的视频被质量门踢掉后仍写作 → reject
5. raw low-quality ASR 被当成 strong evidence → reject

### 5 大单测场景（epic Acceptance 第 12 条）

1. 字幕优先（standard caption / YouTube ASR caption 优先于 local ASR）
2. ASR 路由（priority → backend 映射正确，P3 → mlx-whisper small fallback）
3. 质量门（T0-T3 分级正确，权重公式无误）
4. metadata-only（多次失败后正确进入 metadata-only，retry 不无限）
5. 报告准入（T0/T1 进核心 / T2 weak / T3 拒）

### 后续 Evaluator (S05 验收)

- 逐条核对 12 条 P0 acceptance + 5 条负控 + 5 大单测 + 旧数据迁移证据。
- 任一缺失视为 FAIL；产 eval.md + eval.json verdict。
- 引用 V1 handoff 的命令行号 + ledger 前后行数。

### 后续节点 (S05 verification 之后)

- **Report**：写 `~/.solar/harness/monitor-reports/youtube-transcript-asr-refactor-verification-release.md`（最终报告，给 epic close 用）。
- **Knowledge ingest**：把最终 handoff / eval / report 入 Solar DB / Obsidian / QMD（本 PRD §验收 第 3 条）。
- **Epic close gate**：父 epic 在所有 required gate 通过前不能关闭（本 PRD §验收 第 2 条）。

### 给 Coordinator 的明确指令

- **不动 builder 进度**：sprint 已 `active / planning_complete / handoff_to=builder_main`；V1 builder 已 dispatch。本 PM 仅修 PRD schema，不动 builder pane / dispatch 进度。
- **PRD mtime 已刷新**：coordinator 下一 tick 重跑 gate 应通过；通过后让 sprint 恢复 `active / planning_complete / handoff_to=builder_main`，**不要 advance 到 planner**（已经 planning_complete）。
- **不动其他 12+ 份产物**：包括 design / plan / task_graph / V1 dispatch / V1 physical-plan / planning.html / contract / 上游 epic 文档 + 4 上游 slice handoff。

### Knowledge Context

Knowledge Context: dispatch-embedded unified-context used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中)。

### Harness Modules Used

Harness Modules Used: harness-knowledge (dispatch-embedded unified-context block)。Capability injection 含 ATLAS / Everything Claude Code / Solar-Harness Runtime / agent-rules-books (refactoring hint，本 sprint refactoring intent 87%) — 全部 `injectable_only`。
