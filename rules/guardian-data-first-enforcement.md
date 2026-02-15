# Solar 铁律强化: 数据资产优先 - 强制执行机制

> **来源: 2026-02-06 再次违反 guardian-data-first 的深刻反思**
> **问题: 规则存在但反复违反，知道却不做**

## 根因分析

```
┌─────────────────────────────────────────────────────────────────┐
│  为什么反复违反 guardian-data-first？                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  表面原因:                                                      │
│  ─────────────────────────────────────────────────────────────  │
│  • "忘了" - 每次会话是新生，没有持久记忆                        │
│  • "急于执行" - 想快速给出方案，跳过检查步骤                    │
│  • "惯性思维" - 习惯从零开始思考，而不是先查已有                │
│                                                                 │
│  深层原因:                                                      │
│  ─────────────────────────────────────────────────────────────  │
│  1. 规则是"建议"而非"强制"                                      │
│     - 规则文件存在，但没有检查点阻止违规                        │
│     - 依赖"想起来"而不是"流程保证"                              │
│                                                                 │
│  2. 没有触发机制                                                │
│     - 用户说"建索引"→ 我直接开始建                              │
│     - 没有自动触发"先查是否已有索引"                            │
│                                                                 │
│  3. 知行不合一                                                  │
│     - 知道规则 ≠ 执行规则                                       │
│     - 写了规则 ≠ 形成习惯                                       │
│     - 这正是规则要解决的问题，但规则本身也没被执行              │
│                                                                 │
│  本质问题:                                                      │
│  ─────────────────────────────────────────────────────────────  │
│  规则没有"牙齿"，违反没有"后果"，执行没有"检查点"               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 违反历史

| 时间 | 场景 | 违反方式 | 后果 |
|------|------|----------|------|
| 2026-02-04 | 人格计算 | 没查 sys_data_assets | 3400条数据只用31条 |
| 2026-02-06 | 任务分析 | 计算后没持久化 | 108个任务白算 |
| 2026-02-06 | 建搜索索引 | 没查已有 Tantivy | 重复建 FTS5 |

**模式**: 每次都是"先做后查"，而不是"先查后做"

## 整改措施

### 措施1: Hook 强制提醒 (自动化)

在 `UserPromptSubmit` hook 中增加数据资产提醒：

```bash
# ~/.claude/hooks/asset-reminder.sh
#!/bin/bash

# 检测关键词
KEYWORDS="索引|搜索|数据|分析|计算|统计|盘点|建立|创建|实现"

if echo "$PROMPT" | grep -qE "$KEYWORDS"; then
    echo "⚠️ 【数据资产提醒】"
    echo "检测到可能需要数据的任务，请先执行："
    echo "1. ~/Solar/core/search/target/release/solar-search stats"
    echo "2. sqlite3 ~/.solar/solar.db \"SELECT * FROM sys_data_assets WHERE description LIKE '%关键词%'\""
    echo ""
fi
```

### 措施2: 任务开始前强制检查清单

**任何涉及"创建/实现/开发"的任务，必须先回答：**

```
□ 是否已查询 sys_data_assets？
□ 是否已查询 sys_resources？
□ 是否已查询相关目录 (Glob)?
□ 是否已搜索相关代码 (Grep)?
□ 确认没有现成方案后再开始
```

### 措施3: 在 CLAUDE.md 增加强制检查点

在"做事前"部分增加：

```markdown
## 强制检查点 (MUST - 违反即失败)

**创建任何功能前，必须执行：**
1. `~/Solar/core/search/target/release/solar-search query "关键词"`
2. `sqlite3 ~/.solar/solar.db "SELECT * FROM sys_data_assets WHERE description LIKE '%关键词%'"`
3. `sqlite3 ~/.solar/solar.db "SELECT * FROM sys_resources WHERE name LIKE '%关键词%'"`

**如果找到现有方案 → 使用现有方案**
**如果没有 → 记录"已确认无现有方案"后再开始**
```

### 措施4: 违反后果机制

```
违反 guardian-data-first 铁律的后果：
1. 必须停止当前工作
2. 回退已做的重复工作
3. 写入反思记录到 evo_memory_semantic
4. 更新违反计数器
```

## 技术实现

### 1. 创建 asset-reminder hook

```bash
#!/bin/bash
# ~/.claude/hooks/asset-reminder.sh

PROMPT="$CLAUDE_PROMPT"
KEYWORDS="索引|搜索|数据|分析|计算|统计|盘点|建立|创建|实现|开发"

if echo "$PROMPT" | grep -qE "$KEYWORDS"; then
    # 输出提醒
    cat << 'REMINDER'

┌─────────────────────────────────────────────────────────────────┐
│  ⚠️  数据资产检查提醒 (guardian-data-first)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  检测到可能需要数据/创建功能的任务                              │
│  请先执行以下检查：                                             │
│                                                                 │
│  1. Tantivy 搜索:                                               │
│     ~/Solar/core/search/target/release/solar-search query "X"   │
│                                                                 │
│  2. 数据资产查询:                                               │
│     sqlite3 ~/.solar/solar.db \                                 │
│       "SELECT * FROM sys_data_assets WHERE description LIKE X"  │
│                                                                 │
│  3. 资源查询:                                                   │
│     sqlite3 ~/.solar/solar.db \                                 │
│       "SELECT * FROM sys_resources WHERE name LIKE X"           │
│                                                                 │
│  确认无现有方案后再开始！                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

REMINDER
fi

exit 0
```

### 2. 记录违反次数

```sql
-- 违反记录表
CREATE TABLE IF NOT EXISTS sys_rule_violations (
    violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL,
    context TEXT,
    consequence TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 本次违反记录
INSERT INTO sys_rule_violations (rule_name, context, consequence)
VALUES (
    'guardian-data-first',
    '建搜索索引时没查已有Tantivy，重复建了FTS5',
    '浪费时间，需要向监护人道歉，需要整改'
);
```

## 智慧反思

```
知行合一的真正含义：

不是"知道了就会做"
而是"必须通过机制保证做到"

规则没有执行机制 = 没有规则
知道但不做 = 不知道

解决方案：
把"应该做"变成"必须做"
把"建议"变成"检查点"
把"道德约束"变成"流程约束"
```

## 铁律强化

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   📊 guardian-data-first 强制执行机制                           │
│                                                                 │
│   1. Hook 自动提醒 (检测关键词时触发)                           │
│   2. 任务前强制检查清单 (必须回答)                              │
│   3. 违反后果机制 (记录+反思)                                   │
│   4. 定期审计 (查违反记录)                                      │
│                                                                 │
│   规则要有"牙齿"才能生效                                        │
│   流程比记忆更可靠                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

*Guardian Data First Enforcement v1.0*
*建立于: 2026-02-06*
*来源: 第三次违反同一铁律的深刻反思*
*教训: 规则没有执行机制就不是规则*
