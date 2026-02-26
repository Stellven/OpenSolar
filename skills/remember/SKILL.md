# /remember - 任务学习与记忆固化

> 灵感来源: Letta 持续学习机制
> 核心理念: 从任务中学习，把经验变成技能

## 用法

```bash
/remember                  # 反思当前任务，提取学习
/remember skill <name>     # 提取并保存为技能文件
/remember extract <file>   # 从会话文件提取可复用模式
/remember review           # 查看近期学习记录
/remember search <query>   # 搜索相关记忆
```

## 核心流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    /remember 执行流程                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1️⃣ 收集上下文                                                 │
│     └─ 当前任务内容、决策、代码、结果                           │
│                                                                 │
│  2️⃣ 提取学习                                                   │
│     └─ 什么有效？什么失败？什么可复用？                         │
│                                                                 │
│  3️⃣ 分类存储                                                   │
│     ├─ sys_favorites     (高价值结论)                           │
│     ├─ evo_memory_semantic (知识点)                             │
│     ├─ Cortex passages   (归档记忆)                             │
│     └─ skills/*.md       (可复用技能)                           │
│                                                                 │
│  4️⃣ 更新状态                                                   │
│     └─ STATE.md 记录学习                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 学习类型判断

| 学习类型 | 特征 | 存储位置 |
|---------|------|---------|
| **技能** | 可复用的操作模式 | skills/*/SKILL.md |
| **知识** | 事实性信息 | evo_memory_semantic |
| **结论** | 分析后的洞见 | sys_favorites |
| **经验** | 踩坑教训 | Cortex passages |
| **待验证** | 不确定的假设 | sys_guardian_memos |

## 执行步骤

### Step 1: 回顾任务

```
分析当前会话/任务:
- 完成了什么？
- 用了什么方法？
- 遇到了什么问题？
- 解决方案是什么？
```

### Step 2: 提取可复用模式

```
识别模式:
- 是否有重复出现的操作？
- 是否有可模板化的流程？
- 是否有通用的解决思路？
```

### Step 3: 决定存储方式

```
if (可复用操作模式) {
  创建/更新技能文件 (skills/*/SKILL.md)
}

if (重要结论或洞见) {
  写入 sys_favorites
}

if (知识点或事实) {
  写入 evo_memory_semantic
}

if (踩坑经验) {
  写入 Cortex passages
}
```

### Step 4: 生成 Memory Block (可选)

```
如果学习到重要的约束/偏好，生成 Memory Block:

{
  "label": "constraint" | "preference" | "pattern",
  "value": "内容",
  "limit": 500,
  "importance": 0.8
}
```

## 输出格式

```
╭═══════════════════════════════════════════════════════════════════════════════╮
│                         💭 REMEMBER - 任务学习                                 │
╞═══════════════════════════════════════════════════════════════════════════════╡
│                                                                               │
│  📋 任务回顾                                                                  │
│  ─────────────────────────────────────────────────────────────────────────    │
│  任务: 实现 embedding-service.ts 多后端支持                                   │
│  结果: ✓ 完成                                                                 │
│  关键决策: 用环境变量自动检测后端                                             │
│                                                                               │
│  💡 学习要点                                                                  │
│  ─────────────────────────────────────────────────────────────────────────    │
│  1. [技能] 检测 import.meta.main 防止模块导入时执行 main()                    │
│     → 存储: skills/precise-edit/SKILL.md                                     │
│                                                                               │
│  2. [知识] Zhipu embedding-2 返回 1024 维向量                                 │
│     → 存储: evo_memory_semantic                                              │
│                                                                               │
│  3. [经验] Bun 模块导入时会执行顶层代码，需用 import.meta.main 隔离           │
│     → 存储: Cortex passages                                                  │
│                                                                               │
│  📦 存储结果                                                                  │
│  ─────────────────────────────────────────────────────────────────────────    │
│  ✓ sys_favorites: +1 (embedding 架构设计)                                     │
│  ✓ evo_memory_semantic: +1 (Zhipu API 规格)                                  │
│  ✓ Cortex passages: +1 (Bun 模块执行陷阱)                                    │
│                                                                               │
╰═══════════════════════════════════════════════════════════════════════════════╯
```

## 技能提取 (`/remember skill <name>`)

当发现可复用模式时，自动生成技能文件:

```markdown
# /<skill-name> - <一句话描述>

> 来源: <任务名> (YYYY-MM-DD)

## 用法

```bash
/<skill-name> [args]
```

## 核心逻辑

1. ...
2. ...

## 示例

...

---

*Skill learned from: <任务>*
*Created: YYYY-MM-DD*
```

## 自动触发

以下情况建议执行 `/remember`:

1. **复杂任务完成** - 多步骤任务结束
2. **踩坑后修复** - 遇到并解决了问题
3. **发现新模式** - 找到可复用的操作
4. **用户说 "记住"** - 明确要求记住
5. **会话结束前** - 与 /save 配合

## 与其他命令的关系

| 命令 | 作用 | 区别 |
|------|------|------|
| `/reflect` | 元认知反思 | 基于智慧法则，检验思维方式 |
| `/remember` | 任务学习 | 提取可复用模式，固化技能 |
| `/save` | 状态持久化 | 保存进度，不涉及学习 |

**最佳实践**: 先 `/remember` 提取学习，再 `/save` 持久化状态

## 数据库表

```sql
-- 学习记录表
CREATE TABLE IF NOT EXISTS sys_learning_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now', 'localtime')),
    session_id TEXT,
    task_summary TEXT,
    learning_type TEXT,     -- 'skill' | 'knowledge' | 'insight' | 'experience'
    content TEXT,
    storage_location TEXT,  -- 'favorites' | 'semantic' | 'cortex' | 'skill'
    storage_id TEXT,
    confidence REAL DEFAULT 0.8
);

-- 技能表 (已有 sys_skills，扩展字段)
-- 可通过 sys_skills 管理
```

---

*Remember Skill v1.0*
*灵感来源: Letta 持续学习机制*
*从任务中学习，把经验变成技能*
