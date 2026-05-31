# Design — AI Influence YouTube 报告流默认流程固化与验收 S01 Requirements

epic_id: `epic-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收`
sprint_id: `sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s01-requirements`
slice: `requirements`
role: planner
status: planning_complete
generated_at: 2026-05-29T02:30:00Z
knowledge_context: solar-harness context inject used (mirage:timeout → qmd/obsidian/solar_db fallback)
priority: P0
upstream_truth: PRD 7 AC + 7 实现要求 + 7 用户场景 + contract Acceptance 3 条
cross_epic_dependencies:
  - `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构` (transcript quality T0/T1/T2/T3 分级来源 — 上游 YouTube Transcript epic S03 已 PASS, S05 验证中)
  - `epic-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究` (Browser Agent ChatGPT 5.5 Thinking high 调用模式参考)

## 0. 切片定位

S01 是 epic 首切片 (requirements 拆解), 把 PRD 7 AC + 7 实现要求展开为 10 outcome + 4 N-nodes traceability matrix。本切片**仅产规约文档**, 不实施代码。

**核心痛点**: AI Influence YouTube 报告流此前需求已固化, 但**没有独立闭环 sprint** 且受 transcript 质量阻塞。本 epic 把它升级为完整 P0 闭环, 通过 transcript quality gate + Browser Agent ChatGPT 5.5 Thinking high (3 phase 调用: plan/chapter/synthesis) + 强约束 validator 确保**报告读者友好且证据可回源**。

**关键决策点 (PRD §核心)**:
1. 默认接入 transcript quality gate (T0/T1 核心 / T2 weak / T3 reject)
2. 6 group_type 显式分类 (event/conference/keynote/interview/tutorial/product_update/other), 不允许只靠关键词+时间窗口
3. Browser Agent ChatGPT 5.5 Thinking high 必须用于规划+写作+综合 (不允许 ThunderOMLX 替代终判和正文)
4. 报告 hierarchy trend → chapter → subsection → evidence_refs
5. 读者友好素材映射 (无 video_id / V00x / raw refs / pipeline 字段)
6. SVG 图表强制 (ASCII 禁止)
7. report validator 8 检查
8. 输出归档到 Knowledge raw + ChatGPT 项目"杂项"
9. 2026-W21 fixture smoke

## 1. PRD → outcome 映射 (7 AC + 7 实现要求 聚合为 10 outcome)

| outcome_id | 标题 | PRD AC | 节点 |
|------------|------|--------|------|
| O1 | Transcript quality gate (T0/T1 核心 / T2 weak / T3 reject) 默认接入 plan-ai-influence-reports | AC-2, AC-4, impl §1, impl §7 (validator T3 unentered) | N1 |
| O2 | 6 group_type 分类 (event/conference/keynote/interview/tutorial/product_update/other), 不允许关键词+时间窗口 | AC-3, impl §2 | N1 |
| O3 | Browser Agent ChatGPT 5.5 Thinking high 3-phase 调用 (plan / per-chapter writing / synthesis), 禁止 ThunderOMLX 替代终判 | impl §3, impl §4 | N2 |
| O4 | 结构化 JSON 输出 (trend → chapter → subsection → evidence_refs) | AC-4, impl §3 | N2 |
| O5 | 读者友好素材映射 (频道/标题/发布时间/可信度/引用段; 无 video_id / V00x / raw refs / pipeline 字段) | AC-1 §3 (原始需求), impl §5 | N3 |
| O6 | SVG 图表强制嵌入 HTML, 禁止 ASCII 图表 | AC-5, impl §6 | N3 |
| O7 | Report validator 8 检查: 无内部用语 / 无裸 video_id / 无截断尾巴 / SVG 存在 / evidence_map 完整 / T3 未进核心证据 / 6 group_type 合法 / hierarchy 完整 | AC-6, AC-7, impl §7 | N3 |
| O8 | 输出归档到 Knowledge/_raw/tech-hotspot-radar/ai-influence-planned/<date>/reports + Browser Agent ChatGPT 会话归档到 ChatGPT 项目"杂项" | AC-1 §5, AC-1 §6 | N3 |
| O9 | 2026-W21 fixture smoke + eval (report plan + 1 report render + validator pass + 无内部用语/无裸 video_id/无截断/SVG 存在) | AC-7, AC-1 §7 | N3 |
| O10 | Non-goals 聚合 (5 条): 不绕 transcript gate / 不允许 ASCII / 不用 ThunderOMLX 替代 high model / 不暴露内部字段 / 不允许截断尾巴 | impl §1-7 (negative space) | N4 (join) |

## 2. 4-Node DAG

```
                ┌─→ N1 transcript_gate_classification (O1+O2)        sonnet ─┐
   (无上游) ────┼─→ N2 high_model_chatgpt_plan_writing  (O3+O4)        sonnet ─┼─→ N4 traceability_handoff (O10 join) glm-5.1
                └─→ N3 output_validator_archive_fixture (O5..O9, 5 outcomes) sonnet ─┘
```

