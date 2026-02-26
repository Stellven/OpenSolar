# Solar 铁律: Cortex First

> 设计/开发前必须先查 Cortex，基于证据决策

## 统一查询入口

```bash
# 日常查询
bun ~/.claude/core/cortex/unified-query.ts search "关键词" 10

# 证据链
bun ~/.claude/core/cortex/unified-query.ts evidence "关键词"

# 知识图谱
bun ~/.claude/core/cortex/unified-query.ts graph "关键词"
```

## 决策流程

```
需求到达 → unified-query search → 有证据? → 基于证据设计
                                    ↓ 无
                               调用 /insight 研究 → 写入 Cortex → 设计
```

## 证据质量要求

- credibility / confidence ≥ 0.7 才可信
- 无证据时必须调用 /insight 研究
- 决策必须标注证据来源 (citation_key)
