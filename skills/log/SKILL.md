# /log - 日志分析

## 触发
- `/log` - 查看最近日志
- `/log <文件>` - 分析指定日志
- `/log errors` - 只看错误
- `/log search <关键词>` - 搜索日志
- `/log stats` - 日志统计
- `/log tail` - 实时跟踪

## 执行

### 查看最近日志

```bash
# Solar 日志
tail -50 ~/.solar/logs/*.log

# 系统日志 (macOS)
log show --last 1h --predicate 'processID == 0' | tail -50

# 应用日志
tail -100 /var/log/app.log
```

### 错误过滤

```bash
# 提取错误
grep -i "error\|exception\|fail" $LOG_FILE | tail -50

# 按时间段过滤错误
grep -i error $LOG_FILE | grep "$(date +%Y-%m-%d)"

# 统计错误类型
grep -i error $LOG_FILE | \
  sed 's/.*\(Error:[^:]*\).*/\1/' | \
  sort | uniq -c | sort -rn | head -10
```

### 日志搜索

```bash
# 关键词搜索
grep -n "$KEYWORD" $LOG_FILE

# 上下文搜索 (前后 3 行)
grep -B3 -A3 "$KEYWORD" $LOG_FILE

# 多关键词
grep -E "error|warn|fail" $LOG_FILE

# 时间范围 (假设格式 2024-01-15 10:30:00)
awk '/2024-01-15 10:/ && /2024-01-15 11:/' $LOG_FILE
```

### 日志统计

```bash
# 按级别统计
echo "=== 日志级别分布 ==="
grep -oE "\[(INFO|WARN|ERROR|DEBUG)\]" $LOG_FILE | \
  sort | uniq -c | sort -rn

# 按小时统计
echo "=== 每小时日志量 ==="
grep -oE "[0-9]{2}:[0-9]{2}:[0-9]{2}" $LOG_FILE | \
  cut -d: -f1 | sort | uniq -c

# 错误趋势
echo "=== 错误趋势 (按天) ==="
grep -i error $LOG_FILE | \
  grep -oE "[0-9]{4}-[0-9]{2}-[0-9]{2}" | \
  sort | uniq -c
```

### 实时跟踪

```bash
# 跟踪单个文件
tail -f $LOG_FILE

# 跟踪多个文件
tail -f /var/log/*.log

# 带高亮 (需要 ccze)
tail -f $LOG_FILE | ccze -A

# 过滤跟踪
tail -f $LOG_FILE | grep --line-buffered "error"
```

### JSON 日志分析

```bash
# 解析 JSON 日志
cat $LOG_FILE | jq -r '.level + " " + .message'

# 只看错误
cat $LOG_FILE | jq -r 'select(.level == "error") | .message'

# 统计
cat $LOG_FILE | jq -r '.level' | sort | uniq -c
```

### 日志压缩与归档

```bash
# 压缩旧日志
find ~/.solar/logs -name "*.log" -mtime +7 -exec gzip {} \;

# 删除超过 30 天的日志
find ~/.solar/logs -name "*.gz" -mtime +30 -delete

# 日志轮转 (使用 logrotate)
cat > /tmp/solar-logrotate.conf << 'EOF'
~/.solar/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
EOF
```

## 输出格式

```
┌─ 📋 Log Analysis ───────────────────────────────────────────────┐
│                                                                  │
│  文件: ~/.solar/logs/solar.log                                   │
│  大小: 2.3 MB | 行数: 45,230                                     │
│  时间: 2024-01-15 00:00 ~ 2024-01-15 23:59                       │
│                                                                  │
├─ 级别分布 ───────────────────────────────────────────────────────┤
│                                                                  │
│  INFO     ████████████████████████████  82%  (37,089)            │
│  WARN     █████                         12%  (5,428)             │
│  ERROR    ██                             5%  (2,262)             │
│  DEBUG    ░                              1%  (451)               │
│                                                                  │
├─ 最近错误 ───────────────────────────────────────────────────────┤
│                                                                  │
│  23:45:12  ConnectionError: timeout after 30s                    │
│  23:12:33  ValidationError: invalid input                        │
│  22:58:01  DatabaseError: connection refused                     │
│                                                                  │
├─ 错误模式 ───────────────────────────────────────────────────────┤
│                                                                  │
│  ConnectionError    45 次  (超时/连接拒绝)                       │
│  ValidationError    23 次  (输入验证失败)                        │
│  DatabaseError      12 次  (数据库连接问题)                      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 常用别名

```bash
# ~/.zshrc
alias logs="tail -f ~/.solar/logs/*.log"
alias logerr="grep -i error ~/.solar/logs/*.log | tail -20"
alias logstat="wc -l ~/.solar/logs/*.log"
```
