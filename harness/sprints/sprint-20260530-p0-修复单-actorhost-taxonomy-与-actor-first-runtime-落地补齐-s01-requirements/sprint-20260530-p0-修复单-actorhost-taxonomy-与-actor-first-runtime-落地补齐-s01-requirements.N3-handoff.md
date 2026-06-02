# Handoff — sprint-20260530-p0-修复单-actorhost-taxonomy-与-actor-first-runtime-落地补齐-s01-requirements / N3

## Summary

定义了 7 条非目标边界（OOB-01 至 OOB-07），明确本次 epic 不做的事项及原因。编写了 8 条风险（R1 至 R8），覆盖高/中/低三个等级，每条含触发条件和缓解措施。风险覆盖 S1-S4 全部修复范围，并与 N1 的 13 RG 建立映射关系。

## Changed Files

| 文件 | 变更类型 | 目的 |
|------|---------|------|
| `sprints/s01-req-N3-boundaries-risks.md` | 新增 | 非目标边界清单 (7 条) + 风险矩阵 (8 条) |

## Verification Evidence

```bash
# 1. 非目标条目 >= 5
grep -c 'OOB-' sprints/s01-req-N3-boundaries-risks.md
# 结果: 14 (7 个条目 x 标题+引用，>= 5)

# 2. 风险条目 >= 5
grep -c '^| R[0-9]' sprints/s01-req-N3-boundaries-risks.md
# 结果: 8 (>= 5)

# 3. 覆盖 host_type enum 变更
grep 'R1.*enum' sprints/s01-req-N3-boundaries-risks.md
# 结果: 命中

# 4. 覆盖 physical-operators 降级
grep 'R2.*physical-operators' sprints/s01-req-N3-boundaries-risks.md
# 结果: 命中

# 5. 覆盖双轨过渡
grep 'R3.*双轨' sprints/s01-req-N3-boundaries-risks.md
# 结果: 命中
```

## Capability / KB Usage Evidence

- `[harness-knowledge]` solar-harness context inject: dispatch 中注入 `<solar-unified-context>`（QMD solar-wiki, Solar DB, Obsidian Vault）
- `[harness-graph]` 读取 task_graph.json 确认 N3 依赖 N1 (已 passed)，确认 write scope
- 读取 N1 产物 `s01-req-N1-rg-extraction.md` 作为边界和风险分析的输入
- 未使用: intent engine, ATLAS repair, browser automation, agents SDK (均不适用)

Knowledge Context: solar-harness context inject used

## Scope Compliance

- Write scope: 仅 `sprints/s01-req-N3-boundaries-risks.md` — 已遵守
- Read scope: `sprints/s01-req-N1-rg-extraction.md` — 已读取
- 未修改 DAG 状态、合约或其他 node 产物

## Known Risks

1. **R1 高风险**: host_type enum 变更导致现有代码断裂 — 缓解措施需在 S02 设计阶段执行全文搜索
2. **R2 高风险**: physical-operators 降级后旧代码路径仍读取它 — 需在 S03 实施时确保读取优先级切换
3. **R5 低风险**: 远程 host (ssh_devbox/codex_cloud) stub 缺少实际验证 — 推迟到后续 epic

## Not Done

- 无。N3 scope 全部覆盖。
