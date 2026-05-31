# Design — S01 Requirements 切片：lum1104/Understand-Anything Claude Code 集成

epic_id: `epic-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything`
sprint_id: `sprint-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything-s01-requirements`
slice: `requirements`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-27T14:07:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)`
upstream: `none (epic 首切片)`
downstream: `S02 architecture → S03 core-runtime · S04 orchestration-ui → S05 verification-release`
parent_epic: `epic-20260526-...understand-anything.epic (active; S01=ready, S02..S05=queued)`

## 0. 本切片边界（强制 read-first）

- **S01 是 epic 首切片**：上游空；产出供 S02/S03/S04/S05 消费的需求规约 + traceability。
- **PRD 已超完整**：5 outcome (O1-O5)、Command Matrix (11 行命令)、Traceability Map (S* 接力)、Risks 矩阵、OQ-01..OQ-07 已写定。S01 工作是把 PRD 内容编排为可派 builder 的 requirements 节点 + 聚合 traceability，**不重写 PRD 内容**。
- **本 sprint 允许的写范围**：
  - `~/.solar/harness/sprints/<s01-sid>.requirements.install_and_knowledge_graph.md` (N1, 覆盖 O1+O2)
  - `~/.solar/harness/sprints/<s01-sid>.requirements.command_matrix.md` (N2, 覆盖 O3 / 7 命令)
  - `~/.solar/harness/sprints/<s01-sid>.requirements.evidence_and_safety.md` (N3, 覆盖 O4+O5)
  - `~/.solar/harness/sprints/<s01-sid>.traceability.json` + `<s01-sid>.handoff.md` (N4 join)
- **严格禁止**：
  - 在本切片真跑 `/plugin marketplace add` / `/plugin install` / `/understand` / `/understand-*` 任何命令（这些归 S03/S04）
  - 修改父 epic 任何 artifact (`epic-*.epic.md` / `epic-*.task_graph.json` / `epic-*.traceability.json`)
  - 修改 `~/.claude/settings.json` / `~/.claude/settings.local.json` / `/Users/lisihao/Solar/.claude/*`
  - fork 或修改 Lum1104/Understand-Anything 上游源
  - 打印 secrets / OAuth code / tokens
  - 在 `/tmp` 放产出
- 禁止乐观词；禁止把 P1/P2 outcome 误标 P0；禁止把 OQ 标为 resolved（OQ-01..OQ-07 全保持 open，等下游解决）。

## 1. 用户原始大需求 → PRD outcome 映射

| outcome_id | 标题 | PRD 引用 | 优先级 | builder 直接派 | 聚合到节点 |
|------------|------|----------|--------|----------------|------------|
| O1 | 安装路径 (marketplace add + plugin install + `/plugin list` 自检 + 失败回退) | PRD §验收 A1.O1 + Command Matrix 行 1-2 | P0 | NO (S02 决定 fallback；S03 实施) | N1 |
| O2 | 知识图生成 (`/understand --language zh` → `/Users/lisihao/Solar/.understand-anything/knowledge-graph.json` ＞0 且合法 JSON) | PRD §验收 A1.O2 + Command Matrix 行 3 + Risks 行 2 | P0 | NO (S03 实施 + sample-size guard) | N1 |
| O3 | 7 个 `/understand-*` 命令矩阵 (dashboard / chat / diff / explain / onboard / domain / knowledge) | PRD §验收 A1.O3 + Command Matrix 行 4-10 | P0 | NO (S04 实施 + blocked-with-evidence 容忍) | N2 |
| O4 | 证据接入 (安装日志 + knowledge-graph 路径 + dashboard 访问证据 → status.json accepted_artifacts 或独立 handoff.md) | PRD §验收 A1.O4 | P0 | NO (S05 验证字段位置) | N3 |
| O5 | 安全边界 (settings.json / settings.local.json 前后 hash 一致 + 安装日志无 secrets) | PRD §验收 A1.O5 + 约束 §安全 + Risks 行 3/6 | P0 | NO (S05 secret-scan + hash diff) | N3 |

5 个 outcome 全部 P0；零 builder-eligible（因 PRD 已声明 S02 必须先做 architecture 决定 fallback / 端口 / 证据字段位置）。

## 2. S01 内部 DAG (3 路 fan-out + 1 join)

```
                  ┌─→ N1_install_and_knowledge_graph (O1, O2)    ─┐
   (无上游) ────────┼─→ N2_command_matrix             (O3)         ─┼─→ N4_traceability_handoff
                  └─→ N3_evidence_and_safety        (O4, O5)      ─┘     (join, traceability+handoff)
```

**并行批次**：

| 批次 | 节点 | 模型 | write_scope (零重叠) |
|------|------|------|-----------------------|
| Wave 1 (3 并行) | N1 / N2 / N3 | glm-5.1 ×3 | 3 个 `.requirements.<topic>.md` |
| Wave 2 (join)  | N4 | sonnet | `.traceability.json` + `.handoff.md` |

## 3. 每份 requirements 文档统一结构 (N1..N3)

每份 `*.requirements.<topic>.md` 必含 8 节：

1. **outcome_id 清单** — 本节点覆盖的 O-id 含 PRD 章节回链
2. **目标与背景** — 引用 PRD 原文要点（不抄全文，引段落）
3. **验收标准 per outcome** — 每 O-id ≥3 条可验证条件 (复用 PRD A1 + Command Matrix 已有定义)
4. **数据契约草案** — knowledge-graph.json schema 字段（N1）/ 7 命令输入输出（N2）/ 证据 JSON 字段（N3）—— **不实施**
5. **接口契约草案** — CLI 调用串 / 文件路径 / 副作用 —— **不实施**
6. **依赖与冲突** — 横向（与其他 O-id）+ 纵向（哪个 S0X 消费）
7. **风险边界与非目标** — 复用 PRD §Risks + §Non-Goals 对应行
8. **builder eligibility 判定** — 标 NO + 先需 S02 决定什么（每个节点都写）

## 4. N4 join 产出

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
      "outcome_id": "O1",
      "title": "安装路径",
      "prd_section": "A1.O1 + Command Matrix 行 1-2",
      "priority": "P0",
      "acceptance_count": "<n>",
      "downstream_sprints": ["S02", "S03"],
      "downstream_artifacts": ["architecture.md", "lib/install.sh"],
      "builder_eligible": false,
      "blocked_by": ["OQ-01"],
      "requirements_doc": "sprints/<sid>.requirements.install_and_knowledge_graph.md"
    }
    /* O2..O5 */
  ],
  "outcome_dependency_matrix": {
    "O2": ["O1"],
    "O3": ["O1", "O2"],
    "O4": ["O1", "O2", "O3"],
    "O5": ["O1"]
  },
  "non_goals_aggregate": [
    "不绕过 planner 派 builder",
    "不用单大 PRD 覆盖实现细节",
    "不 fork Lum1104/Understand-Anything",
    "不动 ~/.claude/settings.json 现有键",
    "不在本切片运行 dashboard",
    "不在 S01 真跑 /understand-* 任何命令"
  ],
  "builder_forbidden_aggregate": [
    "禁止 /plugin marketplace add 在 S01 真跑",
    "禁止 /understand --language zh 在 S01 真跑",
    "禁止改 ~/.claude/settings*.json 现有键",
    "禁止打印 secrets / OAuth / tokens",
    "禁止 fork 上游"
  ],
  "downstream_sprint_kickoff_package": {
    "S02_architecture_inputs": [
      "O1..O5 requirements docs",
      "Command Matrix 11 行",
      "OQ-01 (marketplace fallback)",
      "OQ-03 (dashboard port)",
      "OQ-05 (preexisting plugin inventory)",
      "OQ-06 (证据字段位置)"
    ],
    "S03_core_runtime_inputs": [
      "O1 安装契约",
      "O2 knowledge-graph 生成契约 + sample-size guard",
      "OQ-02 (LLM 调用费用)"
    ],
    "S04_orchestration_ui_inputs": [
      "O3 Command Matrix 7 命令",
      "OQ-03 (dashboard port)",
      "OQ-04 (output dir 不覆盖 README)",
      "OQ-07 (dashboard 截图 vs PDF)"
    ],
    "S05_verification_inputs": [
      "O4 证据字段位置最终决定",
      "O5 settings hash + secret-scan",
      "全 outcome acceptance"
    ]
  },
  "open_questions": [
    {"id": "OQ-01", "topic": "marketplace ID 真实有效性", "status": "open", "owner": "S02"},
    {"id": "OQ-02", "topic": "/understand LLM 调用费用", "status": "open", "owner": "S03"},
    {"id": "OQ-03", "topic": "/understand-dashboard 默认端口", "status": "open", "owner": "S04"},
    {"id": "OQ-04", "topic": "/understand-onboard 输出位置", "status": "open", "owner": "S04"},
    {"id": "OQ-05", "topic": "preexisting plugin inventory", "status": "open", "owner": "S02"},
    {"id": "OQ-06", "topic": "证据接入字段位置", "status": "open", "owner": "S05"},
    {"id": "OQ-07", "topic": "dashboard 访问证据格式", "status": "open", "owner": "S04/S05"}
  ],
  "files_touched": [
    "sprints/<sid>.requirements.install_and_knowledge_graph.md",
    "sprints/<sid>.requirements.command_matrix.md",
    "sprints/<sid>.requirements.evidence_and_safety.md",
    "sprints/<sid>.traceability.json",
    "sprints/<sid>.handoff.md"
  ]
}
```

**`<s01-sid>.handoff.md` 必须含**：
- N1..N3 各产出路径 + ≤80 字摘要
- traceability 摘要 (outcome 5 / P0 占比 100% / 阻塞数 / OQ 数 7)
- S02 启动 checklist (先读 O1..O5 + Command Matrix + 7 OQ → 输出 architecture.md / interfaces.md / fallback decisions)
- 已知未闭环项 (OQ-01..OQ-07 全部 open)
- 禁止乐观词声明

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| N1, N2, N3 | glm-5.1 | requirements spec 起草模板化，PRD 已超完整，省钱 |
| N4 (join) | sonnet | 跨节点聚合 + downstream package 推导 + 7 OQ owner 分派需 reasoning |

## 6. Stop Rules（继承 contract）

- 缺 `.task_graph.json` 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 scope 冲突回写 N4 traceability `open_questions`（不动 epic）
- 不实施 Lum1104/Understand-Anything fork
- 不动现有 Claude Code config
- 不打印 secrets
- 不在 S01 真跑 `/understand-*` 任何命令
- PRD 缺任何必需 section 不得状态推进（PRD 已完整，本规则保留）

## 7. 失败恢复 / 降级

- N1..N3 任一 FAIL → 单节点重派，不阻塞另 2 个
- N4 FAIL → 诊断哪个 N 节点 outcome 描述缺失/不一致，回写对应 N 节点重跑
- 若 PRD 内部矛盾 → N4 记 OQ 给 PM，不擅自修 PRD
- mirage degraded：PRD 已超完整，本 sprint self-contained

## 8. 非目标（明确禁止）

- 不实施任何 install/marketplace/understand 命令
- 不擅自修 PRD 原文
- 不主动 close 父 epic
- 不实施 OQ 解决方案（OQ 全部保持 open，等下游 S0X 处理）
- 不在 S01 决定 dashboard 端口（OQ-03，留 S04）
- 不决定证据字段位置（OQ-06，留 S05）
- 不实施 plugin inventory 检查（OQ-05，留 S02 pre-flight）

## 9. 给 epic 推进的接力

- N4 traceability `downstream_sprint_kickoff_package` 写明 S02/S03/S04/S05 各自 inputs。
- coordinator 在 S01 evaluator passed 后自动激活 S02（per epic schedule rule "依赖未 passed 的子 sprint 保持 queued"）。
- S01 不主动 close 任何东西。
