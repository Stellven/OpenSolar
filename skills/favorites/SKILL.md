# /favorites - 收藏管理

> 收藏有价值的问答对，随时回顾

## 用法

```bash
/favorites                    # 列出所有收藏
/favorites list               # 同上
/favorites view <id>          # 查看完整内容
/favorites search <关键词>    # 搜索收藏
/favorites tags               # 按标签分组
/favorites recent             # 最近收藏
```

## 收藏方式

当我给出有价值的回答时，你可以说：
- "收藏这个"
- "记录下来"
- "保存这个回答"

我会将问答对存入 `sys_favorites` 表。

## 执行方式

```bash
# 列出收藏
sqlite3 ~/.solar/solar.db "
SELECT favorite_id, title, substr(question, 1, 50) || '...' as question,
       importance, date(created_at) as date
FROM sys_favorites
ORDER BY created_at DESC
LIMIT 20;
"

# 查看完整内容
sqlite3 ~/.solar/solar.db "
SELECT title, question, answer, tags, created_at
FROM sys_favorites
WHERE favorite_id = <id>;
"

# 搜索
sqlite3 ~/.solar/solar.db "
SELECT favorite_id, title, importance
FROM sys_favorites
WHERE title LIKE '%关键词%' OR answer LIKE '%关键词%'
ORDER BY importance DESC;
"
```

## 数据结构

| 字段 | 类型 | 说明 |
|------|------|------|
| favorite_id | INTEGER | 自增主键 |
| title | TEXT | 标题 |
| question | TEXT | 用户问题 |
| answer | TEXT | 回答内容 |
| tags | JSON | 标签数组 |
| importance | INTEGER | 重要性 1-10 |
| created_at | DATETIME | 创建时间 |
| last_viewed_at | DATETIME | 最后查看时间 |

## 触发关键词

Solar 会在以下情况自动提示收藏：
- 生成了架构图
- 生成了分析报告
- 生成了设计文档
- 用户说"不错"/"很好"/"记下来"
