# /migrate - 数据迁移

## 触发
- `/migrate status` - 查看迁移状态
- `/migrate create <名称>` - 创建迁移
- `/migrate run` - 执行待处理迁移
- `/migrate rollback` - 回滚上次迁移
- `/migrate list` - 列出所有迁移

## 执行

### 查看状态

```bash
sqlite3 ~/.solar/solar.db "
SELECT
  id,
  name,
  applied_at,
  CASE WHEN applied_at IS NOT NULL THEN '✓' ELSE '○' END as status
FROM schema_migrations
ORDER BY id;
" 2>/dev/null || echo "无迁移记录表，需要初始化"
```

### 初始化迁移系统

```bash
sqlite3 ~/.solar/solar.db "
CREATE TABLE IF NOT EXISTS schema_migrations (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  sql_up TEXT NOT NULL,
  sql_down TEXT,
  applied_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"
echo "✓ 迁移系统已初始化"
```

### 创建迁移

```bash
NAME=$1
TIMESTAMP=$(date +%Y%m%d%H%M%S)
MIGRATION_DIR=~/.solar/migrations
mkdir -p "$MIGRATION_DIR"

# 创建迁移文件
cat > "$MIGRATION_DIR/${TIMESTAMP}_${NAME}.sql" << 'EOF'
-- Migration: ${NAME}
-- Created: $(date)

-- UP
-- 在此写入升级 SQL


-- DOWN
-- 在此写入回滚 SQL

EOF

echo "✓ 创建迁移: ${TIMESTAMP}_${NAME}.sql"
```

### 执行迁移

```bash
MIGRATION_DIR=~/.solar/migrations
DB=~/.solar/solar.db

for file in $(ls "$MIGRATION_DIR"/*.sql 2>/dev/null | sort); do
  MIGRATION_NAME=$(basename "$file" .sql)
  MIGRATION_ID=$(echo "$MIGRATION_NAME" | cut -d_ -f1)

  # 检查是否已执行
  APPLIED=$(sqlite3 "$DB" "SELECT COUNT(*) FROM schema_migrations WHERE id = $MIGRATION_ID AND applied_at IS NOT NULL;")

  if [ "$APPLIED" = "0" ]; then
    echo "执行迁移: $MIGRATION_NAME"

    # 提取 UP 部分
    SQL_UP=$(sed -n '/-- UP/,/-- DOWN/p' "$file" | grep -v "^--")

    # 执行
    sqlite3 "$DB" "$SQL_UP"

    # 记录
    sqlite3 "$DB" "
      INSERT OR REPLACE INTO schema_migrations (id, name, sql_up, applied_at)
      VALUES ($MIGRATION_ID, '$MIGRATION_NAME', '$SQL_UP', datetime('now'));
    "

    echo "✓ 完成: $MIGRATION_NAME"
  fi
done
```

### 回滚迁移

```bash
DB=~/.solar/solar.db

# 获取最后一次迁移
LAST=$(sqlite3 "$DB" "
  SELECT id, name, sql_down FROM schema_migrations
  WHERE applied_at IS NOT NULL
  ORDER BY id DESC LIMIT 1;
")

if [ -n "$LAST" ]; then
  ID=$(echo "$LAST" | cut -d'|' -f1)
  NAME=$(echo "$LAST" | cut -d'|' -f2)
  SQL_DOWN=$(echo "$LAST" | cut -d'|' -f3)

  echo "回滚: $NAME"

  if [ -n "$SQL_DOWN" ]; then
    sqlite3 "$DB" "$SQL_DOWN"
  fi

  sqlite3 "$DB" "UPDATE schema_migrations SET applied_at = NULL WHERE id = $ID;"
  echo "✓ 回滚完成"
else
  echo "没有可回滚的迁移"
fi
```

### 迁移模板

```sql
-- Migration: add_user_preferences
-- Created: 2024-01-15

-- UP
CREATE TABLE IF NOT EXISTS user_preferences (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_preferences_updated ON user_preferences(updated_at);

-- DOWN
DROP INDEX IF EXISTS idx_preferences_updated;
DROP TABLE IF EXISTS user_preferences;
```

## 输出格式

```
┌─ 🔄 Migration Status ───────────────────────────────────────────┐
│                                                                  │
│  数据库: ~/.solar/solar.db                                       │
│  版本: 5 / 5 (最新)                                              │
│                                                                  │
├─ 迁移历史 ───────────────────────────────────────────────────────┤
│                                                                  │
│  ID     名称                          状态    时间               │
│  ─────────────────────────────────────────────────────────────   │
│  001    initial_schema                ✓       2024-01-10         │
│  002    add_memory_tables             ✓       2024-01-11         │
│  003    add_skill_proficiency         ✓       2024-01-12         │
│  004    add_evaluation_system         ✓       2024-01-13         │
│  005    add_user_preferences          ✓       2024-01-15         │
│                                                                  │
├─ 待处理 ─────────────────────────────────────────────────────────┤
│                                                                  │
│  (无待处理迁移)                                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 最佳实践

1. **命名规范**: `YYYYMMDDHHMMSS_描述.sql`
2. **原子操作**: 每个迁移只做一件事
3. **可回滚**: 始终提供 DOWN 脚本
4. **测试**: 在备份上测试后再执行
5. **版本控制**: 迁移文件提交到 Git

## 目录结构

```
~/.solar/
├── solar.db                    # 数据库
└── migrations/                 # 迁移文件
    ├── 20240110000000_initial.sql
    ├── 20240111000000_add_memory.sql
    └── 20240115000000_add_prefs.sql
```
