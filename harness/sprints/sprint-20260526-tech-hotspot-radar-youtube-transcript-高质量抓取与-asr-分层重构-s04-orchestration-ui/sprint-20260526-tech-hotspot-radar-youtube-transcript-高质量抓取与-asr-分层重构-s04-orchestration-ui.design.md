# Design — S04 Orchestration-UI 切片：YouTube Transcript Dashboard + CLI 命令树 + 面板集成

epic_id: `epic-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构`
sprint_id: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s04-orchestration-ui`
slice: `orchestration-ui`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-27T17:16:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)`
upstream: `S02 architecture passed (D1-D13 + OQ1-OQ4 decided), S03 core-runtime in parallel`
downstream: `S05 verification-release`

## 0. 切片边界

- **S04 是 orchestration-ui 切片**：消费 S02 D11/D12/D13 决议 + A3 interfaces.md 的 CLI/Dashboard/Config 契约；与 S03 并行（epic.task_graph schedule），但部分节点假定 S03 接口已实现（per S02 handoff §S04 启动 checklist）。
- **本 sprint 允许的写范围**：
  - `~/.solar/harness/sprints/<s04-sid>.dashboard_renderer.md` (C1)
  - `~/.solar/harness/sprints/<s04-sid>.cli_command_tree.md` (C2)
  - `~/.solar/harness/sprints/<s04-sid>.config_ui_and_radar_panel.md` (C3)
  - `~/.solar/harness/sprints/<s04-sid>.premium_e2e_validation_plan.md` (C4)
  - `~/.solar/harness/sprints/<s04-sid>.traceability.json` + `<s04-sid>.handoff.md` (C5 join)
- **严格禁止**：
  - 真改 Tech Hotspot Radar 源码（实施仍归 S04 后续 builder，但本 S04 sprint 是规约层）
  - 真跑 `solar-harness wiki tech-hotspot-radar` 任何子命令
  - 调用真 OpenAI API（C4 只写验证计划，真跑留给 S05）
  - 修改 S02/S03 任何 artifact 或父 epic
  - 打印 OpenAI API key
- 禁止乐观词；禁止假装 S03 已完成（明示依赖等候）

## 1. 上游消费

| S02 产出 | S04 必须消费 |
|----------|---------------|
| A1 architecture.md §D11 | dashboard 渲染栈决议：JSON-only 基线 + HTML/TUI 推迟 S04 |
| A1 architecture.md §D12 | CLI 挂 `solar-harness wiki tech-hotspot-radar` 命名空间 |
| A1 architecture.md §D13 | youtube_config pydantic v2 模块 + env_prefix='SOLAR_YOUTUBE_' |
| A3 interfaces.md §2 | R14 6 CLI 命令签名 + 退出码 + 输出 schema + legacy compat wrapper |
| A3 interfaces.md §4 | R15 YAML 5 子段 schema (供 config UI 渲染) |
| A3 interfaces.md §5 | evidence pack JSON schema (dashboard 引证据) |
| A4 OQ1 决议 | OpenAI gpt-4o-transcribe + $0.006/min cost（C4 端到端） |
| S02 handoff §S04 Checklist | 5 项: dashboard 渲染 / CLI 命令树 / config UI / premium E2E / Radar 面板 |

## 2. S04 内部 DAG（4 路 fan-out + 1 join）

```
                  ┌─→ C1_dashboard_renderer            ─┐
                  ├─→ C2_cli_command_tree              ─┤
   (上游 S02 已 passed) ┼─→ C3_config_ui_and_radar_panel    ─┼─→ C5_traceability_handoff
                  └─→ C4_premium_e2e_validation_plan   ─┘     (join)
```

**Wave 1 并行**: C1, C2, C3, C4 (write_scope 互斥) | **Wave 2 join**: C5

注：本 sprint 只产 markdown 规约（执行计划 / 验证用例 / UI 草图）；真实 UI 实施代码归后续 sprint（S04 内部的 builder phase）。本 S04 sprint 是 "规约 + 验证用例" 层，不真改源码。

## 3. 每节点统一结构

每份 markdown 规约必含 8 节：

1. **outcome 清单** + 上游引用
2. **目标与背景**
3. **验收标准 per outcome** (≥3 条)
4. **数据/接口契约草案**
5. **UI 视图草图 / CLI 调用示例** (markdown 代码块, **不真执行**)
6. **依赖与冲突** (横向 + 纵向到 S05)
7. **风险边界 + 非目标**
8. **builder eligibility** (本 S04 sprint 后续 builder 是否可直接派 vs 需 S03 接口先存在)

