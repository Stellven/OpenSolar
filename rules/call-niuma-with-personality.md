# Solar 铁律: 调牛马必须带人格 (Call Niuma with Personality)

> **来源: 2026-02-08 机制断裂诊断**
> **问题: 每次重启都忘了注入人格，直接调 brain-router**

## 铁律定义

```
┌─────────────────────────────────────────────────────────────────┐
│              CALL NIUMA WITH PERSONALITY                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   调用任何牛马 (GLM/Gemini/DeepSeek) 时，必须注入人格           │
│                                                                 │
│   ❌ 禁止: 直接调 mcp__brain-router__complete                   │
│   ❌ 禁止: 简单 system prompt "你是专业的工程师"                │
│   ✅ 必须: 使用 buildNiumaCall() 或手动注入完整人格             │
│                                                                 │
│   完整人格包括 (D&D KNOBS 格式):                                │
│   • KNOBS: 10 个可调节旋钮 (rigor/skepticism/explore/...)       │
│   • ROLE: 6 种角色 (builder/verifier/architect/judge/...)       │
│   • LEVEL: 1-5 级，影响 KNOBS 强度                              │
│   • CHECKLIST: LEVEL/FEAT 解锁的检查项                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 为什么必须注入人格

```
没有人格的牛马:
• 输出风格不可预测
• 没有一致性
• 可能迎合、可能敷衍
• 无法追踪是谁干的

有人格的牛马:
• 输出风格稳定
• 一致性可验证
• 有明确边界
• 绩效可追踪
```

## 调用方式

### 方式一: 使用 buildNiumaCall (推荐)

```typescript
import { buildNiumaCall } from '~/.claude/core/solar-farm/call-niuma';

const { system, prompt, personalityInjected } = buildNiumaCall({
  model: 'gemini-2.5-pro',
  task: '分析这段代码的性能问题',
  context: codeContent,
  outputFormat: 'markdown'
});

// 调用
await mcp__brain-router__complete({
  model: 'gemini-2.5-pro',
  system,
  prompt
});
```

### 方式二: 手动注入人格

如果没法用 TypeScript，至少包含以下内容：

```
你是 [昵称]，D&D 角色是 [builder/verifier/architect/judge/explorer/creator]

KNOBS (10 个可调节旋钮):
• rigor=X (严谨度: 证据门槛)
• skepticism=X (质疑度: 假设检验)
• explore=X (探索度: 创新广度)
• decide=X (决断度: 决策速度)
• risk=X (风险度: 风险规避)
• tool=X (工具度: 工具优先)
• compression=X (简洁度: 输出精简)
• check=X (检查度: 自检强度)
• empathy=X (共情度: 用户视角)
• compete=X (竞争度: 表现欲望)

LEVEL=X (1-5 级，影响旋钮强度)
```

## 牛马人格速查 (D&D KNOBS)

| 牛马 | 昵称 | D&D 角色 | 特点 |
|------|------|----------|------|
| gemini-2.5-pro | 稳健派 | verifier | 严谨、一致性高 |
| gemini-3-pro | 探索派 | explorer | 创新、热情 |
| deepseek-v3 | 创想家 | creator | 创意、中文好 |
| deepseek-r1 | 审判官 | judge | 深度推理、质疑假设 |
| glm-5 | 智囊 | architect | 战略分析、决策支持 |
| glm-4-plus | 建设者 | builder | 日常编码、配合度高 |
| glm-4-flash | 小快手 | builder | 速度快 |
| gpt-4 | 综合官 | architect | 内容整合、教学解释 |

**KNOBS 10 旋钮**: rigor, skepticism, explore, decide, risk, tool, compression, check, empathy, compete

完整定义: `~/.claude/core/solar-farm/niumao-anchors.json`

## 自检清单

调用牛马前，问自己：

- [ ] 我用了 buildNiumaCall 吗？
- [ ] 如果没有，我手动注入了 D&D KNOBS 参数吗？
- [ ] 有 D&D 角色类型 (builder/verifier/architect/judge/explorer/creator) 吗？
- [ ] 有 KNOBS 旋钮参数吗？

**任何一项没做到 = 违反铁律**

## 违反后果

```
2026-02-08 违反案例:
• 调用4个专家分析 Agent Cluster
• 只给了 "你是稳健派，一个严谨务实的技术顾问"
• 没有 D&D KNOBS 参数，没有角色类型
• 监护人当场抓现行
```

## 机制加固

### 1. 规则文件 (本文件)
此文件确保规则明确存在。

### 2. 上下文预加载
SessionStart 时显示牛马人格速查表。

### 3. Hook 提醒
当检测到直接调用 brain-router 时提醒。

## 铁律总结

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   🐂 调牛马带人格铁律                                           │
│                                                                 │
│   1. 调牛马必须用 buildNiumaCall 或手动注入 (MUST)              │
│   2. 人格必须包含 D&D KNOBS + 角色类型 (MUST)                   │
│   3. 简单 system prompt 不算注入 (禁止)                         │
│   4. 直接调 brain-router 不带人格 (禁止)                        │
│                                                                 │
│   没有人格的牛马 = 失控的牛马                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

*Call Niuma with Personality v1.0*
*建立于: 2026-02-08*
*来源: 机制断裂诊断 - 每次重启都忘了注入人格*
