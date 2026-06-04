# Design — S01 Requirements 切片：KVTC 接入质量修复需求矩阵

epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements`
slice: `requirements`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-22T04:45:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`

## 0. 本切片的边界（强制）

- 本 sprint 只输出**需求拆解、追踪矩阵和下游 sprint 输入清单**，**不允许**改 ThunderOMLX 任何 .py/.ts/.js/.sh 业务代码。
- 父 epic 的 8 项用户要求（详见 PRD 用户原始需求）必须 1:1 映射到一个或多个下游 sprint owner（S02 architecture / S03 core-runtime / S04 orchestration-ui / S05 verification-release）。
- 任何"实现修复"动作禁止在本 sprint 完成；只能写"由谁、用什么验证、什么情况下回退"。
- 任何 ThunderOMLX 真实运行（pytest、ab_correctness、HTTP `/v1/cache/prompt/save`）禁止在 S01 builder 执行；本 sprint 不打开 live pane，不动主服务 cache。

## 1. 上游 / 下游接力

```
PM PRD (s01.prd.md)  ──>  Planner (本文件)
                              │
                              ▼
            ┌─────────────────────────────────────────┐
            │  S01 Builder 节点 N1..N7 (并行文档矩阵) │
            └─────────────────────────────────────────┘
                              │ join
                              ▼
                       N8 traceability 合并
                              │
                              ▼
                     S01 Evaluator (gate)
                              │ passed
                              ▼
        epic 激活 S02 (architecture) ──> S03/S04 ──> S05
```

下游 sprint 的依赖来自父 epic `epic-…task_graph.json`（已就位）：
- S02 architecture：消费 N1+N8 matrix，做接口/数据模型/兼容策略
- S03 core-runtime：消费 N2/N3/N4，实现 calibration key / family classifier / sink-recent bypass / reconstruction gate
- S04 orchestration-ui：消费 N5/N7，做 `/v1/cache/prompt/save` 422 fix + UI gate 开关 + 最近 A/B 结果展示
- S05 verification-release：消费 N4/N6，做 `scripts/kvtc_ab_correctness.py` CI gate + 真实 SSD block 回归

## 2. 用户 8 项要求 -> 需求矩阵节点映射

| # | 用户要求（摘自 PRD） | 矩阵节点 | 下游 owner sprint | 关键风险边界 |
|---|---------------------|---------|-------------------|--------------|
| 1 | 论文对齐审计（PCA 维度 / 校准粒度 / sink-recent / RoPE / K-V 分离 / family / bit budget 与论文一致） | N1 | S02_architecture | 缺审计 → S02 设计偏离论文 |
| 2 | calibration key 改 `per-model + tensor_family + shape_signature + layer_type + rope_state` | N2 | S03_core_runtime | 单一 key → key/value/mamba-like 混 basis |
| 3 | encode 前 shape/family classifier，非 transformer/不支持 family 必须回退 lz4 | N3 | S03_core_runtime | 缺 classifier → 产损坏 .kvtc |
| 4 | sink/recent token bypass + lossless side-band 存储 | N3 | S03_core_runtime | 缺 bypass → 高重要 token 失真 |
| 5 | reconstruction gate：抽样 decode、p95_rel_rmse ≤ 0.02 / min_cos ≥ 0.999、不达标回退 lz4 | N4 | S03_core_runtime + S05_verification_release | 缺 gate → 坏 .kvtc 入缓存 |
| 6 | 修复 `/v1/cache/prompt/save` 422 或明确禁用 + 修文案 | N5 | S04_orchestration_ui | 422 未解 → 真实 KV 无法 A/B |
| 7 | `scripts/kvtc_ab_correctness.py` 升 CI/regression gate，覆盖真实 SSD block + 同维 family + 混合 family + synthetic outlier + named prompt cache | N6 | S05_verification_release | 缺 gate → 回归无法防御 |
| 8 | UI 默认关闭 KVTC，开启前必须显示最近一次 A/B gate 结果 | N7 | S04_orchestration_ui | 默认开 → 未验证特性误暴露给用户 |
| - | 父 epic ↔ 子 sprint traceability map（聚合 N1..N7 + 父 traceability.json） | N8 | S01 自身（join） | 缺 map → epic 关闭时漏 gate |

## 3. 控制面 / 数据面