## 4. C1-C4 内容大纲

### C1 dashboard_renderer.md
- 消费 S02 D11 (JSON-only 基线 + HTML/TUI 推迟 S04)
- 9 dashboard 指标渲染：subtitle tracks / accepted by source-tier / pending by P / failed by error_code / model success rate / score 分布 / metadata-only / report-eligible / premium cost
- HTML 模板草图 (visual-template 引用)
- TUI 替代方案 (基于现有 Tech Hotspot Radar 终端 UI)
- 数据源: 调用 S03 `transcript-status --json` (S03 D11 已承诺)
- SLO 状态行: hard / soft 阈值显示
- 验收 ≥5 条

### C2 cli_command_tree.md
- 消费 S02 D12 (solar-harness wiki tech-hotspot-radar 命名空间)
- 6 命令树 (discover-transcript-tracks / acquire-transcripts / process-transcript-jobs / audit-transcript-quality / transcript-status / transcript-ab-test-asr) 挂载点
- legacy `process-transcripts` 兼容包装层 (调用新 ladder)
- subcommand 路由 + 帮助文本草案
- 退出码统一 (0/1/2/3 per A3 interfaces.md)
- 验收 ≥5 条

### C3 config_ui_and_radar_panel.md
- 消费 S02 D13 (youtube_config pydantic v2)
- Config UI 草图：5 子段 (transcript_acquisition / subtitle_tracks / asr / transcript_quality / premium_asr) 各字段渲染
- env_prefix=SOLAR_YOUTUBE_ 注入路径
- Tech Hotspot Radar 面板集成: 9 指标 + SLO 状态行嵌入现有 radar status view
- 面板布局草图 + 数据刷新策略
- 验收 ≥4 条

### C4 premium_e2e_validation_plan.md
- 消费 S02 D10 + OQ1 (OpenAI gpt-4o-transcribe, $0.006/min)
- 端到端验证用例:
  - 准备阶段: API key 注入 (env=SOLAR_YOUTUBE_PREMIUM_OPENAI_KEY)
  - 触发阶段: P0 视频 + entity 召回率 ≥70% (per OQ4) 触发 premium
  - 调用阶段: gpt-4o-transcribe call + ledger 写入 7 字段
  - 验证阶段: cost 计算 / budget cap=20 USD / quality_score 提升验证
  - 失败阶段: API down / quota exceeded → fallback faster-whisper large-v3
- **本节点只写验证计划，不真调 OpenAI API（留 S05 执行）**
- 失败 fallback 流程草案
- 验收 ≥5 条

### C5 traceability_handoff (join)
- traceability.json 12 字段含 outcomes 4 (C1-C4) / decisions_consumed (S02 D10-D13 + OQ1) / downstream_sprint_kickoff_package S05
- handoff.md 含 C1-C4 摘要 + S05 启动 checklist

## 5. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| C1, C2, C3 | glm-5.1 | 规约 + UI 草图模板化 |
| C4 | sonnet | E2E 验证计划需 reasoning (cost / failure mode 推理) |
| C5 (join) | sonnet | 跨节点聚合 |

## 6. Stop Rules

- 缺 task_graph.json 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 S03 接口偏离 S02 决议 → C5 记 OQ 给协调器，不擅自修 S02
- 不真改 Tech Hotspot Radar 源码
- 不真跑 `solar-harness wiki tech-hotspot-radar` 命令
- 不真调 OpenAI API（C4 只写计划）
- 不打印 API key / OAuth
- 不主动 close 父 epic
- 不用乐观词

## 7. 与 S03 的并行/接力

本 sprint 与 S03 并行启动 (epic schedule)，但实施依赖 S03 输出：

- C1 依赖 S03 `transcript-status --json` 实现 → 本节点写规约不阻塞
- C2 依赖 S03 6 CLI 命令实现 → 本节点写挂载点和兼容包装规约不阻塞
- C3 依赖 S03 youtube_config pydantic model → 本节点写 UI 草图基于 S02 schema 即可
- C4 依赖 S03 premium_escape 模块 → 本节点写验证用例（不真跑），真跑留 S05

S04 sprint passed 后，S03 + S04 都 passed 才能解锁 S05 verification-release。
