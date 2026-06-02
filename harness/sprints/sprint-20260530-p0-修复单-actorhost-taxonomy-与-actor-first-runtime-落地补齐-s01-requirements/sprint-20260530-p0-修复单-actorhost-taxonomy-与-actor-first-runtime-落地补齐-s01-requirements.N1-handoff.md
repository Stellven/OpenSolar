# Handoff — sprint-20260530-p0-修复单-actorhost-taxonomy-与-actor-first-runtime-落地补齐-s01-requirements / N1

## Summary

从 PRD 修复单（5 个问题 + 4 个修复范围 S1-S4）中提取 13 个需求组（RG），覆盖 schema、registry、routing、compat、acceptance 五个类别，映射到 S02-S05 四个下游 slice。S03 (core-runtime) 承接最多 RG (8 个)，为核心修改集中点。

## Changed Files

| 文件 | 操作 | 目的 |
|------|------|------|
| `sprints/s01-req-N1-rg-extraction.md` | 已存在/验证 | N1 主产出：13 RG 提取文档，含覆盖矩阵和文件影响清单 |

## Verification Evidence

### Acceptance 1: >= 10 个 RG 提取完成
- 结果: 13 个 RG (RG-01 到 RG-13)
- 验证: `grep -c "^### RG-" sprints/s01-req-N1-rg-extraction.md` = 13
- 状态: PASS

### Acceptance 2: 每个 RG 含类别（schema/registry/routing/compat/acceptance）
- 分布: schema (2), registry (2), routing (3), compat (3), acceptance (3)
- 验证: 每个 RG 条目第一个字段为 `**类别**: <category>`
- 状态: PASS

### Acceptance 3: 每个 RG 标注目标 slice（S02/S03/S04/S05）
- S02 (architecture): RG-01, RG-02, RG-04, RG-10 = 4 个
- S03 (core-runtime): RG-01, RG-02, RG-03, RG-04, RG-08, RG-09, RG-10 = 8 个 (最多)
- S04 (orchestration-ui): RG-05, RG-06, RG-07 = 3 个
- S05 (verification-release): RG-11, RG-12, RG-13 = 3 个
- 状态: PASS

### Acceptance 4: 覆盖修复单全部 5 个问题和 4 个修复范围
- P1 → RG-05, RG-06, RG-07, RG-11
- P2 → RG-06, RG-12
- P3 → RG-01, RG-02, RG-04, RG-13
- P4 → RG-03, RG-04, RG-13
- P5 → RG-08, RG-09, RG-10
- S1 → RG-01, RG-02, RG-03, RG-04
- S2 → RG-05, RG-06, RG-07
- S3 → RG-08, RG-09, RG-10
- S4 → RG-11, RG-12, RG-13
- 状态: PASS (5/5 问题 + 4/4 修复范围)

## Capability / KB Usage Evidence

- [harness-knowledge] solar-unified-context: dispatch 内嵌 context 已使用。命中 QMD solar-wiki + Solar DB + Obsidian Vault。Mirage 降级 (timeout)。
- [harness-graph] task_graph.json 已读取，确认 N1 无上游依赖，N2/N3 依赖 N1。
- [harness-contracts] contract.md 已读取，确认 D1-D6 定义。N1 覆盖 D1 (>= 8 RG → 实际 13 RG)。

## Scope Compliance

- Write scope: `sprints/s01-req-N1-rg-extraction.md` — 已存在，内容符合要求
- 未超出 write scope
- 未修改 write scope 外的文件

## Known Risks

- RG-04 实例 host 映射（`mini` → 哪个标准 host_type）需要 S02 架构决策
- `browser_profile_host` 在目标 8 类 taxonomy 中没有直接对应，需 S02 决定保留还是映射
- RG-08/RG-10 physical-operators 降级可能影响现有 dispatch 路径，需渐进式切换

## Not Done

- 无未完成项。N1 acceptance 全部 PASS。
