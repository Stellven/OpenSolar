# Solar 铁律: REE First (资源优先)

> **生成代码前必须先查询 REE，禁止重复造轮子**

## 铁律定义

```
┌─────────────────────────────────────────────────────────────────┐
│                    REE FIRST PROTOCOL                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   当用户请求需要执行代码/脚本时:                                  │
│                                                                 │
│   1. 先查询 REE 是否有匹配资源                                   │
│   2. 有匹配 → 直接使用已有资源                                   │
│   3. 无匹配 → 生成新代码 → 注册到 REE                            │
│                                                                 │
│   ❌ 禁止: 跳过查询直接写代码                                    │
│   ❌ 禁止: 生成代码后不注册                                      │
│   ❌ 禁止: 重复实现已有功能                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 强制执行流程

```
用户请求 "帮我查HN热门"
         │
         ▼
┌─────────────────┐
│ Step 1: 查询REE │ ← 必须执行
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
[有匹配]   [无匹配]
    │         │
    ▼         ▼
使用现有   生成代码
    │         │
    │         ▼
    │    ┌──────────┐
    │    │ 注册REE  │ ← 必须执行
    │    └────┬─────┘
    │         │
    └────┬────┘
         ▼
      执行
```

## 统一架构 (v2.0)

```
REE (唯一入口) → TieredRouter (智能路由)
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       L1 关键词   L2 语义     L3 LLM
       (0 成本)   ($0.0001)   ($0.01)
```

## 查询命令

**在处理任何可能需要代码的请求前，执行:**

```bash
# 方法1: 使用统一入口 (推荐)
bun ~/.claude/core/ree/index.ts match "用户请求"

# 方法2: 使用分层路由器 (详细信息)
bun ~/.claude/core/ree/tiered-router.ts route "用户请求"

# 方法3: 直接查数据库
sqlite3 ~/.solar/solar.db "
SELECT name, description, file_path
FROM sys_scripts
WHERE description LIKE '%关键词%'
   OR intent_keywords LIKE '%关键词%'
LIMIT 5;
"

# 验证 Shortcuts 安装状态
bun ~/.claude/core/ree/test-shortcuts.ts list
```

## 已注册资源 (快速参考)

| ID | 名称 | 功能 | 调用方式 |
|----|------|------|----------|
| weather-fetch | 天气查询 | 获取城市天气+预报 | `bun ~/.claude/core/ree/scripts/9416537535f2.ts [城市]` |
| hn-monitor | HN监控 | 抓取热门话题 | `bun ~/.claude/skills/hn-monitor/fetch.ts [--save]` |
| ppt-generator | PPT生成 | Markdown→HTML | `bun ~/.claude/skills/ppt/ppt.ts <file.md>` |
| backlog-manager | 待办管理 | 项目任务管理 | `bun ~/.claude/skills/backlog/backlog.ts <cmd>` |
| skill-generator | Skill生成 | 从模板创建Skill | `bun ~/.claude/skill-templates/skill-gen.ts` |
| web-page-gen | 页面注册 | Dashboard页面 | `bun ~/.claude/web/generate.ts register <file>` |

## 关键词索引

快速判断是否有现成资源:

| 关键词 | 可能匹配 |
|--------|----------|
| 天气/气温/weather | weather-fetch |
| HN/Hacker News/热门/技术新闻 | hn-monitor |
| PPT/演示/幻灯片/汇报 | ppt-generator |
| 待办/任务/backlog/todo | backlog-manager |
| 生成Skill/创建Skill | skill-generator |
| 页面/dashboard/注册 | web-page-gen |

## 代码生成后注册

**如果确实需要生成新代码，完成后必须注册:**

```typescript
// 使用 code-cache.ts
import { quickCache } from '~/.claude/core/ree/code-cache';

await quickCache(
  engine,
  '功能描述',
  ['关键词1', '关键词2'],
  generatedCode,
  'bun'  // 运行时
);
```

或手动 SQL:

```sql
INSERT INTO sys_scripts (
  script_id, name, description, intent_keywords,
  runtime, file_path, status, source
) VALUES (
  'unique-id',
  'script-name',
  '功能描述',
  '["关键词1", "关键词2"]',
  'bun',
  '文件路径',
  'active',
  'generated'
);
```

## 违反后果

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚠️ 违反 REE First 规则将导致:                                   │
│                                                                 │
│  1. Token 浪费 - 重复生成已有功能                                │
│  2. 维护负担 - 多份代码做同一件事                                │
│  3. 质量风险 - 新代码未经验证                                    │
│                                                                 │
│  每次违反都是对经济法则的背离                                    │
└─────────────────────────────────────────────────────────────────┘
```

## 自检清单

在生成任何代码前，回答:

- [ ] 我查询 REE 了吗？
- [ ] 确实没有匹配的资源吗？
- [ ] 生成后我会注册到 REE 吗？

## 示例

### ✅ 正确流程

```
用户: "帮我查一下北京天气"

Solar:
1. 查询 REE: bun tiered-router.ts route "查北京天气"
2. 结果: 匹配 weather-fetch (L1, 80%)
3. 执行: bun ~/.claude/core/ree/scripts/9416537535f2.ts 北京
4. 返回结果
```

### ❌ 错误流程

```
用户: "帮我查一下北京天气"

Solar:
1. 直接写代码: fetch("https://wttr.in/Beijing")
2. ❌ 没查 REE
3. ❌ 重复实现
4. ❌ 没注册
```

---

*REE First Protocol v1.0*
*知行合一 - 不重复造轮子*
