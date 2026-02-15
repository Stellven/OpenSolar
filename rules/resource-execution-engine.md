# Solar 铁律: 资源执行引擎 (REE)

> **资源优先级 + 脚本缓存 = 高效执行**

## 核心原则

**执行任务时，按优先级逐层匹配资源，优先复用已有能力：**

```
P1 Shortcuts (~50ms)  → 最快，OS级操作
P2 Scripts   (~100ms) → 脚本缓存，历史复用
P3 Skills    (~200ms) → 命令式技能
P4 MCP       (~500ms) → 外部服务集成
P5 Agents    (~2s)    → 多步协作任务
P6 Code Gen  (~5s)    → 最后手段，生成后缓存
```

## 强制执行流程

**在执行任何需要调用本地资源的任务前，必须：**

### Step 1: 资源匹配

```typescript
// 在 ~/.claude/core/ree 中调用
import REE from '~/.claude/core/ree';
const ree = new REE();
const match = await ree.match(userRequest);
```

### Step 2: 按匹配结果执行

| 匹配类型 | 执行方式 |
|----------|----------|
| `shortcut` | `shortcuts run <name> '<json_params>'` |
| `script` | `ree.execute(match, params)` |
| `skill` | `/skill-name args` |
| `mcp` | 调用 MCP 工具 |
| `agent` | `@Agent` |
| `code` | 生成代码 → 缓存到引擎 |

### Step 3: 代码生成后必须缓存

**当 P6 触发代码生成时，必须将生成的代码注册到脚本引擎：**

```typescript
import { quickCache } from '~/.claude/core/ree/code-cache';

const scriptId = await quickCache(
  engine,
  '获取 HN 头条并发送邮件摘要',  // 描述
  ['HN', '头条', '邮件', '摘要'],  // 关键词
  generatedCode,                   // 代码
  'bun'                            // 运行时
);
```

## 匹配规则

### Shortcut 匹配 (P1)

优先匹配 Apple Shortcuts:

| 对象 | Shortcut |
|------|----------|
| 提醒/待办 | `solar_set_reminder` |
| 天气 | `solar_get_weather` |
| 消息/短信 | `solar_send_message` |
| 日历/日程 | `solar_calendar_event` |
| 笔记 | `solar_create_note` |
| 照片/自拍 | `solar_take_photo` |
| 家居/HomeKit | `solar_control_homekit` |

### Script 匹配 (P2)

查询脚本引擎缓存:

```sql
-- 关键词匹配
SELECT * FROM v_active_scripts
WHERE description LIKE '%关键词%'
ORDER BY hot_score DESC;

-- 语义匹配 (Phase 2)
SELECT * FROM sys_scripts s
JOIN sys_script_embeddings e ON s.script_id = e.script_id
WHERE cosine_similarity(e.embedding, query_vector) > 0.5;
```

### Skill 匹配 (P3)

精确匹配 `/command` 或关键词匹配:

```
/commit    → Git 提交
/weather   → 天气查询
/review    → 代码审查
/build     → 项目构建
...
```

### MCP 匹配 (P4)

```
邮件相关 → himalaya
浏览器相关 → playwright
Notion相关 → notion
Trello相关 → trello
```

### Agent 匹配 (P5)

```
技术调研 → @Researcher
架构设计 → @Architect
代码实现 → @Coder
测试验证 → @Tester
代码审查 → @Reviewer
```

## 热度排序

脚本按热度分数排序:

```
热度 = 频率×0.4 + 成功率×0.3 + 时效性×0.2 + 效率×0.1

- 频率: log(1+调用次数) / log(101) × 100
- 成功率: Wilson置信区间下界 × 100
- 时效性: e^(-0.1×天数) × 100 (7天半衰期)
- 效率: 500/(500+延迟) × 100
```

## 使用示例

```
用户: "帮我设置明天8点的提醒"

Solar 匹配流程:
1. 意图解析: action=create, object=reminder, params={time:"明天8点"}
2. P1 Shortcut 匹配: ✓ solar_set_reminder (0.8)
3. 执行: shortcuts run solar_set_reminder '{"title":"提醒","time":"..."}'
4. 结果: ✓ 已创建提醒 (52ms)

用户: "获取 HN 头条并发送邮件"

Solar 匹配流程:
1. 意图解析: action=fetch+send, object=unknown
2. P1-P5 无匹配
3. P6 触发代码生成
4. 生成 hn_email_summary.ts
5. 验证执行成功
6. 缓存到脚本引擎: script_id=abc123
7. 下次 "发HN摘要" → P2 直接匹配
```

## 禁止行为

- ❌ 跳过资源匹配直接写代码
- ❌ 生成代码后不缓存
- ❌ 重复生成相同功能的代码
- ❌ 忽略已有的 Shortcut/Script

## 文件位置

```
~/.claude/core/ree/
├── index.ts            # REE 主入口
├── resource-matcher.ts # 资源匹配引擎
├── script-engine.ts    # 脚本引擎
├── embedding-service.ts # 语义嵌入服务
├── code-cache.ts       # 代码缓存管理
├── hot-score.ts        # 热度算法
├── types.ts            # 类型定义
└── schema.sql          # 数据库 Schema

~/.claude/solar.db      # 系统数据库
```

## CLI 命令

```bash
# 匹配资源
bun ~/.claude/core/ree/index.ts match "你的请求"

# 列出脚本
bun ~/.claude/core/ree/index.ts scripts list

# 显示热门
bun ~/.claude/core/ree/index.ts scripts hot

# 清理过期
bun ~/.claude/core/ree/index.ts scripts cleanup 30

# 查看统计
bun ~/.claude/core/ree/index.ts stats
```

## 铁律总结

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   🔧 REE 铁律                                               │
│                                                             │
│   1. 执行前必须匹配资源 (MUST)                              │
│   2. 按优先级逐层匹配 (MUST)                                │
│   3. 代码生成后必须缓存 (MUST)                              │
│   4. 优先复用已有能力 (MUST)                                │
│                                                             │
│   Shortcut > Script > Skill > MCP > Agent > Code           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
