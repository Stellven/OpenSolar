# Solar 铁律: 数据反馈闭环

> **来源**: 2026-02-05 监护人亲授
> **核心**: 反馈信号必须写回系统，形成闭环，才能增强模型参数

## 铁律定义

```
┌─────────────────────────────────────────────────────────────────┐
│                    FEEDBACK LOOP PROTOCOL                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   提取反馈 ≠ 完成                                               │
│   提取 + 写回 + 应用 + 影响行为 = 真正的闭环                    │
│                                                                 │
│   监护人原话:                                                   │
│   "你分析提取了我的反馈信号，但这些信号有没有刷新到轨迹数据中？ │
│    索引中？要反馈才是闭环啊"                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 反馈信号的深层含义

| 用户说 | 深层含义 | 样本类型 | 行动 |
|--------|----------|----------|------|
| "好/可以/OK" | 满意，回复质量高 | 正样本 | 加入收藏 |
| "继续/嗯/懂了" | 方向正确 | 正样本 | 无 |
| "补充/还有" | 思考不错但不完整 | 中性 | 学习教训 |
| "你没想到/漏了" | 思考不够充分 | 负样本 | 学习教训 |
| "应该是/其实是" | 有错误需要纠正 | 负样本 | 学习纠正 |
| "不对/错了/重来" | 质量差 | 负样本 | 记录失败 |

## 闭环数据流

```
用户反馈
    │
    ▼
feedback-enricher.ts (提取 + 分类)
    │
    ├──▶ sys_training_samples (训练数据)
    │
    ├──▶ evo_feedback_v2 (反馈信号)
    │
    ├──▶ evo_memory_semantic (教训经验)
    │
    └──▶ sys_favorites (高质量输出)
           │
           ▼
    feedback-applier.ts (应用)
           │
           ├──▶ evo_memory_procedural (熟练度)
           │
           ├──▶ sys_quality_scores (质量评分)
           │
           └──▶ sys_routing_* (路由权重)
                  │
                  ▼
           Intent Engine (影响决策)
                  │
                  ▼
           执行 & 输出 (影响行为)
                  │
                  ▼
           新的用户反馈 ← 闭环完成
```

## 强制执行

### 定期运行

```bash
# 建议每日或每周运行一次完整闭环
bun ~/.claude/core/intent-engine/feedback-enricher.ts 100
bun ~/.claude/core/intent-engine/feedback-applier.ts all
```

### 验证闭环

```bash
# 检查数据是否已写入
sqlite3 ~/.solar/solar.db "
SELECT 'training_samples' as tbl, COUNT(*) as cnt FROM sys_training_samples
UNION ALL
SELECT 'feedback_v2', COUNT(*) FROM evo_feedback_v2
UNION ALL
SELECT 'procedural', COUNT(*) FROM evo_memory_procedural
UNION ALL
SELECT 'quality_scores', COUNT(*) FROM sys_quality_scores;
"
```

## 数据用途

| 数据 | 用途 |
|------|------|
| 正样本 | 模型微调强化、参考模板 |
| 负样本 | 避免重复错误、失败模式分析 |
| 教训经验 | Intent Engine 决策参考 |
| 熟练度 | 调整执行置信度 |
| 质量评分 | 模型/Agent 升降级建议 |

## 禁止行为

- ❌ 只提取不写回
- ❌ 只写回不应用
- ❌ 只应用不验证
- ❌ 忽视负样本（负样本更有价值）

## 检查清单

每次处理反馈后：

- [ ] 是否写入了 sys_training_samples？
- [ ] 是否写入了 evo_feedback_v2？
- [ ] 教训是否写入了 evo_memory_semantic？
- [ ] 熟练度是否更新了 evo_memory_procedural？
- [ ] Intent Engine 能否查询到新数据？

## 铁律总结

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   🔄 数据反馈闭环铁律                                           │
│                                                                 │
│   1. 反馈必须写回多个目标 (MUST)                                │
│   2. 写回后必须应用到系统 (MUST)                                │
│   3. 应用后必须影响决策 (MUST)                                  │
│   4. 负样本比正样本更有学习价值 (IMPORTANT)                     │
│                                                                 │
│   提取 → 写回 → 应用 → 决策 → 行为 → 新反馈 (完整闭环)          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 架构文档

完整架构设计见: `~/.claude/core/intent-engine/ARCHITECTURE.md`

---

*Feedback Loop Rule v1.0*
*建立于: 2026-02-05*
*监护人指示: 要反馈才是闭环啊*
