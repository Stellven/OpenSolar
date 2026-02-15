# /backup - 自动备份

## 触发
- `/backup` - 立即备份
- `/backup list` - 列出备份
- `/backup restore <id>` - 恢复备份
- `/backup config` - 备份配置
- `/backup clean` - 清理旧备份

## 执行

### 立即备份

```bash
BACKUP_DIR=~/.solar/backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="solar_$TIMESTAMP"

mkdir -p "$BACKUP_DIR"

# 备份数据库
cp ~/.solar/solar.db "$BACKUP_DIR/${BACKUP_NAME}.db"

# 备份配置
tar -czf "$BACKUP_DIR/${BACKUP_NAME}_config.tar.gz" \
  ~/.claude/CLAUDE.md \
  ~/.claude/settings.json \
  ~/.claude/rules/ \
  ~/.claude/skills/ \
  2>/dev/null

# 备份记忆 (可选，较大)
# tar -czf "$BACKUP_DIR/${BACKUP_NAME}_memory.tar.gz" ~/.solar/memories/

echo "✓ 备份完成: $BACKUP_NAME"
ls -lh "$BACKUP_DIR/${BACKUP_NAME}"*
```

### 列出备份

```bash
echo "=== 现有备份 ==="
ls -lht ~/.solar/backups/ | head -20

echo ""
echo "=== 备份统计 ==="
echo "总数: $(ls ~/.solar/backups/*.db 2>/dev/null | wc -l | tr -d ' ') 个"
echo "大小: $(du -sh ~/.solar/backups/ 2>/dev/null | cut -f1)"
```

### 恢复备份

```bash
BACKUP_ID=$1
BACKUP_DIR=~/.solar/backups

# 恢复数据库
if [ -f "$BACKUP_DIR/solar_${BACKUP_ID}.db" ]; then
  cp ~/.solar/solar.db ~/.solar/solar.db.before_restore
  cp "$BACKUP_DIR/solar_${BACKUP_ID}.db" ~/.solar/solar.db
  echo "✓ 数据库已恢复"
fi

# 恢复配置
if [ -f "$BACKUP_DIR/solar_${BACKUP_ID}_config.tar.gz" ]; then
  echo "恢复配置..."
  tar -xzf "$BACKUP_DIR/solar_${BACKUP_ID}_config.tar.gz" -C /
  echo "✓ 配置已恢复"
fi
```

### 自动备份 (launchd)

```bash
# 创建每日备份任务
cat > ~/Library/LaunchAgents/com.solar.backup.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.solar.backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cp ~/.solar/solar.db ~/.solar/backups/solar_$(date +\%Y\%m\%d).db</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</dict>
</plist>
EOF

# 加载任务
launchctl load ~/Library/LaunchAgents/com.solar.backup.plist
echo "✓ 每日 3:00 自动备份已启用"
```

### 清理旧备份

```bash
# 保留最近 7 天
find ~/.solar/backups -name "*.db" -mtime +7 -delete
find ~/.solar/backups -name "*.tar.gz" -mtime +7 -delete

# 保留最近 N 个
ls -t ~/.solar/backups/*.db | tail -n +8 | xargs rm -f 2>/dev/null

echo "✓ 已清理旧备份"
```

### 云端备份 (可选)

```bash
# 同步到 iCloud
ICLOUD_DIR=~/Library/Mobile\ Documents/com~apple~CloudDocs/Solar
mkdir -p "$ICLOUD_DIR"
cp ~/.solar/backups/solar_$(date +%Y%m%d).db "$ICLOUD_DIR/"

# 或使用 rclone 同步到其他云存储
# rclone copy ~/.solar/backups remote:solar-backups/
```

## 输出格式

```
┌─ 💾 Backup ─────────────────────────────────────────────────────┐
│                                                                  │
│  状态: 备份完成                                                  │
│  时间: 2024-01-15 10:30:45                                       │
│                                                                  │
├─ 备份内容 ───────────────────────────────────────────────────────┤
│                                                                  │
│  ✓ solar.db              12.3 MB                                 │
│  ✓ config.tar.gz         456 KB                                  │
│  ✓ 写入 ~/.solar/backups/                                        │
│                                                                  │
├─ 备份历史 ───────────────────────────────────────────────────────┤
│                                                                  │
│  2024-01-15  solar_20240115_103045  12.8 MB  (当前)              │
│  2024-01-14  solar_20240114_030000  12.1 MB                      │
│  2024-01-13  solar_20240113_030000  11.9 MB                      │
│  ...                                                             │
│                                                                  │
│  共 7 个备份，占用 85.2 MB                                       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 备份策略

| 数据类型 | 频率 | 保留期 |
|----------|------|--------|
| 数据库 | 每日 | 7 天 |
| 配置文件 | 每周 | 30 天 |
| 完整备份 | 每月 | 90 天 |

## 注意事项

- 敏感数据加密后再备份
- 定期验证备份可恢复性
- 云端备份注意隐私
