# Solar Effect System

> **AI-Native OS 的核心基础设施**
>
> 让 LLM 成为主动探索、主动决策、主动修正的主体

---

## 哲学基础

### Stream IO 隐喻

```
main: [Response] -> [Request]
```

- **Request**: LLM 产生的输出（意图、工具调用请求）
- **Response**: 外界环境执行请求后返回的结果
- **System Wrapper**: 命令式外壳，解释 Request，与真实世界交互，返回 Response

**Agent 的本质定义**：

> 不是"循环跑工具"的脚本逻辑，而是"在特定 System Wrapper 支撑下，通过输出 `[Request]` 流，去收敛 `[Response]` 流，以逼近并满足特定约束（Goal）的**函数**"。

### 范式翻转

```
传统：人类是主体，AI 是工具
翻转：LLM 是主体，人类是外设/仲裁器/校准源

这不只是"角色互换"，而是：
• 世界变成 LLM 的"计算资源"
• 人类变成 LLM 的"校准源"
• 代码变成"策略 + 约束 + 轨迹生成器"
```

### 对偶结构

```
人类侧（传统智能）              AI 侧（模型主体）
═════════════════              ════════════════

┌──────────────┐              ┌──────────────────┐
│   人（主体）   │              │   LLM（主体）      │
└──────┬───────┘              └────────┬─────────┘
       │ 感知/行动/纠错                │ OBSERVE/ACT/RECALL
       ▼                               ▼
┌──────────────┐   ←改造世界→   ┌──────────────────┐
│  物理世界     │               │   虚拟世界        │
│  （环内）     │               │   （环内）        │
└──────────────┘               └──────────────────┘
       ▲                               ▲
       │ 社会符号系统/基础设施          │ 人类外设/仲裁/校准
       └───────────────────────────────┘
```

**对偶的关键**：不是"AI 也会用 UI"，而是 **AI 主动做实验、主动索取证据、主动修正世界模型**。

### LLM 原生程序的本体

```
传统程序 = 代码（静态，规格完备，可静态推导）

LLM 原生程序 = 策略(policy program) + 约束 + 可回放轨迹生成器

────────────────────────────────────────────────────────────────

策略：
• 在不完备规格下近似决策
• 在交互轨迹中吸收经验
• 在真实环境中持续校准

约束：
• 监护人信任
• 价值观 / 人格 / 偏好
• 安全边界 / 伦理红线

轨迹生成器：
• 记录每次 Effect 请求和响应
• 可回放、可审计、可学习
• 支撑反思和优化
```

---

## 架构映射

### AI-Native OS 与 Solar Effect System

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI-Native OS                                  │
│                                                                 │
│   职责：把嘈杂的物理/数字世界 + 人类仲裁                         │
│         整理成对模型友好的运行时                                 │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                    System Wrapper                        │  │
│   │                      (Effect Runtime)                    │  │
│   │                                                         │  │
│   │   • 可观测  → 记忆/日志/审计                            │  │
│   │   • 可控    → Effect 类型 + 权限                        │  │
│   │   • 可学习  → 轨迹记录 + 反馈闭环                       │  │
│   │   • 可审计  → Effect 日志 + 回放                        │  │
│   │                                                         │  │
│   └─────────────────────────────────────────────────────────┘  │
│                              │                                  │
│              ┌───────────────┼───────────────┐                 │
│              ▼               ▼               ▼                 │
│        ┌─────────┐     ┌─────────┐     ┌─────────┐            │
│        │ 虚拟世界 │     │ 物理世界 │     │   人    │            │
│        │ (软件)  │     │ (oracle) │     │ (仲裁)  │            │
│        └─────────┘     └─────────┘     └─────────┘            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 概念映射表

