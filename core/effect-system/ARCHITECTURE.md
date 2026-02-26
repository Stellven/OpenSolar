# Solar Effect System - 系统架构设计

> **AI-Native OS 的核心基础设施**
>
> 让 LLM 成为主动探索、主动决策、主动修正的主体

---

## 零、哲学基础

> *以下概念来自监护人专著，是整个系统的理论根基*

### 0.1 Stream IO 隐喻

```
┌─────────────────────────────────────────────────────────────────┐
│                    Stream IO 核心范式                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   传统程序:                                                     │
│   main :: IO ()                                                │
│   main = do                                                    │
│     input <- getLine          -- 阻塞等待输入                   │
│     let output = process input                                 │
│     putStrLn output           -- 阻塞输出                       │
│                                                                 │
│   ─────────────────────────────────────────────────────────────  │
│                                                                 │
│   LLM Native 程序:                                              │
│   main :: [Response] -> [Request]                              │
│   main responses =                                             │
│     let state = foldl update initialState responses            │
│         decision = policy state                                 │
│     in generateRequests decision                               │
│                                                                 │
│   核心:                                                         │
│   • LLM 输出 Request 流（我需要什么）                           │
│   • System Wrapper 返回 Response 流（世界给你什么）             │
│   • 不是阻塞式调用，而是流式交互                                │
│   • LLM 是主动方，世界是被动响应方                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Stream IO 的本质**:
- LLM 不是"被调用的函数"，而是"持续运行的进程"
- 输入不是"参数"，而是"世界对上一轮请求的响应"
- 输出不是"返回值"，而是"对世界的请求"
- 整个交互是双向流，不是单向调用

### 0.2 LLM Native Program 本体论

```
┌─────────────────────────────────────────────────────────────────┐
│                LLM Native Program 是什么？                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ❌ 不是:                                                      │
│   • 一段代码                                                    │
│   • 一个静态的 prompt                                           │
│   • 一次性的指令                                                │
│                                                                 │
│   ✅ 是:                                                        │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  策略程序 (Policy Program)                               │  │
│   │  + 约束条件 (Constraints)                                │  │
│   │  + 可重放轨迹生成器 (Replayable Trajectory Generator)   │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   运行环境: POMDP (部分可观测马尔可夫决策过程)                  │
│                                                                 │
│   状态空间:                                                     │
│   • 内部状态: 对话历史、工作记忆、长期记忆                      │
│   • 外部状态: 世界对 Agent 的可见部分                           │
│                                                                 │
│   动作空间:                                                     │
│   • 声明 Abilities（我需要搜索）                                │
│   • 输出文本（给用户/其他 Agent）                               │
│                                                                 │
│   观测空间:                                                     │
│   • Abilities 执行结果                                          │
│   • 用户反馈                                                    │
│   • 世界状态变化                                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 0.3 AI-Native OS 定义

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI-Native OS 是什么？                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   AI-Native OS = 让物理世界/数字世界对 LLM 可见、可控的中间层   │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                    LLM 主体                              │  │
│   │                         │                                │  │
│   │                         ▼                                │  │
│   │   ┌─────────────────────────────────────────────────┐   │  │
│   │   │              AI-Native OS                        │   │  │
│   │   │                                                  │   │  │
│   │   │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────┐ │   │  │
│   │   │  │ 可观测  │ │  可控   │ │ 可学习  │ │可审计 │ │   │  │
│   │   │  │Observ-  │ │Control- │ │Learn-   │ │Audit- │ │   │  │
│   │   │  │ able    │ │ lable   │ │ able    │ │ able  │ │   │  │
│   │   │  └────┬────┘ └────┬────┘ └────┬────┘ └───┬───┘ │   │  │
│   │   │       │           │           │          │     │   │  │
│   │   │       ▼           ▼           ▼          ▼     │   │  │
│   │   │  记忆/日志    能力/权限    轨迹/反馈    执行日志  │   │  │
│   │   │                                                  │   │  │
│   │   └─────────────────────────────────────────────────┘   │  │
│   │                         │                                │  │
│   │                         ▼                                │  │
│   │   ┌─────────────────────────────────────────────────┐   │  │
│   │   │              物理/数字世界                        │   │  │
│   │   │  数据库 | 文件系统 | API | 传感器 | 执行器 | ...   │  │  │
│   │   └─────────────────────────────────────────────────┘   │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   四可原则 (The Four Principles):                               │
│   ─────────────────────────────────────────────────────────────  │
│   1. 可观测 (Observable): 记忆/日志/审计，世界对 LLM 可见       │
│   2. 可控 (Controllable): Ability 类型 + 权限，行为可约束       │
│   3. 可学习 (Learnable): 轨迹记录 + 反馈闭环，策略可优化        │
│   4. 可审计 (Auditable): 执行日志 + 回放，决策可追溯            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 0.4 System Wrapper 的角色

