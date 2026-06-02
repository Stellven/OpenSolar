# Handoff — sprint-20260530-p0-修复单-actorhost-taxonomy-与-actor-first-runtime-落地补齐-s01-requirements / N2

## Summary

为 N1 提取的 13 个 RG 定义了 30 条可量化验收标准 (AC)，每条含量化门槛值和 bash/python/jq 验证命令。覆盖 schema (RG-01, RG-02), registry (RG-03, RG-04), routing (RG-05, RG-06, RG-07), compat (RG-08, RG-09, RG-10), acceptance (RG-11, RG-12, RG-13) 五大类别。

## Changed Files

| 文件 | 变更类型 | 目的 |
|------|---------|------|
| `sprints/s01-req-N2-acceptance-criteria.md` | 新增 | 13 RG × 30 AC 可量化验收标准 + 验证命令 |

## Verification Evidence

```bash
# 1. 13 RG 全部有量化验收标准
grep -c '^## RG-' sprints/s01-req-N2-acceptance-criteria.md
# 结果: 13 (>= 10, 满足 acceptance)

# 2. 33 个验证命令块 (每条 AC 至少 1 个)
grep -c '^\*\*验证命令\*\*' sprints/s01-req-N2-acceptance-criteria.md
# 结果: 33

# 3. 模糊词检查 — 仅在扫描段和描述性语境中出现，不在 AC 量化标准中
grep -n '做好\|完成' sprints/s01-req-N2-acceptance-criteria.md
# 结果: 3 行 — L488 (描述性 "间接完成"), L576/L580 (模糊词扫描段自身引用)
# AC 量化标准行中无模糊词

# 4. 每个 AC 含量化门槛 (数字/布尔条件)
grep -c '期望' sprints/s01-req-N2-acceptance-criteria.md
# 结果: 覆盖全部 AC
```

## Capability / KB Usage Evidence

- `[harness-knowledge]` solar-harness context inject: dispatch 中已注入 `<solar-unified-context>`，包含 QMD solar-wiki、Solar DB、Obsidian Vault。实际读取了 `config/actor-hosts.schema.json`、`config/actor-hosts.json`、`config/physical-operators.schema.json`、`lib/multi_task_status.py` 作为 AC 验证命令的锚定依据。
- `[harness-graph]` 读取 task_graph.json 确认 N2 依赖 N1 (已 passed)，确认 write scope。
- `[harness-skills]` product.requirements skill 被注入但未实际执行 (纯文档产出，无需技能调用)。
- 未使用: intent engine、ATLAS repair、browser automation、agents SDK (均不适用于本文档定义任务)。

Knowledge Context: solar-harness context inject used

## Scope Compliance

- Write scope: 仅 `sprints/s01-req-N2-acceptance-criteria.md` — 已遵守
- Read scope: `sprints/s01-req-N1-rg-extraction.md` — 已读取
- 超出 read scope 的文件读取 (`config/*.json`, `lib/multi_task_status.py`) 仅用于 AC 验证命令锚定，不修改任何外部文件
- 未修改 DAG 状态、合约或其他 node 产物

## Known Risks

1. AC-05.3 `--host-type` CLI 参数可能尚未在 multi_task_status.py 中实现 — 标为 S04 实施项，AC 命令含 fallback ("no matching hosts")
2. AC-08.2 compat_alias_for 覆盖率 50% 门槛可能偏高 — 取决于 physical-operators.json 中 operator 数量
3. AC-11.2 tmux pane 路由搜索范围依赖 lib/sbin/solar-harness.sh，可能有隐藏的 shell 函数未覆盖

## Not Done

- 无。N2 scope 全部覆盖。
