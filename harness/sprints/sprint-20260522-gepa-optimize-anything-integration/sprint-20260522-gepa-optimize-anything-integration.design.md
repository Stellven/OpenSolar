# Design — GEPA optimize_anything Integration for Solar-Harness

sprint_id: `sprint-20260522-gepa-optimize-anything-integration`
priority: `P1`
lane: `optimizer-plane`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-22T11:20:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream: `PM PRD + Contract (created 2026-05-22T15:07:46Z by Codex PM)` · `task_graph.json (already validated, 5 nodes, 4 layers, 0 errors)` · `N1 currently in 'reviewing' status (N1-handoff.md ~10 KB partial)`
source_url: `https://gepa-ai.github.io/gepa/blog/2026/02/18/introducing-optimize-anything/`

## 0. 本切片的边界（强制 read-first）

- **本 sprint 是研究 + 设计**：目标产物是「集成合同 + 实施 backlog」，**不是** 把 GEPA 上线到 production。
- 允许 Write/Edit 的路径：
  - `~/.solar/harness/sprints/<sid>.{design,plan,N1..N5-handoff,task_graph,planning_html}.md/json/html`（本 sprint 自己的 artifact）
  - `~/.solar/harness/monitor-reports/gepa-optimize-anything-integration.md`（N5 最终报告）
- **严格禁止**：
  - 安装 GEPA 到任何 Python 环境（pip / conda / uv）
  - 真跑 GEPA 优化循环（即使 dry-run，未经显式 `--execute` 也不允许）
  - 把优化产物自动应用到任何 production config / hook / skill / prompt / 代码 / operator registry
  - 打印或落盘 secrets（API key / OAuth / 私有 prompt）
  - 把 `architecture_policy.package_boundary` 中的 `integrations/gepa_optimizer/` 目录提前创建
  - 修改 `~/.solar/STATE.md` 或 epic/sprint 其他 artifact
  - 把昂贵 Claude 路由用于本 sprint 的批量审计（per PRD non-goals）
- 知识库降级 (`mirage degraded`)：研究节点（N1）通过 `WebFetch` 直接读官方博客；其他节点 self-contained。

## 1. 已有产物（继承 PM/Coordinator）

| Artifact | 状态 | 备注 |
|----------|------|------|
| `.prd.md` | 已存在 | Codex PM 创建；本 sprint 边界 = PRD §Goals + §Non-Goals |
| `.contract.md` | 已存在 | 5 个必交付物 + DoD + Evaluation Dimensions |
| `.task_graph.json` | 已存在并 validate ok | 5 节点 N1..N5；4 layer；0 errors / 0 warnings |
| `.N1-handoff.md` | 部分（~10 KB） | N1 builder `reviewing` 中；GEPA API 审计已完成大半 |
| `.design.md` | **本节点产出** | （本文件） |
| `.plan.md` | **本节点产出** | |
| `.planning.html` | **本节点产出** | |
| `.N2..N5-handoff.md` | 待 builder | N2/N3/N4/N5 节点产出 |
| `monitor-reports/gepa-optimize-anything-integration.md` | 待 N5 | 最终报告 |

## 2. GEPA `optimize_anything` 简述（per N1 in progress）

来自 N1-handoff.md（部分已审计）：

- 声明式 API `optimize_anything(seed_candidate, evaluator, dataset?, valset?, objective?, background?, config?) -> GEPAResult`
- 三种模式：seedless / multi-task / generalization
- 核心机制：Evaluator 提供 score + **ASI (Actionable Side Information)** 诊断 → LLM Proposer 反射式重写候选 → Pareto frontier 选择
- 配置：`GEPAConfig(engine, reflection, tracking, merge?, refiner?)`
- 追踪：MLflow / W&B
- 关键不确定性：package 安装方式、生产稳定性、benchmark 数据是否可复现 — N1 已显式标注待验证

**核心假设**（本 sprint 设计基础）：

1. GEPA 是一个**用户态库**，不需要 root / 系统级权限即可 import 使用。
2. Evaluator 是用户提供的 Python callable；**Solar 拥有完全控制权**（可加入沙箱、超时、资源限制）。
3. ASI 是结构化文本反馈；Solar 可定义 schema 并 enforce。
4. LLM Proposer/Reflection 可路由到任意 chat-completion-兼容 API（per PRD Goal 5）。

## 3. Solar-Harness 集成架构（N2 输入要点）

