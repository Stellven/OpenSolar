# Design — AI Influence Insight / Social Signal Plane 收口 (sprint-level)

sprint_id: `sprint-20260527-ai-influence-social-signal-plane-convergence`
epic_id: null (standalone convergence)
slice: `convergence-mvp`
role: planner
status: planning_complete
generated_at: 2026-05-28T06:43:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
source_of_truth: `harness/docs/architecture/ai-influence-insight-social-signal-plane.adr.md` (read-only)
detail_reference: `<sid>.S1-design.md` (18K, 12 节完整架构 by S1 planner builder, evaluator PASS 2026-05-28T02:55:44Z)

## 0. Sprint-level Design Index

本 design.md 是 **sprint 级摘要**，详细架构与文件边界已在 `<sid>.S1-design.md` 由 S1 planner 完整产出 (18K, 12 节, evaluator PASS)。本文档不重复 S1-design 内容，仅提供:

1. Sprint DAG 5 节点 (S1-S5) 串联
2. sprint-level 验收映射
3. S1 已 PASS 现状 + S2-S5 接力计划
4. 与同期其他 epic 的关系 (HF Paper Insight / TUI Pane Recover / YouTube Transcript)

**详细架构请直接读 `<sid>.S1-design.md`**:
- §1 Requirement Trace (REQ-000..REQ-003)
- §2 Product Positioning (binding)
- §3 Slice → File / Package Boundary Map (S2 hard write-scope)
- §4 7 MVP operator slice contract (L0-L5)
- §5 S2 per-slice build steps
- §6 Migration DAG (existing → new wrapper)
- §7 Verification spine
- §8 Compatibility / Rollout
- §9 Acceptance → Validation Matrix
- §10 Architecture Guard Response
- §11 Risks
- §12 What S1 is NOT doing

## 1. Sprint DAG (5 节点 S1-S5)

```
S1 planning (DONE, evaluator PASS 2026-05-28T02:55:44Z)
    └─→ S2 implementation (builder, patch.diff + S2-handoff)
          └─→ S3 verification (pytest + smoke + test_report.md)
                └─→ S4 external review (cap.requirement-compiler-verification + review_decision.yaml)
                      └─→ S5 rollout (rollout_notes.md + compat 决策)
```

**为何严格串行**: ACC-S1-1 满足后才能开 S2 (write_scope locked); S2 patch.diff 是 S3 grep gate + pytest 的对象; S3 evidence 是 S4 review 的对象; S4 review_decision 是 S5 rollout 前置。每步副作用必须在下一步可见。

## 2. S1 现状快照

| 维度 | 事实 (实查 evaluator output) |
|------|------------------------------|
| S1 status | reviewing → PASS (evaluator verdict 2026-05-28T02:55:44Z) |
| S1 产出 | S1-design.md (18K) + S1-plan.md + S1-guard-decision.json + S1-resource-binding.json + S1-bridged-artifact.md + S1-handoff.md (8K) + S1-eval.md/json (9K) |
| S1 evaluator | proof_gate=PASS / scope_compliance=true / architecture_guard.compliant=true / 6 checked_artifacts / 0 missing |
| Architecture guard | resolved: package_boundary=`harness/lib/influence/`, plugin_boundary=`harness/scripts/influence/run_*.py` + `config/influence/source_adapters.yaml`, core_patch_allowed=false |
| ThesisExtractor | 2 candidates (A rule+few-shot LLM / B local embedding+template) + kill criteria |
| Session log | warn (parent-status drift), 0 errors, non-blocking |

## 3. S2-S5 接力详细 (per S1-design §5-§9)

### S2 implementation (待启动)

- 9 build steps (per S1-design §5): models+schemas → gates → SeedRegistry → StatementCollector → StatementNormalizer → ThesisExtractor → ThesisMapper → EvidencePacketCompiler → InsightCompiler
- write_scope (per S1-design §3 hard rules): `harness/{lib,schemas,config,scripts,tests}/influence/**`
- 输出: `patch.diff` + `<sid>.S2-handoff.md`
- Scope Change Request 协议: 任何越界写必须在 S2-handoff 中显式声明