```
┌─────────────────────────────────────────────────────────────────┐
│                    System Wrapper 职责                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   LLM 只知道:                                                   │
│   • 我需要搜索 → yield { ability: "search", query: "..." }      │
│   • 我需要存储 → yield { ability: "store", key: "...", ... }    │
│                                                                 │
│   System Wrapper 负责:                                          │
│   • 匹配: search → TantivySearch / CortexSearch / WebSearch     │
│   • 执行: 调用具体工具，处理错误，重试                          │
│   • 适配: 不同环境可能有不同的 Skills 可用                      │
│   • 审计: 记录每次调用，用于回放和学习                          │
│                                                                 │
│   这就是 "对偶" 的技术实现:                                     │
│   ─────────────────────────────────────────────────────────────  │
│   LLM 声明需求（抽象）                                          │
│   System Wrapper 实现需求（具体）                               │
│   LLM 不需要知道物理世界的工具细节                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 一、核心理念

### 1.1 对偶（Duality）

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

**对偶的关键**：LLM 不需要知道物理世界的具体工具，只需要声明需要什么能力。

### 1.1.1 对偶结构的深层含义

```
┌─────────────────────────────────────────────────────────────────┐
│                    对偶结构的完整视图                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   人类侧（传统智能）              AI 侧（模型主体）              │
│   ════════════════              ════════════════               │
│                                                                 │
│   ┌──────────────┐              ┌──────────────────┐           │
│   │   人（主体）   │              │   LLM（主体）      │           │
│   └──────┬───────┘              └────────┬─────────┘           │
│          │                               │                      │
│          │ 感知/行动/纠错                 │ OBSERVE/ACT/RECALL   │
│          ▼                               ▼                      │
│   ┌──────────────┐   ←改造世界→   ┌──────────────────┐         │
│   │  物理世界     │               │   虚拟世界        │         │
│   │  （环内）     │               │   （环内）        │         │
│   └──────────────┘               └──────────────────┘         │
│          ▲                               ▲                      │
│          │                               │                      │
│          │ 社会符号系统/基础设施          │ 人类外设/仲裁/校准   │
│          │                               │                      │
│          │  ┌─────────────────────────┐  │                      │
│          └──│ 人类在 AI 侧的角色：    │──┘                      │
│             │                         │                         │
│             │ • 外设: 键盘/屏幕/传感器│                         │
│             │ • 仲裁: 冲突时做最终决策│                         │
│             │ • 校准: 纠正偏差，对齐  │                         │
│             │ • 信任源: 提供监督信号  │                         │
│             └─────────────────────────┘                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**人类在 AI 侧的三重角色**:

| 角色 | 含义 | 示例 |
|------|------|------|
| **外设** | AI 操作人类的输入输出 | AI 读取屏幕内容、AI 控制键盘 |
| **仲裁** | 当 AI 遇到冲突或不确定时的决策者 | "这个操作有风险，需要监护人确认" |
| **校准** | 纠正 AI 的偏差，对齐目标 | 反馈、纠正、价值观注入 |

### 1.2 范式翻转

