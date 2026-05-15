# Sprint Evaluation — sprint-20260515-professor-grade-deepresearch-survey

## 总判定: PASS

## 依据 (Log-Native + Node Roll-Up)

- Session Log: `solar-harness session evaluate sprint-20260515-professor-grade-deepresearch-survey --json` used → 9/9 model calls terminal, errors=[], warnings=[stale_activities/legacy_unpaired_activity] are pre-existing legacy graph_nodes_dispatched/planner_notified runtime carryover, not blocking the sprint.
- Knowledge Context: `solar-harness context inject` used (Solar DB + QMD solar-wiki + Obsidian Vault default; mirage degraded).
- DAG node roll-up: all 7 nodes status=passed in task_graph.json (N1_survey_schemas, N2_survey_planner, N3_evidence_pack_builder, N4_section_compiler, N5_survey_evaluator, N6_cli_integration, N7_e2e_survey_smoke). Each has node-level eval.md + eval.json with research_quality_gate ok=true.

## Done 条件逐条

| # | 合约 Done | 判定 | 证据 |
|---|----------|------|------|
| D1 | Survey package skeleton + schemas with schema_version | PASS | `ls lib/research/survey/` → 11 files (schemas/planner/evidence_pack/section_compiler/evaluator/report_ast/writing_loop/backends/quality/watch_automation/__init__). N1 node-eval PASS. |
| D2 | Planner 8-12 chapters / 30-40 sections, source matrix, target_chars/audience/domain | PASS | Parent smoke `survey-plan --target-chars 50000` → 8 chapters / 32 sections + survey_plan.json + survey_report_ast.json + survey_source_matrix.json. N2 node-eval PASS. |
| D3 | Evidence pack builder with diversity/min-count/contradiction slots, blocks weak packs | PASS | N3 node-eval PASS (4 blocker tag families: evidence_count_low / claim_count_low / source_diversity_low / missing_source_types; contradiction_slots default non-empty). |
| D4 | Section compiler: blocked-pack enforcement, deterministic artifacts, revision loop input | PASS | N4 node-eval PASS (fail-closed on blocked; ready-pack 3-paragraph scaffold with [claims:][evidence:] markers); writing_loop.py adds reviewer/reviser revision artifacts. |
| D5 | Professor-grade scorecard (10 fields) + strict-mode FAIL unless verdict=PASS | PASS | Parent smoke survey-eval --strict on plan-only → verdict=FAIL with issues=[evidence_packs_missing, source_type_count_low:0<4, evidence_count_low:0<32, claim_count_low:0<32, contradiction_coverage_low, finalized_sections_low:0<3]. N5 node-eval PASS. |
| D6 | CLI thin commands (≥6 survey- subcommands) without rewriting existing CLI | PASS | grep `add_parser` in lib/research/cli.py → 10 survey-* subcommands (plan/pack/write-section/run-sections/watch-responses/watch-register/watch-tick/review/compile/eval). N6 node-eval PASS. |
| D7 | E2E smoke: 8 chapters / ≥30 sections, weak-pack strict FAIL, strong-fixture strict PASS | PASS | N7 node-eval PASS: pytest tests/research_survey/test_e2e_professor_survey.py 1 passed in 0.05s; Phase 1 ≥8/≥30; Phase 2 weak strict=False; Phase 4 strong strict=True with finalized_sections==3. Raw evidence report at Knowledge/_raw/solar-harness/. |

## 验证命令实测

```bash
$ cd /Users/sihaoli/.solar/harness && python3 -m pytest -q tests/research_survey \
    tests/research_unit/test_cli.py tests/research_unit/test_evaluator.py \
    tests/research_unit/test_cli_claim_quality.py tests/research_unit/test_cli_synthesize.py \
    tests/graph/test_graph_dispatch_submit.py
→ 94 passed in 1.11s

$ solar-harness research survey-plan --brief "隐空间推理技术架构和演进方向" --target-chars 50000 --output-dir /tmp/solar-survey-parent-smoke
→ ok=True, 8 chapters / 32 sections, 3 JSON artifacts written

$ solar-harness research survey-eval --output-dir /tmp/solar-survey-parent-smoke --strict --json
→ ok=False, verdict=FAIL, issues=[evidence_packs_missing, source_type_count_low:0<4, evidence_count_low:0<32, claim_count_low:0<32, contradiction_coverage_low:0.0000<0.8000, finalized_sections_low:0<3], strict=True

$ grep -c add_parser lib/research/cli.py
→ 31 total (10 of which are survey-* subcommands)

$ ls lib/research/survey/
→ 11 modules (8 spec'd + 3 expansion: writing_loop.py / backends.py / quality.py / watch_automation.py)
```

注: handoff 声称 `68 passed` (runtime + source repo), 实测扩展后 `94 passed in 1.11s` (额外覆盖 graph dispatch submit + cli_claim_quality + cli_synthesize). 实测优于声明.

## Stop Rules 检查

- ✅ "5-section brief 不能假装是 professor-grade survey": 已被 evaluator strict mode 阻断 (chapter_count<8 / section_count<30 + 多项 strict 拒绝条件).
- ✅ "不得重写 coordinator / autopilot / 主调度器": 所有 7 个节点 architecture guard 报 `core_hits: ` / `guard_warnings: none` / `guard_errors: none`; package_boundary=harness/lib/research/survey 全程被尊重.
- ✅ "Section 不得在无 evidence pack 和 claim 链接的情况下 finalize": N4 blocked-pack enforcement 验证, weak fixture 下所有 section 被 block, 强 fixture 下需 evidence-claim 链接才进 finalize.
- ✅ "测试不得依赖在线付费 API": 94 测试纯本地 fixture, 0.05~1.11 秒级 offline 执行, 无网络依赖.

