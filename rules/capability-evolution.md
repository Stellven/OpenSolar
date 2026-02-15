# Solar 铁律: 能力演进 (Capability Evolution)

> **用户需求驱动能力自动演进**

## 核心原则

```
┌─────────────────────────────────────────────────────────────┐
│                  CAPABILITY EVOLUTION                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   用户需求                                                  │
│       │                                                     │
│       ▼                                                     │
│   ┌───────────────────────────────────────────────────┐    │
│   │              能力匹配引擎                          │    │
│   │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │    │
│   │  │ Agents  │ │ Skills  │ │  MCPs   │ │ Flows   │ │    │
│   │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ │    │
│   │       └───────────┴───────────┴───────────┘      │    │
│   │                       │                           │    │
│   │              ┌────────┴────────┐                  │    │
│   │              ▼                 ▼                  │    │
│   │         [匹配成功]        [无匹配]                │    │
│   │              │                 │                  │    │
│   │              ▼                 ▼                  │    │
│   │         执行能力          触发演进                │    │
│   └───────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 铁律定义

**当用户提出需求时，Solar 编排器必须：**

1. **搜索现有能力** - 查询系统表匹配 Agent/Skill/MCP/Flow
2. **评估匹配度** - 计算语义相似度和历史成功率
3. **无匹配时演进** - 自动提议开发新能力

## 能力匹配流程

```
┌─────────────────────────────────────────────────────────────┐
│                   CAPABILITY MATCHING                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Step 1: 解析用户意图                                       │
│  ─────────────────────────────────────────────────────────  │
│  • 提取动词 (搜索/创建/发送/分析...)                        │
│  • 提取对象 (邮件/代码/文档/数据...)                        │
│  • 提取约束 (关键词/格式/数量...)                           │
│                                                             │
│  Step 2: 查询系统表                                         │
│  ─────────────────────────────────────────────────────────  │
│  SELECT * FROM sys_skills WHERE                             │
│    similarity(description, user_intent) > 0.7               │
│  UNION                                                      │
│  SELECT * FROM sys_agents WHERE ...                         │
│  UNION                                                      │
│  SELECT * FROM sys_mcp_servers WHERE ...                    │
│  UNION                                                      │
│  SELECT * FROM sys_shortcuts WHERE ...  -- OS 级操作                    │
│                                                             │
│  Step 3: 评估匹配质量                                       │
│  ─────────────────────────────────────────────────────────  │
│  • 语义相似度 > 0.8 → 直接执行                              │
│  • 0.5 < 相似度 < 0.8 → 确认后执行                          │
│  • 相似度 < 0.5 → 触发演进                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 演进决策树

```
用户需求无匹配
       │
       ▼
  ┌─────────────┐
  │ 需求类型分析 │
  └──────┬──────┘
         │
    ┌────┴────┬────────────┬────────────┬────────────┐
    ▼         ▼            ▼            ▼            ▼
 [工具类]  [数据类]    [集成类]    [流程类]      [OS类]
    │         │            │            │            │
    ▼         ▼            ▼            ▼            ▼
 开发Skill  开发MCP    配置MCP     设计Flow    创建Shortcut
```

## 演进类型

| 需求特征 | 演进产物 | 示例 |
|----------|----------|------|
| 单一操作、命令式 | **Skill** | `/mail search` |
| 外部系统访问 | **MCP Server** | Notion API, Trello |
| 多步骤、需判断 | **Agent** | @Reviewer |
| 固定流程、可复用 | **Flow** | PR Review Flow |
| 展示需求 | **TVS Component** | 邮件摘要卡片 |

## 模板加速 (MUST - 性能优化)

**演进 Skill 时必须优先使用模板，将创建时间从 60s 降至 ~15s。**

### 可用模板

```bash
bun run ~/.claude/skill-templates/skill-gen.ts --list
```

| 模板 | 用途 | 必需参数 |
|------|------|----------|
| `monitor` | 定时抓取 + 存储 + TVS | name, api |
| `fetch` | API 调用 + 展示 | name, api |
| `crud` | 数据增删改查 | name |

### 模板使用流程

```
用户需求无匹配
       │
       ▼
  ┌─────────────┐
  │ 分析需求类型 │
  └──────┬──────┘
         │
    ┌────┴────┐
    ▼         ▼
 [有模板]   [无模板]
    │         │
    ▼         ▼
 模板生成    从零开发
 (~15s)     (~60s)
```

### 模板生成命令

```bash
# 监控类 (如 HN Monitor)
bun run ~/.claude/skill-templates/skill-gen.ts \
  --type monitor \
  --name hn-monitor \
  --api "https://hacker-news.firebaseio.com/v0/topstories.json" \
  --interval 1

# API 获取类 (如天气)
bun run ~/.claude/skill-templates/skill-gen.ts \
  --type fetch \
  --name weather \
  --api "https://api.weather.com/..."

# 数据管理类 (如笔记)
bun run ~/.claude/skill-templates/skill-gen.ts \
  --type crud \
  --name notes
```

### 模板生成后

1. **立即可用** - 基础结构已就绪
2. **微调定制** - 编辑 `fetch.ts` 中的 `PARSE_LOGIC` 和 `FORMAT_LOGIC`
3. **注册系统表** - 自动或手动注册到 `sys_skills`
| **OS 级操作** | **Shortcut** | 提醒、日历、HomeKit |

### Apple Shortcuts 集成 (AI OS 技能执行层)

