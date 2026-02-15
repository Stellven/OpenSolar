---
name: shortcut-builder
description: 苹果快捷指令编辑器 - 分析需求、自动创建、验证并执行 Shortcuts
user-invocable: true
argument-hint: "<需求描述>"
---

# /shortcut-builder - 快捷指令智能编辑器

分析用户需求，判断是否适合用 Apple Shortcuts 实现，自动创建、验证并执行。

## 触发条件

当用户需求满足以下条件时，**自动触发**此 Skill：

| 条件 | 示例 |
|------|------|
| 涉及 OS 级操作 | "提醒我..."、"发消息给..."、"打开..." |
| 需要 Siri 语音触发 | "我想用语音控制..." |
| 需要自动化 | "每天早上..."、"到家后自动..." |
| 涉及 Apple 生态 | HomeKit、日历、提醒事项、消息 |
| 需要跨 App 数据流 | "把照片发给..."、"把剪贴板内容..." |

## 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│              SHORTCUT BUILDER WORKFLOW                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 需求分析                                                │
│     ┌──────────────────────────────────────────────────┐   │
│     │ 用户: "每天早上7点告诉我今天天气和日程"           │   │
│     │ ↓                                                 │   │
│     │ 解析:                                             │   │
│     │ • 触发: 时间 (07:00 daily)                        │   │
│     │ • 动作1: 获取天气                                 │   │
│     │ • 动作2: 获取今日日历                             │   │
│     │ • 动作3: 语音播报                                 │   │
│     │ • 适合 Shortcut: ✓                               │   │
│     └──────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  2. 生成 Shortcut 定义                                      │
│     ┌──────────────────────────────────────────────────┐   │
│     │ {                                                 │   │
│     │   "name": "solar_morning_briefing",               │   │
│     │   "actions": [                                    │   │
│     │     {"type": "GetWeather"},                       │   │
│     │     {"type": "GetCalendarEvents", "date": "today"}│   │
│     │     {"type": "SpeakText", "text": "..."}          │   │
│     │   ],                                              │   │
│     │   "trigger": {"type": "time", "time": "07:00"}    │   │
│     │ }                                                 │   │
│     └──────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  3. 创建 Shortcut (AppleScript)                             │
│     ┌──────────────────────────────────────────────────┐   │
│     │ osascript shortcut-generator.applescript          │   │
│     │ → 打开 Shortcuts.app                              │   │
│     │ → 创建新快捷指令                                   │   │
│     │ → 添加动作                                         │   │
│     │ → 保存                                             │   │
│     └──────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  4. 验证 & 执行                                             │
│     ┌──────────────────────────────────────────────────┐   │
│     │ shortcuts run "solar_morning_briefing"            │   │
│     │ → 检查输出                                         │   │
│     │ → 返回结果给用户                                   │   │
│     └──────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 用法

```bash
# 自动分析并创建
/shortcut-builder "每天早上告诉我天气"

# 指定名称
/shortcut-builder --name solar_weather_report "获取天气并语音播报"

# 只分析不创建
/shortcut-builder --analyze "发消息给妈妈说我到家了"

# 从现有 Shortcut 编辑
/shortcut-builder --edit solar_morning_briefing "添加股票信息"
```

## 适合 Shortcut 的场景判断

```python
def should_use_shortcut(request):
    """判断是否应该用 Shortcut 实现"""

    # 高优先级 (强烈建议 Shortcut)
    HIGH_PRIORITY = [
        "提醒", "reminder", "日历", "calendar", "日程",
        "消息", "message", "短信", "发送",
        "电话", "call", "facetime",
        "homekit", "智能家居", "灯", "空调",
        "siri", "语音", "播报",
        "自动化", "每天", "每周", "到达", "离开",
        "剪贴板", "clipboard",
        "位置", "location", "天气", "weather"
    ]

    # 中优先级 (可以用 Shortcut)
    MEDIUM_PRIORITY = [
        "打开", "open", "启动", "launch",
        "分享", "share",
        "照片", "photo", "相册",
        "音乐", "music", "播放"
    ]

    # 低优先级 (可能更适合其他方案)
    LOW_PRIORITY = [
        "搜索", "查询",  # 可能需要复杂逻辑
        "分析", "处理"   # 可能需要 AI
    ]

    score = 0
    for keyword in HIGH_PRIORITY:
        if keyword in request.lower():
            score += 3
    for keyword in MEDIUM_PRIORITY:
        if keyword in request.lower():
            score += 2
    for keyword in LOW_PRIORITY:
        if keyword in request.lower():
            score += 1

    return score >= 3, score
```

## Shortcut 动作库

### 系统动作

