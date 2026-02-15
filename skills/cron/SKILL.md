# /cron - 定时任务管理

## 触发
- `/cron list` - 列出所有定时任务
- `/cron add <任务> <时间>` - 添加定时任务
- `/cron remove <任务ID>` - 删除定时任务
- `/cron status` - 任务状态
- `/cron logs <任务ID>` - 查看日志

## 执行

### 列出定时任务

```bash
# 系统 crontab
echo "=== 系统 Crontab ==="
crontab -l 2>/dev/null || echo "无 crontab"

# launchd (macOS)
echo "=== LaunchAgents ==="
ls ~/Library/LaunchAgents/com.solar.* 2>/dev/null || echo "无 Solar 任务"

# Solar 注册的任务
echo "=== Solar 定时任务 ==="
sqlite3 ~/.solar/solar.db "
SELECT job_id, job_name, schedule, status, last_run
FROM sys_cron_jobs
ORDER BY last_run DESC;
" 2>/dev/null || echo "sys_cron_jobs 表不存在"
```

### 添加定时任务

**使用 launchd (推荐):**

```bash
# 创建 plist 文件
cat > ~/Library/LaunchAgents/com.solar.$JOB_NAME.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.solar.$JOB_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>$COMMAND</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$HOUR</integer>
        <key>Minute</key>
        <integer>$MINUTE</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$HOME/.solar/logs/$JOB_NAME.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.solar/logs/$JOB_NAME.error.log</string>
</dict>
</plist>
EOF

# 加载任务
launchctl load ~/Library/LaunchAgents/com.solar.$JOB_NAME.plist
```

**使用 crontab:**

```bash
# 添加到 crontab
(crontab -l 2>/dev/null; echo "$MINUTE $HOUR * * * $COMMAND") | crontab -
```

### 删除定时任务

```bash
# launchd
launchctl unload ~/Library/LaunchAgents/com.solar.$JOB_NAME.plist
rm ~/Library/LaunchAgents/com.solar.$JOB_NAME.plist

# crontab
crontab -l | grep -v "$JOB_NAME" | crontab -
```

### 查看日志

```bash
# 查看任务日志
tail -50 ~/.solar/logs/$JOB_NAME.log

# 查看错误日志
tail -20 ~/.solar/logs/$JOB_NAME.error.log
```

## Solar 已配置的定时任务

| 任务 | 时间 | 脚本 |
|------|------|------|
| SES 日评估 | 每天 04:00 | `~/.claude/core/ses/evaluate.ts daily` |
| SES 周评估 | 周日 03:00 | `~/.claude/core/ses/evaluate.ts weekly` |
| SES 月评估 | 1日 02:00 | `~/.claude/core/ses/evaluate.ts monthly` |
| 记忆整合 | 每天 05:00 | `~/.claude/core/memory/consolidate.ts` |

## 时间格式

```
cron 格式: 分 时 日 月 周
示例:
  "0 4 * * *"     - 每天 4:00
  "0 3 * * 0"     - 每周日 3:00
  "0 2 1 * *"     - 每月1日 2:00
  "*/30 * * * *"  - 每30分钟
```

## 数据库支持

```sql
-- 创建任务表 (如不存在)
CREATE TABLE IF NOT EXISTS sys_cron_jobs (
    job_id TEXT PRIMARY KEY,
    job_name TEXT NOT NULL,
    schedule TEXT NOT NULL,
    command TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    last_run DATETIME,
    next_run DATETIME,
    run_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 输出格式

```
┌─ ⏰ 定时任务 ─────────────────────────────────────────────────────┐
│                                                                   │
│  ID          名称              时间           状态    上次运行    │
│  ─────────────────────────────────────────────────────────────    │
│  ses-daily   SES 日评估        04:00 daily    ✓       2h ago     │
│  ses-weekly  SES 周评估        03:00 weekly   ✓       5d ago     │
│  consolidate 记忆整合          05:00 daily    ✓       2h ago     │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```
