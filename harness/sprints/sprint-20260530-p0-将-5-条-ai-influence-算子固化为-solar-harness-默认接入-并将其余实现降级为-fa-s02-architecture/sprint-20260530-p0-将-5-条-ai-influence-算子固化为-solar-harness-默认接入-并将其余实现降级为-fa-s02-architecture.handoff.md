# Handoff — AI Influence 算子固化: 架构设计与接口契约

Builder: 建设者化身 (Opus 4.6)
Round: 1
Sprint: `sprint-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa-s02-architecture`
DAG Nodes: N1 → {N2 ∥ N3} → {N4 ∥ N5} → N6 (全部完成)

---

## 一、3 层架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Presentation Layer                              │
│                                                                         │
│  /ai-influence 状态页                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ ┌──────┐│
│  │X / Social│ │GitHub New│ │GH Legacy │ │HF Papers │ │YouTube│ │Gemini││
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └──┬───┘ └──┬───┘│
│       │         ┌───┴───────────┘             │          │        │    │
│       │         │ side-by-side diff           │          │        │    │
│       ▼         ▼                             ▼          ▼        ▼    │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │          status.json (6 StatusCard + DualRunView)                 │ │
│  └──────────────────────────────┬───────────────────────────────────┘ │
└─────────────────────────────────┼───────────────────────────────────────┘
                                  │ 消费 metadata.json
┌─────────────────────────────────┼───────────────────────────────────────┐
│                         Control Layer                                   │
│                                                                         │
│  ┌────────────────────┐  ┌───────────────────────┐                      │
│  │operator_registry   │  │  Router / Dispatcher   │                      │
│  │.json               │──│  R1: primary-first     │                      │
│  │                    │  │  R2: fallback-on-fail   │                      │
│  │ 6 lines            │  │  R3: executor-internal  │                      │
│  │ 10 operators       │  │  R5: dual-run-parallel  │                      │
│  │ 5 routing rules    │  │  R6: no-dup-report      │                      │
│  └────────────────────┘  └───────────┬───────────┘                      │
│                                      │ dispatch                          │
│  Role Enforcement:                   │                                   │
│  E1: executor ≠ generate_report()   │                                   │
│  E2: produces_final_report ⊆ primary|fallback                           │
│  E3: 1 report per line (dual-run 例外)                                   │
└──────────────────────────────────────┼──────────────────────────────────┘
                                       │
┌──────────────────────────────────────┼──────────────────────────────────┐
│                         Data Layer                                      │
│                                                                         │
│  PRIMARY Operators:                  ▼                                   │
│  ┌───────────────┐ ┌──────────────┐ ┌──────────────┐                    │
│  │ai_influence   │ │github_trends │ │tech_hotspot  │                    │
│  │_daily.py      │ │_pipeline.py  │ │_radar.py     │                    │
│  │(X/Social)     │ │(GH New)      │ │(HF Papers)   │                    │
│  └───────┬───────┘ └──────────────┘ └──────────────┘                    │
│          │                                                               │
│  ┌───────────────┐ ┌──────────────┐                                     │
│  │gemini_deep_   │ │youtube_      │                                     │
│  │research_op.py │ │influence_    │                                     │
│  │(Gemini DR)    │ │digest.py     │                                     │
│  └───────┬───────┘ └──────┬───────┘                                     │
│          │                │                                              │
│  EXECUTOR Layer (internal):                                              │
│  ┌───────────────┐ ┌──────────────┐ ┌──────────────┐                    │
│  │playwright_    │ │browser_agent │ │browser_agent │                    │
│  │twitter_       │ │_gemini_dr_   │ │_youtube_     │                    │
│  │scraper.py     │ │wrapper.py    │ │transcript_   │                    │
│  │               │ │              │ │wrapper.py    │                    │
│  └───────────────┘ └──────────────┘ └──────────────┘                    │
│                                                                         │
│  Unified Output: {line_id}/{date}/{run_id}/                              │
│  ├── report.md  ├── raw/  ├── metadata.json  └── diagnostic.log         │
│                                                                         │
│  Shared Libs: operator_flow_control, browser_job_runtime                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 二、Operator Registry Schema (N2)

**格式**: `operator_registry.json` (JSON, schema version `solar-harness/operator-registry/v1`)

### 核心设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| Registry 格式 | JSON (非 YAML) | 可被 Python/JS 直接解析, 支持 JSON Schema 验证 |
| Line 粒度 | 6 lines (5 主线 + 1 Legacy 对照) | GitHub Legacy 独立 line 便于对照视图和退役管理 |
| 角色枚举 | primary / executor / fallback / control / helper | 覆盖所有 9 个 operator 的实际角色 |
| 路由策略 | primary-first, fallback-on-failure, executor-internal-only | 简洁、可预测、符合 PRD 要求 |
| dual-run | 仅 GitHub 支持, 其余主线不支持 | PRD 明确只有 GitHub 需要新旧对照 |

### Operator 角色映射

