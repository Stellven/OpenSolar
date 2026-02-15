# /queue - 任务队列管理

## 触发
- `/queue status` - 查看队列状态
- `/queue add <任务>` - 添加任务到队列
- `/queue history` - 查看任务历史
- `/queue cancel <id>` - 取消任务
- `/queue start` - 启动队列处理器
- `/queue cleanup` - 清理旧任务

## 执行

### 查看状态

```bash
bun ~/.claude/core/task-queue/queue.ts status
```

### 添加任务

```bash
# 添加命令任务
bun ~/.claude/core/task-queue/queue.ts add "my-task" '{"command":"echo hello"}' normal

# 添加高优先级任务
bun ~/.claude/core/task-queue/queue.ts add "urgent-task" '{"command":"..."}' high
```

### 查看历史

```bash
bun ~/.claude/core/task-queue/queue.ts history
```

### 启动队列

```bash
bun ~/.claude/core/task-queue/queue.ts start
```

## 设计理念

参考 OpenClaw 的 Lane Queue 设计:

```
┌─────────────────────────────────────────────────────────────────┐
│                       LANE QUEUE                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Task 1 ──▶ Task 2 ──▶ Task 3 ──▶ ...                          │
│                                                                  │
│   特点:                                                          │
│   • 默认串行执行 (避免资源冲突)                                  │
│   • 优先级排序 (critical > high > normal > low)                 │
│   • 任务隔离 (每个任务独立上下文)                                │
│   • 超时控制 (防止无限阻塞)                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 优先级

| 级别 | 权重 | 使用场景 |
|------|------|----------|
| critical | 1000 | 系统紧急任务 |
| high | 100 | 用户主动触发 |
| normal | 10 | 常规任务 |
| low | 1 | 后台任务 |

## 任务类型

| 类型 | payload | 说明 |
|------|---------|------|
| command | `{"command":"..."}` | Shell 命令 |
| skill | `{"skill":"name","args":[]}` | 调用 Skill |
| script | `{"path":"...","args":[]}` | 执行脚本 |

## 输出格式

```
┌─ 📋 Task Queue Status ───────────────────────────────────────────┐
│                                                                  │
│  Running: ✓                                                      │
│  Current: build-project                                          │
│  Pending: 3  Completed: 15  Failed: 1                            │
│                                                                  │
├─ Pending Tasks ──────────────────────────────────────────────────┤
│                                                                  │
│  1. [high]   run-tests                                           │
│  2. [normal] deploy-staging                                      │
│  3. [low]    cleanup-logs                                        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 数据库表

```sql
-- 任务队列表
CREATE TABLE task_queue (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  payload TEXT,
  priority TEXT DEFAULT 'normal',
  status TEXT DEFAULT 'pending',
  result TEXT,
  error TEXT,
  timeout_ms INTEGER DEFAULT 60000,
  created_at DATETIME,
  started_at DATETIME,
  completed_at DATETIME
);

-- 待处理视图 (按优先级排序)
CREATE VIEW v_task_queue_pending AS
SELECT * FROM task_queue
WHERE status = 'pending'
ORDER BY priority_weight DESC, created_at ASC;
```

## 使用场景

| 场景 | 为什么用队列 |
|------|-------------|
| 多个 Agent 任务 | 避免并发冲突 |
| 长时间任务 | 超时控制+状态追踪 |
| 批量操作 | 有序执行，可取消 |
| 定时任务 | 与 /cron 配合 |

## 与其他系统集成

- **/cron** - 定时任务入队
- **/sandbox** - 危险命令在沙箱执行
- **@Agent** - Agent 任务串行执行
- **Hooks** - PostToolUse 可触发入队

## 最佳实践

1. **长任务用队列** - 超过 30s 的任务建议入队
2. **设置合理超时** - 避免任务无限阻塞
3. **定期清理** - 运行 `/queue cleanup` 清理历史
4. **监控失败** - 关注 failed 任务数量
