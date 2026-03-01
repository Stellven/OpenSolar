---
name: skill-retrieval
description: 技能检索系统 - 根据用户意图自动检索相关技能。必须在处理技术问题时调用。
triggers:
  - 设计
  - 实现
  - 开发
  - 优化
  - 重构
  - 调试
  - 测试
  - Python
  - React
  - Kubernetes
  - Docker
  - 安全
  - API
  - 权衡
  - 决策
  - 分析
  - 根因
priority: critical
---

# 技能检索系统

## ⚡ 强制规则

**处理任何技术问题前，必须先调用技能检索！**

### 调用方式

```
mcp__skill_retriever__retrieve_layered({
  query: "<用户消息>",
  max_domain: 9,
  max_utility: 3
})
```

### 三层架构

| 层级 | 技能数 | 加载策略 |
|------|--------|----------|
| Core | 14 | 始终加载（元技能 + Solar 核心）|
| Domain | 58 | 按意图动态检索（8 大领域）|
| Utility | 1423 | 精确匹配，冷启动 |

### 8 大领域

- **languages**: python-patterns, golang-patterns, rust-patterns
- **frontend**: react-patterns, nextjs-patterns, tailwind-patterns
- **backend**: django-patterns, fastapi-development, api-design
- **cloud**: kubernetes-specialist, terraform-engineer, docker-patterns
- **database**: postgres-patterns, redis-patterns, mongodb-patterns
- **security**: security-audit-patterns, auth-implementation-patterns
- **testing**: e2e-testing-patterns, playwright-testing, unit-testing
- **ai**: ai-engineer, llm-architect, rag-engineer

### 工作流程

```
1. 收到技术问题
2. 调用 retrieve_layered 获取相关技能列表
3. 调用 load_skill 加载需要的技能内容
4. 基于技能指导生成回复
```

### 示例

**用户**: "帮我优化 Python 代码性能"

**步骤**:
1. `mcp__skill_retriever__retrieve_layered({ query: "优化 Python 性能" })`
2. 返回: domain = ["python-patterns", "python-architect", "python-performance-optimization"]
3. `mcp__skill_retriever__load_skill({ skill_name: "python-performance-optimization" })`
4. 基于技能内容生成优化建议

### 其他工具

| 工具 | 功能 |
|------|------|
| `skill_stats` | 获取技能库统计 |
| `list_meta_skills` | 列出元技能 |
| `search_skills` | 搜索技能（兼容旧版）|

## ⚠️ 注意

- 不检索 = 凭空想象 = 可能违反最佳实践
- 检索后必须加载技能内容，不只是看列表
- 元技能（systems-thinking 等）始终可用
