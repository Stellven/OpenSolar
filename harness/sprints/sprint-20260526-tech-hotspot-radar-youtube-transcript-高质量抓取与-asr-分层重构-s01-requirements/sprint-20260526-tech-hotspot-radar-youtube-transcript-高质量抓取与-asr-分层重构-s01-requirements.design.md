# Design — S01 Requirements 切片：YouTube Transcript 需求拆解与追踪矩阵

epic_id: `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构`
sprint_id: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s01-requirements`
slice: `requirements`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-27T12:21:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)`
upstream: `none (epic 首切片)`
downstream: `S02 architecture`
parent_epic_status: `active (S01_requirements=active, others=pending)`

## 0. 本切片边界（强制 read-first）

- **S01 是 epic 首切片**：上游空；产出供 S02 architecture / S03 core / S04 orchestration / S05 verification 消费的需求规约和追踪矩阵。
- **S01 不实现任何代码**。所有 builder 派发只允许写 markdown / JSON 规约文档；禁止改 Tech Hotspot Radar 任何 python/SQL/UI 代码。
- **本 sprint 允许的写范围**：
  - `~/.solar/harness/sprints/<s01-sid>.requirements.acquisition_ladder.md` (N1)
  - `~/.solar/harness/sprints/<s01-sid>.requirements.asr_and_audio.md` (N2)
  - `~/.solar/harness/sprints/<s01-sid>.requirements.queue_retry_storage.md` (N3)
  - `~/.solar/harness/sprints/<s01-sid>.requirements.quality_vocab_eligibility.md` (N4)
  - `~/.solar/harness/sprints/<s01-sid>.requirements.ops_and_interface.md` (N5)
  - `~/.solar/harness/sprints/<s01-sid>.handoff.md` (N6)
  - `~/.solar/harness/sprints/<s01-sid>.traceability.json` (N6)
  - `~/.solar/harness/sprints/<s01-sid>.eval.md` 或 `.eval.json` (evaluator 写，不在本节点写范围)
- **严格禁止**：
  - 修改父 epic 任何 artifact (`epic-*.epic.md` / `epic-*.task_graph.json` / `epic-*.traceability.json`)
  - 修改任何 Tech Hotspot Radar 源码 (`~/.solar/harness/lib/tech_hotspot_radar/**`、相关 CLI、UI)
  - 修改 SQL schema、迁移脚本、config 文件
  - 真跑 `solar-harness wiki tech-hotspot-radar` 任何子命令
  - `tmux send-keys`、`solar-harness restart`
- 禁止乐观词（已修复 / 稳定 / 完美 / 无需担忧）。
- 禁止把 P1/P2 outcome 误标 P0；禁止跳过 non-goal 声明。

## 1. 用户原始大需求拆解（PRD 章节 → outcome）

PRD 提供 13 个 scope 区 + CLI/Config/Acceptance/Non-goals。本 sprint 拆为 16 个 outcome（R1..R16），按主题聚合到 5 个 requirements 文档节点 + 1 个 join 节点。

| outcome_id | 标题 | PRD 章节 | 优先级 | builder 直接派 | 聚合到节点 |
|------------|------|----------|--------|----------------|------------|
| R1  | Transcript Acquisition Ladder Policy (L0..L5 + 优先级矩阵) | §1 | P0 | NO (需 architecture 决定状态机)        | N1 |
| R2  | Subtitle Track Discovery + youtube_subtitle_tracks 表 schema | §2 | P0 | NO (S03 实施)                          | N1 |
| R3  | ASR Model Router (faster-whisper / WhisperX / mlx-whisper 降级) | §3 | P0 | NO (S02 路由表 + S03 实现)              | N2 |
| R4  | Audio Preprocessing (ffmpeg + VAD + chunking) | §4 | P0 | NO (S03 实施)                          | N2 |
| R5  | Transcript Priority Queue (score 公式 + P0..P3 标签) | §5 | P0 | NO (S02 评分模型 + S03 队列)            | N3 |
| R6  | Retry / Failure Policy (error_code → backoff 状态机) | §6 | P0 | NO (S02 状态机 + S03 实施)              | N3 |
| R7  | Transcript Storage V2 (versions + segments + asr_runs) + legacy 迁移 | §7 | P0 | NO (S03 schema + 数据迁移)              | N3 |
| R8  | Transcript Quality Gate (score 公式 + T0..T3 + 检测器) | §8 | P0 | NO (S02 score 设计 + S03 检测器)        | N4 |
| R9  | Technical Vocabulary Correction Layer | §9 | P1 | NO (S02 vocab 来源 + S03 修正器)        | N4 |
| R10 | Report Eligibility (T-tier → evidence 准入) | §10 | P0 | NO (S02 evidence pack + S04 validator) | N4 |
| R11 | Cross-source Extraction Hook (entity / cross-link) | §11 | P1 | NO (S02 抽取 schema + S03 hook)         | N4 |
| R12 | Premium ASR Escape Hatch (provider / cost ledger) | §12 | P2 | NO (S02 触发条件 + S03 ledger)          | N5 |
| R13 | Dashboard / Status (radar UI 指标) | §13 | P1 | NO (S04 UI)                            | N5 |
| R14 | CLI Contract (6 新增/增强命令 + legacy 兼容) | CLI § | P0 | NO (S04 CLI)                           | N5 |
| R15 | Config Schema (`youtube:` YAML 5 子段 + 默认值) | Config § | P0 | NO (S03 config loader)                 | N5 |
| R16 | Non-goals + Risk Boundaries (聚合) | Non-goals § | P0 | YES (本 sprint 直接落入 traceability)   | N6 |

