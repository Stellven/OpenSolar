# Design — S02 Architecture 切片：YouTube Transcript 链路系统设计

epic_id: `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构`
sprint_id: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s02-architecture`
slice: `architecture`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-27T14:13:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)`
upstream: `S01 requirements (passed 2026-05-27, 16 outcomes, 67 acceptance, 4 OQ open)`
downstream: `S03 core-runtime · S04 orchestration-ui`

## 0. 本切片边界（强制 read-first）

- **S02 是 architecture 切片**：上游 S01 passed；产出供 S03 core-runtime / S04 orchestration-ui / S05 verification-release 消费的架构 + 数据模型 + 接口 + 兼容/迁移 + OQ 决议。
- **S02 不写实施代码**。所有 builder 派发只允许写 markdown / JSON 规约 / DDL 草案 / API 签名草案；禁止改 Tech Hotspot Radar 任何 python/SQL 文件。
- **本 sprint 允许的写范围**：
  - `~/.solar/harness/sprints/<s02-sid>.architecture.md` (A1)
  - `~/.solar/harness/sprints/<s02-sid>.data_models.md` (A2)
  - `~/.solar/harness/sprints/<s02-sid>.interfaces.md` (A3)
  - `~/.solar/harness/sprints/<s02-sid>.open_questions_resolutions.md` (A4)
  - `~/.solar/harness/sprints/<s02-sid>.traceability.json` + `<s02-sid>.handoff.md` (A5)
- **严格禁止**：
  - 修改 S01 任何 artifact（5 份 requirements docs / traceability / handoff）
  - 修改父 epic 任何 artifact
  - 修改 Tech Hotspot Radar / Solar 源码
  - 真跑 `solar-harness wiki tech-hotspot-radar *` / `yt-dlp` / `faster-whisper` / `whisperx` 任何命令
  - 实施 SQL DDL（A2 只写 DDL 草案文档，不真创表）
  - 实施 config loader（A3 只写 schema 草案，不写 python loader）
- 禁止乐观词；禁止放宽 R8 hard 阈值（T0≥0.85 / T1≥0.70 / T2≥0.50）；禁止把 OQ 标 resolved 后留空理由。

## 1. 上游摘要（S01 → S02）

| S01 产出 | S02 必须消费 |
|----------|---------------|
| `*.requirements.acquisition_ladder.md` (343 行) | R1 ladder 状态机 + R2 subtitle discovery 14 字段 |
| `*.requirements.asr_and_audio.md` (328 行) | R3 6 行 ASR 路由表 + R4 ffmpeg/VAD 参数 |
| `*.requirements.queue_retry_storage.md` (404 行) | R5 priority_score 6 项 + R6 5 状态机 + R7 4 张表 schema + legacy 迁移 |
| `*.requirements.quality_vocab_eligibility.md` (376 行) | R8 7 项 score + 8 backend 映射 + R9 7 类词表 + R10 evidence pack + R11 4 cross-link |
| `*.requirements.ops_and_interface.md` (462 行) | R12 5 触发 + 7 ledger + R13 9 指标 + R14 6 CLI + R15 YAML 5 子段 |
| `*.traceability.json` | 16 outcome + outcome_dependency_matrix + 4 OQ + S02 启动 checklist 13 决策项 |

总计 ≥ 1913 行需求文档 + 14 outcome blocked_by S02。

## 2. S02 必须解决的 13 决策项（从 S01 handoff §S02 启动 checklist）

| Dec-id | R-id | 主题 | 落入文档 |
|--------|------|------|----------|
| D1  | R1  | ladder 状态机实现位置 (独立模块 vs 嵌入 dispatcher) | A1 |
| D2  | R2  | youtube_subtitle_tracks DDL + discovery 幂等策略 | A1/A2 |
| D3  | R3  | ASR 路由表实现位置 + distil-large-v3 en 默认 | A1 |
| D4  | R4  | audio 中间件模块边界 + chunking 产物生命周期 | A1 |
| D5  | R5  | priority 阈值标定方法 (历史推导 vs 硬编码) | A1 |
| D6  | R6  | backoff 调度器 (cron / asyncio / next_retry_at 轮询) | A1 |
| D7  | R7  | schema 迁移工具 (alembic vs 直接 DDL) + 队列实现 (SQLite/Redis/heapq) | A1/A2 |
| D8  | R8  | score 实现位置 (pipeline step vs post-processor) + R8↔R9 循环依赖解法 | A1 + A4(OQ3) |
| D9  | R9  | 词表 ingest 流 (push/pull + 频率) + ThunderOMLX 二阶校正 critical path | A1 |
| D10 | R12 | premium provider 选型 + ledger 物理 schema (独立 vs 合并 asr_runs) | A4(OQ1) + A2 |
| D11 | R13 | dashboard 渲染栈 (HTML / TUI / JSON-only) | A1 |
| D12 | R14 | CLI 入口宿主 (独立 solar-cli vs solar-harness wiki 子命令) | A3 |
| D13 | R15 | config loader 模块边界 (独立 youtube_config vs 扩展全局) | A3 |