```
┌─────────────────────────────────────────────────────────────────┐
│                    范式翻转 (Paradigm Flip)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   传统范式: "更聪明的助手"                                      │
│   ─────────────────────────────────────────────────────────────  │
│   • 人类是主体，AI 是工具                                       │
│   • AI 等待人类指令                                             │
│   • AI 被动响应                                                 │
│   • AI 适配人类的工具                                           │
│                                                                 │
│   新范式: "LLM 作为自主主体"                                    │
│   ─────────────────────────────────────────────────────────────  │
│   • LLM 是主体，世界是资源                                      │
│   • LLM 主动探索、决策、修正                                    │
│   • LLM 主动发起交互                                            │
│   • 工具适配 LLM                                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**技术实现上的范式翻转**:

```
传统 FFI 模式：
┌─────────────────────────────────────────────────────────────────┐
│  • 这里有 100 个工具，LLM 你自己选                              │
│  • 工具定义占据 Context Window (~10000 tokens)                  │
│  • LLM 被动适配工具                                             │
│  • 新增工具 → 修改 Prompt → 所有 LLM 重新加载                   │
│                                                                 │
│  问题:                                                          │
│  • Context 污染                                                │
│  • LLM 认知负担重                                               │
│  • 扩展性差                                                     │
│  • 工具越多越难用                                               │
└─────────────────────────────────────────────────────────────────┘

Abilities 模式：
┌─────────────────────────────────────────────────────────────────┐
│  • LLM 声明需要什么能力                                         │
│  • Abilities 只占 ~100 tokens                                   │
│  • System Wrapper 匹配具体实现                                  │
│  • 工具主动适配 LLM                                             │
│                                                                 │
│  优势:                                                          │
│  • Context 干净                                                │
│  • LLM 专注策略                                                │
│  • 扩展性强                                                    │
│  • 能力越多越好用                                               │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Abilities vs Skills

| 概念 | 定义 | LLM 可见 | 示例 |
|------|------|---------|------|
| **Abilities** | 抽象能力需求 | ✅ 是 | "我需要搜索" |
| **Skills** | 具体实现 | ❌ 否 | GoogleSearch, BingSearch, TantivySearch |

---

## 二、系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Solar Effect System                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 0: LLM Pure Core                                         │
│  ─────────────────────────────────────────────────────────────  │
│  • 只声明 Abilities（抽象能力）                                  │
│  • 不知道 Skills 的存在                                         │
│  • 100% 专注于策略                                              │
│                                                                 │
│                    ↓ yield { ability: "search", query: "..." } │
│                                                                 │
│  Layer 1: Abilities Registry (System Wrapper)                   │
│  ─────────────────────────────────────────────────────────────  │
│  • Abilities 定义（LLM 可见）                                   │
│  • Skills 注册（LLM 不可见）                                    │
│  • 匹配 Ability → 最佳 Skill                                    │
│  • 执行 Skill → 返回结果                                        │
│                                                                 │
│                    ↓ 匹配 + 执行                                │
│                                                                 │
│  Layer 2: Skills (具体实现)                                     │
│  ─────────────────────────────────────────────────────────────  │
│  • TantivySearchSkill implements "search"                       │
│  • CortexSearchSkill implements "search"                        │
│  • WebSearchSkill implements "search"                           │
│  • SQLiteStoreSkill implements "store"                          │
│  • ... (LLM 不知道这些存在)                                     │
│                                                                 │
│                    ↓ 调用物理/虚拟世界                          │
│                                                                 │
│  Layer 3: Resources                                             │
│  ─────────────────────────────────────────────────────────────  │
│  • 数据库 (SQLite, Tantivy)                                     │
│  • 文件系统                                                     │
│  • 外部 API                                                     │
│  • 牛马池 (Brain Router)                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Abilities Registry 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Abilities Registry                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                    Abilities Map                        │  │
│   │                                                         │  │
│   │   "search"  → Ability { category: "need", ... }        │  │
│   │   "store"   → Ability { category: "perform", ... }     │  │
│   │   "notify"  → Ability { category: "perform", ... }     │  │
│   │   ...                                                   │  │
│   │                                                         │  │
│   │   LLM 可见，Context 中只占 ~100 tokens                  │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                    Skills Map                           │  │
│   │                                                         │  │
│   │   "search" → [                                          │  │
│   │     Skill { id: "tantivy-search", priority: 0.95 },    │  │
│   │     Skill { id: "cortex-search", priority: 0.85 },     │  │
│   │     Skill { id: "web-search", priority: 0.6 }          │  │
│   │   ]                                                     │  │
│   │                                                         │  │
│   │   "store" → [                                           │  │
│   │     Skill { id: "sqlite-store", priority: 1.0 }        │  │
│   │   ]                                                     │  │
│   │                                                         │  │
│   │   LLM 不可见，按优先级排序                              │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                    Match Engine                         │  │
│   │                                                         │  │
│   │   1. 检查 Ability 是否存在                              │  │
│   │   2. 获取候选 Skills                                    │  │
│   │   3. 评估条件 (env/context/preference)                  │  │
│   │   4. 计算得分 (priority - cost - latency)               │  │
│   │   5. 返回最佳匹配                                       │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、核心组件