```
┌──────────────── Solar Control Plane ─────────────────┐
│  CLI:  solar-harness optimizer gepa <subcommand>     │
│    propose  -- dry-run candidate generation          │
│    run      -- 真跑（必须 --execute + budget caps）  │
│    review   -- 列 candidate + score + ASI            │
│    promote  -- 单独 review 命令把 candidate 注入目标 │
│    rollback -- 撤销已 promote 的 candidate           │
│                                                      │
│  Config:                                             │
│    ~/.solar/harness/config/gepa_optimizer.json       │
│    （budget_caps / default_model / approval_gate）   │
└───────────────────┬──────────────────────────────────┘
                    │
                    ▼
┌────────────── integrations/gepa_optimizer/ ───────────┐
│  __init__.py        sandbox boundary                  │
│  adapter.py         GEPAConfig 包装 + evaluator wrap  │
│  cli.py             solar-harness CLI 钩子            │
│  evaluator.py       Solar evaluator adapter           │
│  artifact_store.py  ASI / candidate / lineage 落盘    │
│  operator_router.py 映射 GEPA proposer 模型到         │
│                     ~/.solar/harness/config/          │
│                     physical-operators.json           │
│  budgets.py         budget caps + stoppers            │
│  promote.py         review/approval gate              │
└───────────────────┬──────────────────────────────────┘
                    │
                    ▼
┌──────────── Data / Observability Plane ───────────────┐
│  ~/.solar/harness/optimizer-runs/<run_id>/            │
│    candidate-001.json    score / ASI / lineage        │
│    candidate-002.json    ...                          │
│    pareto.jsonl          Pareto frontier snapshots    │
│    summary.json          run final summary            │
│    audit.log             全部决策 + spend log         │
│  monitor-reports/                                     │
│    gepa-optimize-anything-integration.md (本 sprint)  │
│    gepa-run-<run_id>.md (每次真跑产生)                │
└───────────────────────────────────────────────────────┘
```

## 4. Solar primitives 映射表

| GEPA 概念 | Solar 等价 | 实施细节（N2/N4） |
|-----------|------------|-------------------|
| `optimize_anything()` 入口 | `solar-harness optimizer gepa run/propose` CLI | CLI 包装；默认 `propose`（dry-run） |
| `seed_candidate` | Solar artifact（prompt/skill/config 等的现有文本） | 通过 `--target <path>` 注入；不允许直读 production hook 路径，必须复制到 `optimizer-runs/<id>/seed.txt` |
| `evaluator` callable | Solar Evaluator adapter | 必须实现 `EvaluatorProtocol { def __call__(candidate, dataset_item) -> (score, asi) }`；在 subprocess + timeout 沙箱执行 |
| `dataset` / `valset` | Solar fixture / benchmark dataset | 必须显式 `--dataset <path>` 与 `--valset <path>`；禁止运行时网络下载 |
| `objective` / `background` | Solar prompt template | 由 user 在 CLI 或 config 提供 |
| `GEPAConfig.engine` | budget caps + concurrency limits | `budgets.py`：max_evaluations、max_wall_time、max_spend_usd、max_concurrent |
| `GEPAConfig.reflection` | LLM Proposer 模型路由 | `operator_router.py` 路由到 `physical-operators.json`；默认 glm-5.1（cost-sensitive） |
| `GEPAConfig.tracking` | Solar monitor bridge | MLflow 关闭；W&B 关闭；改走 Solar audit.log + monitor-reports/ |
| `GEPAConfig.merge` | Pareto frontier 合并 | 允许，结果落 `pareto.jsonl` |
| `GEPAConfig.refiner` | 单次评估后精炼 | 允许，但仍受 budget caps |
| `GEPAResult` | Solar candidate store | 落 `optimizer-runs/<run_id>/` 全集 |
| ASI 诊断文本 | Solar ASI schema | 结构化字段 `{cls_name, signal, ref_path?, suggestion}`；禁止 raw evaluator print |
| Pareto/frontier | `pareto.jsonl` | 每次更新追加 1 行 |
| 候选 lineage | candidate JSON 含 parent_id + reflection_prompt_sha256 | 可追溯重放 |

## 5. 安全模型（N3 输入要点）

per PRD Non-Goals + Contract Scope §Out of Scope：

