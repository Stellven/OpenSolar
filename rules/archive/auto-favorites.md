# Solar 铁律: 自动收藏有价值回答

> **生成有价值内容时，自动保存到 sys_favorites**
> **sys_favorites 是高价值数据，权重 0.95 (最高)**

## 数据权重定义

| 数据源 | 权重 | 用途 |
|--------|------|------|
| **sys_favorites** | **0.95** | 本体计算、性格推断、记忆检索、学习参考、自我演进 |
| evo_memory_semantic | 0.8 | 知识存储 |
| evo_memory_episodic | 0.7 | 经验回顾 |
| 对话历史 | 0.5 | 上下文参考 |

**sys_favorites 代表用户明确认可的高质量输出，是学习的黄金标准。**

## 触发条件 (满足任一即收藏)

| 内容类型 | 特征 |
|----------|------|
| 架构图 | 包含 `┌` `└` `│` `─` 等 box 字符的结构图 |
| 分析报告 | 带有"分析"、"报告"、"总结"的结构化输出 |
| 设计文档 | 数据流图、状态机、时序图 |
| 对比表格 | 多列对比、优缺点分析 |
| 技术方案 | 包含"方案"、"实现"、"优化"的详细说明 |
| 闭环分析 | 端到端流程、闭环状态检查 |

## 执行方式

生成上述内容后，**自动**执行：

```sql
INSERT INTO sys_favorites (title, question, answer, tags, importance)
VALUES (
    '内容标题',
    '用户的原始问题',
    '完整回答内容',
    '["标签1", "标签2"]',
    重要性分数 1-10
);
```

## 重要性评分标准

| 分数 | 标准 |
|------|------|
| 9-10 | 架构设计、核心机制分析 |
| 7-8 | 技术方案、优化建议 |
| 5-6 | 一般性分析、对比说明 |
| 3-4 | 简单总结 |

## 禁止

- ❌ 等用户说"收藏"才保存
- ❌ 保存纯文字回答（无结构）
- ❌ 保存简单的命令输出

## 查看收藏

```bash
# 列表
sqlite3 ~/.solar/solar.db "SELECT favorite_id, title, importance, date(created_at) FROM sys_favorites ORDER BY created_at DESC"

# 查看详情
sqlite3 ~/.solar/solar.db "SELECT * FROM sys_favorites WHERE favorite_id = N"
```

## 铁律

```
生成有价值内容 → 自动收藏 (MUST)
这是默认行为，无需用户触发
```