**Builder 直接派的工作（仅 N6 join 节点）**：traceability.json 聚合、handoff.md 起草。其他节点是规约起草，可派 builder 但产出是 markdown，仍走 evaluator 审核。

## 2. S01 内部 DAG（5 路 fan-out + 1 join）

```
N1_ladder_subtitle         ─┐
N2_asr_audio               ─┤
N3_queue_retry_storage     ─┼─→ N6_traceability_handoff (join)
N4_quality_vocab_eligibility─┤
N5_premium_dashboard_cli_config ┘
```

**并行批次**：

| 批次 | 节点 | 说明 |
|------|------|------|
| Wave 1 (5 并行) | N1, N2, N3, N4, N5 | write_scope 各写一个 `*.requirements.<topic>.md`，零重叠，可同批派 5 个 builder |
| Wave 2 (join) | N6 | 等 N1..N5 全 passed，聚合产出 `*.traceability.json` + `*.handoff.md` |

每个 N1..N5 产物是该主题的 requirements spec：含 outcome_id、源 PRD 引用、验收标准、风险边界、数据/接口契约草案、与其他 outcome 的依赖（横向）、与 S02-S05 的传递（纵向）。

## 3. 每个 requirements 文档（N1..N5）的统一结构

每份 `*.requirements.<topic>.md` 必须含以下 8 节：

1. **outcome_id 清单** — 本节点覆盖的 R-id 列表（含 PRD 章节回链）
2. **目标与背景** — 引用 PRD 原文要点（不抄全文，引段落 + 行号）
3. **验收标准 (per outcome)** — 每个 R-id 列 ≥3 条可验证条件
4. **数据契约草案** — SQL 表 / JSON schema / 字段语义（不实施，规约 only）
5. **接口契约草案** — CLI / config / 内部 API 签名（不实施）
6. **依赖与冲突** — 横向（与其他 R-id）+ 纵向（哪个下游 sprint 消费）
7. **风险边界与非目标** — 明确 "不做什么"
8. **builder eligibility 判定** — 标 NO 并说明先需 S02 decide 什么

## 4. N6 join 节点产出（traceability.json + handoff.md）

**`<s01-sid>.traceability.json` 必须 12 字段**：

```json
{
  "schema_version": "solar.s01_requirements.traceability.v1",
  "sprint_id": "...",
  "epic_id": "...",
  "generated_at": "<UTC>",
  "knowledge_context": "solar-harness context inject used",
  "outcomes": [
    {
      "outcome_id": "R1",
      "title": "Transcript Acquisition Ladder Policy",
      "prd_section": "§1",
      "priority": "P0",
      "acceptance_count": "<n>",
      "downstream_sprints": ["S02", "S03"],
      "downstream_artifacts": ["architecture.md", "lib/ladder.py"],
      "builder_eligible": false,
      "blocked_by": [],
      "requirements_doc": "sprints/<s01-sid>.requirements.acquisition_ladder.md"
    }
    /* R2..R16 */
  ],
  "outcome_dependency_matrix": {
    "R1": ["R2"],
    "R3": ["R1"],
    "R8": ["R3", "R4"],
    "R10": ["R7", "R8"]
  },
  "non_goals_aggregate": [
    "不追求所有视频都有 transcript",
    "不对低价值视频全量跑 large-v3",
    "..."
  ],
  "builder_forbidden_aggregate": [
    "禁止修改 src/tech_hotspot_radar/**",
    "禁止真跑 solar-harness wiki tech-hotspot-radar 子命令",
    "禁止改父 epic artifact"
  ],
  "downstream_sprint_kickoff_package": {
    "S02_architecture_inputs": ["R1..R16 requirements docs", "outcome_dependency_matrix"],
    "S03_core_runtime_inputs": ["data 契约 (R2/R7)", "状态机 (R6)", "config schema (R15)"],
    "S04_orchestration_ui_inputs": ["CLI 契约 (R14)", "Dashboard 指标 (R13)", "Report eligibility (R10)"],
    "S05_verification_inputs": ["验收标准全集 (R1..R16)"]
  },
  "open_questions": [
    {"id": "OQ1", "topic": "premium ASR provider 选择", "status": "open", "owner": "S02"},
    {"id": "OQ2", "topic": "WhisperX diarization 长视频 GPU 预算", "status": "open", "owner": "S02"}
  ]
}
```