| 动作 | AppleScript 实现 | 用途 |
|------|------------------|------|
| GetClipboard | `the clipboard` | 获取剪贴板 |
| SetClipboard | `set the clipboard to` | 设置剪贴板 |
| GetWeather | Weather API | 获取天气 |
| SpeakText | `say "text"` | 语音播报 |
| ShowNotification | `display notification` | 显示通知 |
| OpenApp | `tell app to activate` | 打开应用 |
| OpenURL | `open location` | 打开链接 |

### 提醒/日历

| 动作 | 实现方式 | 用途 |
|------|----------|------|
| AddReminder | Reminders.app | 添加提醒 |
| GetReminders | Reminders.app | 获取提醒列表 |
| AddCalendarEvent | Calendar.app | 添加日历事件 |
| GetCalendarEvents | Calendar.app | 获取日历事件 |

### 通信

| 动作 | 实现方式 | 用途 |
|------|----------|------|
| SendMessage | Messages.app | 发送 iMessage |
| MakeCall | FaceTime | 拨打电话 |
| SendMail | Mail.app | 发送邮件 |

### HomeKit

| 动作 | 实现方式 | 用途 |
|------|----------|------|
| ControlDevice | Home.app | 控制设备 |
| GetDeviceState | Home.app | 获取设备状态 |
| RunScene | Home.app | 运行场景 |

## 输出格式

### 分析结果

```
┌─────────────────────────────────────────────────────────────┐
│              🔍 SHORTCUT ANALYSIS                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Request    "每天早上7点告诉我天气和日程"                   │
│  Score      9/10 (强烈推荐 Shortcut)                        │
│                                                             │
│  Detected:                                                  │
│  • 时间触发: 每天 07:00                                     │
│  • 动作: 获取天气 + 获取日历 + 语音播报                     │
│  • 平台: iOS / macOS                                        │
│                                                             │
│  Recommendation: ✓ 使用 Shortcut 实现                       │
│                                                             │
│  [C] Create shortcut                                        │
│  [S] Skip and use other method                              │
│                                                             │
└───────────────────────────────────────────────────────────────┘
```

### 创建成功

```
┌─────────────────────────────────────────────────────────────┐
│              ✅ SHORTCUT CREATED                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Name        solar_morning_briefing                         │
│  Actions     3 steps                                        │
│  Trigger     Daily at 07:00                                 │
│                                                             │
│  Steps:                                                     │
│  1. Get Current Weather                                     │
│  2. Get Calendar Events (Today)                             │
│  3. Speak Text (Weather + Events summary)                   │
│                                                             │
│  Test Command:                                              │
│  shortcuts run "solar_morning_briefing"                     │
│                                                             │
│  Siri Phrase:                                               │
│  "Hey Siri, Solar 早安"                                     │
│                                                             │
└───────────────────────────────────────────────────────────────┘
```

## 创建方法

### 方法 1: Shell Script Shortcut (推荐)

创建一个通用的 "Solar Shell" Shortcut，通过 Shell 脚本实现任意逻辑：

```bash
# 在 Shortcuts.app 中创建一次性基础设施：
# 1. 创建 "solar_shell" Shortcut
# 2. 添加 "Shortcut Input" 动作
# 3. 添加 "Run Shell Script" 动作，脚本内容为：
#    eval "$1"
# 4. 添加 "Stop and Output" 返回结果

# 然后任意命令都可以通过它执行：
shortcuts run "solar_shell" <<< 'curl wttr.in?format=3'
```

### 方法 2: AppleScript 创建

```applescript
-- 通过 AppleScript 控制 Shortcuts.app (有限支持)
tell application "Shortcuts"
    -- 注意: Shortcuts.app 的 AppleScript 支持有限
    -- 主要用于运行已有的 Shortcut
    run shortcut "solar_get_weather"
end tell
```

### 方法 3: URL Scheme

```bash
# 运行 Shortcut
open "shortcuts://run-shortcut?name=solar_get_weather"

# 带输入运行
open "shortcuts://run-shortcut?name=solar_set_reminder&input=text&text=开会"
```

## 与 Solar 集成

当 Solar Agent 检测到适合 Shortcut 的需求时：

```
用户: "提醒我明天下午3点开会"

Solar Agent:
1. 检测关键词: "提醒" → 触发 shortcut-builder
2. 分析: 适合 Shortcut (score=9)
3. 检查: solar_set_reminder 是否存在
   - 存在 → 直接调用
   - 不存在 → 创建后调用
4. 执行: shortcuts run "solar_set_reminder" ...
5. 返回: "已创建提醒: 明天下午3点开会"
```

## 依赖

- **macOS 12+**: shortcuts CLI
- **Shortcuts.app**: 系统自带
- **osascript**: AppleScript 执行

## 相关 Skill

- `/shortcut` - 执行已有 Shortcuts
- `/call` - FaceTime/电话呼叫
- `/office-reminders` - 提醒事项管理