**Wave 1 (3 并行 write_scope 互斥)**: N1 / N2 / N3 (write_scope 各自子文档)
**Wave 2 (join)**: N4 (depends N1+N2+N3, 含 O10 non-goals 聚合)

N3 较大 (5 outcomes) 但内部高度耦合 (validator 直接消费素材映射/SVG/archive/fixture), 不拆分。

## 3. 节点内容大纲

### N1 transcript_gate_classification.md (O1 + O2)

#### §1 Transcript quality gate (O1)
- 复用 YouTube Transcript epic 已有 T0/T1/T2/T3 分级 (entity recall / WER / segment density)
- 默认行为:
  - T0 (≥95% entity recall, ≤5% WER): 核心证据, 允许直接被 high model 引用
  - T1 (≥80% entity recall, ≤15% WER): 核心证据
  - T2 (≥60% entity recall, ≤30% WER): **weak evidence**, high model 必须显式标注 "based on partial transcript"
  - T3 (<60% entity recall 或 >30% WER): **reject**, 自动从 plan 排除, 报告中不得引用
- plan-ai-influence-reports 入口必须先调 transcript quality gate, 不通过即降级或排除
- 验收 ≥4: T0-T3 4 级分类表 + 排除/降级行为 + plan-ai-influence-reports 接入位置 + T3 排除证据

#### §2 6 group_type classification (O2)
- 6 group_type: event / conference / keynote / interview / tutorial / product_update / other (实为 7, "other" 是兜底)
- 分类信号: title pattern + channel type + duration + speaker count + Q&A presence + slide density
- **不允许只靠关键词和时间窗口** — 必须组合多信号
- 分类输出: group_type + confidence + signal_breakdown
- 验收 ≥4: 7 type 列表 + 多信号组合 + confidence 阈值 + signal_breakdown schema

### N2 high_model_chatgpt_plan_writing.md (O3 + O4)

#### §1 Browser Agent ChatGPT 5.5 Thinking high 3-phase 调用 (O3)
- Phase 1 plan: 输入 = 视频分组 + transcript quality 分布; 输出 = trend → chapter → subsection plan JSON
- Phase 2 per-chapter writing: 逐 chapter 调用 high model, 输入 = chapter spec + relevant transcript segments + group_type context; 输出 = chapter body + inline evidence_refs
- Phase 3 synthesis: 综合 chapters 写 executive summary + cross-chapter insights
- **禁止用 ThunderOMLX/Qwen 替代** Phase 1/2/3 (per impl §4); 仅允许 ThunderOMLX 做 transcript semantic extract (pre-input)
- model_call_ledger 记录 3 phase 调用 (call_count + cost + sprint_id)
- 验收 ≥5: 3 phase 接口 + 禁止 ThunderOMLX 替代终判 + per-chapter 调用 + ledger 记录 + Browser Agent 会话 ID 保存

#### §2 结构化 JSON 输出 (O4)
- Phase 1 plan 输出 schema:
  ```json
  {
    "report_id": "...",
    "trends": [{
      "trend_id": "T1",
      "title": "...",
      "chapters": [{
        "chapter_id": "T1.C1",
        "title": "...",
        "subsections": [{
          "subsection_id": "T1.C1.S1",
          "title": "...",
          "evidence_refs": [{
            "video_handle": "channel/title/published_at",  // NOT video_id
            "transcript_segment_index": 42,
            "confidence": 0.85
          }]
        }]
      }]
    }]
  }
  ```
- 验收 ≥3: schema 完整 + evidence_refs 指向 segment 不是 raw video_id + 4 层 hierarchy 验证 schema

### N3 output_validator_archive_fixture.md (O5 + O6 + O7 + O8 + O9)

#### §1 Reader-friendly source mapping (O5)
- 报告中 source mapping 必须显示: **频道 / 标题 / 发布时间 / 可信度 (T0/T1/T2) / 引用段摘要 (1-2 句)**
- **禁止暴露**: video_id / V00x / raw refs / pipeline fields (transcript_status / processing_log / etc.)
- 验收 ≥3: 5 字段 source mapping 模板 + 6 禁止字段列表 + 渲染示例

#### §2 SVG 图表强制 (O6)
- 所有架构图/趋势图/分布图/时间线必须 SVG (embedded via `<svg>` in HTML, 不是 `<img src=".png">`)
- **禁止 ASCII 图作为最终图表** — ASCII 仅允许中间草图, 渲染前必须替换为 SVG
- SVG 生成路径: high model 输出 SVG source → embedded → HTML
- 验收 ≥3: SVG 嵌入要求 + ASCII 禁止规则 + SVG 来源 (high model 输出 or 模板生成)