| operator_id | line | role | produces_final_report |
|---|---|---|---|
| ai-influence-daily | x-social | primary | ✅ |
| playwright-twitter-scraper | x-social | executor | ❌ |
| github-trends-pipeline | github-new | primary | ✅ |
| github-intelligence-legacy | github-legacy | primary (retiring) | ✅ |
| tech-hotspot-radar-hf | hf-papers | primary | ✅ |
| run-tech-hotspot-radar-sh | hf-papers | helper | ❌ |
| gemini-deep-research-operator | gemini-dr | primary | ✅ |
| browser-agent-gemini-dr-wrapper | gemini-dr | executor | ❌ |
| youtube-influence-digest | youtube | primary | ✅ |
| browser-agent-youtube-transcript-wrapper | youtube | executor | ❌ |

完整 JSON Schema 见 `N2-handoff.md`.

---

## 三、Unified Output Schema (N3)

### 4 类产物

| 产物 | 文件 | 必需 | 消费方 |
|---|---|---|---|
| report | `report.md` / `digest.md` | ✅ | 人类读者, 状态页 |
| raw | `raw/` 目录 | ✅ | 下游分析, debug |
| metadata | `metadata.json` | ✅ | 状态页 StatusCard |
| diagnostic | `diagnostic.log` | ⚠️ 建议 | 运维 debug |

### metadata.json 最小公共字段

```
line, operator, role, run_id, status, started_at, completed_at,
duration_seconds, stats{items_collected, items_processed, items_in_report,
failures, api_calls, tokens_used}, artifacts{report, raw_dir, diagnostic},
errors[{stage, message, severity}], upstream_runs[], environment{}
```

### 适配策略

- **Wrapper 模式**: 每个 PRIMARY 的 `main()` 末尾调用 `emit_metadata()` 写入 `metadata.json`
- **目录重组**: 通过符号链接将现有产物路径映射到标准目录结构
- **改动量评估**: Gemini DR 最低 (已有 report.md), HF Papers 最高 (SQLite → metadata 导出)

完整 JSON Schema 和适配矩阵见 `N3-handoff.md`.

---

## 四、状态页数据模型 (N4)

### 6 Card 数据模型

每个 StatusCard 包含: `run_status`, `last_run`, `stats`, `artifacts`, `errors`, `trend`

| Card | line_id | 特殊字段 |
|---|---|---|
| X / Social | x-social | handles_scanned, gmail_status |
| GitHub New | github-new | repos_discovered, sudden_hot_count |
| GitHub Legacy | github-legacy | repos_tracked, retirement_status |
| HF Papers | hf-papers | papers_collected, trending_count |
| YouTube | youtube | channels_scanned, transcripts_ok, asr_queued |
| Gemini DR | gemini-dr | citations_count, conversation_id |

### GitHub New/Legacy 对照视图

- `GitHubDualRunView` 接口: side-by-side display + 覆盖率 Venn 图 + 退役进度条
- 对照指标: `coverage_overlap`, `new_exclusive`, `legacy_exclusive`, `quality_comparison`
- 交互: 点击 Card → 展开报告, 对比按钮 → diff 视图, 退役条件悬停提示

完整 TypeScript 接口和 API 格式见 `N4-handoff.md`.

---

## 五、兼容策略与迁移方案 (N5)

### GitHub Legacy 退役

- **对照期**: 14 天 (Day 1-14 双跑, Day 14 评估, Day 14+ 退役)
- **退役条件**: 新版覆盖度 ≥ 90% + 连续 7 天成功 + 报告质量 ≥ 80% + 人工确认
- **退役后**: 代码保留 30 天, registry `status: retired`, 历史数据永久保留

### Executor 内化

- 3 个 EXECUTOR 保持 subprocess 调用关系不变, 不修改代码
- 仅通过 registry `role: executor` 标记禁止直接调度
- 不再暴露为独立接入点

### 回滚策略

6 步分阶段回滚, 每步可独立回退:
1. registry 文件 → 删除, 回退硬编码
2. metadata 写入 → 注释掉 emit 调用
3. 目录重组 → 删除符号链接
4. 状态页数据源 → 回退直接扫描
5. dual-run → 禁用标志
6. legacy 退役 → 恢复 active 状态

### Breaking Changes

**0 个直接 breaking change**. 3 个潜在低/中风险项已有缓解措施.

完整清单见 `N5-handoff.md`.

---

## 六、S03/S04 下游接口需求

### S03 (core-runtime) 需要实现

| 需求 | 来源 | 说明 |
|---|---|---|
| 各 operator 添加 `emit_metadata()` | N3 | 每个 PRIMARY 写入 `metadata.json` |
| 产物目录标准化 | N3 | 符号链接或路径重组到标准结构 |
| `operator_registry.json` 文件创建 | N2 | 具体 JSON 实例化 |
| GitHub dual-run 调度逻辑 | N2, N5 | 新旧并行运行、独立产物 |
| `github_trends_pipeline.py` CLI 化 | N1 | 添加 argparse 接口 (当前是纯 `__main__`) |

