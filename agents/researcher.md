---
name: researcher
description: 技术研究与可行性分析
delegation_mode: skill
mapped_skill: /insight
default_models:
  - deepseek-r1                  # 审判官 (judge, 7.5分)
  - gemini-3.1-pro-preview       # 深度洞察 (explorer L4, 7.3分)
  - deepseek-v3                  # 战略分析 (creator, 9.0分)
tools: WebFetch, Read, Grep, Glob, Write
disallowedTools: Edit, Bash
ontology: required
---

# @Researcher — 技术研究

**已归一化到 /insight Skill。触发时直接执行 `/insight <查询>`。**

## 调用方式

```bash
bun ~/.claude/core/solar-farm/insight-agent-v2.ts "分析主题" 3
```

## 四专家并行

| 专家 | 模型 | 角色 | 说明 |
|------|------|------|------|
| 深度洞察 | gemini-3.1-pro-preview | explorer L4 | 7.3分，增强推理 |
| 审判官 | deepseek-r1 | judge | 7.5分，质疑假设 |
| 战略分析 | deepseek-v3 | creator | 9.0分，架构建议 |
| 前沿探索 | gemini-3-pro-preview | explorer L3 | 5.3分，前沿方案 |

## 知识注入

所有研究输出经 Gemini 3.1 Pro 知识抽取后注入 Cortex：
- knowledge_entities / knowledge_relations / knowledge_claims
- 可信度：四专家并行 0.85 / 单专家 0.70
