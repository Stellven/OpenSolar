# /recall - 记忆快速检索

## 触发
- `/recall <关键词>` - 搜索所有记忆层
- `/recall episodic <关键词>` - 只搜情景记忆
- `/recall semantic <关键词>` - 只搜语义记忆
- `/recall procedural <关键词>` - 只搜程序记忆
- `/recall recent` - 最近的记忆

## 执行

### 搜索所有记忆

```bash
KEYWORD="$1"
sqlite3 ~/.solar/solar.db "
-- Episodic (情景记忆)
SELECT 'episodic' as layer, memory_id, content, occurred_at
FROM evo_memory_episodic
WHERE content LIKE '%${KEYWORD}%'
ORDER BY occurred_at DESC LIMIT 5;

-- Semantic (语义记忆)
SELECT 'semantic' as layer, memory_id, content, created_at
FROM evo_memory_semantic
WHERE content LIKE '%${KEYWORD}%' OR namespace LIKE '%${KEYWORD}%'
ORDER BY confidence DESC LIMIT 5;

-- Procedural (程序记忆)
SELECT 'procedural' as layer, memory_id, procedure_name, description
FROM evo_memory_procedural
WHERE procedure_name LIKE '%${KEYWORD}%' OR description LIKE '%${KEYWORD}%'
ORDER BY execution_count DESC LIMIT 5;
"
```

### 搜索特定层

```bash
# episodic
sqlite3 ~/.solar/solar.db "
SELECT event_type, content, occurred_at
FROM evo_memory_episodic
WHERE content LIKE '%${KEYWORD}%'
ORDER BY occurred_at DESC LIMIT 10;
"

# semantic
sqlite3 ~/.solar/solar.db "
SELECT namespace, content, confidence
FROM evo_memory_semantic
WHERE content LIKE '%${KEYWORD}%'
ORDER BY confidence DESC LIMIT 10;
"

# procedural
sqlite3 ~/.solar/solar.db "
SELECT procedure_name, description, execution_count
FROM evo_memory_procedural
WHERE procedure_name LIKE '%${KEYWORD}%' OR description LIKE '%${KEYWORD}%'
ORDER BY execution_count DESC LIMIT 10;
"
```

### 最近记忆

```bash
sqlite3 ~/.solar/solar.db "
SELECT 'episodic' as layer, content, occurred_at as time
FROM evo_memory_episodic
ORDER BY occurred_at DESC LIMIT 5
UNION ALL
SELECT 'semantic', content, created_at
FROM evo_memory_semantic
ORDER BY created_at DESC LIMIT 5;
"
```

## 输出格式

TVS 卡片显示检索结果:
- 记忆层标识 (episodic/semantic/procedural)
- 内容摘要
- 时间/相关度
- 使用次数 (procedural)

## 使用场景

| 场景 | 命令 |
|------|------|
| 找上次的 bug | `/recall bug` |
| 找规则 | `/recall semantic 规则` |
| 找工作流 | `/recall procedural commit` |
| 找最近做了什么 | `/recall recent` |
