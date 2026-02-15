# Solar 铁律: Cortex First (中枢神经优先)

> **来源: 2026-02-13 监护人亲授**
> **核心: 设计/开发前必须先查Cortex，基于证据决策**
> **更新: 2026-02-15 统一查询入口**

## 铁律定义

```
┌─────────────────────────────────────────────────────────────────┐
│                    CORTEX FIRST PROTOCOL v3.0                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   任何设计方案/开发任务开始前，必须:                            │
│                                                                 │
│   1. 先查统一入口 Unified Query                                 │
│   2. 查已有方案/结论/评估/知识图谱                              │
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

设计方案/开发前，**第一步**执行：

```bash
# 统一查询入口 (同时查 Cortex + Knowledge)
bun ~/.claude/core/cortex/unified-query.ts search "关键词" 10
```

**场景化命令：**

| 场景 | 命令 |
|------|------|
| 日常查询 | `bun unified-query.ts search "xxx" 10` |
| 需要证据链 | `bun unified-query.ts evidence "xxx"` |
| 查知识图谱 | `bun unified-query.ts graph "xxx"` |
| 查看统计 | `bun unified-query.ts stats` |

## 统一查询架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Unified Query 统一入口                        │
│                                                                 │
│   bun unified-query.ts search "memory" 10                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────┐    ┌─────────────────────┐           │
│   │   Cortex Query      │    │   Knowledge Query   │           │
│   │   (深度洞察产出)     │    │   (知识图谱)        │           │
│   │                     │    │                     │           │
│   │ • Tantivy 召回      │    │ • 实体 entities     │           │
│   │ • SQLite 门禁       │    │ • 关系 relations    │           │
│   │ • FS 装配          │    │ • 结论 claims        │           │
│   │ • evidence_pack    │    │                     │           │
│   │                     │    │                     │           │
│   │ 90 artifacts        │    │ 128 entities        │           │
│   │ 482 sources         │    │ 1343 relations      │           │
│   │ 3 claims            │    │ 111 claims          │           │
│   └─────────────────────┘    └─────────────────────┘           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 决策流程

```
User需求: "设计XXX系统"
       │
       ▼
┌─────────────────────┐
│ Unified Query       │ ← 一条命令搞定
│ search "xxx" 10     │
└────────┬────────────┘
         │
         ▼
   ┌─────────────────────────────────────┐
   │ Cortex: sources/claims/artifacts    │
   │ Knowledge: entities/relations/claims│
   └────────┬────────────────────────────┘
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

| 证据类型 | 来源 | 说明 |
|---------|------|------|
| 参考资料 | Cortex | 论文/文章/先验知识 |
| 结论论点 | Cortex | 已验证的结论 |
| 评估结果 | Cortex | 专家互评 |
| 设计方案 | Cortex | 完整产出 |
| 知识实体 | Knowledge | 人名/技术/概念/组织 |
| 知识关系 | Knowledge | 实体间关联网络 |
| 知识结论 | Knowledge | 高置信度结论 (≥0.7) |

## 查询模式

### 模式1: 统一搜索 (默认)

```bash
bun unified-query.ts search "GPU推理优化" 10

# 输出示例:
# 🔍 统一查询结果 (93ms)
#    来源: Cortex 5 | 知识库 3
#
# 📚 Cortex 参考资料:
#    1. [85%] GPU推理优化最佳实践
#       本文总结了 GPU 推理优化的关键技巧...
#
# 👤 知识图谱实体:
#    [technology] CUDA: NVIDIA 的并行计算平台...
#    [concept] Flash Attention: 高效注意力计算方法...
```

### 模式2: 深度证据 (需要 evidence_pack)

```bash
bun unified-query.ts evidence "AI Agent 记忆机制"

# 额外输出:
# 📊 Evidence Pack:
#    来源: 5 | 结论: 3 | 平均可信度: 0.85
#    引用链: artifact_1 → source_3 → claim_2
```

### 模式3: 知识图谱

```bash
bun unified-query.ts graph "Transformer"

# 输出:
# 🔗 实体关系:
#    Transformer --[basis_for]--> BERT
#    Transformer --[basis_for]--> GPT
#    Attention --[core_mechanism]--> Transformer
```

## 违反检测

当我的输出包含以下模式时，说明违反了铁律：

- "我认为..."（主观判断）
- "根据我的经验..."（未查Cortex）
- "通常做法是..."（未验证）
- 直接给出设计方案（未查证据）

**正确模式：**

- "根据 Unified Query 结果..."
- "查询 Cortex 发现..."
- "Knowledge Graph 显示..."
- "/Insight 研究后得出结论..."

## 自检问题

开始设计/开发前，问自己：

- [ ] 我执行 `unified-query.ts search` 了吗？
- [ ] 有相关证据吗？(Cortex sources / Knowledge claims)
- [ ] 证据质量如何？（credibility/confidence ≥ 0.7）
- [ ] 无证据时，我调用/Insight 了吗？
- [ ] 我的决策基于证据还是主观？

## 与其他规则的关系

- **Cortex First**: 先查中枢神经（最高优先级）
- **Data First**: 先查数据资产
- **REE First**: 先查可执行资源
- **Research First**: 研究业界实践

**优先级**: Cortex First > Data First > REE First > Research First

## 铁律总结

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   🧠 Cortex First 铁律 v3.0                                     │
│                                                                 │
│   1. 一条命令: unified-query.ts search "关键词" (MUST)          │
│   2. 同时覆盖 Cortex + Knowledge (MUST)                         │
│   3. 基于证据决策 (MUST)                                        │
│   4. 无证据调用/Insight (MUST)                                  │
│   5. 证据质量 ≥ 0.7 才可信 (SHOULD)                             │
│                                                                 │
│   Unified Query = 唯一真相源入口                                │
│   证据驱动 > 主观判断                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

*Cortex First Protocol v3.0*
*建立于: 2026-02-13*
*更新于: 2026-02-15 (统一查询入口 unified-query.ts)*
*监护人指示: 第一时间查中枢神经和知识库*
