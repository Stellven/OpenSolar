# /perf - 性能分析

## 触发
- `/perf` - 系统性能概览
- `/perf <命令>` - 分析命令性能
- `/perf profile <进程>` - CPU 分析
- `/perf memory` - 内存分析
- `/perf io` - IO 分析
- `/perf flame` - 火焰图生成

## 执行

### 系统概览

```bash
echo "=== 系统性能概览 ==="

# CPU
echo "CPU 使用率:"
top -l 1 | grep "CPU usage" | awk '{print $3, $5, $7}'

# 内存
echo "内存使用:"
vm_stat | perl -ne '/page size of (\d+)/ and $size=$1;
  /Pages (free|active|inactive|wired down):\s+(\d+)/ and
  printf "%-12s: %6.1f MB\n", $1, $2*$size/1048576'

# 磁盘
echo "磁盘使用:"
df -h / | tail -1 | awk '{print "Used:", $3, "Free:", $4, "(" $5 ")"}'

# 负载
echo "系统负载:"
uptime | awk -F'load averages:' '{print $2}'
```

### 命令耗时分析

```bash
# 简单计时
time $COMMAND

# 详细计时
/usr/bin/time -l $COMMAND 2>&1

# 多次运行取平均 (需要 hyperfine)
brew install hyperfine
hyperfine "$COMMAND"

# 对比两个命令
hyperfine "$CMD1" "$CMD2"
```

### CPU Profiling

```bash
# 使用 sample (macOS 自带)
sample $PID 10 -file /tmp/profile.txt

# 使用 instruments
xcrun xctrace record --template "Time Profiler" --launch -- $COMMAND

# Node.js
node --prof app.js
node --prof-process isolate-*.log > profile.txt

# Python
python -m cProfile -o profile.prof script.py
python -c "import pstats; p = pstats.Stats('profile.prof'); p.sort_stats('cumtime').print_stats(20)"
```

### 内存分析

```bash
# 进程内存
ps aux | head -1
ps aux | sort -k4 -rn | head -10

# 详细内存 (需要进程 ID)
vmmap $PID | head -50

# 内存泄漏检测 (Node.js)
node --inspect app.js
# 打开 Chrome DevTools 进行 heap snapshot

# Python
pip install memory_profiler
python -m memory_profiler script.py
```

### IO 分析

```bash
# 磁盘 IO
iostat -d 1 5

# 网络 IO
nettop -m tcp -d

# 文件打开
lsof -p $PID | head -50

# 系统调用跟踪
dtruss -p $PID 2>&1 | head -100
```

### 火焰图

```bash
# 安装 FlameGraph
git clone https://github.com/brendangregg/FlameGraph.git ~/FlameGraph

# 使用 DTrace (macOS)
sudo dtrace -x ustackframes=100 -n 'profile-99 /pid == '$PID'/ { @[ustack()] = count(); }' -o /tmp/out.stacks
~/FlameGraph/stackcollapse.pl /tmp/out.stacks > /tmp/out.folded
~/FlameGraph/flamegraph.pl /tmp/out.folded > flame.svg

# Node.js 火焰图
npm install -g 0x
0x app.js
```

### 数据库性能

```bash
# SQLite 查询分析
sqlite3 $DB "EXPLAIN QUERY PLAN $SQL"

# 查询耗时
sqlite3 $DB ".timer on" "$SQL"

# 索引建议
sqlite3 $DB "ANALYZE; SELECT * FROM sqlite_stat1;"
```

## 输出格式

```
┌─ ⚡ Performance ─────────────────────────────────────────────────┐
│                                                                  │
│  命令: npm run build                                             │
│  耗时: 4.532s                                                    │
│                                                                  │
├─ 资源使用 ───────────────────────────────────────────────────────┤
│                                                                  │
│  CPU        ████████████████░░░░  78%  peak                      │
│  Memory     ██████████░░░░░░░░░░  512 MB                         │
│  Disk I/O   ████░░░░░░░░░░░░░░░░  45 MB read, 12 MB write        │
│                                                                  │
├─ 时间分解 ───────────────────────────────────────────────────────┤
│                                                                  │
│  TypeScript 编译    2.1s  (46%)                                  │
│  Bundle 打包        1.8s  (40%)                                  │
│  资源复制           0.6s  (14%)                                  │
│                                                                  │
├─ 建议 ───────────────────────────────────────────────────────────┤
│                                                                  │
│  • 考虑使用 esbuild 替代 tsc (预计提升 5x)                       │
│  • 启用增量编译 (--incremental)                                  │
│  • 检查是否有不必要的 node_modules 扫描                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 基准测试集成

```bash
# 与 /benchmark 集成
# 记录性能数据到数据库
sqlite3 ~/.solar/solar.db "
INSERT INTO perf_records (command, duration_ms, cpu_percent, memory_mb)
VALUES ('$COMMAND', $DURATION, $CPU, $MEMORY);
"
```

## 常用别名

```bash
# ~/.zshrc
alias perf-top="top -o cpu -n 10"
alias perf-mem="ps aux --sort=-%mem | head -10"
alias perf-io="iostat -d 1"
```