加上 4 OQ：

| OQ | 主题 | 落入文档 |
|----|------|----------|
| OQ1 | Premium ASR provider 选择 | A4 |
| OQ2 | WhisperX GPU 内存预算 | A4 |
| OQ3 | R8 ↔ R9 循环依赖解法 | A4 |
| OQ4 | R12 触发 #5 entity 召回保障 | A4 |

## 3. S02 内部 DAG（关键路径 + fan-out + join）

```
A1_architecture (sonnet, 关键路径)
    ├─→ A2_data_models      ┐
    └─→ A3_interfaces       ├─→ A5_traceability_handoff (sonnet, join)
A4_open_questions_resolutions ┘   (与 A1 并行)
```

**并行批次**：

| 批次 | 节点 | 模型 | write_scope |
|------|------|------|-------------|
| Wave 1 | A1, A4 | sonnet ×2 | `architecture.md`, `open_questions_resolutions.md` |
| Wave 2 | A2, A3 | glm-5.1 ×2 | `data_models.md`, `interfaces.md` (依赖 A1) |
| Wave 3 (join) | A5 | sonnet | `traceability.json`, `handoff.md` |

**write_scope 互斥**：A1-A5 每个写一个独立文件，零重叠。

**why A1 是关键路径**：架构总览定模块边界 → A2 知道 DDL 落在哪些表 + A3 知道 API 签名落在哪些模块。如果 A2/A3 与 A1 并行，可能写出与架构不一致的 DDL/接口。

**why A4 可与 A1 并行**：OQ 是研究/调研性质（provider 选型 / GPU 预算 / 循环依赖证明 / 召回率分析），不直接消费架构图。

## 4. 每份 architecture 文档（A1..A4）的统一结构

### A1 `architecture.md` 必须 10 节

1. **系统全景图** (text/mermaid)
2. **模块划分** (≥6 模块: ladder / subtitle_discovery / asr_router / audio_middleware / job_queue / quality_gate / vocab_correction / report_eligibility / cross_source / premium_escape / dashboard / config_loader 中选 ≥6 列)
3. **control plane vs data plane 划分**
4. **状态机设计** (R1 ladder 状态机 + R6 5 error_code 状态机，含状态转移表)
5. **失败恢复策略** (per R6 5 error_code → backoff)
6. **观测设计** (per R13 9 dashboard 指标 + SLO 状态行 + 日志/指标/告警)
7. **13 决策项落地** (D1-D13 每项 ≤200 字决议)
8. **冲突 / 依赖 / 降级**
9. **非目标 (明确禁止)**
10. **给 S03/S04 的接力** (S03 必须先实现什么 + S04 必须先实现什么)

### A2 `data_models.md` 必须 7 节

1. **表清单** (R2 youtube_subtitle_tracks + R7 youtube_transcripts / segments / asr_runs / jobs + R11 cross_source_links + R12 premium_asr_ledger)
2. **每表 DDL 草案** (字段 / 类型 / NULL / DEFAULT / 约束)
3. **外键 + 索引** (覆盖 PK + 业务查询热路径)
4. **legacy `youtube_transcripts` 迁移策略** (3 阶段: 增列 / 反填 / 切换；165 条污染数据清理 SQL 草案)
5. **数据生命周期** (audio chunks / asr 中间产物 / segments_json_path 何时归档/删除)
6. **存储估算** (per video 平均大小 + per 100 video / 1000 video 容量)
7. **降级路径** (PG vs SQLite / 容量超限策略)

### A3 `interfaces.md` 必须 8 节

1. **内部模块 API 签名** (per A1 模块划分逐一列 Python class/function 签名草案)
2. **CLI 契约** (R14 6 命令 argparse 签名 + 退出码 + 输出 schema)
3. **legacy `process-transcripts` 兼容包装层** (D12 决议落地)
4. **config schema** (R15 YAML 5 子段 + 每字段类型/默认/验证规则)
5. **evidence pack JSON schema** (R10 + R11 cross_source 引用)
6. **事件契约** (ladder 状态转移事件 / job 状态事件 / quality_gate 决议事件)
7. **版本与兼容** (API v1 锁定 + 兼容 deprecation policy)
8. **测试桩点** (S05 必须 mock 哪些边界)

### A4 `open_questions_resolutions.md` 必须每 OQ 5 字段

每 OQ 至少：
- **decision** (明确给出选定方案，禁止"待定")
- **rationale** (≥3 项支撑事实)
- **alternatives_considered** (≥2 个被否方案 + 否定理由)
- **risks_residual** (即使决策后仍存在的风险)
- **owner_for_implementation** (S03 / S04 / S05)
- **fallback** (决策落地后失败的兜底)

外加：14 个 blocked_by 非空的 outcome 各自标 "blocker resolved by Dec-XX / OQ-X" 或 "remaining blocker → S03 sub-decision"。

### A5 `traceability.json` + `handoff.md` 必须 12 字段

