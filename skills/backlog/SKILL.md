# /backlog - Solar 待办管理

> 项目 → 特性 → 任务 三层结构待办管理

## 命令

| 命令 | 说明 |
|------|------|
| `/backlog` | 当前项目 Backlog 概览 |
| `/backlog add "Feature"` | 添加特性 |
| `/backlog task <feature> "Task"` | 为特性添加任务 |
| `/backlog done <id>` | 完成任务/特性 |
| `/backlog extract` | 从当前会话提取未完成任务 |
| `/backlog search "关键词"` | 搜索 |
| `/backlog list [project]` | 列出特性 |
| `/backlog queue` | 查看消息任务队列 |
| `/backlog stats` | 统计信息 |

## 参数

- `--project, -p`: 指定项目 ID
- `--priority, -P`: 优先级 (0-100)
- `--agent, -a`: 指派 Agent (@Coder, @Tester, etc.)
- `--due, -d`: 截止日期

## 示例

```bash
# 添加特性
/backlog add "消息驱动执行器" -p Solar

# 为特性添加任务
/backlog task solar:msg-executor "实现 iMessage 监听"

# 查看 Solar 项目 backlog
/backlog -p Solar

# 完成任务
/backlog done solar:msg-executor:abc123

# 从会话提取任务
/backlog extract

# 搜索
/backlog search "监听"
```

## 输出格式 (TVS)

```
┌─ 📋 Backlog ────────────────────────────────────┐
│ Project: Solar                                  │
├─────────────────────────────────────────────────┤
│ Feature         Status      Progress   Tasks    │
│ ─────────────────────────────────────────────── │
│ 消息驱动执行器   in_progress  ████░░ 67%  3/4   │
│ Backlog系统      done         ██████ 100% 5/5   │
│ 配额调度器       open         ░░░░░░ 0%   0/3   │
└─────────────────────────────────────────────────┘
```

## 实现

执行: `bun run ~/.claude/skills/backlog/backlog.ts`
