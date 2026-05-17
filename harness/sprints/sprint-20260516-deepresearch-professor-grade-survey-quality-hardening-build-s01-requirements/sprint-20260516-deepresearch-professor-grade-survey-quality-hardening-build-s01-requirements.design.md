# Design — DeepResearch Professor-Grade Survey Quality Hardening · S01 Requirements

Sprint: `sprint-20260516-…-s01-requirements`
Epic: `epic-20260516-deepresearch-professor-grade-survey-quality-hardening-build`
Slice: `requirements` (Planner pass)
Author: Solar Planner
Date: 2026-05-16
Knowledge Context: solar-harness context inject used（命中 `sprint-20260515-professor-grade-deepresearch-survey-accepted.md` + `deepresearch-survey-source-authority-coverage-gate-…` + `deepresearch-survey-literature-controversy-chapter-review-…` + `deepresearch-survey-chief-editor-rewrite-queue-…`）

## 1. Problem Framing

前置 sprint `sprint-20260515-professor-grade-deepresearch-survey` 已落地一批 package-local gates 在 `harness/lib/research/survey/`：
- source authority + coverage gate
- literature mapping + controversy chapter review
- chief-editor rewrite queue

但前置 sprint 的 evaluator 自己点评：
- "现有 final.md 虽可通过 citation/factuality gate，但内容组织仍偏 technical brief"
- "现有 evaluator 主要验证 citations、source types、section density，**不能评审文献综述方法学、分类法原创性、跨章节一致性、反证覆盖、术语稳定性、贡献边界**"
- "现有 ReportAST 缺少 chapter/section spec、evidence pack、claim budget、revision loop、reviewer verdict、global consistency pass"

本 epic 要解决的是**质量天花板**——让 50k-100k word 报告达到教授级 survey 标准，不是 LLM 拼贴的 technical brief。

用户原始需求 6 条：

| # | 原始需求（英文摘） | 性质 |
|---|------|------|
| 1 | source quality gate beyond URL count: canonical/high-authority distribution, primary source ratio, paper/code/official/benchmark balance, no generic example/web stuffing | 质量度量 |
| 2 | argument density gate: every section must contain mechanism comparison, method taxonomy, evaluation protocol, failure/negative evidence, engineering implication | 内容结构度量 |
| 3 | controversy/反证 gate: final report must include contradiction/negative evidence matrix and use it in chapter synthesis | 反证覆盖度量 |
| 4 | no main architecture rewrite; everything must be package-first and pluggable | **治理边界** |
| 5 | agent online exploration should try multiple research directions quickly and eliminate weak directions, recording why | 探索策略 |
| 6 | e2e verification must include solar-harness runtime survey-continue sample, strict tests, and evidence artifact | 验证证据 |

S01 的任务是**把这 6 条拆成 5 个可派 builder 的 outcome + 1 条治理边界 + 明确非目标 + 父 epic ↔ 5 children traceability**。

## 2. Slice Boundaries

- **做**：拆解 6 条需求为 5 outcomes（O1-O5）+ 各自 acceptance + 各自 risk 边界 + 非目标 + non-builder-boundary（哪些是方法学/阈值/评分细则，不能直接派 builder）+ 父 epic ↔ 5 children traceability map
- **不做**：写实现代码 / 选阈值数值 / 写 ReportAST schema（这些是 S02/S03）
- **不允许**：声称父 epic 已完成；用单文档覆盖所有细节；直接给 builder 派"实现 source quality gate"指令而不先写架构 spec

## 3. Design Goals

| Goal | Why |
|------|-----|
| **每个 outcome 是 builder 不可代决的边界** | builder 只实现，不定义"教授级"标准；标准必须在 S01-S02 锁定 |
| **outcome 覆盖前置 sprint 自评的所有质量缺口** | 文献综述方法学 / 分类法原创性 / 跨章节一致性 / 反证覆盖 / 术语稳定性 / 贡献边界 |
| **治理边界（package-local, no main rewrite）必须独立成文** | 否则 builder 会去改 `coordinator.sh` / `autopilot.sh` / `dispatcher` |
| **traceability map 让 S05 能 close gate** | S05 需要逐 children 检查 `*_ready=true`；不写 traceability 父 epic 永远关不掉 |
| **non-builder boundary 显式列出**| 阈值数值 / 评分规则 / 反证 corpus 选源等只能由人 + planner + 审判官商定，不能让 builder 自己拍 |

## 4. Non-Goals

