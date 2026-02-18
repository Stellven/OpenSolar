# Solar 三层知识库同步架构设计

## 设计目标
将知识从 Level 1 自动流向 Level 3，形成完整的知识网络。

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│              🔄 三层知识库同步机制                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Level 1: sys_favorites (高价值存档)                            │
│     └─ 原始内容: 分析报告、设计文档、专家会审                    │
│              │                                                  │
│              ▼ 提取: 实体识别 + 关系抽取 + 规则提取              │
│                                                                 │
│  Level 2: Cortex (中枢神经)                                     │
│     └─ 结构化来源: sources, artifacts, claims                   │
│              │                                                  │
│              ▼ 存储: 向量化 + 索引                              │
│                                                                 │
│  Level 3: Knowledge Graph (知识图谱)                            │
│     ├─ entities: 实体 (人物/技术/概念/组织)                     │
│     ├─ relations: 关系 (created_by/is_a/contains/influences)    │
│     └─ claims: 结论 (可信度 + 证据链)                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 实体识别模式

| 类型 | 匹配规则 | 示例 |
|------|----------|------|
| person | 人名模式 | 黄仁勋, Musk, Thiel |
| technology | 技术术语 | LLM, GPU, MLX, Transformer |
| concept | 概念名词 | 人格, Big Five, 控制论 |
| organization | 组织名称 | NVIDIA, OpenAI, Google |
| framework | 框架名称 | Solar, Cortex, REE |
| rule | 规则关键词 | 铁律, 法则, 原则 |

## 关系抽取模式

| 关系类型 | 模式 | 示例 |
|----------|------|------|
| created_by | 发明/创建/设计/提出 | Wiener 创立 控制论 |
| is_a | 属于/是...之一 | GPU 是 硬件 |
| contains | 包含/包括/由 | Solar 包含 Cortex |
| influences | 影响/决定/导致 | 人格 影响 输出 |
| better_than | 优于/快于/高于 | 4-bit 优于 8-bit |

## 实现文件

- **同步脚本**: `~/.claude/core/knowledge-sync/sync-knowledge.ts`
- **定时任务**: `~/Library/LaunchAgents/com.solar.knowledge-sync.plist`
- **执行时间**: 每天凌晨 3:00
- **日志位置**: `/tmp/solar-knowledge-sync.log`

## 数据库 Schema 扩展

```sql
-- sys_favorites 新增字段
ALTER TABLE sys_favorites ADD COLUMN synced_to_graph INTEGER DEFAULT 0;

-- knowledge_entities 新增字段
ALTER TABLE knowledge_entities ADD COLUMN source_favorite_id INTEGER;
```

## 同步流程

1. 扫描未同步的 sys_favorites (synced_to_graph = 0)
2. 按重要性排序，每次处理最多 50 条
3. 对每条内容:
   a. 提取实体 → 注入 knowledge_entities
   b. 提取关系 → 注入 knowledge_relations
   c. 提取结论 → 注入 knowledge_claims
4. 标记 synced_to_graph = 1
5. 输出统计报告

## 首次同步结果 (2026-02-17)

| 指标 | 数量 |
|------|------|
| 处理 favorites | 50 |
| 注入实体 | 186 |
| 注入关系 | 1 |
| 注入结论 | 46 |

## 当前知识库状态

| 知识库 | 数量 |
|--------|------|
| sys_favorites | 80 |
| knowledge_entities | 252 |
| knowledge_relations | 1744 |
| knowledge_claims | 701 |

## 运维命令

```bash
# 手动执行同步
bun ~/.claude/core/knowledge-sync/sync-knowledge.ts

# 查看定时任务状态
launchctl list | grep knowledge-sync

# 查看同步日志
tail -f /tmp/solar-knowledge-sync.log

# 强制重新同步 (重置标记)
sqlite3 ~/.solar/solar.db "UPDATE sys_favorites SET synced_to_graph = 0"
```