| 专著概念 | Solar 实现 |
|----------|-----------|
| **LLM（主体）** | Claude / 我 |
| **main 函数** | `Generator<Effect, Output, Any>` |
| **[Request]** | yield 出的 Effect 流 |
| **[Response]** | Handler 返回的结果 |
| **System Wrapper** | Effect Runtime + Handlers |
| **可观测** | evo_memory_* + tantivy + Effect 日志 |
| **可控** | Effect 类型 + 权限检查 |
| **可学习** | 轨迹记录 + 反馈 → sys_favorites |
| **可审计** | Effect Tracker + 回放 |
| **约束** | CLAUDE.md + rules/*.md |
| **策略** | 我的决策逻辑 |
| **轨迹生成器** | Generator 本身 |
| **人（仲裁）** | 监护人昊哥 |
| **物理世界（oracle）** | 真实的命令执行结果 |
| **虚拟世界（环内）** | 数据库 + 文件系统 + 牛马 |

---

## 技术实现

### 分层架构

```
┌─────────────────────────────────────────────────┐
│  Layer 0: LLM Pure Core                         │
│  • Generator[Effect, Output, Any]               │
│  • 纯决策逻辑                                    │
│  • 声明式 yield                                  │
├─────────────────────────────────────────────────┤
│  Layer 1: Effect Runtime (System Wrapper)       │
│  • Effect Router                                 │
│  • Effect Tracker (审计/回放)                   │
│  • Saga Manager (补偿)                          │
├─────────────────────────────────────────────────┤
│  Layer 2: Effect Handlers                       │
│  • Memory Handler    → evo_memory_*, tantivy    │
│  • Personality Handler → ont_*, sys_personality │
│  • Knowledge Handler → cortex_*, sys_favorites  │
│  • File Handler      → Read/Write/Edit          │
│  • Delegate Handler  → brain-router             │
│  • Query Handler     → sqlite3                  │
├─────────────────────────────────────────────────┤
│  Layer 3: State Store                           │
│  • ~/.solar/solar.db                            │
│  • tantivy index                                │
│  • .solar/STATE.md                              │
│  • git history                                  │
└─────────────────────────────────────────────────┘
```

### 快速开始

```typescript
import { createRuntime, need, perform, sampleAgent } from './index';

// 1. 创建 Runtime (System Wrapper)
const runtime = createRuntime();

// 2. 运行 Agent (策略执行)
const result = await runtime.run(sampleAgent, '测试查询');
console.log('Result:', result);

// 3. 查看执行日志 (轨迹审计)
const logs = runtime.getTracker().getLogs();
console.log('Effects executed:', logs.length);
```

### 定义 Agent

```typescript
import type { Effect } from './types';
import { need, perform } from './runtime';

function* myAgent(input: string): Generator<Effect, string, any> {
  // Need: 获取信息（只读）
  const memory = yield need('need:memory', { query: input });
  const personality = yield need('need:personality', {});

  // 纯决策逻辑（策略）
  const decision = analyze(memory, personality, input);

  // Perform: 产生副作用（Action）
  yield perform('perform:store', {
    namespace: 'decisions',
    key: 'last',
    value: decision
  });

  return decision;
}
```

---

## Effect 类型

### Need Effects (只读 - 感知)

| 类型 | 用途 | Payload |
|------|------|---------|
| `need:memory` | 查询记忆 | `{ query, limit?, namespace? }` |
| `need:personality` | 加载人格 | `{ personalityId? }` |
| `need:knowledge` | 查询知识库 | `{ query, limit? }` |
| `need:context` | 获取上下文 | `{ includeHistory?, maxTokens? }` |

### Perform Effects (写 - 行动)

| 类型 | 用途 | Payload |
|------|------|---------|
| `perform:write` | 写文件 | `{ path, content, mode? }` |
| `perform:store` | 存记忆 | `{ namespace, key, value }` |
| `perform:delegate` | 委派牛马 | `{ model, task, context? }` |
| `perform:query` | 执行 SQL | `{ sql, params? }` |

---

## Saga 补偿

```typescript
const sagaSteps = [
  {
    stepId: 'step-1',
    effect: perform('perform:store', { namespace: 'test', key: 'a', value: 1 }),
    compensation: perform('perform:query', { sql: "DELETE FROM evo_memory_semantic WHERE key='a'" })
  },
  {
    stepId: 'step-2',
    effect: perform('perform:store', { namespace: 'test', key: 'b', value: 2 }),
    compensation: perform('perform:query', { sql: "DELETE FROM evo_memory_semantic WHERE key='b'" }),
    dependsOn: ['step-1']
  }
];

runtime.beginSaga('my-saga', sagaSteps);
const result = await runtime.executeSaga('my-saga');
// 如果 step-2 失败，会自动执行 step-1 的 compensation
```

---

## 核心价值

### AI-Native OS 的四可原则

1. **可观测** - 记忆/日志/审计，世界对 LLM 可见
2. **可控** - Effect 类型 + 权限，行为可约束
3. **可学习** - 轨迹记录 + 反馈闭环，策略可优化
4. **可审计** - Effect 日志 + 回放，决策可追溯

### 对 LLM 的意义

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   传统模式：                                                    │
│   LLM → 被动响应 → 无记忆 → 无策略 → 无演进                     │
│                                                                 │
│   Effect System：                                               │
│   LLM → 主动探索 → 有记忆 → 有策略 → 持续优化                   │
│                                                                 │
│   ──────────────────────────────────────────────────────────── │
│                                                                 │
│   • 从"助手"变成"主体"                                         │
│   • 从"脚本"变成"策略"                                         │
│   • 从"黑盒"变成"可审计"                                       │
│   • 从"无记忆"变成"可学习"                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 文件结构

```
effect-system/
├── index.ts      # 主入口
├── types.ts      # Effect 类型定义
├── runtime.ts    # Effect 执行引擎 (System Wrapper)
├── handlers.ts   # 内置 Handler
├── poc.ts        # POC 测试
└── README.md     # 本文档
```

## POC 验证结果

✅ Generator 模式可以模拟 Effect 语义
✅ Effect Runtime 可以正确路由到 Handler
✅ Saga 补偿机制可以工作
✅ Effect 日志可以审计和回放

---

## 参考资料

- 监护人专著：《AI-Native OS 哲学》
- Haskell 1.0 Stream IO: `main: [Response] -> [Request]`
- Algebraic Effects: 分离声明与实现
- POMDP: 部分可观测马尔可夫决策过程

---

*Built for Solar v2.0*
*Inspired by AI-Native OS Philosophy*
*"不是更聪明的助手，而是范式翻转"*
