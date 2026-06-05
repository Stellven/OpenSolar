# DeepDive Insight Runtime v2: CAIS Agent Insight Profile

Status: P0 requirement package
Owner: Solar Harness
Created: 2026-06-05
Source request: user critique of failed CAIS 2026 Agent DeepDive output

## 1. Executive Summary

DeepDive 当前失败不是模型写作能力问题，而是任务契约、planner、writer、evaluator、renderer 允许“正确废话”通过门禁。CAIS 2026 Agent 洞察任务被当成 generic survey 处理，导致输出有证据底座但无中心论点、无 CAIS paper 到 Solar 架构映射、无图、无可执行路线图、机器标签泄漏、模板复读严重。

本需求要求把 DeepDive 从 evidence-grounded survey 扩展为 insight-grounded monograph runtime，并先以 `cais-agent-insight` profile 收口。目标不是追求 4 到 10 万字，而是先稳定产出 8,000 到 15,000 字高密度 CAIS Agent 洞察报告。

## 2. Diagnosis

### 2.1 Root Cause

当前系统允许以下错误通过：

- Generic survey TOC 进入 conference insight 任务。
- Writer 被 survey section template 绑架，重复输出“正确但无新增信息”的段落。
- Evidence ledger 被留在机器产物里，human final 缺少 claim-to-evidence 可见映射。
- Chief editor 更像语言润色器，不是 insight editor。
- Renderer 是 HTML wrapper，不是 SectionRender publisher。
- Evaluator 主要杀事实错误，不杀“正确废话”。

### 2.2 Failed Output Symptoms

- 目录暴露 survey planner 泄漏，例如“历史脉络与技术演进”“方法分类与代表系统”“产业生态与开源实现”。
- 约 20 万 token 输入只输出 3 条人读脚注，证据密度过低。
- `official_doc`、`paper`、`code`、`benchmark`、`claim_id`、`evidence_id` 等机器标签泄漏到 final body。
- 重复固定小标题和固定金句，例如“机制可行性不等于工程可控性”。
- HTML 没有 claim-linked figure、evidence rail、takeaway box。
- 未把 CAIS 信号转成 Solar operator/schema/gate/runtime 改造。

## 3. Product Goal

新增 DeepDive `--mode insight` 的严格产品路径，并先固化 `cais-agent-insight` profile。

用户给出 CAIS/Agent/Solar 类任务时，DeepDive 必须回答：

1. CAIS 2026 释放了什么 Agent 技术信号？
2. 当前 Agent 的重大技术挑战是什么？
3. Solar 应该吸收成哪些 operator、schema、gate、runtime？
4. 未来 24 到 36 个月 Agent 系统会怎么演进？

如果报告没有明确回答这些问题，必须 fail，不允许发布。

## 4. Non Goals

- 不重写普通 survey mode。
- 不污染 PM requirement compiler 的 schema、route、state 和 artifact。
- 不把 DeepDive 泛化成所有研究任务的默认路径。
- 不用 deterministic 伪洞察替代真实 evidence path。
- 不把 CAIS 论文事实硬编码成最终事实。Profile 可声明必查信号，但最终报告必须由 collectors/evidence ledger 支撑。

## 5. CLI Contract

新增或固化：

```bash
solar-harness research deepdive-run \
  --mode insight \
  --profile cais-agent-insight \
  --brief "通过洞察 CAIS 2026 学术会议，分析当前 Agent 应如何发展、重大技术挑战是什么、Solar 该如何吸收这些思想" \
  --output-dir runs/cais2026-agent-solar \
  --target-words 12000 \
  --format html \
  --run-chief-editor \
  --run-chief-insight-editor \
  --auto-source-collect \
  --require-figures \
  --strict
```

Insight mode 默认行为：

- `--run-chief-editor=true`
- `--run-chief-insight-editor=true`
- `--require-figures=true`
- `--strict=true`
- 禁止使用 generic survey TOC。

## 6. Profile: cais-agent-insight

新增 profile file:

`harness/lib/research/profiles/cais_agent_insight.yaml`

Required content:

