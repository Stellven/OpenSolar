---
name: shortcut
description: 执行 Apple Shortcuts - AI OS 技能执行层
user-invocable: true
argument-hint: "<shortcut_name> [params_json]"
---

# /shortcut - Apple Shortcuts 执行

执行 macOS/iOS Shortcuts 作为 Solar AI OS 的技能执行层。

## 用法

```bash
/shortcut list                              # 列出所有可用 shortcuts
/shortcut run <name>                        # 执行 shortcut
/shortcut run <name> '{"key":"value"}'      # 带参数执行
/shortcut check <name>                      # 检查 shortcut 是否存在
```

## Solar 预置 Shortcuts

### 系统操作类 (system)

| Shortcut | 功能 | 触发词 |
|----------|------|--------|
| `solar_set_reminder` | 创建提醒 | "提醒我..." |
| `solar_add_calendar` | 添加日历 | "安排会议..." |
| `solar_send_message` | 发送消息 | "发消息给..." |
| `solar_make_call` | 打电话 | "打电话给..." |
| `solar_control_home` | 控制智能家居 | "打开/关闭..." |

### AI 处理类 (ai)

| Shortcut | 功能 | 触发词 |
|----------|------|--------|
| `solar_summarize` | 文本摘要 | "总结一下..." |
| `solar_translate` | 翻译 | "翻译成..." |
| `solar_analyze_image` | 图像分析 | "分析这张图..." |
| `solar_transcribe` | 语音转文字 | "转录..." |
| `solar_generate_text` | 生成文本 | "写一段..." |

### 数据获取类 (data)

| Shortcut | 功能 | 触发词 |
|----------|------|--------|
| `solar_get_clipboard` | 获取剪贴板 | "剪贴板内容" |
| `solar_get_location` | 获取位置 | "我在哪" |
| `solar_get_weather` | 获取天气 | "今天天气" |
| `solar_search_files` | 搜索文件 | "找一下..." |

### 工作流类 (workflow)

| Shortcut | 功能 | 触发词 |
|----------|------|--------|
| `solar_morning_briefing` | 早间简报 | "早安" |
| `solar_end_of_day` | 日终总结 | "今天完成了什么" |
| `solar_meeting_prep` | 会议准备 | "准备会议" |
| `solar_travel_mode` | 出行模式 | "我要出门" |

## 执行流程

### 1. 意图解析

```
用户: "提醒我明天下午3点开会"
     ↓
Solar Agent 解析:
├── 动作: remind
├── 时间: tomorrow 3pm
├── 内容: 开会
└── 匹配: solar_set_reminder
```

### 2. 参数映射

```json
{
  "shortcut": "solar_set_reminder",
  "params": {
    "title": "开会",
    "datetime": "2026-01-31T15:00:00"
  }
}
```

### 3. 执行

```bash
shortcuts run "solar_set_reminder" \
  --input-type "json" \
  --input '{"title":"开会","datetime":"2026-01-31T15:00:00"}'
```

### 4. 结果返回

```json
{
  "success": true,
  "shortcut": "solar_set_reminder",
  "result": {
    "reminder_id": "xxx",
    "message": "已创建提醒: 明天下午3点开会"
  },
  "duration_ms": 150
}
```

## 输出格式

### 成功执行

```
┌─────────────────────────────────────────────────────────────┐
│                  ⚡ SHORTCUT EXECUTED                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Shortcut   solar_set_reminder                              │
│  Status     SUCCESS ✓                                       │
│  Duration   150ms                                           │
│                                                             │
│  Result:                                                    │
│  {                                                          │
│    "reminder_id": "xxx",                                    │
│    "message": "已创建提醒: 明天下午3点开会"                   │
│  }                                                          │
│                                                             │
└───────────────────────────── [solar-dark] Powered by Solar ─┘
```

### 执行失败

```
┌─────────────────────────────────────────────────────────────┐
│                  ⚠️ SHORTCUT FAILED                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Shortcut   solar_unknown                                   │
│  Status     FAILED ✗                                        │
│  Error      Shortcut not found                              │
│                                                             │
│  Suggestions:                                               │
│  1. Run `/shortcut list` to see available shortcuts         │
│  2. Check if the shortcut is installed in Shortcuts.app     │
│                                                             │
└───────────────────────────── [solar-dark] Powered by Solar ─┘
```

## 自然语言路由

Solar Agent 会自动将自然语言路由到合适的 Shortcut:

```
用户输入                      → 路由到
─────────────────────────────────────────────────
"提醒我明天开会"              → solar_set_reminder
"翻译成英语: 你好"            → solar_translate
"今天天气怎么样"              → solar_get_weather
"帮我安排下周一的会议"        → solar_add_calendar
"打开客厅的灯"                → solar_control_home
```

## Siri 集成

所有 Solar Shortcuts 都支持 Siri 触发:

```
"Hey Siri, Solar 提醒我明天开会"
"Hey Siri, Solar 翻译"
"Hey Siri, Solar 天气"
```

## 权限级别

| 级别 | 说明 | 确认策略 |
|------|------|---------|
| 0 | 只读 (天气、时间) | 静默执行 |
| 1 | 本地写入 (提醒、笔记) | 静默执行 |
| 2 | 通信 (消息、邮件) | 显示预览 |
| 3 | 敏感 (支付) | 必须确认 |

## 开发新 Shortcut

### 1. 在 Shortcuts.app 创建

1. 打开 Shortcuts.app
2. 创建新快捷指令
3. 命名为 `solar_<功能名>`
4. 添加 "Get Input" 动作接收 JSON
5. 实现逻辑
6. 添加 "Output" 返回结果

### 2. 注册到 Solar

在 `shortcuts-seed.sql` 添加:

```sql
INSERT INTO sys_shortcuts (...) VALUES (
  'solar_new_feature',
  '新功能',
  '功能描述',
  'category',
  '["触发词1", "触发词2"]',
  'Solar 新功能',
  '{"type":"object","properties":{...}}',
  '{"type":"object","properties":{...}}',
  permission_level,
  requires_confirmation,
  supports_siri
);
```

## 相关文件

- Schema: `/Users/sihaoli/Solar/core/shortcuts/shortcuts-schema.sql`
- Seed: `/Users/sihaoli/Solar/core/shortcuts/shortcuts-seed.sql`
- Architecture: `/Users/sihaoli/Solar/core/shortcuts/ARCHITECTURE.md`
- Runner: `/Users/sihaoli/Solar/core/shortcuts/shortcut-runner.sh`

## 依赖

- **macOS 12+**: `shortcuts` 命令行工具
- **Shortcuts.app**: 已安装目标 shortcuts
- **jq**: JSON 处理 (`brew install jq`)

## 示例

```bash
# 列出所有 shortcuts
/shortcut list

# 执行天气查询
/shortcut run solar_get_weather '{"location":"北京"}'

# 创建提醒
/shortcut run solar_set_reminder '{"title":"开会","datetime":"2026-01-31T15:00:00"}'

# 检查 shortcut 是否存在
/shortcut check solar_set_reminder
```