## Non-Negotiables 检查

- ✅ Package-first: 所有新代码在 `harness/lib/research/survey/` 和 `harness/tests/research_survey/`.
- ✅ 主 CLI 兼容: `research run / handoff-search / import-search / source-audit / eval-artifacts` 未被改动 (N6 验证).
- ✅ 无 fake completion: strict mode 主动拒绝低质输出.
- ✅ 无 one-shot 100k: 输出按 section spec + evidence pack 切分, 30-40 个 section 工件.
- ✅ 无 unsupported claim: claim_id -> evidence_id -> source_id 链路是 finalize 前置条件.
- ✅ Human-in-the-loop source acquisition first-class: backends.py 包含 human/pane writer 后端 (current_truth 确认).
- ✅ Online exploration 多方向: source matrix 包含 paper/benchmark/code/official_doc 等 required_source_types (smoke 输出确认).
- ✅ 文档可导出到 Knowledge/_raw/solar-harness: N7 acceptance #4 验证 (raw evidence report 已在该路径).

## Capability / KB 使用证据

- `research.report.compile`: planner.create_survey_plan + section_compiler.compile_survey 真跑产出 32 个 section 蓝图. CLI smoke 实测.
- `research.report.score`: evaluator.evaluate_survey 真跑产出 10 字段 scorecard + 严格门禁. CLI strict smoke 实测.
- `research.fact_check`: unsupported_claim_rate / citation_span_accuracy / contradiction_coverage 三字段已挂载 evaluator (presence-proxy MVP). N5 carryover: 真正的 LLM 级 span 校验是下一阶段升级.
- `research.source_matrix`: planner 产出 survey_source_matrix.json 含 required_source_types per section. N2 验证.
- `research.evidence.pack`: evidence_pack.py 完整产出 sections/<sid>/evidence_pack.json + section.spec.json + 总览 survey_evidence_packs.json. N3 验证.

## 范围扩展 (Informational, 不算违约)

合约 D1 列了 8 个文件; builder 交付了 11 个文件 (新增 writing_loop.py / backends.py / quality.py / watch_automation.py). 合约 D6 列了 6 个 survey- subcommand; builder 交付了 10 个 (新增 survey-run-sections / survey-watch-responses / survey-watch-register / survey-watch-tick).

判定: **超出合约最低标准, 不违反 Non-Negotiables**. 新模块都在 `harness/lib/research/survey/` 内, package-first 边界没破, 主 CLI 没被改, 反而实现了 D4 acceptance 中的"Supports revision loop inputs from evaluator"和 current_truth 中"writer backends + 自动 watcher"目标. 不应被视为 scope creep 拒绝.

## Risks / 残留事项

- **MED (presence-proxy fact-check)**: unsupported_claim_rate / citation_span_accuracy 当前基于 review.json 存在性, 不是真正的 span-text 验证. 达到合约 D5 acceptance 字段层要求, 但深度依赖下游 LLM writer. → 后续 sprint 升级方向.
- **MED (LLM prose layer)**: handoff "Remaining Limitations" 自述: "真正 professor-grade prose 仍需 LLM/expert writer; chapter-level editorial synthesis + cross-chapter contradiction review 待补". MVP artifact contracts + failure gates 已交付, 但 5-10 万字真实生产线仍需下一阶段 LLM 接入. 合约 D1-D7 不要求真实长文生成, 仅要求 pipeline 能拒绝 fake completion → 满足.
- **LOW (write_scope path drift on N7)**: 见 N7 eval — Knowledge/_raw/solar-harness 位置正确, 文件名 `deepresearch-professor-grade-survey-mvp-20260515T154558-0400.md` (与 dispatch 声明的 harness/reports/professor-grade-survey-smoke.md 不同, 但更贴合 acceptance 原文).
- **LOW (test filename drift on N5)**: test_survey_evaluator.py vs spec'd test_evaluator.py. Package boundary 一致, 仅文件名漂移.
- **LOW (session log warnings)**: stale_activities / legacy_unpaired_activity, 全部是 graph_nodes_dispatched / planner_notified runtime carryover, 与本 sprint 实现无关.

## 额外发现

- 实测测试数 (94) 多于 handoff 声明 (68). 建设者保守低报, 实际覆盖更广.
- 实测 CLI subcommand 数 (10) 多于合约 D6 spec (6). 新增 watcher / batch runner / write-section 工具链.
- Schema version `solar.research.survey.v1` 已挂载, 为后续 schema 升级预留兼容路径.

## 总结

Sprint 完整闭环交付了 survey-native pipeline (planner → evidence pack → section compiler → evaluator → CLI → e2e smoke). 7 个 DAG node 全部 PASS, 94 测试通过, strict eval 主动拒绝低质输出, package-first 边界无破, 主 CLI 兼容. 合约 D1-D7 + Non-Negotiables + Stop Rules 全部满足. 残留 MED 风险 (LLM prose layer 未上线 + fact-check 是 presence-proxy) 是下一阶段升级方向, 不构成本 sprint FAIL.

总判定: **PASS**

## Harness Modules Used

Harness Modules Used: harness-knowledge, harness-graph, harness-skills, harness-contracts
Knowledge Context: solar-harness context inject used
Session Log: solar-harness session evaluate used