#### §3 Report validator 8 检查 (O7)
- validator 必须检查 8 项, 任一 FAIL 则 report 拒绝归档:
  1. 无内部用语 (grep blacklist: video_id / V00x / pipeline / transcript_status / processing_log / raw_refs)
  2. 无裸 video_id (regex: `\b[A-Za-z0-9_-]{11}\b` 在 source mapping 字段 → FAIL)
  3. 无截断尾巴 (HTML/markdown 末尾 100 chars 不含 "..." / "TBD" / 半句中断)
  4. SVG 存在 (HTML 含至少 1 `<svg>` tag, 不允许 0)
  5. evidence_map.json 完整 (所有 evidence_refs 都有 video_handle + segment_index + confidence)
  6. T3 未进核心证据 (validator 扫描 evidence_refs, 任一 transcript_quality=T3 → FAIL)
  7. 6 group_type 合法 (group_type ∈ {event/conference/keynote/interview/tutorial/product_update/other})
  8. Hierarchy 完整 (trend → chapter → subsection 4 层不缺)
- 验收 ≥4: 8 检查列表 + 任一 FAIL 拒绝归档 + grep blacklist + validator exit code

#### §4 Archive (O8)
- 报告 markdown/html/json/evidence_map.json 归档到 `~/Knowledge/_raw/tech-hotspot-radar/ai-influence-planned/<date>/reports/`
- Browser Agent ChatGPT 会话归档到 ChatGPT 项目 "杂项" (session_id + URL 记录到 archive metadata)
- 验收 ≥3: 4 文件类型 + Knowledge raw 路径模板 + ChatGPT 项目归档

#### §5 2026-W21 fixture smoke (O9)
- fixture: 2026-W21 (5 月第 21 周, 即 2026-05-18 到 2026-05-24) 的 YouTube 视频集合
- smoke 步骤:
  1. 跑 plan-ai-influence-reports --week 2026-W21 → plan JSON
  2. 跑 render-ai-influence-report --plan <path> → 1 报告 (markdown + HTML + evidence_map)
  3. 跑 validate-report --report <path> → validator 8 检查全 PASS
- 验收 ≥4: fixture 数据范围 + 3-step smoke + validator 8 检查全 PASS + smoke 退出码 0

### N4 traceability_handoff.md (join, O10)

- traceability matrix (PRD AC + impl 要求 → outcome → node 全链路表)
- non-goals 5 条 显式 (O10 聚合):
  1. **不绕 transcript quality gate** (T3 必须 reject 或 weak evidence)
  2. **不允许 ASCII 图表** 作为最终输出
  3. **不允许 ThunderOMLX/Qwen 替代** Browser Agent ChatGPT 5.5 Thinking high (Phase 1/2/3 终判)
  4. **不暴露内部字段** (video_id / V00x / raw refs / pipeline fields)
  5. **不允许截断尾巴** (报告必须完整, validator 强制)
- handoff package 给下游 S02 architecture:
  - 4 N-nodes spec 引用 (N1-N4)
  - 上游 cross-epic dependencies (YouTube Transcript epic + HF Paper Insight epic Browser Agent 模式)
  - S02 启动 checklist: 实现 transcript_gate + 6 group_type classifier + Browser Agent 3-phase + validator 8 检查 + Knowledge raw archive + 2026-W21 fixture
- **不主动 close epic** (V6 后续)
- 验收 ≥5: traceability 12 字段 + non-goals 5 条 + S02 启动包 + 不 close epic + cross-epic refs

## 4. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| N1 | sonnet | transcript gate 多 quality 级 + 6 group_type 多信号 需 reasoning |
| N2 | sonnet | Browser Agent 3-phase + 结构化 JSON schema 需 reasoning |
| N3 | sonnet | 5 子 outcome (素材映射 + SVG + validator + archive + fixture) 集成 |
| N4 | glm-5.1 | traceability + handoff 模板化 |

## 5. Stop Rules

- 不实施代码 (S01 是规约层)
- 不真跑 plan-ai-influence-reports (本 sprint 仅 spec)
- 不真调 Browser Agent ChatGPT 5.5 Thinking (留 S03/S05)
- 不允许 ThunderOMLX/Qwen 替代终判方案设计
- 不允许 ASCII 图表作为最终输出方案
- 不暴露内部字段方案 (video_id 等)
- 不绕 transcript gate
- 不打印 secrets (ChatGPT API key / Browser session token)
- 不主动 close 父 epic
- 不绕 planner 直派 builder
- 不用乐观词

## 6. Knowledge Context

PRD 7 AC + 7 impl 要求 + contract 3 条 + 上游 YouTube Transcript epic S01-S05 (T0/T1/T2/T3 分级 + ASR ladder + cleanup) + HF Paper Insight S02/S04 (Browser Agent ChatGPT 5.5 Thinking high 调用模式) = self-contained。mirage degraded → QMD/Obsidian/Solar DB fallback。
