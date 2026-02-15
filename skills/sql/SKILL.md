# /sql - 数据库查询助手

## 触发
- `/sql <查询描述>` - 自然语言查询
- `/sql tables` - 列出所有表
- `/sql schema <表名>` - 查看表结构
- `/sql <SQL语句>` - 直接执行 SQL

## 数据库位置

```
~/.solar/solar.db
```

## 执行

### 列出所有表

```bash
sqlite3 ~/.solar/solar.db ".tables"
```

### 查看表结构

```bash
sqlite3 ~/.solar/solar.db ".schema $TABLE_NAME"
```

### 常用查询模板

```sql
-- 工具使用统计
SELECT tool_name, COUNT(*) as cnt,
       SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success
FROM evo_tool_calls
GROUP BY tool_name
ORDER BY cnt DESC;

-- 技能熟练度
SELECT skill_name, usage_count, dreyfus_level
FROM ses_skill_proficiency
ORDER BY usage_count DESC;

-- 记忆统计
SELECT 'episodic' as layer, COUNT(*) FROM evo_memory_episodic
UNION ALL SELECT 'semantic', COUNT(*) FROM evo_memory_semantic
UNION ALL SELECT 'procedural', COUNT(*) FROM evo_memory_procedural;

-- 学习信号
SELECT signal_type, COUNT(*) as cnt
FROM evo_learning_signals
GROUP BY signal_type;

-- 任务记录
SELECT task_type, COUNT(*) as cnt, AVG(quality_score) as avg_quality
FROM ses_task_records
GROUP BY task_type;

-- 评估历史
SELECT run_type, overall_score, completed_at
FROM ses_evaluation_runs
WHERE status = 'completed'
ORDER BY completed_at DESC LIMIT 10;
```

### 自然语言映射

| 描述 | SQL |
|------|-----|
| "工具使用情况" | SELECT tool_name, COUNT(*) ... |
| "最近的记忆" | SELECT * FROM evo_memory_episodic ORDER BY occurred_at DESC |
| "评估分数" | SELECT * FROM ses_evaluation_runs |
| "技能等级" | SELECT * FROM ses_skill_proficiency |
| "学习了什么" | SELECT * FROM evo_learning_signals |

## 核心表说明

| 表名 | 用途 |
|------|------|
| evo_tool_calls | 工具调用记录 |
| evo_memory_episodic | 情景记忆 |
| evo_memory_semantic | 语义记忆 |
| evo_memory_procedural | 程序记忆 |
| evo_learning_signals | 学习信号 |
| ses_skill_proficiency | 技能熟练度 |
| ses_evaluation_runs | 评估运行 |
| ses_recommendations | 改进建议 |
| ses_task_records | 任务记录 |
| sys_scripts | REE 脚本 |

## 安全

- 只允许 SELECT 查询
- 禁止 DROP/DELETE/TRUNCATE
- 自动备份重要操作
