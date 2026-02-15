# /alert - 监控告警

## 触发
- `/alert status` - 告警状态
- `/alert list` - 列出告警规则
- `/alert add <规则>` - 添加告警
- `/alert test <规则ID>` - 测试告警
- `/alert silence <规则ID>` - 静默告警
- `/alert history` - 告警历史

## 执行

### 查看状态

```bash
echo "=== 告警状态 ==="

# 系统健康检查
echo "系统检查:"
[ $(df -h / | tail -1 | awk '{print int($5)}') -lt 90 ] && echo "  ✓ 磁盘空间正常" || echo "  ⚠️ 磁盘空间不足"
[ $(vm_stat | awk '/Pages free/ {print $3}' | tr -d '.') -gt 10000 ] && echo "  ✓ 内存正常" || echo "  ⚠️ 内存不足"

# Solar 健康检查
echo "Solar 检查:"
[ -f ~/.solar/solar.db ] && echo "  ✓ 数据库存在" || echo "  ✗ 数据库丢失"
[ $(sqlite3 ~/.solar/solar.db "SELECT COUNT(*) FROM evo_tool_calls WHERE created_at > datetime('now', '-1 hour');" 2>/dev/null || echo 0) -gt 0 ] && echo "  ✓ 最近有活动" || echo "  ○ 最近无活动"
```

### 告警规则表

```sql
-- 初始化告警规则表
CREATE TABLE IF NOT EXISTS alert_rules (
  rule_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  condition TEXT NOT NULL,      -- SQL 或 Shell 条件
  threshold REAL,
  severity TEXT DEFAULT 'warn', -- info, warn, error, critical
  channel TEXT DEFAULT 'log',   -- log, notification, email
  enabled BOOLEAN DEFAULT TRUE,
  silenced_until DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alert_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rule_id TEXT,
  triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  value REAL,
  message TEXT,
  acknowledged BOOLEAN DEFAULT FALSE
);
```

### 添加告警规则

```bash
sqlite3 ~/.solar/solar.db "
INSERT INTO alert_rules (rule_id, name, condition, threshold, severity, channel)
VALUES
  ('disk_space', '磁盘空间', 'df -h / | tail -1 | awk \"{print int(\\\$5)}\"', 90, 'error', 'notification'),
  ('db_size', '数据库大小', 'du -m ~/.solar/solar.db | cut -f1', 500, 'warn', 'log'),
  ('error_rate', '错误率', 'SELECT COUNT(*)*100.0/(SELECT COUNT(*) FROM evo_tool_calls) FROM evo_tool_calls WHERE status=\"error\"', 10, 'warn', 'log'),
  ('memory_free', '可用内存', 'vm_stat | awk \"/Pages free/ {print \\\$3}\" | tr -d \".\"', 5000, 'error', 'notification');
"
```

### 检查告警

```bash
#!/bin/bash
# check-alerts.sh

DB=~/.solar/solar.db

sqlite3 "$DB" "SELECT rule_id, name, condition, threshold, severity, channel FROM alert_rules WHERE enabled = 1 AND (silenced_until IS NULL OR silenced_until < datetime('now'));" | \
while IFS='|' read rule_id name condition threshold severity channel; do
  # 执行条件
  VALUE=$(eval "$condition" 2>/dev/null)

  if [ -n "$VALUE" ] && [ $(echo "$VALUE > $threshold" | bc -l 2>/dev/null || echo 0) -eq 1 ]; then
    MESSAGE="⚠️ [$severity] $name: $VALUE (阈值: $threshold)"

    # 记录历史
    sqlite3 "$DB" "INSERT INTO alert_history (rule_id, value, message) VALUES ('$rule_id', $VALUE, '$MESSAGE');"

    # 发送通知
    case $channel in
      notification)
        osascript -e "display notification \"$MESSAGE\" with title \"Solar Alert\""
        ;;
      log)
        echo "$(date): $MESSAGE" >> ~/.solar/logs/alerts.log
        ;;
    esac

    echo "$MESSAGE"
  fi
done
```

### 发送通知

```bash
# macOS 通知
notify() {
  osascript -e "display notification \"$2\" with title \"$1\""
}

# 声音提醒
alert_sound() {
  afplay /System/Library/Sounds/Ping.aiff
}

# 邮件 (需要配置)
# echo "$MESSAGE" | mail -s "Solar Alert" user@example.com
```

### 定时检查 (launchd)

```bash
cat > ~/Library/LaunchAgents/com.solar.alert-check.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.solar.alert-check</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>~/.claude/scripts/check-alerts.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.solar.alert-check.plist
```

## 输出格式

```
┌─ 🔔 Alert Status ───────────────────────────────────────────────┐
│                                                                  │
│  活跃规则: 4 | 静默: 1 | 触发中: 1                               │
│                                                                  │
├─ 当前告警 ───────────────────────────────────────────────────────┤
│                                                                  │
│  ⚠️ [warn] 数据库大小: 523 MB (阈值: 500 MB)                     │
│     └─ 触发时间: 10 分钟前                                       │
│                                                                  │
├─ 告警规则 ───────────────────────────────────────────────────────┤
│                                                                  │
│  ID           名称          阈值      级别     状态              │
│  ─────────────────────────────────────────────────────────────   │
│  disk_space   磁盘空间      90%       error    ✓ 正常            │
│  db_size      数据库大小    500 MB    warn     ⚠️ 触发           │
│  error_rate   错误率        10%       warn     ✓ 正常            │
│  memory_free  可用内存      5000      error    ✓ 正常            │
│                                                                  │
├─ 最近告警 ───────────────────────────────────────────────────────┤
│                                                                  │
│  2024-01-15 10:30  db_size     523 MB                            │
│  2024-01-14 15:45  disk_space  92%     (已处理)                  │
│  2024-01-12 08:00  error_rate  12%     (已处理)                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 预置告警规则

| 规则 | 阈值 | 级别 | 说明 |
|------|------|------|------|
| 磁盘空间 | 90% | error | 磁盘使用超过 90% |
| 数据库大小 | 500MB | warn | 数据库超过 500MB |
| 错误率 | 10% | warn | 工具调用错误率 |
| 内存 | 5000 pages | error | 可用内存过低 |
| 备份过期 | 7 天 | warn | 超过 7 天未备份 |
