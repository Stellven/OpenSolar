# Plan — S01 Requirements (YouTube Transcript 需求拆解切片)

epic_id: `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构`
sprint_id: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s01-requirements`
slice: `requirements`
gate: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s01-requirements:passed`
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)

## 0. 切片定位

Epic 第一切片。产出 R1..R16 需求 + outcome 依赖矩阵 + S02-S05 启动包。**禁止实施代码**；只产 markdown 规约 + traceability.json + handoff.md。

## 1. DAG 与并行边界

```
                ┌─→ N1_ladder_subtitle (R1,R2)            ─┐
                ├─→ N2_asr_audio (R3,R4)                  ─┤
   (无上游) ──────┼─→ N3_queue_retry_storage (R5,R6,R7)    ─┼─→ N6_traceability_handoff
                ├─→ N4_quality_vocab_eligibility (R8..R11)─┤      (join, 写 traceability+handoff)
                └─→ N5_premium_dashboard_cli_config (R12..R15) ┘
```

**并行批次**：

| 批次 | 节点 | 模型 | write_scope | 说明 |
|------|------|------|-------------|------|
| Wave 1 | N1 / N2 / N3 / N4 / N5 | glm-5.1 ×5 | 5 个 `.requirements.<topic>.md` 各一份，零重叠 | 5 builder 并行起草 |
| Wave 2 (join) | N6 | sonnet | `.traceability.json` + `.handoff.md` | 等 5 节点全 passed |

**write_scope 互斥**：

- N1: `sprints/<sid>.requirements.acquisition_ladder.md`
- N2: `sprints/<sid>.requirements.asr_and_audio.md`
- N3: `sprints/<sid>.requirements.queue_retry_storage.md`
- N4: `sprints/<sid>.requirements.quality_vocab_eligibility.md`
- N5: `sprints/<sid>.requirements.ops_and_interface.md`
- N6: `sprints/<sid>.traceability.json` + `sprints/<sid>.handoff.md`

5 个 wave-1 节点路径完全互斥，调度器可同批派发。

## 2. 每节点统一交付结构（N1..N5）

每份 `*.requirements.<topic>.md` 必含 8 节（design §3）：

1. outcome_id 清单（含 PRD 章节回链）
2. 目标与背景（引段不抄全文）
3. 验收标准 per outcome (≥3 条/R-id)
4. 数据契约草案 (SQL / JSON schema / 字段语义，不实施)
5. 接口契约草案 (CLI / config / 内部 API 签名，不实施)
6. 依赖与冲突（横向 R-id + 纵向下游 sprint）
7. 风险边界与非目标
8. builder eligibility 判定（NO + 先需 S02 决定什么）

## 3. 每节点验收 gate（hard）

| 节点 | 关键验收 |
|------|----------|
| **N1** | 含 R1 + R2 ≥6 验收条件；youtube_subtitle_tracks 全 14 字段含语义；L0-L5 优先级矩阵明示；与 R3 接力点写明 |
| **N2** | 含 R3 + R4 ≥6 验收条件；ASR 路由表 6 行齐 (caption_std / caption_asr / P0_multi / P0P1 / P2 / P3)；ffmpeg 命令含参数；chunking 默认值 (120-300s/1.5s/1s/0.5s) 锁定 |
| **N3** | 含 R5 + R6 + R7 ≥9 验收条件；priority_score 6 项公式列齐；retry 5 个 error_code 状态机；3 张表 schema (transcripts/segments/asr_runs/jobs) 字段全；legacy 迁移策略明示 |
| **N4** | 含 R8 + R9 + R10 + R11 ≥12 验收条件；quality_score 7 项公式列齐；source_quality 8 个 backend 映射；T0-T3 阈值 (0.85/0.70/0.50/<0.50) + tier→evidence 准入；vocab 来源 7 类 + 修正规则 (raw 不覆盖)；cross-source 4 个 link 类型 |
| **N5** | 含 R12 + R13 + R14 + R15 ≥12 验收条件；premium ASR 5 触发条件 + ledger 字段；dashboard 9 指标；CLI 6 命令签名；YAML config 5 子段含默认值 |
| **N6** | traceability.json 含 12 字段 (schema_version / sprint_id / epic_id / generated_at / knowledge_context / outcomes[16] / outcome_dependency_matrix / non_goals_aggregate / builder_forbidden_aggregate / downstream_sprint_kickoff_package / open_questions / files_touched)；handoff.md 含 N1..N5 摘要 + S02 启动 checklist + OQ 列表；禁止乐观词 |

## 4. Stop Rules

- 缺 task_graph.json 不得派 builder。
- 缺可复现验证不得标记 passed。
- 发现 scope 冲突回写 N6 traceability `open_questions`（不动 epic）。
- 不写任何 python/SQL/YAML 实施代码。
- 不擅自修 PRD 原文。
- 不主动 close 父 epic。
- 不用乐观词「已完成 / 稳定 / 完美 / 无需担忧」。

## 5. SLO（本切片）

| 指标 | hard | soft |
|------|------|------|
| outcome 覆盖率 (R1..R16 全到位) | < 16 → FAIL | n/a |
| 每 R-id 验收条件数 | < 3 → FAIL | < 5 → WARN |
| traceability outcome_dependency_matrix 节点数 | < 16 → FAIL | < 18 → WARN |
| open_questions 含 owner+status | 缺一即 FAIL | n/a |
| builder eligibility 标记 | 任一 outcome 未标即 FAIL | n/a |
| 任一 outcome 含实施代码 | > 0 → 立即 FAIL | n/a |

## 6. 失败恢复

- N1..N5 任一 FAIL：单节点重派，不阻塞另 4 个。
- N6 FAIL：诊断哪个上游 outcome 缺失/不一致，回写对应 N 节点修复后重跑。
- 若 PRD 内部矛盾（如 §3 §8 source_quality 不一致）→ N6 记 OQ 给 PM，不擅自修 PRD。

## 7. 给下游接力（S02 architecture）

N6 traceability `downstream_sprint_kickoff_package`：
- **S02 architecture inputs**: R1..R16 全部 requirements 文档 + outcome_dependency_matrix
- **S02 必须先解决**: R1/R2/R3/R5/R7 接口与状态机
- 然后推导: R8/R10/R11/R13/R14
- **不传给 S02**: 任何实施细节（S02 自己决定）

coordinator 在 S01 evaluator passed 后自动激活 S02 (per epic.task_graph activation_policy)。

## 8. Knowledge Context 声明

`solar-harness context inject` 已在 planner 入场时跑过；mirage degraded → QMD solar-wiki + Obsidian Vault + Solar DB 作为默认源。本 sprint self-contained，PRD 已完整，节点起草不必额外检索。