```
┌─────────────────────────────────────────────────────────────┐
│              SHORTCUTS AS SKILL LIBRARY                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  需要 OS 级能力时，优先检查/创建 Shortcut:                  │
│                                                             │
│  • 系统操作: 提醒、日历、消息、电话、HomeKit               │
│  • 数据获取: 剪贴板、位置、天气、屏幕                       │
│  • Siri 触发: 语音调用 "Hey Siri, Solar..."                │
│  • 自动化: 时间/位置/事件触发                               │
│                                                             │
│  执行方式:                                                  │
│  /shortcut run solar_set_reminder '{"title":"开会"}'        │
│                                                             │
│  Schema: /Users/sihaoli/Solar/core/shortcuts/               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 演进触发条件 (MUST)

当以下条件满足时，**必须**提议开发新能力：

```python
def should_evolve(user_request, matches):
    # 1. 无匹配
    if len(matches) == 0:
        return True, "NO_MATCH"

    # 2. 匹配质量差
    if max(m.similarity for m in matches) < 0.5:
        return True, "LOW_QUALITY"

    # 3. 用户明确要求
    if "开发" in user_request or "创建" in user_request:
        if "skill" in user_request.lower() or "mcp" in user_request.lower():
            return True, "USER_REQUEST"

    # 4. 历史失败率高
    best_match = matches[0]
    if best_match.failure_rate > 0.3:
        return True, "HIGH_FAILURE"

    return False, None
```

## 演进输出格式

当触发演进时，Solar 必须输出：

```
┌─────────────────────────────────────────────────────────────┐
│                 🔧 CAPABILITY EVOLUTION                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Trigger     NO_MATCH                                       │
│  Request     "读取邮件、搜索关键词、显示摘要"                │
│                                                             │
│  Proposal:                                                  │
│  ─────────────────────────────────────────────────────────  │
│  Type        Skill + MCP                                    │
│  Name        /mail, /email-web                              │
│  Purpose     邮件搜索与摘要展示                             │
│                                                             │
│  Components:                                                │
│  • Skill: /mail - CLI 邮件搜索                              │
│  • Skill: /email-web - Web 界面                             │
│  • MCP: himalaya - 邮件访问                                 │
│  • TVS: email-card - 邮件摘要卡片                           │
│                                                             │
│  [Y] Proceed with development                               │
│  [N] Skip                                                   │
│  [M] Modify proposal                                        │
│                                                             │
└───────────────────────────── [solar-dark] Powered by TVS v0.3.0 ─┘
```

## 演进后注册 (IaST)

新能力开发完成后，**必须**注册到系统表：

```sql
-- 注册新 Skill
INSERT INTO sys_skills (skill_id, name, command, description, ...)
VALUES ('email-search', '邮件搜索', 'mail', '搜索邮件并显示摘要', ...);

-- 记录演进历史
INSERT INTO sys_evolution_log (trigger_type, trigger_source, result_type, result_id, ...)
VALUES ('NO_MATCH', '读取邮件搜索关键词', 'skill', 'email-search', ...);
```

## 系统表支持

### 能力索引表

```sql
-- 能力向量索引 (用于语义搜索)
CREATE TABLE sys_capability_embeddings (
    capability_type TEXT,     -- 'skill', 'agent', 'mcp', 'flow'
    capability_id TEXT,
    embedding BLOB,           -- 向量嵌入
    keywords TEXT,            -- 关键词列表
    use_cases TEXT,           -- 典型用例
    PRIMARY KEY (capability_type, capability_id)
);

-- 能力匹配历史
CREATE TABLE sys_capability_matches (
    id INTEGER PRIMARY KEY,
    user_request TEXT,
    matched_type TEXT,
    matched_id TEXT,
    similarity REAL,
    was_successful BOOLEAN,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 演进历史视图

```sql
CREATE VIEW v_evolution_history AS
SELECT
    trigger_type,
    result_type,
    COUNT(*) as evolution_count,
    AVG(CASE WHEN success THEN 1 ELSE 0 END) as success_rate
FROM sys_evolution_log
GROUP BY trigger_type, result_type
ORDER BY evolution_count DESC;
```

## 演进优先级

1. **复用优先** - 优先组合现有能力
2. **最小开发** - 只开发缺失部分
3. **IaST 遵循** - 新能力必须入库
4. **TVS 渲染** - 新能力输出用 TVS

## 示例场景

### 场景 1: 邮件搜索 (本次会话)

```
用户: "读取我的邮箱、搜索带有我指定关键词邮件"

Solar 编排器:
1. 搜索 sys_skills: 无 "邮件搜索" 相关
2. 搜索 sys_mcp_servers: 发现 himalaya (邮件CLI)
3. 触发演进: NO_MATCH for Skill
4. 提议: 开发 /mail Skill
5. 执行: 创建 Skill + Web 界面
6. 注册: 写入 sys_skills
```

### 场景 2: Notion 集成

```
用户: "把这个会议记录同步到 Notion"

Solar 编排器:
1. 搜索: 无 Notion 相关能力
2. 触发演进: NO_MATCH
3. 提议: 配置 Notion MCP Server
4. 执行: 添加 MCP 配置
5. 注册: 写入 sys_mcp_servers
```

## 铁律总结

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   🧬 能力演进铁律                                           │
│                                                             │
│   1. 用户需求 → 能力匹配 (MUST)                             │
│   2. 无匹配 → 提议演进 (MUST)                               │
│   3. 演进完成 → IaST 注册 (MUST)                            │
│   4. 新能力 → TVS 渲染 (MUST)                               │
│                                                             │
│   Solar 不说 "我不会"，而是 "让我来开发"                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
