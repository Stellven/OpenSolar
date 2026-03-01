---
name: skill-finder
description: 动态检索相关技能，只注入高相关度的技能上下文。当用户提出复杂问题时自动调用。
---

# Skill Finder

智能技能检索系统，根据用户意图动态匹配相关技能。

## 核心功能

1. **意图识别** - 分析用户问题，识别核心意图
2. **技能匹配** - 基于意图映射表检索相关技能
3. **优先级排序** - 元技能 > 领域技能 > 工具技能
4. **上下文生成** - 只注入 Top-K 相关技能

## 使用方式

```bash
# 搜索相关技能
bun ~/.claude/core/skill-retriever.ts search "<用户问题>"

# 生成上下文注入
bun ~/.claude/core/skill-retriever.ts context "<用户问题>"
```

## 元技能列表（高杠杆）

| 技能 | 触发场景 |
|------|----------|
| systems-thinking | 复杂系统、多利益相关者 |
| problem-definition | 问题模糊、需要澄清 |
| evaluating-trade-offs | 技术选型、方案对比 |
| decision-helper | 决策困难、需要框架 |
| root-cause-analysis | 调试、故障排查 |
| firstprinciples | 本质思考、创新方案 |
| sequential-thinking | 复杂推理、多步骤问题 |

## 调用示例

当用户问：
- "这个架构方案怎么权衡？" → 调用 evaluating-trade-offs + decision-helper
- "为什么系统突然变慢了？" → 调用 root-cause-analysis + systems-thinking
- "这个复杂问题怎么分析？" → 调用 problem-definition + systems-thinking

## 注意事项

- 元技能优先级最高，始终优先返回
- 领域技能按关键词匹配
- 最多返回 5 个相关技能
- 上下文总长度控制在 4000 token 以内
