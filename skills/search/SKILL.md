# /search - Solar 全文搜索

> 使用 Tantivy 高性能搜索引擎查找对话历史、记忆、代码等

## 用法

```bash
/search <query>                    # 搜索所有内容
/search <query> -t conversation    # 只搜索对话
/search <query> -t memory          # 只搜索记忆
/search <query> -t registry        # 只搜索技能/脚本/Agent
/search <query> --limit 20         # 限制结果数量
/search <query> --json             # JSON 输出
```

## 文档类型 (-t)

| 类型 | 说明 |
|------|------|
| `conversation` | Claude Code 对话历史 |
| `memory` | 语义/情景/程序记忆 |
| `registry` | Skills、Scripts、Agents |
| `code` | 代码片段 |
| `document` | 文档文件 |

## 执行方式

调用 `~/Solar/bin/solar-search` CLI:

```bash
~/Solar/bin/solar-search query "<query>" [--limit N] [-t TYPE] [--format pretty|json]
```

## 示例

1. **搜索性能优化相关内容**
   ```
   /search 性能优化
   ```

2. **搜索 GPU 相关对话**
   ```
   /search GPU -t conversation
   ```

3. **搜索记忆中的偏好设置**
   ```
   /search 偏好 preference -t memory
   ```

4. **搜索已注册的 Skill**
   ```
   /search commit review -t registry
   ```

## 索引来源

| 数据源 | 触发方式 | 说明 |
|--------|----------|------|
| ~/.claude/projects/**/*.jsonl | File Watcher | 对话历史 |
| evo_memory_semantic | SQLite Trigger | 语义记忆 |
| evo_memory_episodic | SQLite Trigger | 情景记忆 |
| evo_memory_procedural | SQLite Trigger | 程序记忆 |
| sys_skills | SQLite Trigger | 技能注册 |
| sys_scripts | SQLite Trigger | 脚本注册 |
| sys_agents | SQLite Trigger | Agent 注册 |

## 管理命令

```bash
# 查看索引状态
~/Solar/bin/solar-search stats

# 手动处理队列
~/Solar/bin/solar-search process

# 重建对话索引
~/Solar/bin/solar-search index conversations

# 启动守护进程 (持续监控)
~/Solar/bin/solar-search daemon
```

## 性能

- 索引: 15,000+ 文档
- 查询延迟: <10ms
- 支持中文分词 (jieba)
- 实时增量索引