### S3 verification (待启动)

- `pytest harness/tests/influence/` 全 green
- smoke: `scripts/influence/run_insight_compiler.py --dry-run` 产 ≥1 of each 8 asset types
- 输出: `<sid>.S3-handoff.md` (`test_report.md`)

### S4 external review (待启动)

- evaluator: `cap.requirement-compiler-verification` (独立于 S2 writer)
- 输出: `review_decision.yaml` (machine-readable, `decision: passed | failed`)
- 输出: `<sid>.S4-handoff.md` + `<sid>.eval.md/json` (sprint 整体)

### S5 rollout (待启动)

- `<sid>.S5-handoff.md` 含: compat 路径 (per S1-design §8) + rollback (删 5 新目录) + launchd plist 决策 (新 plist for `run_insight_compiler.py` 是否在 MVP 内, OQ-03 等 S5 决)
- 输出: `<sid>.S5-rollout-notes.md`

## 4. Sprint-level Acceptance (per S1-design §9 + 本 sprint contract)

| Acceptance ID | 来源 | 落实节点 | 验证产物 |
|---------------|------|----------|----------|
| ACC-S1-1 | Implementation path explicit | S1 (PASS) | S1-design+S1-eval |
| ACC-S2-1 | Patch in declared write scope | S2 builder | S2-handoff + patch.diff + S3 grep gate |
| ACC-S3-1 | Verification evidence attached | S3 | S3-handoff (test_report.md) |
| ACC-S4-1 | Verifier decision machine-readable | S4 | review_decision.yaml |
| ACC-S5-1 | Compat/rollout notes explicit | S5 | S5-rollout-notes.md |

## 5. Stop Rules (继承 contract)

- 缺可验证 acceptance 不得标完成
- 缺 verifier 决策不得 DONE
- 缺 task_graph.json 不得派 builder (已满足, codex-bridge 已生成)
- S2-S5 任一 phase 验收不过, 不进下一 phase
- 不允许 Statement → high model 直通 (必须经 Thesis → EvidencePacket)
- 不允许编辑 ADR / 现有 3 个脚本源 / infra/prod / .env / secrets
- 不写实施代码以外的乐观词

## 6. 失败恢复 / 降级

- S2 失败: 单节点重派; ThesisExtractor Direction A 触发 kill criteria → 切 Direction B (S1-design §4.4)
- S3 pytest 失败: 回到 S2 修复 + 重跑
- S4 review FAIL: 升级 ATLAS structured repair + S2 重 patch
- S5 rollout 失败: rollback (删 5 新目录, 不动现有脚本) + post-mortem 写 S5-handoff

## 7. 与同期 epic 的关系

| 同期 epic / sprint | 关系 |
|--------------------|------|
| HF Paper Insight Flow epic (S01-S05) | 本 sprint L3 ThesisMapper 可消费 HF connector (若可用); S1-design §11 风险 2 |
| Tech Hotspot Radar / Code Signal Plane | 本 sprint L3 ThesisMapper 通过 subprocess 调用现有 `tech_hotspot_radar.py` |
| YouTube Transcript epic | 本 sprint L1 StatementCollector wraps `youtube_influence_digest.py` (现有 long-form source); 与 transcript quality ladder 互补 |
| TUI Pane Recover epic | 本 sprint S2-S5 builder/evaluator 使用 5-pane spillover (S04 实施完成后更稳) |

## 8. 非目标

- 不创建第四套社交系统
- 不重写 ADR
- 不编辑现有 3 个脚本源
- 不动 launchd plist (MVP 内)
- 不动 `Knowledge/_raw/**` schema
- 不触动 infra/prod / .env / secrets
- 不让高模型见 raw post list
- 不允许 Statement → high model 直通

## 9. Knowledge Context / Harness Modules

Knowledge Context: solar-harness context inject used (mirage degraded → QMD + Obsidian + Solar DB)
Harness Modules Used: harness-knowledge, harness-graph (validate / dispatch S1), harness-skills, harness-ATLAS, Codex Bridge (S1 走过 codex pane), Autoresearch (advisor)
