---
name: shortcut-search
description: 搜索并下载快捷指令 - 从网上查找满足需求的 Shortcuts
user-invocable: true
argument-hint: "<搜索关键词>"
---

# /shortcut-search - 快捷指令搜索与下载

从互联网搜索满足用户需求的 Apple Shortcuts，预览后一键下载安装。

## 用法

```bash
/shortcut-search weather              # 搜索天气相关快捷指令
/shortcut-search "morning routine"    # 搜索早晨例程
/shortcut-search 翻译                  # 搜索翻译相关
/shortcut-search --source routinehub productivity  # 指定来源搜索
```

## 搜索来源

| 来源 | 网址 | 特点 |
|------|------|------|
| **RoutineHub** | routinehub.co | 最大社区，质量高 |
| **ShortcutsGallery** | shortcutsgallery.com | 分类清晰 |
| **ShareShortcuts** | shareshortcuts.com | 简洁易用 |
| **MacStories** | macstories.net/shortcuts | 专业评测 |
| **Reddit** | r/shortcuts | 社区分享 |

## 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│              SHORTCUT SEARCH WORKFLOW                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 用户输入搜索词                                          │
│     "我想要一个番茄钟计时器"                                │
│                          │                                  │
│                          ▼                                  │
│  2. 多来源并行搜索                                          │
│     ┌─────────────┬─────────────┬─────────────┐            │
│     │ RoutineHub  │ Shortcuts   │ Web Search  │            │
│     │   API       │  Gallery    │   (Google)  │            │
│     └──────┬──────┴──────┬──────┴──────┬──────┘            │
│            └─────────────┼─────────────┘                    │
│                          ▼                                  │
│  3. 结果聚合 & 排序                                         │
│     • 相关度                                                │
│     • 下载量                                                │
│     • 评分                                                  │
│     • 更新时间                                              │
│                          │                                  │
│                          ▼                                  │
│  4. 展示结果                                                │
│     ┌─────────────────────────────────────────────────┐    │
│     │ 1. Pomodoro Timer Pro ⭐4.8 (1.2k downloads)    │    │
│     │ 2. Focus Timer ⭐4.5 (800 downloads)            │    │
│     │ 3. Simple Pomodoro ⭐4.2 (500 downloads)        │    │
│     └─────────────────────────────────────────────────┘    │
│                          │                                  │
│                          ▼                                  │
│  5. 用户选择 → 下载安装                                     │
│     open "shortcuts://import-shortcut?url=..."              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 输出格式

### 搜索结果

```
┌─────────────────────────────────────────────────────────────┐
│              🔍 SHORTCUT SEARCH: "pomodoro"                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Found 5 shortcuts                                          │
│                                                             │
│  1. 🍅 Pomodoro Timer Pro                                   │
│     Source:    RoutineHub                                   │
│     Rating:    ⭐⭐⭐⭐⭐ (4.8)                                │
│     Downloads: 1,234                                        │
│     Updated:   2025-12-15                                   │
│     [I] Install                                             │
│                                                             │
│  2. ⏱️ Focus Timer                                          │
│     Source:    ShortcutsGallery                             │
│     Rating:    ⭐⭐⭐⭐ (4.5)                                  │
│     Downloads: 856                                          │
│     Updated:   2025-11-20                                   │
│     [I] Install                                             │
│                                                             │
│  3. 🎯 Simple Pomodoro                                      │
│     Source:    iCloud Link                                  │
│     Rating:    N/A                                          │
│     Downloads: N/A                                          │
│     [I] Install                                             │
│                                                             │
│  Enter number to install, or 'q' to quit:                   │
│                                                             │
└───────────────────────────── [solar-dark] Powered by Solar ─┘
```

### 安装确认

```
┌─────────────────────────────────────────────────────────────┐
│              📥 INSTALLING SHORTCUT                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Name        Pomodoro Timer Pro                             │
│  Source      RoutineHub                                     │
│  Author      @productivity_guru                             │
│  Version     2.1.0                                          │
│                                                             │
│  Description:                                               │
│  A professional pomodoro timer with customizable            │
│  work/break intervals, statistics tracking, and             │
│  Apple Watch support.                                       │
│                                                             │
│  Actions:    15 steps                                       │
│  Requires:   Notifications, Calendar                        │
│                                                             │
│  ⚠️  This shortcut will be added to Shortcuts.app           │
│                                                             │
│  [Y] Install  [N] Cancel  [P] Preview in browser            │
│                                                             │
└───────────────────────────────────────────────────────────────┘
```

## 安装方式

### 方式 1: iCloud 链接 (推荐)

```bash
# 直接打开 iCloud 分享链接
open "https://www.icloud.com/shortcuts/abc123..."

# Shortcuts.app 会自动弹出安装确认
```

### 方式 2: URL Scheme

```bash
# 使用 shortcuts:// URL scheme
open "shortcuts://import-shortcut?url=https://www.icloud.com/shortcuts/abc123"
```

### 方式 3: 下载 .shortcut 文件

```bash
# 下载到本地后打开
curl -L "https://routinehub.co/download/123" -o shortcut.shortcut
open shortcut.shortcut
```

## 搜索 API

### RoutineHub API

```bash
# 搜索
curl "https://routinehub.co/api/v1/shortcuts?search=pomodoro"

# 获取详情
curl "https://routinehub.co/api/v1/shortcuts/123"
```

### Web Search (Fallback)

```bash
# 使用 Google 搜索
site:routinehub.co OR site:icloud.com/shortcuts "pomodoro timer"
```

## 命令参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `<keyword>` | 搜索关键词 | `/shortcut-search timer` |
| `--source` | 指定来源 | `--source routinehub` |
| `--limit` | 结果数量 | `--limit 10` |
| `--sort` | 排序方式 | `--sort downloads` |
| `--install` | 直接安装第一个 | `--install` |

## 安全检查

安装前自动检查：

| 检查项 | 说明 |
|--------|------|
| 来源验证 | 确认来自可信网站 |
| 权限审查 | 列出需要的系统权限 |
| 动作预览 | 显示主要动作步骤 |
| 社区评价 | 显示用户评分和评论 |

## 与 Solar 集成

```
用户: "我需要一个能自动发送消息的快捷指令"

Solar Agent:
1. 解析意图: 需要 "自动发送消息" 功能
2. 检查本地: 无匹配的 solar_* shortcuts
3. 触发搜索: /shortcut-search "auto send message"
4. 展示结果: 3 个相关 shortcuts
5. 用户选择: 安装 "Scheduled Messages"
6. 注册到系统表: sys_shortcuts
```

## 示例

```bash
# 搜索天气相关
/shortcut-search weather

# 搜索生产力工具
/shortcut-search productivity --source routinehub --limit 5

# 搜索中文快捷指令
/shortcut-search 翻译

# 搜索并直接安装评分最高的
/shortcut-search "morning routine" --sort rating --install
```

## 相关 Skill

- `/shortcut` - 执行已安装的 Shortcuts
- `/shortcut-builder` - 自己创建 Shortcuts
