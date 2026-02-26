# Routing Decision MCP Server 使用指南

## 概述

Routing Decision MCP Server 是一个基于 effective_score 的模型推荐服务，为 Brain Router 提供决策支持。

## 核心功能

1. **基于数据驱动的模型推荐**：从 `sys_routing_model` 表查询 effective_score，过滤高质量模型
2. **任务类型感知**：根据任务类型和复杂度推荐合适的模型
3. **阈值过滤**：自动过滤掉低质量模型（默认 threshold = 0.7）

## MCP 工具

### 1. get_recommended_models

获取推荐模型列表（基于 effective_score）

**参数**:
- `threshold` (number, optional): 最低有效分数阈值，默认 0.7

**返回示例**:
```json
{
  "threshold": 0.7,
  "count": 4,
  "models": [
    {
      "model_id": "glm-4-flash",
      "avg_effective_score": 0.983,
      "min_effective_score": 0.95,
      "max_effective_score": 1.0,
      "rule_count": 3
    },
    {
      "model_id": "deepseek-r1",
      "avg_effective_score": 0.937,
      "min_effective_score": 0.84,
      "max_effective_score": 0.98,
      "rule_count": 4
    }
  ]
}
```

### 2. get_model_recommendation

根据任务类型和复杂度获取模型推荐

**参数**:
- `task_type` (string, required): 任务类型 (coding/analysis/reasoning/general)
- `complexity` (number, optional): 复杂度 1-10，默认 5

**返回示例**:
```json
{
  "task_type": "coding",
  "complexity": 8,
  "recommendation": {
    "model_id": "deepseek-r1",
    "avg_effective_score": 0.937,
    "min_effective_score": 0.84,
    "max_effective_score": 0.98,
    "rule_count": 4
  }
}
```

**推荐逻辑**:
- 复杂任务 (complexity >= 7)：优先推荐高端模型（deepseek-r1, gemini-2.5-pro, o1）
- 简单任务 (complexity <= 3)：推荐快速模型（glm-4-flash, glm-5）
- 中等任务：按 effective_score 排序推荐

## 使用方式

### 方式一：通过 MCP 调用

```typescript
// 在 Claude Code 中直接调用
const result = await mcp__routing-decision__get_recommended_models({ threshold: 0.8 });
```

### 方式二：命令行查询

```bash
# 运行分析脚本查看当前模型质量分布
cd ~/.claude/core/cortex
bun routing-decision.ts
```

## 当前模型质量分布 (2026-02-20)

| 排名 | 模型 | 平均分 | 推荐级别 |
|-----|------|-------|----------|
| 1 | glm-4-flash | 0.983 | ⭐⭐⭐ 强烈推荐 |
| 2 | deepseek-r1 | 0.937 | ⭐⭐⭐ 强烈推荐 |
| 3 | glm-5 | 0.926 | ⭐⭐⭐ 强烈推荐 |
| 4 | deepseek-v3 | 0.900 | ⭐⭐⭐ 强烈推荐 |
| 5 | gemini-2.5-pro | 0.843 | ⭐⭐ 推荐 |
| 6 | o1 | 0.819 | ⭐⭐ 推荐 |
| 7 | gpt-4o | 0.774 | ⭐ 可用 |
| 8 | glm-5 | 0.225 | ❌ 不推荐 |

**关键发现**:
- ✅ T2 成功降权：GLM-5 的 effective_score = 0.225（base_weight 0.3 × q_score 0.75）
- ⭐ 高质量模型：glm-4-flash, deepseek-r1, glm-5 表现优异
- 📊 数据驱动：所有推荐基于 sys_routing_model 的实际数据

## 数据来源

所有数据来自 `~/.solar/solar.db` 的 `sys_routing_model` 表：

```sql
-- 查看当前路由规则
SELECT
  target_model,
  base_weight,
  effective_score,
  rule_name
FROM sys_routing_model
WHERE enabled = 1
ORDER BY effective_score DESC;
```

## 配置文件

MCP server 配置在 `~/.mcp.json`:

```json
{
  "mcpServers": {
    "routing-decision": {
      "command": "bun",
      "args": ["/Users/lisihao/.claude/core/cortex/routing-decision-mcp.ts"],
      "env": {}
    }
  }
}
```

## 后续优化方向

1. **集成到 Brain Router**：修改 brain-router.sh hook，在路由前先查询 routing-decision
2. **动态阈值调整**：根据系统负载动态调整 threshold
3. **更多维度**：考虑成本、延迟、上下文窗口等因素
4. **反馈闭环**：将实际执行结果写回 sys_routing_model，更新 effective_score

## 文件列表

- `routing-decision.ts` - 命令行分析工具
- `routing-decision-mcp.ts` - MCP server 实现
- `ROUTING-DECISION.md` - 本文档

---

*创建时间: 2026-02-20*
*维护者: Solar 自演进系统*
