# Plan — S04 Orchestration-UI (YouTube Transcript Dashboard + CLI + Radar 面板切片)

gate: `sprint-20260526-tech-hotspot-radar-youtube-transcript-高质量抓取与-asr-分层重构-s04-orchestration-ui:passed`
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db)
upstream: S02 architecture passed (D1-D13, OQ1-OQ4 decided); S03 core-runtime in parallel

## 0. DAG 与并行边界

```
                ┌─→ C1_dashboard_renderer        (glm-5.1) ─┐
                ├─→ C2_cli_command_tree          (glm-5.1) ─┤
   (上游 S02 ok) ─┼─→ C3_config_ui_and_radar_panel (glm-5.1) ─┼─→ C5_traceability_handoff (sonnet)
                └─→ C4_premium_e2e_validation_plan (sonnet) ─┘     (join)
```

**Wave 1 (4 并行)**: C1 / C2 / C3 / C4 (write_scope 互斥)
**Wave 2 (join)**: C5

## 1. 节点验收

| 节点 | 关键验收 |
|------|----------|
| **C1** dashboard | 9 指标渲染规约 + HTML/TUI 双方案草图 + 数据源 `transcript-status --json` + SLO 状态行；引 S02 D11 + R13 9 指标；≥5 验收 |
| **C2** CLI | `solar-harness wiki tech-hotspot-radar` 命名空间挂载 + 6 命令路由 + legacy `process-transcripts` 包装 + 退出码 0/1/2/3 统一；引 S02 D12 + A3 §2；≥5 验收 |
| **C3** config UI + Radar 面板 | youtube_config 5 子段 UI 草图 + env_prefix=SOLAR_YOUTUBE_ + Tech Hotspot Radar 面板嵌入 (9 指标 + SLO 状态)；引 S02 D13 + R15；≥4 验收 |
| **C4** premium E2E plan | 端到端验证用例 (准备/触发/调用/验证/失败 5 阶段) + budget cap 20 USD 测试 + fallback faster-whisper 流程；**只写计划不真跑 OpenAI API**；引 S02 D10+OQ1；≥5 验收 |
| **C5** join | traceability.json 12 字段 (含 outcomes=4 / decisions_consumed=S02 D10-D13+OQ1 / downstream_sprint_kickoff_package S05); handoff 含 C1-C4 摘要 + S05 启动 checklist + 剩余风险 |

## 2. Stop Rules

- 缺 task_graph.json 不得派 builder
- 缺可复现验证不得标记 passed
- 发现 S03 接口偏离 S02 决议 → C5 记 OQ
- 不真改 Tech Hotspot Radar 源码 (本 sprint 是规约层)
- 不真跑 `solar-harness wiki tech-hotspot-radar` 命令
- 不真调 OpenAI API (C4 只写计划; 真跑留 S05)
- 不打印 API key / OAuth
- 不主动 close 父 epic
- 不假装 S03 已实现 (依赖等候明示)
- 不用乐观词

## 3. SLO

| 指标 | hard | soft |
|------|------|------|
| outcome 覆盖 (C1-C4) | < 4 → FAIL | n/a |
| C1 dashboard 指标数 | < 9 → FAIL | n/a |
| C2 命令数 | < 6 → FAIL | n/a |
| C4 验证用例阶段 | < 5 → FAIL | n/a |
| 任一节点含真跑命令 (shell exec / API call) | > 0 → 立即 FAIL | n/a |
| premium API key 在文档中明文出现 | > 0 → 立即 FAIL | n/a |

## 4. 失败恢复

- C1-C4 任一 FAIL: 单节点重派
- C5 FAIL: 诊断哪个 C 节点缺失/不一致，回写对应 C 节点重跑
- 若 S03 提前完成: C4 可升级到真跑 (但仍属 S05 范围, 不在本 sprint)
- 若 S03 偏离 S02 D11/D12/D13: C5 记 OQ 给协调器, 不擅自修 S02

## 5. 给下游接力 (S05 verification-release)

C5 traceability `downstream_sprint_kickoff_package.S05_verification_inputs`:
- C1-C4 全部规约文档
- 9 dashboard 指标验收测试用例
- CLI 6 命令 + legacy 兼容 E2E 测试
- premium E2E 真跑用例 (使用真 OpenAI API key + 20 USD budget)
- S03 完成后 S04 实施 builder 的 hand-off