```yaml
profile_id: cais-agent-insight
mode: insight

task_contract:
  must_answer:
    - "CAIS 2026 释放了什么 Agent 技术信号？"
    - "当前 Agent 的重大技术挑战是什么？"
    - "Solar 应该吸收成哪些 operator/schema/gate/runtime？"
    - "未来 24-36 个月 Agent 系统会怎么演进？"

  central_thesis_required: true
  title_must_be_claim: true
  solar_action_required_per_chapter: true
  figure_required_per_chapter: true

required_signal_types:
  - conference_track
  - accepted_paper
  - workshop
  - system_demo
  - framework_spec
  - evaluation_benchmark
  - verification_method

required_cais_paper_clusters:
  deep_research:
    must_include:
      - "Dossier"
  planning:
    must_include:
      - "Do Agents Need to Plan Step-by-Step?"
  specification:
    must_include:
      - "Open Agent Specification"
  protocol_verification:
    must_include:
      - "TraceFix"
  wild_deployment:
    must_include:
      - "AI Agents for Discovery in the Wild"

required_outputs:
  - conference_signal_map
  - cais_paper_signal_packs
  - agent_challenge_matrix
  - paper_to_solar_absorption_map
  - solar_operator_roadmap
  - prediction_packets
  - section_render_cards
  - figures
  - final_html
  - insight_eval
  - chief_insight_review

forbidden:
  - generic_survey_toc
  - source_type_label_leak
  - repeated_template_sections
  - execution_metrics_in_final_body
  - bottom_only_citations
  - no_figure_report
```

## 7. Runtime DAG Extension

Current D1-D9 are retained. Insight mode must make D10-D18 runtime-mapped nodes, not just contract decoration.

```text
D1  DeepDiveBriefCapture
D2  DeepDiveSourcePlanner
D3  DeepDiveSourceCollector
D4  DeepDiveClaimCompiler
D5  DeepDiveContradictionScanner
D6  DeepDiveChapterPlanner
D7  DeepDiveChiefEditor
D8  DeepDiveClaimVerifier
D9  DeepDiveArtifactPublisher
D10 InsightThesisPlanner
D11 ConferenceSignalExtractor
D12 PaperToSolarMapper
D13 TypedClaimCompiler
D14 PredictionPacketBuilder
D15 SectionRenderCompiler
D16 FigureSpecRenderer
D17 ChiefInsightEditor
D18 InsightArtifactPublisher
```

Each D10-D18 node must have:

- physical implementation or explicit stub with failing gate.
- expected artifact path.
- task_graph node.
- closeout acceptance.
- evaluator sidecar.

## 8. Required Data Structures

### 8.1 CAISSignalPack

Write to:

`conference_signal_map.json`
`cais_paper_signal_packs.jsonl`

Required schema:

```json
{
  "signal_id": "cais2026_open_agent_spec",
  "source": {
    "type": "accepted_paper",
    "title": "Open Agent Specification",
    "track": "Architectural Patterns & Composition",
    "url": "..."
  },
  "raw_signal": "...",
  "technical_challenge": "...",
  "agent_development_implication": "...",
  "solar_absorption": {
    "design_thesis": "...",
    "new_schema": ["AgentSpecIR", "ToolContract", "RuntimeBehaviorTrace"],
    "new_operators": ["AgentSpecBridgeOperator", "CrossRuntimeEvaluationHarness"],
    "new_gates": ["spec_portability_gate", "runtime_semantics_diff_gate"]
  },
  "forecast": {
    "claim": "...",
    "confidence": 0.72,
    "leading_indicators": ["..."],
    "falsification_condition": "..."
  }
}
```

### 8.2 SolarAbsorptionMap

Write to:

`paper_to_solar_absorption_map.json`
`solar_operator_roadmap.json`

Required schema:

```json
{
  "absorption_items": [
    {
      "cais_signal": "Dossier",
      "solar_problem": "DeepDive source acquisition is too linear and lacks persistent gap tracking.",
      "solar_design": "Introduce BranchingResearchPlanner and PersistentResearchLedger.",
      "operators": ["BranchingSearchOperator", "GapTrackerOperator"],
      "schemas": ["PersistentResearchLedger", "ClaimContradictionGapTracker"],
      "gates": ["branch_coverage_gate", "gap_resolution_gate"],
      "priority": "P0"
    }
  ]
}
```

### 8.3 SectionRenderCard

Writer output in insight mode must be structured JSON, not free Markdown.

Write to:

`section_render_cards/*.json`

Required fields:

- `section_id`
- `title`
- `title_claim_type`
- `body_blocks`
- `figure`
- `evidence_callouts`
- `takeaways`
- `citations`
- `solar_absorption`
- `prediction_packet_refs`

### 8.4 PredictionPacket

Write to:

`prediction_packets.jsonl`

Every prediction requires:

- time horizon
- confidence
- drivers
- counter scenario
- leading indicators
- falsification condition

## 9. New Gates

### 9.1 GenericSurveyTOCGate

Fail insight profile if final AST or final HTML contains generic survey chapter patterns:

- 问题定义与研究边界
- 历史脉络与技术演进
- 核心架构范式
- 方法分类与代表系统
- 评估方法与基准体系
- 工程实现与部署约束
- 风险、安全与可解释性
- 产业生态与开源实现