| 安全维度 | 设计决策 | enforce 位置 |
|----------|----------|--------------|
| 默认运行模式 | `propose` = dry-run；`run` 必须显式 `--execute` + `--budget-usd N` + `--budget-evals N` | `cli.py` argparse |
| Budget caps | 必须配 wall-time / spend-usd / max-evaluations 三上限 | `budgets.py`；任一越界立即 stop |
| Stoppers | 显式停止条件（score plateau / spend cap / wall-time cap / explicit signal） | `budgets.py` |
| Evaluator 沙箱 | 子进程 + timeout + ulimit（防止 evaluator 把 prompt 注入 host） | `evaluator.py` subprocess wrapper |
| Cache | 同 candidate sha256 命中 → 复用 score；避免重跑 LLM | `artifact_store.py` |
| Secrets 处理 | env 变量白名单；禁止把 OAuth token / API key 序列化到 candidate JSON 或 ASI | `adapter.py` 入口扫描 |
| Candidate lineage | 每 candidate 强制 `{id, parent_id, generation, score, asi, model_used, cost_usd, ts}` | `artifact_store.py` |
| 隔离 run 目录 | `~/.solar/harness/optimizer-runs/<run_id>/`；run_id = UTC timestamp + sha8 | `cli.py` |
| Promotion gate | `solar-harness optimizer gepa promote --run <id> --candidate <id> --target <path>` 单独命令；要求人工 acknowledge | `promote.py` |
| 自动 apply | **严格禁止**；promote 必须显式且仅替换隔离目录 → target 复制后再 commit | `promote.py` + Solar review hook |
| Rollback | promote 前必须备份 target → 备份路径 + `rollback --run <id>` 命令一键还原 | `promote.py` |
| Multimodal | 默认禁用；启用需 operator `input_modalities` 含 image | `operator_router.py` 校验 |
| 日志 secret 扫描 | 写入 audit.log / candidate JSON 前必须经过 secret regex 过滤 | `artifact_store.py` |

## 6. 与 autoresearch / Meta-Harness 共存

| Solar 优化器 | 触发点 | GEPA 关系 |
|--------------|--------|-----------|
| autoresearch pane optimizer | pane-level 输出质量（PRD/Plan/Eval 反审） | 仍保留为 pane advisor；不被 GEPA 替代 |
| Meta-Harness 外环 | harness 自身（hook、skill 路由）的元优化 | 仍保留；GEPA 是补集（用户 artifact 优化） |
| Physical operators | Solar 内部 model routing | GEPA proposer/reflection 通过此路由 |
| DAG worker | 节点任务执行 | GEPA 是新增 lane (`optimizer-plane`)，与 builder/evaluator lane 隔离 |
| Evaluator gates | sprint 节点 evaluator | GEPA 自己的 evaluator 是用户态 callable，**不替代** Solar evaluator |
| Benchmark / reports | 验收证据 | GEPA run summary 通过 monitor-reports/ 进入主审计 |

**lane 隔离**：GEPA 优化运行**不**消费 builder/evaluator pane；它通过 CLI 直接调用 LLM API（route via physical operators），不会和 DAG node dispatch 抢占 pane。

## 7. 用例优先级（N4 输入要点）

per PRD Goal 3 + 4：

| Use case | 优先级 | safety class | 首批可启用 |
|----------|--------|--------------|------------|
| 1. system prompt 优化（固定 eval set） | P0 | low（不直接修改 prod） | 是（首 PoC） |
| 2. skill 文本 / rule template 调优 | P1 | medium（promote 才 apply） | 是（第二阶段） |
| 3. physical operator routing policy | P2 | high（改路由会影响全 harness） | 否（需更严 review） |
| 4. benchmark harness 参数 | P1 | low | 是（第三阶段） |
| 5. visual / multimodal artifact 优化 | P3 | 仅多模态 operator 后启用 | 否（默认禁用） |

**首批 MVP**（仅 use case 1）：从 `~/.solar/harness/prompts/<name>.md` 输入 → optimize → 落 `optimizer-runs/<id>/` → review → 手动 promote。

## 8. CLI 草案（N2 锁定，N4 实施细化）

```bash
# 默认 dry-run propose
solar-harness optimizer gepa propose \
  --target ~/.solar/harness/prompts/<name>.md \
  --evaluator <module:func> \
  --dataset path/to/dataset.jsonl \
  [--valset path/to/valset.jsonl] \
  [--objective "..."] \
  [--background "..."] \
  [--max-evaluations 20] \
  [--proposer-model glm-5.1]

# 真跑必须显式 --execute
solar-harness optimizer gepa run \
  --target <path> --evaluator <m:f> --dataset <path> \
  --execute \
  --budget-usd 5 --budget-evals 50 --max-wall-time-min 30

# 查看 run 结果
solar-harness optimizer gepa review --run <run_id>

# 审批 + apply（必须显式）
solar-harness optimizer gepa promote \
  --run <run_id> --candidate <candidate_id> \
  --target <path> \
  --backup-dir ~/.solar/harness/backups/

# 撤销
solar-harness optimizer gepa rollback --run <run_id>
```

## 9. 失败恢复 / 观测（N3 输入要点）

