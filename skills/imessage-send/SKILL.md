---
name: imessage-send
description: "发送 iMessage 消息到指定手机号"
homepage: https://github.com/sihaoli/solar
metadata: {"moltbot":{"emoji":"💬","requires":{"bins":["osascript"]}}}
---

# iMessage 发送工具

## 快速使用

```bash
# 发送简单消息
bun ~/.claude/skills/imessage-send/send.ts "+8618688716450" "你好！"

# 发送多行消息
bun ~/.claude/skills/imessage-send/send.ts "+8618688716450" "第一行
第二行
第三行"
```

## 参数

| 参数 | 说明 | 示例 |
|------|------|------|
| phone | 手机号（必须） | "+8618688716450" |
| message | 消息内容（必须） | "你好" |

## 注意事项

1. **手机号格式**：必须加国际区号，如 `+86` 开头
2. **iMessage 账号**：需要在 Messages.app 中登录 Apple ID
3. **特殊字符**：消息中的引号会自动转义

## 示例场景

### 发送邮件整理报告

```bash
bun send.ts "+8618688716450" "📧 邮件整理
未读：127封
工作：25封
社交：35封
促销：67封"
```

### 发送提醒

```bash
bun send.ts "+8618688716450" "⏰ 提醒：15分钟后开会"
```
