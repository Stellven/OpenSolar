---
name: apple-reminders
description: 管理 Apple Reminders - 支持 remindctl CLI 和 AppleScript 两种方式
homepage: https://github.com/steipete/remindctl
user-invocable: true
argument-hint: "[today|add <内容>|complete <id>]"
---

# Apple Reminders 管理

支持两种方式访问 Apple Reminders：
1. **remindctl** (推荐) - 功能完整的 CLI
2. **AppleScript** (备用) - 无需额外授权

## 方式一: remindctl CLI

### 安装
```bash
brew install steipete/tap/remindctl
```

### 授权
```bash
remindctl authorize  # 触发授权对话框
```

### 查看提醒
```bash
remindctl today      # 今日提醒
remindctl tomorrow   # 明日提醒
remindctl week       # 本周提醒
remindctl overdue    # 过期提醒
remindctl all        # 所有提醒
```

### 管理提醒
```bash
remindctl add "买牛奶"                           # 快速添加
remindctl add --title "打电话" --due tomorrow   # 指定截止日期
remindctl complete 1 2 3                        # 完成提醒
remindctl delete 4A83 --force                   # 删除提醒
```

### 管理列表
```bash
remindctl list                    # 显示所有列表
remindctl list Work               # 显示指定列表
remindctl list Projects --create  # 创建列表
```

---

## 方式二: AppleScript (备用)

当 remindctl 无法授权时，使用 AppleScript：

### 查看所有未完成提醒
```bash
osascript -e 'tell application "Reminders"
  set output to ""
  repeat with r in (every reminder whose completed is false)
    set output to output & (name of r) & "\n"
  end repeat
  return output
end tell'
```

### 查看提醒列表
```bash
osascript -e 'tell application "Reminders" to get name of every list'
```

### 添加提醒
```bash
osascript -e 'tell application "Reminders"
  tell list "提醒事项"
    make new reminder with properties {name:"买牛奶"}
  end tell
end tell'
```

### 添加带截止日期的提醒
```bash
osascript -e 'tell application "Reminders"
  set dueDate to (current date) + 1 * days
  tell list "提醒事项"
    make new reminder with properties {name:"打电话", due date:dueDate}
  end tell
end tell'
```

### 完成提醒
```bash
osascript -e 'tell application "Reminders"
  set r to first reminder whose name is "买牛奶"
  set completed of r to true
end tell'
```

### 查看指定列表的提醒
```bash
osascript -e 'tell application "Reminders"
  set output to ""
  repeat with r in (every reminder in list "工作" whose completed is false)
    set output to output & (name of r) & "\n"
  end repeat
  return output
end tell'
```

## 注意事项

- macOS 专用
- AppleScript 方式通常无需额外授权
- remindctl 需要在「系统设置 → 隐私与安全性 → 提醒事项」中授权
