# Solar 铁律: 牛马调用必须使用 Prompt Template v3.0

> **来源: 2026-02-07 监护人批准**
> **实测: Token -59%, 延迟 -49%, 质量 ↑**

## 铁律定义

```
┌─────────────────────────────────────────────────────────────────┐
│              PROMPT TEMPLATE v3.0 PROTOCOL                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   调用牛马 (GLM/Gemini/DeepSeek) 时，必须使用 v3.0 模板        │
│                                                                 │
│   ❌ 禁止: 简单提示 "你是专业的工程师，写个xxx"                 │
│   ✅ 必须: 使用完整模板 (边界+格式+Bookending)                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 模板位置

```
~/.claude/core/solar-farm/prompt-template.ts
```

## 快速使用

```typescript
import { buildCodePrompt, buildReviewPrompt, buildAnalysisPrompt }
  from '~/.claude/core/solar-farm/prompt-template';

// 代码任务
const { system, prompt } = buildCodePrompt(
  '实现 fibonacci 函数',           // 目标
  '项目: Solar Core',              // 上下文
  ['O(n) 复杂度', '只输出代码']    // 约束
);

// 审查任务
const { system, prompt } = buildReviewPrompt(
  codeContent,                      // 代码
  ['性能', '安全', '可读性']       // 关注点
);

// 分析任务
const { system, prompt } = buildAnalysisPrompt(
  '这个架构有什么问题？',          // 问题
  contextContent                    // 上下文
);

// 调用牛马
await mcp__brain_router__complete({ model: 'glm-4-plus', system, prompt });
```

## 模板核心要素 (必须包含)

| 要素 | 来源 | 作用 |
|------|------|------|
| **任务边界** | NEXEN | 只做/不做/不确定 |
| **输出格式** | Anthropic | 结构化输出 |
| **Bookending** | Lost in the Middle | 开头结尾放关键信息 |
| **上下文压缩** | LLMLingua | 中间区可压缩 |
| **规模规则** | Anthropic | 复杂度匹配 |

## v1 vs v3 实测对比

| 指标 | v1 简单提示 | v3 完整模板 | 改进 |
|------|------------|-------------|------|
| 输出 Token | 233 | 95 | **-59%** |
| 延迟 | 9138ms | 4623ms | **-49%** |
| 遵守约束 | ✗ | ✓ | - |
| 算法正确性 | ✗ 递归 | ✓ 迭代 | - |

## 系统表注册

| 表 | ID | 状态 |
|----|----|----|
| sys_scripts | solar-farm-prompt-template-v3 | active |
| sys_resources | solar-farm-prompt-v3 | active |

## 学术支撑

- Anthropic Multi-Agent Task Delegation (2026)
- Lost in the Middle (Liu et al., TACL 2024)
- LLMLingua Prompt Compression (Microsoft, EMNLP 2023)
- Self-Debug (ICLR 2024)
- Constitutional AI / RLAIF (Anthropic)

## 检查清单

调用牛马前，确认：

- [ ] 使用了 v3 模板？
- [ ] 有任务边界 (只做/不做)？
- [ ] 有输出格式要求？
- [ ] 关键信息在开头/结尾 (Bookending)？
- [ ] 中间区上下文已压缩？

---

*Prompt Template v3.0 Rule*
*建立于: 2026-02-07*
*实测验证: Token -59%, 延迟 -49%*