### S04 (orchestration-ui) 需要实现

| 需求 | 来源 | 说明 |
|---|---|---|
| 状态页 6 card 渲染 | N4 | 消费 `metadata.json` 的 `StatusCard` |
| GitHub 对照视图 | N4 | `GitHubDualRunView` side-by-side |
| Dispatcher 集成 registry | N2 | 从 `operator_registry.json` 读取路由规则 |
| 退役进度监控 | N5 | 退役条件实时检查和展示 |

---

## 七、Open Questions (待 S03/S04 解决)

| # | 问题 | 责任切片 | 风险 |
|---|---|---|---|
| OQ-1 | `tech_hotspot_radar.py` 的 HF 子命令 vs 整体: 是否需要拆分独立模块? | S03 | 中 — 12812 行单体, 但 NG1 禁止重写内部逻辑 |
| OQ-2 | 状态页技术栈 (静态 HTML / Vue / React)? | S04 | 低 — 不影响数据模型 |
| OQ-3 | 各 operator 的 `emit_metadata()` 是否提取为公共 lib 函数? | S03 | 低 — 推荐提取到 `lib/metadata_emitter.py` |
| OQ-4 | GitHub legacy 的具体调度入口 (`collect-github` 子命令的完整调用链)? | S03 | 低 |

---

## Done 定义达成

| D# | 要求 | 状态 | 证据 |
|----|------|------|------|
| D1 | 9 个 operator 文件的现状审计表完成 | ✅ | N1-handoff.md: 9 文件 + 1 配置, 每个含路径/存在性/角色/接口签名/输出格式/依赖 |
| D2 | 系统分层设计覆盖 control plane 和 data plane | ✅ | 3 层架构图 (Presentation + Control + Data), N2 registry + routing |
| D3 | Primary/Fallback/Executor 配置 schema 定义完成 | ✅ | N2: operator_registry.json schema 含 5 种角色, 6 条路由规则, 5 条 enforcement |
| D4 | 统一输出 schema 定义完成 | ✅ | N3: 4 类产物 + metadata.json JSON Schema + 5 条主线适配方案 |
| D5 | /ai-influence 状态页数据模型设计完成 | ✅ | N4: 6 StatusCard + GitHubDualRunView + API 响应格式 |
| D6 | 兼容策略和迁移方案文档化 | ✅ | N5: 14 天对照期 + 4 退役条件 + 6 步回滚 + 0 breaking changes |
| D7 | handoff.md 写明设计决策、接口边界、下游影响 | ✅ | 本文件: 3 层架构 + registry + output schema + 状态页 + 迁移方案 + S03/S04 接口需求 + open questions |

---

## 变更文件

| 文件 | 操作 | 说明 |
|---|---|---|
| `.N1-handoff.md` | 新建 | 9 个 operator 现状审计表 + 依赖关系图 |
| `.N2-handoff.md` | 新建 | Control Plane: registry schema + routing + role enforcement |
| `.N3-handoff.md` | 新建 | Data Plane: 4 类产物格式 + metadata.json 公共 schema + 适配方案 |
| `.N4-handoff.md` | 新建 | Presentation: 6 StatusCard 数据模型 + GitHub 对照视图 |
| `.N5-handoff.md` | 新建 | 兼容策略: GitHub 退役 + Executor 内化 + 回滚 + breaking changes |
| `.handoff.md` | 新建 | 本文件 — 最终架构 handoff 汇总 |

---

## 验证方法

1. **Registry Schema**: 用 `python3 -c "import json; json.load(open('...'))"` 验证 JSON 可解析
2. **metadata.json Schema**: 用 JSON Schema 验证工具 (`jsonschema`) 验证示例符合 schema
3. **6 Card 数据模型**: 检查 N4-handoff.md 中 6 个 card 定义, 每个含 run_status/last_run/artifacts/stats/errors
4. **退役条件**: 检查 N5-handoff.md 中 4 条 RC 均有量化标准
5. **回滚策略**: 检查 N5-handoff.md 中 6 步回滚, 每步有回滚方法
6. **Breaking Changes**: 检查 N5-handoff.md 中 0 个直接 breaking change

---

## 备注

- 本切片为纯架构设计产出, 无代码变更
- S03 (core-runtime) 和 S04 (orchestration-ui) 是下游实现切片
- `tech_hotspot_radar.py` 的单体问题 (586KB, 12812 行) 是已知技术债, 但 NG1 禁止在本 epic 内重写
- GitHub Legacy 退役需人工审批, 不会自动执行

Knowledge Context: solar-harness context inject used (via dispatch-injected STATE.md preflight + direct file reads)
Harness Modules Used: harness-knowledge (direct file reads ✅), harness-graph (dag.validate, graph-scheduler mark ×5 ✅), Solar-Harness Runtime (STATE preflight ✅), Superpowers (workflow.planning, architecture ✅)