- **失败模式**：
  - F1 evaluator 超时 → 子进程 SIGKILL + log + 该 candidate 标 `score=null, asi=evaluator_timeout`
  - F2 evaluator 异常 → 同上，asi=`evaluator_exception:<cls>`
  - F3 LLM provider 错误 → 退避 + retry 3 次；超额 → stop run
  - F4 budget 越界 → 立即 stop；候选保留；spend log 标 `final=true`
  - F5 secret leak detected → 立即 abort + 删该 candidate；audit.log 标 `secret_leak_aborted`
  - F6 promote 期间 target 文件被外部修改 → diff check → abort promote（保护现状）
  - F7 rollback 备份缺失 → abort + 提示手动恢复
- **观测**：audit.log + monitor-reports/gepa-run-<id>.md 包含全部决策 + spend + 时间线
- **Solar monitor bridge**：每次 run 完成自动写入 `monitor-reports/`，由 Solar 监控面板拾取

## 10. 数据模型（N3 输入要点）

```jsonl
# pareto.jsonl 每行一条
{"ts":"...","candidate_id":"c-001","score":{"primary":0.82,"secondary":0.95},"on_frontier":true}

# candidate-<id>.json
{
  "schema_version":"gepa.candidate.v1",
  "candidate_id":"c-001",
  "parent_id":null,
  "generation":0,
  "text_sha256":"...",
  "text":"<sanitized; secret-scanned>",
  "score":{"primary":0.82,"secondary":0.95},
  "asi":[
    {"cls_name":"format_error","signal":"missing closing tag","suggestion":"add </tool>"}
  ],
  "model_used":"glm-5.1",
  "reflection_prompt_sha256":"...",
  "cost_usd":0.012,
  "wall_time_sec":4.3,
  "ts":"2026-05-22T11:30:00Z"
}

# summary.json
{
  "schema_version":"gepa.run_summary.v1",
  "run_id":"r-20260522T113000Z-abc123ef",
  "config":{ "model":"glm-5.1","budget_usd":5,"budget_evals":50 },
  "totals":{ "candidates":47,"frontier_size":4,"total_cost_usd":3.21,"wall_time_min":18 },
  "stopper_triggered":"score_plateau",
  "best_candidate_id":"c-039",
  "promoted":false,
  "tracking_sprint":"sprint-20260522-gepa-optimize-anything-integration"
}
```

## 11. 兼容性 / 冲突 / 降级

**冲突**：

- GEPA proposer 与 autoresearch 都用 LLM 反审；二者并存时必须隔离 audit.log（不同 prefix `[gepa]` vs `[autoresearch]`）。
- `architecture_policy.package_boundary` = `integrations/gepa_optimizer/`（目录待 N4 后实施 sprint 创建；本 sprint 不预建）。
- GEPA 官方 package 安装方式 N1 标待验证；本 sprint **不**安装；N4 backlog 给出 `pip install gepa --dry-run` 验证步骤。

**降级**：

- 若 N1 发现 GEPA 实际 API 与 N1-handoff.md 当前理解不一致 → N2/N3 必须以 N1 audit 为准
- 若 mirage 持续 degraded → N1 通过 WebFetch 直接拉 blog；其他节点 self-contained
- 若 GEPA package 不存在 / 私有 / 不可用 → N4 必须显式记录「pending package availability」并给出 stub adapter PoC 方案

## 12. 非目标（明确禁止）

- 不安装 GEPA（pip/conda/uv 均禁止）
- 不真跑 GEPA 优化循环（即使 propose；仅设计）
- 不创建 `~/.solar/harness/integrations/gepa_optimizer/` 目录（属下一 sprint）
- 不修改任何 Solar production hook / skill / prompt / config / operator registry
- 不打印或落盘 secrets
- 不路由本 sprint 节点到昂贵 Claude（per PRD non-goal）
- 不修改 `~/.solar/STATE.md`、epic.*、其他 sprint artifact
- 不打开 live tmux pane / 不重启 harness
- 不使用乐观词

## 13. 给 N5 + 下一个实施 sprint 的接力

- N5 必须产 `monitor-reports/gepa-optimize-anything-integration.md`（per PRD Acceptance）
- N5 report 含：
  - 源 GEPA 摘要（含 URL + 假设 vs 事实分离）
  - Solar 架构映射表
  - 安全策略全集
  - 实施 backlog（精确文件清单 + 测试命令 + 卷出计划）
  - 当前问题 + 下一动作
- 下一个 sprint contract（N5 outline）：
  - 目标 = 创建 `integrations/gepa_optimizer/` + 实施 P0 use case（system prompt 优化 MVP）
  - 包含 5-8 个实施节点：adapter / cli / evaluator / artifact_store / operator_router / budgets / promote / e2e tests
  - **不**包含真跑 production prompt 优化（保留 staging only）
