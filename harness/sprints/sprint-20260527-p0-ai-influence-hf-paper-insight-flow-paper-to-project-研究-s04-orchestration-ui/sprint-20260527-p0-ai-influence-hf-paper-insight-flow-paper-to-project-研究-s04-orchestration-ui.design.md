# Design — HF Paper Insight Flow S04 Orchestration-UI

epic_id: `epic-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究`
sprint_id: `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s04-orchestration-ui`
slice: `orchestration-ui`
role: planner
status: planning_complete
generated_at: 2026-05-28T17:40:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
upstream: S02 (passed, 13 modules + 7 schemas + 5 OQ resolutions) + S03 (in parallel)
downstream: S05 verification-release

## 0. 切片定位

HF Paper Insight Flow epic 的 orchestration-ui 切片。消费 S02 §architecture (Compiler + KnowledgeStore + WatchTrigger + CLI + ConfigLoader 5 modules) + S02 §interfaces (Compiler+Store+Watch+CLI+Config API)。与 YouTube/TUI S04 同款 C1-C5 模式, 特化为 HF Paper Insight 输出 7 资产 + radar CLI + 三源共振 dashboard。

## 1. 上游消费

| S02 产出 | S04 必须消费 |
|----------|---------------|
| architecture.md §模块划分 | Compiler / KnowledgeStore / WatchTrigger / CLI / ConfigLoader 5 模块 |
| architecture.md §control plane | CLI + ConfigLoader + WatchTrigger 调度链 |
| interfaces.md §6 Compiler+Store+Watch+CLI+Config API | 7 输出资产 + 4 ingest 通道 + CLI 10 flags + Config schema |
| OQ-04 + OQ-05 决议 | YAML config 5 子段 + Knowledge ingest 写入顺序 (raw 同步 + extracted/QMD/graph 异步并行) |

## 2. 5-Node DAG (复用 YT/TUI S04 同款)

```
                  ┌─→ C1_dashboard_renderer_spec ─┐
                  ├─→ C2_cli_command_tree_spec   ─┤
   (上游 S02 ok) ─┼─→ C3_config_ui_spec          ─┼─→ C5_traceability_handoff
                  └─→ C4_high_model_e2e_plan     ─┘
```

**Wave 1 (4 并行)**: C1, C2, C3, C4 (write_scope 互斥)
**Wave 2 (join)**: C5

## 3. C1-C4 内容大纲

### C1 dashboard_renderer_spec.md
- 三源共振 radar (Paper / Project / Influence) HF Paper Insight 区域: 7 输出资产卡片 (Insight Report / Cards / Resonance Seeds / Topics / Experiments / Project Briefs / Deep Research Seeds)
- HTML 模板 (visual-template CSS) + TUI Rich 表格
- 数据源: KnowledgeStore.query_outputs() + Compiler.last_run_status()
- SLO 状态行: HF Paper API 命中率 / High Model 调用率 / Knowledge ingest 延迟
- 验收 ≥5 条

### C2 cli_command_tree_spec.md
- CLI 10 flags 挂载 `solar radar hf-papers run` 命名空间
- 退出码 0/1/2/3 统一
- subcommand 路由 + cron 使用示例
- legacy `arxiv_digest` (若有) 兼容包装
- 验收 ≥5 条

### C3 config_ui_spec.md
- YAML config 5 子段 (collection / enrichment / scoring / output / quality) hot-reload
- High Model 4 路由阈值 (0.75/0.55/0.40/<0.40) + 3 override 编辑
- Knowledge ingest 4 通道顺序配置 (per OQ-05)
- 5 Provider 限流参数 (HF/arXiv/HF assets/Semantic Scholar/GitHub) 可调
- 验收 ≥4 条

### C4 high_model_e2e_plan.md
- ChatGPT 5.5 Thinking high 5 phase E2E (准备/触发/调用/验证/失败) per S02 OQ-03 (gstack browser.browse 复用)
- Browser Agent 接入 (gstack browser.browse + ChatGPT 5.5 Thinking high)
- 触发条件: score >= 0.75 → full packet; 0.55-0.75 → compact packet; <0.40 → raw archive
- 失败回退: Browser Agent 不可用 → 降级 ChatGPT 5.5 normal (无 thinking)
- 7 输出资产验证: insight report / cards / seeds / topics / experiments / projects / deep-research
- **本节点只写计划, 不真调高模型** (留 S05)
- 验收 ≥5 条

### C5 traceability_handoff (join)
- traceability.json 12 字段 + S03 dependencies + S05 启动包
- handoff 含 C1-C4 摘要 + S05 启动 checklist + 5 OQ-C5

## 4. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| C1, C2, C3 | glm-5.1 | 规约模板化 |
| C4 | sonnet | High Model E2E 设计需 reasoning |
| C5 | sonnet | join |

## 5. Stop Rules

- 不真调 ChatGPT 5.5 Thinking (C4 只写计划)
- 不真跑 5 provider API (HF/arXiv/GitHub 等; 留 S05)
- 不修改 solar radar 源码 (本 sprint 是规约层)
- 不动 ~/Knowledge raw/extracted/QMD/graph 实际数据
- 不打印 API key (HF / Semantic Scholar / GitHub / OpenAI)
- 不主动 close 父 epic
- 不用乐观词
- 不把 HF ranking 当结论 (per PRD 核心决策 1+2)

## 6. 与 S03 并行 + 给 S05 接力

- S04 与 S03 并行 (epic.task_graph S03/S04 都 depends_on=S02)
- C1-C4 假定 S03 实施接口; 不阻塞 S03
- S05 启动包: 4 测试矩阵 (DASHBOARD / CLI / CONFIG / HIGH_MODEL_E2E 真跑) + S01 67 AC 全回归 + S02 13 决议 + 5 OQ

## 7. Knowledge Context

S02 3.9K handoff + 6.5K traceability + S01 5 requirements docs self-contained. mirage degraded → QMD + Obsidian + Solar DB.