### 9.2 TemplateRepetitionGate

Fail if repeated template headings or repeated slogans exceed thresholds.

Default banned repeated patterns:

- 研究问题与术语边界
- 关键机制与设计空间
- 证据链与代表工作
- 工程取舍与评价标准
- 风险与争议
- 未解问题
- 机制可行性不等于工程可控性

### 9.3 MachineLabelLeakGate

Fail final human output if it contains:

- `official_doc`
- `claim_id`
- `evidence_id`
- `source type`
- `Execution Metrics`
- `estimated_from_report_artifacts`
- raw source type labels as argument language

Allowed locations:

- `final_machine.md`
- `audit_dossier.json`
- `appendix_evidence_matrix.html`

### 9.4 SolarActionabilityGate

Every major chapter requires:

- Solar absorption thesis
- affected Solar module
- proposed operator or schema
- proposed quality gate
- implementation priority

Minimum report-level thresholds:

- operator recommendations: 6
- schema recommendations: 3
- gate recommendations: 5

### 9.5 CAISCoverageGate

For `cais-agent-insight`:

- min named CAIS papers: 6
- min paper-to-Solar mappings: 5
- required signal names:
  - Dossier
  - Do Agents Need to Plan Step-by-Step?
  - Open Agent Specification
  - TraceFix
  - AI Agents for Discovery in the Wild

Fail if named paper is only mentioned once without challenge extraction and Solar mapping.

### 9.6 FigureRequiredGate

For MVP:

- min figures: 6
- every major chapter has a claim-linked figure
- required figure types:
  - conference_signal_map
  - agent_challenge_matrix
  - solar_absorption_architecture
  - roadmap

For full report:

- min figures: 20

### 9.7 CitationVisibilityGate

Fail if:

- only bottom footnotes exist
- fewer than 10 visible sources in human output
- major sections have fewer than 2 visible citations or evidence callouts
- key claims cannot be traced in human output

### 9.8 PredictionPacketGate

Fail if fewer than 4 prediction packets exist, or any prediction lacks drivers, leading indicators, counter scenario, and falsification condition.

### 9.9 UserQuestionFitnessGate

Fail if final output does not explicitly answer all must-answer questions.

## 10. Auto Source Collection

For insight mode, handoff is fallback, not primary path.

Collectors:

```yaml
auto_source_collectors:
  conference:
    - CAISHomepageCollector
    - CAISAcceptedPapersCollector
    - CAISWorkshopsCollector
    - CAISDemosCollector
  paper:
    - ACMPageCollector
    - arXivCollector
    - SemanticScholarCollector
  code:
    - GitHubRepoCollector
    - ArtifactLinkCollector
  influence:
    - YouTubeTranscriptCollector
    - BlogPostCollector
    - SocialMentionCollector
  market:
    - CompanyBlogCollector
    - NewsCollector
```

Source gap policy must shift from `source_type_gap` to `insight_ammunition_gap`.

Gap kinds:

- missing_cais_paper_signals
- missing_solar_absorption
- missing_prediction_drivers
- missing_counter_scenarios
- missing_operator_design
- missing_figure_spec
- missing_visible_citation

## 11. Renderer Requirements

Final HTML must be compiled from `SectionRenderCard` and `FigureSpec`, not from free Markdown wrapper.

Required human section layout:

- claim-title
- body blocks
- evidence rail
- figure
- evidence callouts
- takeaway box
- visible citations

Required files:

- `final.html`
- `assets/figures/*.svg`
- `assets/style.css`
- `visual_audit.json`
- `appendix_evidence_matrix.html`

## 12. MVP Report Skeleton

`cais-agent-insight` MVP output should use this report skeleton unless profile override says otherwise:

```text
0. 核心判断: Agent 正在从模型应用变成可验证执行系统
1. CAIS 会议信号: Agent 已进入 compound system 工程阶段
2. Dossier: Deep Research 需要 branching search 和 Persistent Research Ledger
3. Planning: step-by-step 不是默认真理，Solar 需要 PlanningHorizonOptimizer
4. Open Agent Specification: Solar 需要 AgentSpec IR 和 CrossRuntimeEvaluationHarness
5. TraceFix: 多 Agent 协作需要 ProtocolVerifierOperator
6. Discovery in the Wild: benchmark 外评估、噪声反馈和人工监督是真实瓶颈
7. Solar Agent Runtime Evidence OS: 吸收架构
8. 24-36 个月预测
9. P0/P1/P2 工程路线图
```

## 13. P0 Implementation Scope

P0 must ship:

