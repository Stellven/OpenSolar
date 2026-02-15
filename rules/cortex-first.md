# Solar 铁律: Cortex First (中枢神经优先)

> **来源: 2026-02-13 监护人亲授**
> **核心: 设计/开发前必须先查Cortex，基于证据决策**

## 铁律定义

```
┌─────────────────────────────────────────────────────────────────┐
│                    CORTEX FIRST PROTOCOL                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   任何设计方案/开发任务开始前，必须:                            │
│                                                                 │
│   1. 先查Cortex中枢神经                                         │
│   2. 查已有方案/结论/评估                                       │
│   3. 基于证据决策                                               │
│   4. 无证据才调用/Insight研究                                   │
│                                                                 │
│   ❌ 禁止: 凭主观经验直接设计                                   │
│   ❌ 禁止: 跳过Cortex查询                                       │
│   ✅ 必须: 证据驱动决策                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 强制检查清单

设计方案/开发前，必须执行：

```bash
# 1. 查已有方案
bun cortex.ts query "SELECT * FROM cortex_sources WHERE title LIKE '%关键词%'"

# 2. 查已有结论
bun cortex.ts query "SELECT * FROM cortex_claims WHERE claim_text LIKE '%关键词%'"

# 3. 查历史评估
bun cortex.ts query "SELECT * FROM cortex_evals WHERE task_id IN (
  SELECT task_id FROM cortex_tasks WHERE topic LIKE '%关键词%'
)"

# 4. 查完整产出
bun cortex.ts task <task_id>
```

## 决策流程

```
User需求: "设计XXX系统"
       │
       ▼
┌─────────────────┐
│ 查Cortex        │ ← 必须先查
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
[有证据]   [无证据]
    │         │
    ▼         ▼
基于证据   调用/Insight
设计方案   研究
    │         │
    │         ▼
    │    Insight产出
    │    写入Cortex
    │         │
    └────┬────┘
         ▼
    设计方案
         │
         ▼
     实现
```

## 证据类型

| 证据类型 | 表 | 说明 |
|---------|-----|------|
| 参考资料 | cortex_sources | 论文/文章/先验知识 |
| 结论论点 | cortex_claims | 已验证的结论 |
| 评估结果 | cortex_evals | 专家互评 |
| 设计方案 | cortex_artifacts | 完整产出 |

## 查询模板

### 查某主题的所有证据

```sql
SELECT
  s.citation_key,
  s.title,
  s.finding,
  s.credibility
FROM cortex_sources s
JOIN cortex_tasks t ON s.task_id = t.task_id
WHERE t.topic LIKE '%记忆系统%'
ORDER BY s.credibility DESC;
```

### 查某主题的结论

```sql
SELECT
  c.claim_text,
  c.supporting_sources,
  c.confidence
FROM cortex_claims c
JOIN cortex_tasks t ON c.task_id = t.task_id
WHERE t.topic LIKE '%记忆系统%'
ORDER BY c.confidence DESC;
```

### 查某主题的评估

```sql
SELECT
  e.reviewer_model,
  e.score,
  e.verdict,
  e.suggestions
FROM cortex_evals e
JOIN cortex_tasks t ON e.task_id = t.task_id
WHERE t.topic LIKE '%记忆系统%'
ORDER BY e.score DESC;
```

## 人类先验路由

**我的主观经验/观点不直接注入prompt，而是先存入Cortex：**

```typescript
// 不要这样做
const prompt = `设计记忆系统。我认为应该用三层架构...`;

// 而是这样做
await saveSolarPrior('记忆系统架构', '三层架构：Episodic/Semantic/Procedural');

// 然后显式引用
const prompt = `设计记忆系统。参考: solar_prior_memory_arch`;
```

## 违反检测

当我的输出包含以下模式时，说明违反了铁律：

- "我认为..."（主观判断）
- "根据我的经验..."（未查Cortex）
- "通常做法是..."（未验证）
- 直接给出设计方案（未查证据）

**正确模式：**

- "根据Cortex中的XXX证据..."
- "查询cortex_sources后发现..."
- "/Insight研究后得出结论..."
- "基于cortex_evals评分..."

## 自检问题

开始设计/开发前，问自己：

- [ ] 我查Cortex了吗？
- [ ] 有相关证据吗？
- [ ] 证据质量如何（credibility/confidence/score）？
- [ ] 无证据时，我调用/Insight了吗？
- [ ] /Insight产出写入Cortex了吗？
- [ ] 我的决策基于证据还是主观？

## 与其他规则的关系

- **Data First**: 先查数据资产
- **Cortex First**: 先查中枢神经（数据资产的一部分）
- **REE First**: 先查可执行资源
- **Research First**: 研究业界实践

**优先级**: Cortex First > Data First > REE First > Research First

## 铁律总结

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   🧠 Cortex First 铁律                                          │
│                                                                 │
│   1. 设计/开发前先查Cortex (MUST)                               │
│   2. 基于证据决策 (MUST)                                        │
│   3. 无证据调用/Insight (MUST)                                  │
│   4. 主观经验先入库再引用 (MUST)                                │
│                                                                 │
│   证据驱动 > 主观判断                                           │
│   Cortex = 唯一真相源                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

*Cortex First Protocol v1.0*
*建立于: 2026-02-13*
*监护人指示: 第一时间查中枢神经和知识库*