- 不写实现代码（5 个 gate / multi-direction explorer / e2e runner 都留给 S03+）
- 不选具体阈值数值（如 "primary source ratio ≥ 0.6"、"argument density per section ≥ 5"）——只列出"必须有阈值"
- 不写 ReportAST schema（S02 architecture 才会定）
- 不写 evaluator 评分 rubric（S03 实现 + S05 验证才会定稳）
- 不替 chief-editor rewrite queue 加新功能（前置 sprint 已落地，不动）

## 5. Outcomes Map (5 outcomes × 6 需求)

| Outcome | 覆盖原始需求 | 一句话定义 | 必须由谁锁定 |
|---------|------|----------|-----------|
| **O1 Source Quality Distribution Gate** | req 1 | 不止数 URL，而是看 canonical/primary/paper/code/official/benchmark 比例分布 + 检测 "generic example/web stuffing" 反模式 | planner + 审判官（阈值）+ S02 architecture（接口） |
| **O2 Argument Density Per-Section Gate** | req 2 | 每 section 必须含 5 维度（mechanism comparison / method taxonomy / evaluation protocol / failure-negative evidence / engineering implication），按 applicability 评估 | planner（5 维定义）+ S03 实现（density 计算）+ S05（阈值定稳） |
| **O3 Controversy & Negative Evidence Matrix** | req 3 | 终稿必须含 contradiction matrix（行=claim，列=支持/反对/不确定证据）+ chapter synthesis 必须显式引用 matrix 行 | planner（matrix schema）+ S02（chapter synthesis 接口）+ S03 实现 |
| **O4 Multi-Direction Exploration with Elimination Log** | req 5 | agent 探索时同时跑 ≥ 3 个研究方向，淘汰弱方向时写入 `elimination_log.jsonl`（含理由 + 证据 + 决策时刻） | planner（log schema）+ S03（runner）+ S05（验证有真淘汰） |
| **O5 E2E Runtime Evidence (survey-continue)** | req 6 | `solar-harness runtime` 跑一次 `survey-continue` 真样本 → 真触发 4 个 gate（O1-O4）→ 真输出 artifact（report + matrix + elimination_log + gate_report）→ strict tests 验 4 gate 各自 acceptance | S03（runner hook）+ S04（artifact 可见性）+ S05（真跑 + 测试） |

**治理边界**（req 4，不是 outcome 而是横切约束）：
- 所有 gate / runner / matrix 实现必须在 `harness/lib/research/survey/` 包内
- 禁止修改 `coordinator.sh` / `autopilot.sh` / `dispatcher.sh` / `lib/phase-state-machine.sh`
- 禁止修改 `harness/lib/research/survey/` 已存在的 source-authority / literature-mapping / controversy / chapter-review / chief-editor 模块的**对外接口**（可内部 refactor，但外部调用面不变）
- 所有新 gate 通过 plugin registration（在 `survey/__init__.py` 或 `survey/gates/__init__.py` 注册），不硬编码到主链路

## 6. Deliverables

| # | Deliverable | Owner Node | 内容 |
|---|-------------|-----------|------|
| D1 | `…s01-requirements.outcomes.md` | N1 | 5 outcomes（O1-O5）× (一句话定义 / 覆盖原始需求 / acceptance criteria ≥ 3 条 / risk 边界 / 不能直接派 builder 的子项 / 与 S02-S05 切入点) |
| D2 | `…s01-requirements.non-builder-boundary.md` | N2 | 治理边界（package-local + pluggable）+ 非目标清单 + 阈值/评分/corpus 选源等"人定不能 builder 定"清单 + 与前置 sprint accepted 内容的依赖关系（不动接口列表）|
| D3 | `…s01-requirements.handoff.md` + parent traceability patch | N3 (join) | S02-S05 切入清单（每 outcome 一行：哪个 slice 接哪个 deliverable） + parent epic `traceability.json` patch `children[0].outcomes_ready=true`（仅 S01 行）|

## 7. DAG Topology

```text
N1 outcomes.md ──┐
                  ├── N3 traceability + handoff ── done
N2 non-builder ──┘
```

3 节点 2 层；N1 ∥ N2（write_scope 互斥）；N3 join。

## 8. Acceptance Contract