1. `cais-agent-insight` profile.
2. Insight mode defaults for strict chief editor and chief insight editor.
3. GenericSurveyTOCGate.
4. MachineLabelLeakGate.
5. TemplateRepetitionGate.
6. SolarActionabilityGate.
7. CAISCoverageGate.
8. FigureRequiredGate.
9. CitationVisibilityGate.
10. PredictionPacketGate.
11. CAISSignalPack schema and writer.
12. SolarAbsorptionMap schema and writer.
13. SectionRenderCard schema.
14. Minimal SectionRender HTML publisher.
15. End-to-end test that current failed CAIS generic survey fixture fails.
16. Golden MVP fixture that passes with six section render cards and six figures.

## 14. P1 Implementation Scope

1. `insight_planner.py` that plans from central thesis and signals.
2. `conference_signal_extractor.py`.
3. `solar_absorption_mapper.py`.
4. `prediction_packet_builder.py`.
5. `figure_spec_renderer.py`.
6. Source collectors for CAIS home, accepted papers, workshops, demos.
7. Auto-source-collect fallback to handoff only if collectors fail.

## 15. P2 Implementation Scope

1. Full publication renderer with evidence rail, figure grid, claim-linked diagrams, and appendix.
2. ChiefInsightEditor model pass that removes correct-but-useless prose.
3. Visual audit gate.
4. Full 20 figure report support.
5. Report-level token consumption and insight density metrics visible in audit, not final body.

## 16. Acceptance Criteria

### P0 Acceptance

- Running evaluator on the failed CAIS generic survey fixture returns `ok=false`.
- Fail reasons include generic survey TOC, machine label leak, low action mapping, missing figures, and weak citation visibility.
- Running profile compiler for `cais-agent-insight` returns D10-D18 in task graph and profile-specific output contracts.
- Golden MVP report with six section render cards, six figures, visible citations, CAIS signals, Solar mappings, and prediction packets passes.
- Final human HTML does not contain raw machine labels.

### P1 Acceptance

- `deepdive-run --mode insight --profile cais-agent-insight --auto-source-collect` produces conference signal map and CAIS paper signal packs.
- Source gap emits insight ammunition gaps, not only source type gaps.
- Planner generates thesis-first chapters, not generic survey chapters.

### P2 Acceptance

- Final HTML is generated from SectionRender cards and FigureSpec.
- ChiefInsightEditor review is mandatory and visible.
- Every major chapter has claim-linked figure, evidence rail, takeaways, and Solar absorption mapping.

## 17. Test Plan

Required tests:

- `test_cais_agent_insight_profile_contract`
- `test_insight_mode_defaults_enable_chief_insight_editor`
- `test_generic_survey_toc_gate_rejects_failed_cais_report`
- `test_machine_label_leak_gate_rejects_human_final`
- `test_template_repetition_gate_rejects_repeated_slogans`
- `test_solar_actionability_gate_requires_operator_schema_gate_mapping`
- `test_cais_coverage_gate_requires_named_signals`
- `test_figure_required_gate_requires_claim_linked_figures`
- `test_citation_visibility_gate_rejects_bottom_only_footnotes`
- `test_prediction_packet_gate_requires_falsifiable_predictions`
- `test_section_render_publisher_uses_cards_not_free_markdown`
- `test_deepdive_insight_mvp_golden_passes`

Run at minimum:

```bash
python3 -m pytest -q harness/tests/research_survey/test_deepdive_requirement_compiler.py \
  harness/tests/research_survey/test_planner.py \
  harness/tests/research_survey/test_survey_evaluator.py
python3 -m py_compile harness/lib/research/deepdive_requirement_compiler.py \
  harness/lib/research/survey/planner.py \
  harness/lib/research/survey/evaluator.py
```

## 18. Dispatch Guidance

Recommended task split:

- S01 requirements/profile contract: profile, D10-D18 contract, mode defaults.
- S02 insight gates: evaluator gates and failed fixture.
- S03 signal/action schemas: CAISSignalPack, SolarAbsorptionMap, PredictionPacket.
- S04 planner/writer: thesis-first planner and SectionRender card writer.
- S05 renderer: SectionRender HTML publisher and FigureSpec SVG path.
- S06 verification-release: golden MVP and failed-report regression.

Preferred planners:

- Opus planner or GPT-5.5 planner.

Preferred builders:

- GPT-5.5 / Spark when available for code implementation.
- Deepseek-v4-pro may be used for low-risk evaluator/gate fixture work only if closeout sidecars are enforced.

Do not route to:

- Gemini/Antigravity unless explicitly no other capacity.
- Deepseek as primary complex builder.

## 19. Key Product Principle

The product must not publish a report that is merely true, cautious, and well-formatted. For insight mode, publish only if the report is thesis-led, evidence-visible, action-mapped, figure-backed, and directly answers the user question.
