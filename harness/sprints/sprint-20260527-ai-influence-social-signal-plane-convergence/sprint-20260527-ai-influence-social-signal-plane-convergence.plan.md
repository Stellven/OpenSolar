# Plan — AI Influence Insight / Social Signal Plane 收口 (sprint-level)

gate: `G_PLAN` / `G_IMPL` / `G_VERIFY` / `G_REVIEW` (per task_graph.json required_gates)
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db)
source_of_truth: `harness/docs/architecture/ai-influence-insight-social-signal-plane.adr.md` (read-only)
detail_reference: `<sid>.S1-design.md` + `<sid>.S1-plan.md` (S1 planner builder 产出, 18K + ?K)

## 0. 切片定位

Sprint-level plan; 串联 5 节点 S1-S5。S1 已 PASS (evaluator 2026-05-28T02:55:44Z), S2-S5 待启动。本文档不重复 S1-plan 内容, 仅提供 sprint-level DAG + gate map + 验证命令 + rollback。详细 per-node plan 见 `<sid>.S1-plan.md`。

## 1. DAG (严格串行 5 节点)

```
S1 planning (DONE PASS)
    └─→ S2 implementation (builder, glm-5.1)
          └─→ S3 verification (glm-5.1)
                └─→ S4 external review (cap.requirement-compiler-verification, sonnet)
                      └─→ S5 rollout (sonnet)
```

**为何串行**: write_scope 锁 → patch.diff → pytest evidence → independent review → compat 决策。每步副作用是下一步前提。

## 2. Gate Map

| Gate | 触发节点 | 通过条件 |
|------|----------|----------|
| `G_PLAN` | S1 | ACC-S1-1 (S1-design §3+§4+§5+§9 全到位) — **PASSED** 2026-05-28T02:55:44Z |
| `G_IMPL` | S2 | ACC-S2-1 (patch.diff 在声明 write_scope 内 + 不触动现有 3 个脚本源) |
| `G_VERIFY` | S3 | ACC-S3-1 (pytest green + smoke 8 asset types) |
| `G_REVIEW` | S4 | ACC-S4-1 (review_decision.yaml.decision==passed) + ACC-S5-1 (rollout_notes.md) |

## 3. 文件级写范围 (per S1-design §3 hard rules)

| 节点 | write_scope (may write) | 严格禁止写 |
|------|--------------------------|-------------|
| S2 | `harness/{lib,schemas,config,scripts,tests}/influence/**` + `<sid>.S2-*.md` | `harness/scripts/ai_influence_*.py` / `youtube_influence_digest.py` / `tech_hotspot_radar.py` / ADR / `infra/prod/**` / `.env*` / `secrets/**` |
| S3 | `<sid>.S3-handoff.md` + `<sid>.S3-test_report.md` + `harness/tests/influence/**` (新增测试用例) | 同 S2 禁止集合 + 不真改 production launchd |
| S4 | `<sid>.S4-handoff.md` + `<sid>.eval.md/json` + `<sid>.review_decision.yaml` | 同 S2 + 不写代码 |
| S5 | `<sid>.S5-handoff.md` + `<sid>.S5-rollout-notes.md` + (可选) 新 plist for `run_insight_compiler.py` | 不改现有 launchd plist; 不动 `Knowledge/_raw/**` schema |

## 4. 并发边界

- **严格串行**: S1 → S2 → S3 → S4 → S5; 各节点内可并行 (S2 9 build steps 内部 step 1+2 可并行, step 3-9 串行依赖)
- **不允许跨节点并行**: 因为 ACC 与 write_scope 锁严格依赖前置 evidence
- **多 evaluator 同 sprint 可并行其他 sprint**: 5-pane spillover (per TUI epic S04, 实施完成后稳)

## 5. 验证命令 (per S1-design §7)

### S2 验证 (单元)

