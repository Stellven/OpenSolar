# Handoff — sprint-20260530-p0-...-s01-requirements

Builder: 建设者化身 (Opus 4.6)
Round: 1
Sprint: `sprint-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa-s01-requirements`
DAG Nodes: N1 → N2 ∥ N3 → N4 → N5 (全部完成)

---

## 1. Operator Inventory (N1)

| # | 主线 | 文件 | 角色 | 存在性 | 行数 |
|---|------|------|------|--------|------|
| 1 | X/Social | `scripts/ai_influence_daily.py` | PRIMARY | ✅ | 1783 |
| 2 | X/Social | `tools/playwright_twitter_scraper.py` | EXECUTOR | ✅ | 78 |
| 3 | GitHub | `scripts/github_trends_pipeline.py` | PRIMARY | ✅ | 346 |
| 4 | GitHub | `config/github_intelligence_config.yaml` | CONTROL | ✅ | 163 |
| 5 | HF | `scripts/tech_hotspot_radar.py` | PRIMARY | ✅ | 12812 |
| 6 | HF | `scripts/run_tech_hotspot_radar.sh` | HELPER | ✅ | 9 |
| 7 | Gemini | `tools/gemini_deep_research_operator.py` | PRIMARY | ✅ | 305 |
| 8 | Gemini | `scripts/browser_agent_gemini_deep_research_wrapper.py` | EXECUTOR | ✅ | 621 |
| 9 | YouTube | `scripts/youtube_influence_digest.py` | PRIMARY | ✅ | 1448 |
| 10 | YouTube | `scripts/browser_agent_youtube_transcript_wrapper.py` | EXECUTOR | ✅ | 749 |

角色分布: 5 PRIMARY / 3 EXECUTOR / 1 HELPER / 1 CONTROL

---

## 2. Requirement Groups (N2)

| RG | 名称 | 优先级 | 验收标准数 |
|----|------|--------|-----------|
| RG1 | Operator Registration & Default Entry Points | P0 | 3 |
| RG2 | Responsibility Boundaries | P0 | 3 |
| RG3 | Primary/Fallback Configuration Schema | P0 | 3 |
| RG4 | Unified Output Schema | P0 | 3 |
| RG5 | Status Page Integration (/ai-influence 6 区块) | P1 | 3 |
| RG6 | GitHub Dual-Run (新旧对照) | P1 | 3 |
| RG7 | No-Duplicate / Single-Host Constraint | P0 | 3 |
| RG8 | Smoke Testing & Regression | P2 | 3 |
| RG9 | Operator Lifecycle Management | P2 | 2 |

**总计**: 9 个 RG (5 P0 / 2 P1 / 2 P2)，每个有 2-3 条可量化验收标准和风险缓解措施。

---

## 3. 验收矩阵 (精简)

每个 RG 的关键验收指标:

| RG | 核心量化指标 |
|----|------------|
| RG1 | 配置中恰好 5 个 `role: primary`，0 重复 |
| RG2 | EXECUTOR 无 `generate_report()` 等最终输出逻辑 |
| RG3 | YAML/JSON 中 5 条主线各有 primary + fallback 字段 |
| RG4 | 每个 PRIMARY 输出含 report/raw/metadata/log 四层 |
| RG5 | 页面 DOM 恰好 6 个 section/card |
| RG6 | 新旧各自产出独立日报，日志互不干扰 |
| RG7 | 全部算子在 `Solar/harness/` 内，无外部宿主 |
| RG8 | 5 个 smoke test 脚本存在且全 PASS |
| RG9 | 配置有 `retirement_policy` 字段 |

---

## 4. 非目标 (N3)

| # | 非目标 |
|---|--------|
| NG1 | 不重写现有算子内部逻辑 |
| NG2 | 不引入第二执行宿主 |
| NG3 | 不为 EXECUTOR 添加独立最终报告能力 |
| NG4 | 不在本 epic 内完成 github_intelligence 退役 |
| NG5 | 不统一算子内部技术栈 |
| NG6 | 不新增算子/主线 |
| NG7 | 不用单个大 PRD 覆盖所有实现细节 |

---

## 5. 约束矩阵

| 约束 | 关键规则 |
|------|---------|
| C1 唯一宿主 | 所有算子在 solar-harness 内运行 |
| C2 禁止重复入口 | 每主线 1 个 PRIMARY (GitHub CONTROL 例外) |
| C3 Fallback 规则 | fallback 不覆写 primary 产物 |
| C4 产物口径 | report + raw + metadata + log 四层 |

GitHub 旧版对照: 7-30 天，退役条件为新版覆盖度 >= 旧版 90%。

---

## 6. Traceability Map (N4)