```json
{
  "schema_version": "solar.s02_architecture.traceability.v1",
  "sprint_id": "...",
  "epic_id": "...",
  "generated_at": "<UTC>",
  "knowledge_context": "solar-harness context inject used",
  "decisions": [
    {"dec_id": "D1", "outcome": "R1", "decision": "...", "doc": "architecture.md§7.D1"}
    /* D1..D13 */
  ],
  "oq_resolutions": [
    {"oq_id": "OQ1", "decision": "...", "owner": "S03", "doc": "open_questions_resolutions.md§OQ1"}
    /* OQ1..OQ4 */
  ],
  "module_inventory": ["ladder", "subtitle_discovery", "asr_router", "audio_middleware", "job_queue", "quality_gate", "vocab_correction", "report_eligibility", "cross_source", "premium_escape", "dashboard", "config_loader"],
  "table_inventory": ["youtube_subtitle_tracks", "youtube_transcripts", "youtube_transcript_segments", "youtube_asr_runs", "youtube_transcript_jobs", "cross_source_links", "premium_asr_ledger"],
  "downstream_sprint_kickoff_package": {
    "S03_core_runtime_inputs": ["A1 模块划分 + 状态机", "A2 全部 DDL + 迁移", "A3 内部 API 签名", "A4 OQ 决议"],
    "S04_orchestration_ui_inputs": ["A1 dashboard 设计", "A3 CLI 契约 + legacy 兼容", "A4 dashboard 渲染栈决议 (D11)"],
    "S05_verification_inputs": ["A3 测试桩点", "A1 失败恢复 + 观测"]
  },
  "open_questions_carried_over": [
    /* S02 阶段如有新发现矛盾，标 status=open，owner=S03/S04 */
  ],
  "files_touched": [...]
}
```

`handoff.md` 至少含：A1-A4 各产出路径 + ≤100 字摘要；13 决策 + 4 OQ 决议摘要；S03/S04 启动 checklist；剩余风险；禁止乐观词声明。

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| A1 | sonnet | 架构总览 + 13 决策需 reasoning |
| A2, A3 | glm-5.1 | DDL/API 签名起草模板化 |
| A4 | sonnet | OQ 决策 + alternatives 分析需 reasoning |
| A5 (join) | sonnet | 跨节点聚合 + downstream package |

## 6. 跨 outcome 依赖矩阵（从 S01 复用）

S01 traceability 已给定 R1..R16 横向依赖。S02 架构必须按 4 个 phase 拓扑顺序：

- **Phase 1 (基础)**: R1, R2, R3, R5
- **Phase 2 (中间)**: R4, R6, R7, R8
- **Phase 3 (应用)**: R9, R10, R11, R12, R15
- **Phase 4 (接口)**: R13, R14

A1 architecture.md §模块划分必须按此拓扑组织章节。

## 7. SLO 阈值（继承 S01 R8）

A1/A4 必须保留下列硬阈值，禁止放宽：

| 指标 | 硬阈值 |
|------|--------|
| T0 quality_score | ≥ 0.85 |
| T1 quality_score | ≥ 0.70 |
| T2 quality_score | ≥ 0.50 |
| T3 quality_score | < 0.50 (拒绝核心证据) |
| min_report_core_tier | T1 (per R10) |
| max_daily_cost_usd (premium) | 20 (per R12) |
| mlx-whisper small 默认启用 | false (per R3) |

## 8. Stop Rules（继承 contract）

- 缺 `task_graph.json` 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 scope 冲突回写父级 traceability (A5 负责，**不动 epic**)
- 不写实施代码（即使 stub）
- 不擅自修 S01 任何 artifact
- 不主动 close 父 epic
- 不放宽 R8 硬阈值

## 9. 失败恢复 / 降级

- A1 失败 → A2/A3 不能启动；单节点重派
- A2/A3 任一失败 → 单独重派，不阻塞另一个
- A4 失败 → 与 A1 独立，单独重派；A5 join 必须等 A4 passed 才能定 oq_resolutions
- A5 join 失败 → 诊断哪个 A 节点决议缺失/不一致，回写对应 A 节点修复
- 若发现 S01 requirements 内部矛盾 → A4 记 OQ-new 给 PM，不擅自修 S01

## 10. 非目标（明确禁止）

- 不写 python / SQL / YAML 实施代码
- 不真跑任何 yt-dlp / faster-whisper / whisperx / solar-harness wiki 命令
- 不擅自修 S01 requirements docs / traceability
- 不主动 close 父 epic
- 不预判 S03/S04 选型（A4 OQ 决议属本 sprint，但 S03 内部 sub-decision 不在 S02 范围）
- 不用乐观词
- 不放宽 R8 quality_score hard 阈值
- 不实施 SQL DDL（只写草案文档）
- 不实施 config loader（只写 schema 草案）

## 11. 给 epic 推进的接力

- A5 traceability `downstream_sprint_kickoff_package` 写明 S03/S04/S05 各自 inputs 与必须先实现项。
- coordinator 在 S02 evaluator passed 后自动激活 S03 + S04 (per epic.task_graph activation_policy，S03 与 S04 都 depends_on=S02，可同批激活)。
- S02 不主动 close 任何东西。