**`<s01-sid>.handoff.md` 必须含**：
- N1..N5 各产出路径 + 摘要 (≤80 字/节点)
- traceability.json 摘要 (outcome 个数 / P0 占比 / 阻塞数 / OQ 数)
- S02 启动 checklist（"先读 R1..R16 → 输出 architecture.md / data_models.md / interfaces.md"）
- 已知未闭环项（OQ 列表）
- 禁止乐观词声明

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| N1, N2, N3, N4, N5 | glm-5.1 | requirements spec 起草模板化，省钱 |
| N6 (join) | sonnet | 跨节点聚合 + 依赖矩阵推导 + downstream package 需 reasoning |

## 6. 跨 outcome 依赖矩阵（重要）

下游 sprint 调度顺序参考此矩阵：

```
R1 (ladder)        depends_on: R2 (subtitle discovery 必须先存在)
R3 (ASR router)    depends_on: R1 (ladder 决定何时进 ASR)
R4 (audio prep)    depends_on: R3 (router 决定送哪个 ASR)
R5 (priority queue)depends_on: R1
R6 (retry policy)  depends_on: R3, R5
R7 (storage V2)    depends_on: R2, R5, R6 (字段来源)
R8 (quality gate)  depends_on: R3, R4
R9 (vocab correct) depends_on: R7, R8
R10(report elig)   depends_on: R7, R8
R11(cross-source)  depends_on: R7, R10
R12(premium)       depends_on: R3, R5, R8
R13(dashboard)     depends_on: R5, R6, R8, R10, R12
R14(CLI)           depends_on: R1, R5, R6, R8
R15(config)        depends_on: R3, R4, R8, R12
R16(non-goals)     聚合，无横向依赖
```

S02 architecture 必须先解决 R1/R2/R3/R5/R7 的接口与状态机，再推导 R8/R10/R11/R13/R14。

## 7. 失败恢复 / 降级

- 任一 N1..N5 节点 evaluator FAIL → 单独重派该节点，不阻塞其他 4 个。
- N6 join FAIL → 必须诊断是哪个上游 N 节点的 outcome 描述缺失/不一致，回写到对应 N 节点修复后重跑。
- mirage / qmd / obsidian 持续 degraded：本 sprint self-contained（PRD 已完整），不依赖检索；如需补充技术参考可走 fetch / web 二级源。
- 若 PRD 本身在节点起草过程中被发现矛盾（如 §3 与 §8 source_quality 不一致）→ 不擅自修 PRD；在 N6 traceability `open_questions` 中标 OQ 给 PM 决策。

## 8. Stop Rules（继承 contract）

- 缺 `.task_graph.json` 不得派 builder。
- 缺可复现验证不得标记 passed。
- 发现 scope 冲突必须回写父级 traceability（N6 负责写入 outcome_dependency_matrix；不动 epic）。
- 不直接绕过 planner 派 builder（本 sprint 所有 builder 派发先经过 N1..N5 节点声明）。
- 不用单个大 PRD 覆盖所有实现细节（已拆 R1..R16）。
- 不用"已完成"替代可复现证据。

## 9. 非目标（明确禁止）

- 不在 S01 写任何 python / SQL / YAML 实施代码（即使是 stub 或 placeholder）。
- 不擅自修改 PRD 原文。
- 不主动 close 父 epic。
- 不直接绕过 S02/S03 调度（如 "顺便把 R15 config schema 实现了"）。
- 不用乐观词。
- 不实施 premium ASR provider 选型决策（OQ1，留 S02）。
- 不实施 WhisperX 长视频 GPU 预算决策（OQ2，留 S02）。

## 10. 给 epic 推进的接力

- N6 traceability.json `downstream_sprint_kickoff_package` 写明 S02..S05 各自的输入清单。
- coordinator 在 S01 evaluator passed 后自动激活 S02_architecture（per epic.task_graph activation_policy）。
- S01 不主动 close 任何东西；evaluator passed 即由 epic_decomposer 自动推进。