| RG | S02 | S03 | S04 | S05 |
|----|:---:|:---:|:---:|:---:|
| RG1 | **主** | | | |
| RG2 | **主** | 辅 | | |
| RG3 | **主** | 辅 | | |
| RG4 | | **主** | | |
| RG5 | | | **主** | |
| RG6 | | **主** | 辅 | |
| RG7 | **主** | | | |
| RG8 | | | | **主** |
| RG9 | 辅 | **主** | | |

**覆盖率**: 9/9 = 100%

### 跨切片依赖 (5 个)

| ID | 方向 | 说明 |
|----|------|------|
| DEP-1 | S02 → S03 | RG1 operator registry → RG4 output schema |
| DEP-2 | S02 → S04 | RG3 primary/fallback config → RG5 status page |
| DEP-3 | S02 → S03 | RG2 role boundaries → RG4 output guard |
| DEP-4 | S03+S04 → S05 | RG6 dual-run + RG5 page → RG8 smoke test |
| DEP-5 | S03 → S04 | RG4 metadata format → RG5 page data layer |

---

## 7. 不能直接派 Builder 的工作

以下必须先经 S02 architecture:
- Operator registry schema 设计
- Primary/fallback routing 逻辑
- Unified output schema 定义
- /ai-influence 页面架构
- GitHub 双跑调度机制

---

## 8. 未闭环项 (Open Questions)

| # | 问题 | 状态 | 负责切片 |
|---|------|------|----------|
| OQ1 | github_intelligence 旧版的具体运行入口和调度方式待确认 | open | S02 |
| OQ2 | /ai-influence 页面现有实现的技术栈和状态未知 | open | S04 |
| OQ3 | 各算子现有产物格式的差异度待量化 | open | S03 |
| OQ4 | GitHub 新旧对照的比较维度 (哪些指标) 未定义 | open | S03 |
| OQ5 | 部分算子 smoke test 需要外部 API (Twitter/Gemini)，dry-run 策略待定 | open | S05 |

---

## Done 定义达成

| D# | 要求 | 状态 | 证据 |
|----|------|------|------|
| D1 | 5 条主线 + 4 条执行器/辅助 (共 9 个文件) operator inventory 表完成 | ✅ | N1-handoff.md: 10 条目 (含 github_intelligence config)，全部标注角色和主线 |
| D2 | >= 8 个 requirement groups 从 PRD 6 大目标提取并编号 | ✅ | N2-handoff.md: 9 个 RG (RG1-RG9)，5 P0 / 2 P1 / 2 P2 |
| D3 | 每个 RG 有 >= 2 条可量化验收标准和风险边界 | ✅ | N2-handoff.md: 每个 RG 有 2-3 条 AC + 风险等级 + 缓解措施 |
| D4 | 非目标清单 >= 5 条 | ✅ | N3-handoff.md: 7 条 (NG1-NG7)，覆盖 PRD §6 和反模式 |
| D5 | Traceability map 将所有 RG 映射到 S02-S05 | ✅ | N4-handoff.md: 9/9 RG 映射，100% 覆盖率，5 个跨切片依赖 |
| D6 | handoff.md 包含全部 6 个板块 | ✅ | 本文件: inventory + RG + 验收矩阵 + 非目标 + traceability + 未闭环项 |

---

## 验证方法

1. **Operator Inventory**: 在终端执行 `ls -la` 验证 10 个文件的存在性和行数
2. **RG 数量**: 计数 N2-handoff.md 中的 RG 编号 (9 个)
3. **验收标准量化**: 检查每个 RG 的 AC 表格，确认有量化指标
4. **非目标数量**: 计数 N3-handoff.md 中的 NG 编号 (7 个)
5. **Traceability 覆盖率**: 验证映射矩阵中每个 RG 至少有一个 **主** 标记
6. **跨切片依赖**: 计数 DEP 编号 (5 个, >= 3)

## 变更文件

| 文件 | 变更 |
|------|------|
| `.N1-handoff.md` | 新建 — operator inventory 表 |
| `.N2-handoff.md` | 新建 — 9 个 requirement groups |
| `.N3-handoff.md` | 新建 — 7 非目标 + 4 约束 + 退役条件 |
| `.N4-handoff.md` | 新建 — traceability map + 5 跨切片依赖 |
| `.handoff.md` | 新建 — 本文件，汇总全部 N1-N4 |

---

## 备注

- `solar-harness context inject` 在当前环境不可用 (command not found)，使用 direct file reads 作为降级路径
- 本切片为纯文档/分析产出，无代码变更
- S02 architecture 是下一个激活切片，所有代码变更需等 S02 完成后才可开始

Knowledge Context: solar-harness context inject failed (command not found), used direct file reads as fallback.
Harness Modules Used: harness-knowledge (degraded/direct-reads), harness-graph (task_graph.json read)
