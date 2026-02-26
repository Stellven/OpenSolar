# /brain - 大脑切换

> 快速切换 Brain Router 路由模式

## 口令

| 口令 | 效果 | 说明 |
|------|------|------|
| `省钱` / `经济` / `economy` | 切换到经济模式 | GLM 优先，成本最低 |
| `平衡` / `balanced` | 切换到平衡模式 | 智能路由，质量成本兼顾 |
| `用Claude` / `anthropic` | 切换到 Anthropic 模式 | 纯 Claude，质量最高 |
| `用Gemini` / `谷歌` | 切换到 Gemini 模式 | Google 模型 |
| `用DS` / `用DeepSeek` | 切换到 DeepSeek 模式 | 中文推理强 |
| `用GLM` / `智谱` | **GLM 全量模式** | 尽可能用 GLM (60%+) |
| `大脑` / `brain` | 显示当前状态 | 查看模式和可用模型 |

## 执行

收到口令后，调用对应的 MCP 工具：

```
省钱/经济   → mcp__brain-router__switch_mode { mode: "economy" }
平衡        → mcp__brain-router__switch_mode { mode: "balanced" }
用Claude    → mcp__brain-router__switch_mode { mode: "anthropic" }
用Gemini    → mcp__brain-router__switch_mode { mode: "gemini" }
用DeepSeek  → mcp__brain-router__switch_mode { mode: "deepseek" }
用GLM       → mcp__brain-router__switch_mode { mode: "glm_only" }
大脑        → mcp__brain-router__current_mode
```

## GLM 全量模式详解

**激活口令:** `用GLM` / `智谱`

**核心机制:** 绕过 Task Agent，通过 Brain Router 直接调用 GLM

| 任务类型 | 执行方式 | 使用模型 |
|----------|----------|----------|
| 主脑编排 | Solar 直接处理 | Claude (无法替换) |
| 工具调用 | Read/Write/Bash | 直接执行 |
| **写代码** | Brain Router | **GLM-4-Plus** |
| **写测试** | Brain Router | **GLM-4-Plus** |
| **代码审查** | Brain Router | **GLM-4-Plus** |
| **技术分析** | Brain Router | **GLM-4-Plus** |

**执行方式:**
```typescript
mcp__brain-router__complete({
  model: "glm-5",
  system: "你是专业的...",
  prompt: "任务描述"
})
```

**比例:** Claude 40% (编排) | GLM 60% (执行)

## 输出格式

切换后显示确认：

```
┌─ 🧠 大脑切换 ─────────────────────────────────────────────────┐
│                                                               │
│  模式: economy → glm_only                                     │
│  说明: 尽可能用GLM (编码/测试/审查都用GLM)                    │
│  优先级: glm-5 → glm-4-flash                             │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## 快捷口令 (自然语言)

以下表达也会触发切换：

- "帮我省点钱" / "用便宜的" → economy
- "质量优先" / "用好的" → anthropic
- "用智谱" / "切GLM" / "尽可能用GLM" → glm_only
- "恢复默认" / "正常模式" → balanced
- "用谷歌" / "用Gemini" → gemini
- "用DS" / "用DeepSeek" → deepseek