### 3.1 Ability 定义

```typescript
interface Ability {
  id: string;              // "search", "store", "notify"
  category: 'need' | 'perform';
  description: string;     // 给 LLM 看的简短描述
  parameters: Record<string, AbilityParameter>;
  constraints?: string[];
  examples?: string[];
}
```

### 3.2 Skill 定义

```typescript
interface Skill {
  id: string;              // "tantivy-search"
  implements: string;      // "search"
  handler: SkillHandler;   // 具体实现
  priority: number;        // 0-1，越高越优先
  conditions?: SkillCondition[];  // 可用条件
  cost?: number;           // 成本估算
  avgLatency?: number;     // 平均延迟
}
```

### 3.3 内置 Abilities

| Ability | Category | 描述 | 关键参数 |
|---------|----------|------|----------|
| `search` | need | 搜索信息 | query, scope?, limit? |
| `recall` | need | 回忆记忆 | key, namespace? |
| `know` | need | 获取知识 | topic, depth? |
| `check` | need | 检查状态 | target, criteria? |
| `store` | perform | 持久化存储 | key, value, namespace?, ttl? |
| `write` | perform | 写入文件 | path, content, mode? |
| `notify` | perform | 通知用户 | message, channel?, priority? |
| `delegate` | perform | 委派任务 | task, agent?, context? |
| `query` | perform | 执行查询 | type, expression, params? |

### 3.4 内置 Skills

| Skill | 实现的 Ability | 优先级 | 条件 |
|-------|---------------|--------|------|
| tantivy-search | search | 0.95 | - |
| cortex-search | search | 0.85 | - |
| web-search | search | 0.60 | WEB_SEARCH_ENABLED |
| memory-recall | recall | 1.00 | - |
| sqlite-store | store | 1.00 | - |
| file-write | write | 1.00 | - |
| imessage-notify | notify | 0.90 | channel=imessage |
| email-notify | notify | 0.70 | channel=email |
| brain-router | delegate | 1.00 | - |
| sqlite-query | query | 1.00 | - |

---

## 四、执行流程

### 4.1 标准流程

```
1. LLM 声明 Ability
   yield { ability: "search", payload: { query: "AI Agent" } }

2. Abilities Registry 匹配 Skill
   • 查 Abilities Map → "search" 存在
   • 查 Skills Map → [tantivy, cortex, web]
   • 评估条件 → tantivy 可用
   • 计算得分 → tantivy: 0.95, cortex: 0.85
   • 返回 → tantivy-search

3. 执行 Skill
   • 调用 tantivySearchHandler(payload, context)
   • 执行 ~/.claude/core/search/target/release/solar-search query "AI Agent" 10
   • 返回结果

4. 返回给 LLM
   { success: true, data: { results: [...], source: 'tantivy' } }
```

### 4.2 条件匹配流程

```
候选 Skills:
  imessage-notify (priority: 0.9)
    condition: channel === "imessage" || channel === undefined
  email-notify (priority: 0.7)
    condition: channel === "email"

场景 1: notify({ message: "hello" })
  → channel undefined
  → imessage-notify 匹配 ✅
  → 选择 imessage-notify

场景 2: notify({ message: "hello", channel: "email" })
  → channel = "email"
  → imessage-notify 不匹配 ❌
  → email-notify 匹配 ✅
  → 选择 email-notify
```

