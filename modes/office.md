# Office 办公模式

> 当用户说 "我要办公" 时加载此上下文

## 工具概览

| 类型 | 工具 | 命令/入口 |
|------|------|----------|
| 📧 邮件 | Himalaya | `himalaya` CLI |
| 📝 笔记 | Apple Notes | AppleScript |
| ⏰ 提醒 | Reminders | `remindctl` CLI |
| ✅ 任务 | Things 3 | `things` CLI |
| 📓 Notion | Notion API | HTTP API |
| 📋 Trello | Trello API | HTTP API |

## 快捷入口

| 说 | 动作 |
|---|------|
| 查邮件 | `himalaya envelope list` |
| 发邮件 | `himalaya message write` |
| 添加提醒 | `remindctl add "内容"` |
| 添加任务 | `things add "任务"` |
| 查笔记 | AppleScript 搜索 Notes |

## 邮件 (Himalaya)

```bash
# 列出邮件
himalaya envelope list

# 读取
himalaya message read <ID>

# 回复
himalaya message reply <ID>

# 发送
cat << 'EOF' | himalaya template send
From: you@example.com
To: recipient@example.com
Subject: 主题

内容
EOF
```

## 提醒 (remindctl)

```bash
# 添加提醒
remindctl add "买牛奶" --due "tomorrow 9am"

# 列出提醒
remindctl list

# 完成
remindctl complete <ID>
```

## 任务 (Things 3)

```bash
# 添加任务
things add "完成报告" --when "today"

# 查看今日
things today

# 查看收件箱
things inbox
```

## 笔记 (Apple Notes)

通过 AppleScript 操作，直接说需求即可。

## Notion / Trello

通过 API 操作，需要配置 token。详见对应 skill。

## 模式切换

- `/office email` - 邮件模式
- `/office tasks` - 任务模式
- `/office reminders` - 提醒模式
