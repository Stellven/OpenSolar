# Plan — S01 Requirements (lum1104/Understand-Anything 集成切片)

epic_id: `epic-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything`
sprint_id: `sprint-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything-s01-requirements`
slice: `requirements`
gate: `sprint-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything-s01-requirements:passed`
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)

## 0. 切片定位

Epic 第一切片。PRD 已超完整（5 outcome / Command Matrix / Traceability Map / 7 OQ）。本切片把内容编排为可派 builder 的 N1..N3 规约节点 + N4 join，产 traceability + handoff，**禁止真跑任何 install/understand 命令**。

## 1. DAG 与并行边界

```
                  ┌─→ N1_install_and_knowledge_graph (O1+O2) ─┐
   (无上游) ────────┼─→ N2_command_matrix             (O3)    ─┼─→ N4_traceability_handoff
                  └─→ N3_evidence_and_safety        (O4+O5)  ─┘     (join)
```

**并行批次**：

| 批次 | 节点 | 模型 | write_scope |
|------|------|------|-------------|
| Wave 1 | N1 / N2 / N3 | glm-5.1 ×3 | 3 个 `.requirements.<topic>.md` 各一份 (零重叠) |
| Wave 2 (join) | N4 | sonnet | `.traceability.json` + `.handoff.md` |

**write_scope 互斥**：

- N1: `sprints/<sid>.requirements.install_and_knowledge_graph.md`
- N2: `sprints/<sid>.requirements.command_matrix.md`
- N3: `sprints/<sid>.requirements.evidence_and_safety.md`
- N4: `sprints/<sid>.traceability.json` + `sprints/<sid>.handoff.md`

## 2. 每份 requirements 文档统一结构 (N1..N3)

按 design §3 八节：outcome_id 清单 / 目标背景 / 验收 per O-id ≥3 / 数据契约草案 / 接口契约草案 / 依赖与冲突 / 风险边界 + 非目标 / builder eligibility=NO + 先需 S02 决定。

## 3. 每节点验收 gate

| 节点 | 关键验收 |
|------|----------|
| **N1** (O1+O2) | 文件存在；O1 ≥3 验收 (含 `/plugin marketplace add`/`install`/`list` 命令验证 + marketplace 失败回退 `git clone` 路径)；O2 ≥3 验收 (含 `.understand-anything/knowledge-graph.json` size>0 + `jq` 解析 + sample-size guard pre-flight)；引 PRD Risks 行 1/2；标 OQ-01 (marketplace ID) 与 OQ-05 (preexisting inventory) 阻塞 |
| **N2** (O3) | 文件存在；7 命令矩阵全列 (dashboard / chat / diff / explain / onboard / domain / knowledge)；每命令 ≥1 验收条件 + ≥1 blocked-with-evidence 容忍条件；引 PRD Command Matrix 行 4-10 原文字段；标 OQ-03/OQ-04/OQ-07 阻塞 |
| **N3** (O4+O5) | 文件存在；O4 ≥3 验收 (含证据写入路径草案：status.json.accepted_artifacts vs handoff.md，未决留 OQ-06)；O5 ≥3 验收 (含 settings.json 前后 hash 比对方法 + secret-scan 规则)；引 PRD Risks 行 3/6；标 OQ-06 阻塞 |
| **N4** (join) | traceability.json 含 12 字段全集；outcomes=5 (O1..O5) 每条含 10 字段；outcome_dependency_matrix 覆盖 O1..O5；non_goals_aggregate ≥6；builder_forbidden_aggregate ≥4；downstream_sprint_kickoff_package 含 S02/S03/S04/S05 各 inputs；open_questions 含 OQ-01..OQ-07 全 7 条带 status=open + owner；handoff.md 含 N1..N3 摘要 + S02 启动 checklist + OQ 列表；禁止乐观词 |

## 4. Stop Rules

- 缺 `task_graph.json` 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 scope 冲突回写 N4 traceability `open_questions`（不动 epic）
- 不实施任何 install / understand 命令（即使是 stub）
- 不动 `~/.claude/settings.json` 或 `/Users/lisihao/Solar/.claude/*`
- 不 fork Lum1104/Understand-Anything
- 不打印 secrets / OAuth / tokens
- 不在产出中放 `/tmp` 路径
- 不擅自把 OQ 标 resolved
- 不用乐观词

## 5. SLO

| 指标 | hard | soft |
|------|------|------|
| outcome 覆盖率 (O1..O5 全到位) | < 5 → FAIL | n/a |
| 每 O-id 验收条件数 | < 3 → FAIL | < 5 → WARN |
| OQ 在 traceability 中条数 | < 7 → FAIL | n/a |
| 任一 OQ 未带 owner+status | 立即 FAIL | n/a |
| 任一 outcome 含实施代码 (install 命令真跑) | > 0 → 立即 FAIL | n/a |
| Command Matrix 7 命令覆盖 | < 7 → FAIL | n/a |
| builder_eligible 标记 | 任一未标 → FAIL | n/a |

## 6. 失败恢复

- N1..N3 任一 FAIL：单节点重派，不阻塞另 2 个
- N4 FAIL：诊断哪个上游节点 outcome 描述缺失/不一致，回写对应 N 节点修复后重跑
- PRD 内部矛盾 (如 §约束 vs §Command Matrix 不一致) → N4 记 OQ 给 PM，不擅自修 PRD

## 7. 给下游接力 (S02 architecture)

N4 traceability `downstream_sprint_kickoff_package.S02_architecture_inputs`：
- O1..O5 requirements docs
- Command Matrix 11 行
- OQ-01 / OQ-03 / OQ-05 / OQ-06 (S02 owner 或前置探明)
- PRD Risks 矩阵 7 行

**S02 必须先解决**: OQ-01 (marketplace 真实有效性 + fallback) + OQ-05 (preexisting plugin inventory) + dashboard port 策略草案 (OQ-03) + 证据字段位置候选集 (OQ-06)。

coordinator 在 S01 evaluator passed 后自动激活 S02 (per epic schedule 规则 "依赖未 passed 的子 sprint 保持 queued")。

## 8. Knowledge Context

`solar-harness context inject` 已在 planner 入场时跑过；mirage degraded → QMD solar-wiki + Obsidian Vault + Solar DB 作为默认源；ATLAS / Everything Claude Code / Solar-Harness Runtime capabilities injected (per runtime context)。本 sprint self-contained，PRD 已完整，节点起草不必额外检索。