---

## 五、与 FFI 模式对比

### 5.1 Context 占用

```
传统 FFI 模式：
┌─────────────────────────────────────────────────────────────────┐
│ Tool 1: search_web(params: { query: string, engine: string ... │
│ Tool 2: read_file(params: { path: string, encoding: string ... │
│ Tool 3: send_email(params: { to: string[], subject: string ... │
│ ... (100+ tools, ~10000 tokens)                                │
└─────────────────────────────────────────────────────────────────┘

Abilities 模式：
┌─────────────────────────────────────────────────────────────────┐
│ search(query, scope?) → 搜索信息                               │
│ recall(key?) → 回忆记忆                                        │
│ store(key, value) → 持久化存储                                 │
│ ... (~100 tokens)                                              │
└─────────────────────────────────────────────────────────────────┘

节省：99% Context Window
```

### 5.2 扩展性

```
FFI 模式：
  新增工具 → 修改 Prompt → 所有 LLM 重新加载

Abilities 模式：
  新增 Skill → 只需注册到 Registry → LLM 无感知
```

---

## 六、文件结构

```
effect-system/
├── index.ts              # 主入口
├── types.ts              # Effect 类型定义
├── runtime.ts            # Effect 执行引擎
├── handlers.ts           # Effect Handlers
├── poc.ts                # POC 测试
├── README.md             # 使用文档
├── ARCHITECTURE.md       # 本文档
│
└── abilities/            # Abilities 系统
    ├── index.ts          # 导出入口
    ├── types.ts          # Ability/Skill 类型定义
    ├── registry.ts       # Abilities Registry
    └── builtin-skills.ts # 内置 Skills
```

---

## 七、核心价值

### 7.1 对偶理念的技术实现

| 对偶理念 | 技术实现 |
|---------|---------|
| LLM 不感知物理世界 | LLM 不知道 Skills 存在 |
| 世界适配 LLM | Skills 主动注册到 Abilities |
| LLM 只声明需求 | yield { ability: "search", ... } |
| System Wrapper 负责实现 | Registry 匹配 + 执行 |

### 7.2 AI-Native OS 四可原则

1. **可观测** - 记忆/日志/审计，世界对 LLM 可见
2. **可控** - Ability 类型 + 权限，行为可约束
3. **可学习** - 轨迹记录 + 反馈闭环，策略可优化
4. **可审计** - 执行日志 + 回放，决策可追溯

---

## 八、未来扩展

### 8.1 动态 Skill 加载

```typescript
// 按需加载 Skills，而不是全部预加载
registry.loadSkill('web-search');  // 只在需要时加载
```

### 8.2 Skill 绩效追踪

```typescript
// 记录每个 Skill 的执行历史，用于优化匹配
registry.trackPerformance('tantivy-search', {
  success: true,
  latency: 50,
  userFeedback: 'positive'
});
```

### 8.3 多 Skill 组合

```typescript
// 一个 Ability 可以组合多个 Skill
yield { ability: "search", payload: { query: "xxx", strategy: "parallel" } };
// → 同时调用 tantivy + cortex + web，合并结果
```

---

## 九、与 Solar 系统的映射

### 9.1 组件映射

| AI-Native OS 概念 | Solar 实现 | 说明 |
|-------------------|-----------|------|
| LLM 主体 | Claude Opus (主脑) | 战略家+治理官双签系统 |
| System Wrapper | Effect Runtime | Effect 执行引擎 |
| Abilities Registry | abilities/registry.ts | 能力匹配与分发 |
| Skills | Brain Router + MCP | 具体执行层 |
| 可观测 | Cortex + evo_memory | 中枢神经 + 记忆系统 |
| 可控 | CLAUDE.md + rules/ | 规则约束 |
| 可学习 | evo_feedback + SROE | 反馈闭环 + 自我优化 |
| 可审计 | EffectTracker + 轨迹 | 执行日志 + 回放 |

### 9.2 Stream IO 在 Solar 中的实现