```bash
pytest harness/tests/influence/test_models.py -v
pytest harness/tests/influence/test_gates.py -v
pytest harness/tests/influence/test_seed_registry.py -v
pytest harness/tests/influence/test_statement_normalizer.py -v
pytest harness/tests/influence/test_thesis_extractor.py -v  # 含 thesis_recall metric
pytest harness/tests/influence/test_thesis_mapper.py -v
pytest harness/tests/influence/test_evidence_packet_compiler.py -v
pytest harness/tests/influence/test_insight_compiler.py -v
```

### S3 验证 (集成 + smoke)

```bash
pytest harness/tests/influence/ -v --tb=short  # 全套件
python3 harness/scripts/influence/run_insight_compiler.py --dry-run --frozen-fixtures  # smoke
```

### S4 验证 (独立 review)

```bash
solar-harness session evaluate sprint-20260527-ai-influence-social-signal-plane-convergence --json
solar-harness graph-scheduler validate --graph ~/.solar/harness/sprints/sprint-20260527-ai-influence-social-signal-plane-convergence.task_graph.json
```

## 6. no-live-pane-mutation 保护

- S2-S5 builder/evaluator **绝不** `tmux send-keys` 到生产 pane
- 不真改 `~/.solar/harness/run/pane-hygiene.json` (由 TUI epic 治理)
- 不真改 launchd plist (S5 rollout 仅 docs)
- 不真触发 launchd reload (留人工)

## 7. Rollback / Stop Rules

### Rollback

- S2 失败 → 删 patch.diff + S2-handoff, 不 commit 任何新文件
- S5 决策回滚 → 删 5 新目录 (`harness/{lib,schemas,config,scripts,tests}/influence/`), 现有脚本不受影响
- launchd 不动 → 现有 daily job 持续运行

### Stop Rules

- 缺可验证 acceptance 不得 DONE
- 缺 verifier 决策不得 DONE
- 任一 phase 验收不过, 不进下一 phase
- 不允许 Statement → high model 直通
- 不允许编辑 ADR / 现有 3 个脚本源
- 不允许触动 infra/prod / .env / secrets
- 不允许真改 launchd
- 不允许杀主 pane
- 不允许把 cooldown 当最终修复 (per TUI epic 治理)
- 不用乐观词 (已修复 / 稳定 / 完美 / 无需担忧 / done / complete / implemented)

## 8. SLO

| 指标 | hard | soft |
|------|------|------|
| 5 节点 S1-S5 全 pass | < 5 → sprint FAIL | n/a |
| S2 patch 在 write_scope 内 | 越界 > 0 → 立即 FAIL | n/a |
| S2 触动现有 3 个脚本源 | > 0 → 立即 FAIL | n/a |
| S3 pytest green | < 100% → FAIL | < 80% coverage → WARN |
| S3 smoke 8 asset types | < 8 → FAIL | n/a |
| S4 review_decision == passed | failed → sprint FAIL | n/a |
| S5 rollout_notes 含 rollback 段 | 缺 → FAIL | n/a |
| Statement → high model 直通 | > 0 → 立即 FAIL | n/a |

## 9. 失败恢复 / 升级

- S2 失败: 单节点重派; ThesisExtractor Direction A kill criteria 触发 → 切 Direction B (per S1-design §4.4)
- S3 pytest 失败: 回 S2 修复 + 重跑
- S4 review FAIL: 升 ATLAS structured repair + S2 重 patch
- S5 失败: rollback (删 5 新目录) + post-mortem
- 任一 ATLAS 升级: 写 `<sid>.atlas-repair-<seq>.md`

## 10. 给后续接力

- S5 passed → sprint completed; no epic auto-activation (standalone sprint)
- 后续 epic 可消费本 sprint 产出: HF Paper Insight Flow / AI Influence 主报告 / Tech Hotspot Radar 三源共振

## 11. Knowledge Context

`solar-harness context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB; Codex Bridge / Autoresearch / ATLAS / Solar-Harness Runtime / Superpowers / solar-graph-scheduler capabilities injected。