- **控制面**：solar-harness coordinator + graph-scheduler；本 sprint 不直接调度业务进程。
- **数据面**：sprint artifacts (`sprints/<sid>.*.md/json/html`) → 入 solar DB raw → S02 Planner 读取。
- 所有需求矩阵文件存活于 `~/.solar/harness/sprints/`，禁止写入 `/Users/lisihao/ThunderOMLX/`、禁止写入 `/tmp/`、禁止改 `~/.solar/STATE.md`。

## 4. 状态、失败恢复、观测

- 本切片所有 N1..N8 builder 节点必须把结果写为 markdown/json 文件 + 一行 evidence summary，由 evaluator 抽检。
- 任一 N1..N7 失败 → S01 整体 FAIL；不允许部分通过（否则下游 S02 拿不到完整矩阵）。
- 失败处理路径：ATLAS structured repair → builder 在原节点重写文件并重跑 `graph-scheduler validate`。
- 观测：所有矩阵节点产物必须含 `acceptance_evidence` 段落（明示"哪个下游 sprint 验证哪一条"）。

## 5. 接口边界与兼容策略（给 S02 的输入清单）

- N1 输出 `sprints/<sid>.requirements.paper_alignment.md`：表格列 = {论文位置, ThunderOMLX 当前实现位置, gap 描述, 验证方法}；S02 必须基于此选择保留/重写。
- N2 输出 `sprints/<sid>.requirements.calibration_key.md`：含 key schema BNF + 旧 key 迁移策略 + 校准存储路径；S03 据此改 `kvtc_calibration_store.py` 不破坏旧消费者读取。
- N3 输出 `sprints/<sid>.requirements.family_classifier_bypass.md`：定义 family taxonomy + classifier 输入 contract + lz4 fallback 决策表 + sink/recent bypass 默认参数；S03 据此改 `kvtc_codec.py` encode 入口。
- N4 输出 `sprints/<sid>.requirements.reconstruction_gate.md`：列默认阈值 + family profile 表 + 失败回退动作 + log schema；S05 据此扩 `scripts/kvtc_ab_correctness.py`。
- N5 输出 `sprints/<sid>.requirements.named_prompt_cache_422.md`：含 422 复现步骤 + 三种 root cause 假设（schema / 鉴权 / KV capture 时机）+ 决策树（修 vs 禁用 + 文案）+ 回滚指令；S04 据此修 API 或禁用 + UI 文案。
- N6 输出 `sprints/<sid>.requirements.ci_regression_gate.md`：列覆盖矩阵 {真实 SSD block, 同维 family, 混合 family, synthetic outlier, named prompt cache} × {pass/fallback/fail 期望}；S05 据此扩测试用例。
- N7 输出 `sprints/<sid>.requirements.ui_default_off_gate.md`：UI 开关 state machine + 最近 A/B 结果数据源（现有产物 vs 新 manifest）+ rollback 文案；S04 据此改 UI gate。
- N8 输出 `sprints/<sid>.requirements.traceability_map.md` + `sprints/<sid>.requirements.traceability.json`：聚合 N1..N7 到父 epic.traceability.json 的 child mapping（PRD 第 7 节"非目标"列出的反例必须被显式标 `not_in_scope`）。

## 6. 降级策略 / Stop Rules

- `solar-harness context inject` 失败 → 必须在 design.md 头部记录 degraded 来源，**已记录**：`mirage degraded -> qmd/obsidian/solar_db fallback`。
- `graph-scheduler validate` 失败 → 不允许提交 task_graph.json；必须修复 schema 再写盘。
- `html_artifact.py register` 失败 → 只 warn，不阻断 planner→builder 主链路（dispatch step 7 明确允许）。
- N1..N7 任一节点产出 acceptance_evidence 缺失 → evaluator 必须 FAIL，禁止"看起来差不多"通过。
- 父 epic 在 S05 通过前禁止 close；activation_policy 中 `passed_child_statuses = [passed, completed, eval_passed]` 已就位，本 sprint 不更改。

## 7. 非目标（明确禁止 builder 误以为是任务）

- 不修 `kvtc_codec.py` / `kvtc_calibration_store.py` / `paged_ssd_cache.py` 代码（属 S03）。
- 不修 `/v1/cache/prompt/save` HTTP handler（属 S04）。
- 不写或改 `scripts/kvtc_ab_correctness.py`（属 S05）。
- 不动 UI（属 S04）。
- 不跑 pytest / 不跑 ab_correctness / 不调 ThunderOMLX HTTP API。
- 不写父 epic 关闭报告。
- 不打开 live tmux pane、不重启 harness、不动主服务 cache。