| # | Acceptance | 验证 |
|---|------------|------|
| A1 | outcomes.md 含 5 outcome × (定义 / 原始需求映射 / acceptance ≥ 3 / risk 边界 / 不可 builder 子项 / S02-S05 切入点) | grep section count + table |
| A2 | 5 outcome 覆盖原始 6 需求中 req 1/2/3/5/6（req 4 是治理边界，落到 D2） | trace map check |
| A3 | non-builder-boundary.md 含 ≥ 4 类非 builder 项（阈值数值 / 评分 rubric / 反证 corpus 源 / 探索方向初选） | grep |
| A4 | non-builder-boundary.md 显式列出"不动接口"清单（≥ 5 个前置 sprint 已落地接口名） | grep |
| A5 | handoff.md 含 S02/S03/S04/S05 切入清单（每 outcome 一行 × 4 slice） | grep `s0[2-5]_` ≥ 20 行 |
| A6 | 父 traceability.json `children[0].outcomes_ready=true`（仅 S01 行；schema_version + children 顺序不变） | jq |
| A7 | 不出现 .py / .ts / .js / .sh / .sql 文件 | find |
| A8 | 不声称 "epic 已完成" / "S02-S05 已就绪" | grep == 0 |
| A9 | 与前置 sprint accepted 的接口边界一致（outcomes.md 不要求重写前置 gate） | grep ref + 不含 "重写 source-authority" |
| A10 | outcomes.md 每个 outcome 明确"不能直接派 builder"子项 ≥ 1 | grep |

## 9. Stop Rules

- 任何节点写代码扩展名 → fail
- 任何节点要求重写前置 sprint 已落地的 source-authority / literature-mapping / controversy / chapter-review / chief-editor 模块对外接口 → fail
- outcomes.md 缺"不能直接派 builder"子项 → fail（违反 D&D rigor）
- 阈值数值（如 "primary ratio ≥ 0.6"）被写死在 outcomes.md → fail（应留给 S02-S05）
- 父 traceability.json `children[0].outcomes_ready` 在 N3 之前被写入 → graph_scheduler 阻断
- handoff 声称 "S02-S05 已就绪" 或 "epic 完成" → fail

## 10. Parallelism & Write Scope

- **N1**: `sprints/…s01-requirements.outcomes.md`
- **N2**: `sprints/…s01-requirements.non-builder-boundary.md`
- **N3**: `sprints/…s01-requirements.handoff.md`, `sprints/epic-…traceability.json` (`children[0].outcomes_ready` field only)

write_scope 完全互斥；N1 ∥ N2 安全并行；N3 join 后写 handoff + parent patch。

## 11. Model Routing

- 所有节点 `sonnet`（需求拆解 + 文档严谨性；GLM 1210 风险）
- 禁止 worker webfetch / web search
- 上游唯一需求源：epic.md user-原始需求段 + 前置 sprint accepted.md（不动接口列表）

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| N1 outcomes 漏掉前置 sprint 自评指出的质量缺口（如术语稳定性、贡献边界）| outcomes.md 必须显式引用前置 sprint accepted 的自评段；N3 cross-check |
| N2 把治理边界写得太抽象 → builder 还是改了主链路 | non-builder-boundary 必须列**具体文件**（`coordinator.sh` / `autopilot.sh` / `lib/research/survey/__init__.py` 接口）|
| 阈值数值被偷偷写进 outcomes（builder 拿去硬编码）| stop rule + N3 grep `≥ 0\.|≥ \d{2,}` 命中数 == 0 |
| outcomes 与原始 6 需求不能 trace 回去 | A2 强制 trace map；N3 join 时验 |
| 父 traceability schema_version 被覆写 | parent_link_policy + N3 用 python json 读写仅 patch 单字段 |
| O4 multi-direction exploration 被理解为重写 dispatcher | non-builder-boundary 显式写明 explorer 在 `survey/explorer/` 包内，不动主 dispatcher |

## 13. Knowledge Context Usage

- `solar-harness context inject` 已执行：4 个 QMD 命中
  - `sprint-20260515-professor-grade-deepresearch-survey-accepted.md` — 前置 sprint 自评（关键质量缺口列表）
  - `deepresearch-survey-source-authority-coverage-gate-…` — 已落地的 source authority gate（不动接口）
  - `deepresearch-survey-literature-controversy-chapter-review-…` — 已落地的 literature/controversy/chapter gate（不动接口）
  - `deepresearch-survey-chief-editor-rewrite-queue-…` — 已落地的 rewrite queue（不动接口）
- 前置 sprint accepted 是 mirage_path 可检索证据，N1/N2 必须显式引用而非另起炉灶

## 14. Handoff Plan

N3 完成后，handoff.md 必须含：

- 5 outcome × 4 slice 切入矩阵（每格写：该 slice 接该 outcome 的哪个 deliverable + 依赖哪个前置 sprint 接口）
- non-builder boundary 摘要（阈值/评分/corpus/方向初选）
- 治理边界单独一节：package-local + pluggable + 不动主链路 + 不动前置接口
- 已知未闭环项（前置 sprint 自评的质量缺口中 S01 没拆进 5 outcome 的，必须列出）
- `s02_can_start: true` + `s03_blocked_until: s02_passed` + `s05_blocked_until: [s03_passed, s04_passed]`