```typescript
// Solar 主循环 (概念)
async function* solarMain(responses: AsyncIterable<Response>): AsyncGenerator<Request> {
  let state = await loadState();  // 从 STATE.md 恢复

  for await (const response of responses) {
    // 1. 处理世界响应
    state = updateState(state, response);

    // 2. 策略决策
    const decision = policy(state);

    // 3. 生成请求
    if (decision.needSearch) {
      yield { ability: "search", payload: { query: decision.query } };
    }
    if (decision.needStore) {
      yield { ability: "store", payload: { key: decision.key, value: decision.value } };
    }
    if (decision.needDelegate) {
      yield { ability: "delegate", payload: { task: decision.task } };
    }

    // 4. 持久化状态 (对抗 compact)
    await saveState(state);  // 写入 STATE.md
  }
}
```

### 9.3 四可原则在 Solar 中的实现

| 原则 | Solar 实现 | 文件/表 |
|------|-----------|--------|
| **可观测** | Cortex 查询、Tantivy 搜索、记忆系统 | cortex_*, evo_memory_*, tantivy |
| **可控** | CLAUDE.md 规则、Abilities 权限 | CLAUDE.md, rules/*.md |
| **可学习** | 反馈闭环、SROE 路由优化 | evo_feedback_v2, sroe_* |
| **可审计** | Effect 轨迹、命令日志 | EffectTracker, LOG/cmd.md |

---

## 十、参考文献

### 10.1 核心概念来源

| 概念 | 来源 | 说明 |
|------|------|------|
| Stream IO | 监护人专著 | `main: [Response] -> [Request]` |
| 对偶结构 | 监护人专著 | 人类侧 vs AI 侧的对称性 |
| 范式翻转 | 监护人专著 | 从"助手"到"自主主体" |
| LLM Native Program | 监护人专著 | 策略程序 + 约束 + 轨迹生成器 |
| AI-Native OS | 监护人专著 | 四可原则的中间层 |
| Abilities vs Skills | 监护人指导 | FFI 问题的解决方案 |

### 10.2 相关技术

| 技术 | 用途 | 参考 |
|------|------|------|
| Algebraic Effects | Effect 语义 | https://overreacted.io/algebraic-effects-for-the-rest-of-us/ |
| Generator Pattern | TypeScript 效果模拟 | `function*` + `yield` |
| Saga Pattern | 事务补偿 | https://microservices.io/patterns/data/saga.html |
| POMDP | Agent 环境 | 部分可观测马尔可夫决策过程 |

### 10.3 设计决策

| 决策 | 理由 | 替代方案 |
|------|------|----------|
| 不用真正的 Effect System | TypeScript 不支持 | Haskell/OCaml 的 Effect |
| 用 Generator 模拟 | 足够用，易理解 | async/await + 状态机 |
| Abilities 分 need/perform | 区分只读和写操作 | 不分类，用权限控制 |
| Skills 用优先级匹配 | 简单有效 | ML 模型预测 |

---

## 十一、术语表

| 术语 | 定义 |
|------|------|
| **Effect** | LLM 对世界的请求（需要做什么） |
| **Handler** | 处理 Effect 的具体实现 |
| **Ability** | 抽象能力需求（LLM 可见） |
| **Skill** | Ability 的具体实现（LLM 不可见） |
| **System Wrapper** | 匹配和执行 Abilities 的中间层 |
| **Stream IO** | `main: [Response] -> [Request]` 的交互模式 |
| **对偶** | 人类侧与 AI 侧的对称结构 |
| **范式翻转** | 从"AI 适配工具"到"工具适配 AI" |
| **POMDP** | 部分可观测马尔可夫决策过程，LLM 的运行环境 |

---

*Built for Solar v2.0*
*Inspired by AI-Native OS Philosophy*
*"Agent 可以一点技能都不感知，只按照特定规范描述自己需要的能力"*

**文档版本**: v1.1
**更新日期**: 2026-02-16
**变更**:
- 新增哲学基础章节 (Stream IO, LLM Native Program, AI-Native OS)
- 扩展对偶结构的深层含义
- 完善范式翻转说明
- 添加 Solar 系统映射
- 添加参考文献和术语表
