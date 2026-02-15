---
name: call
description: FaceTime/电话呼叫 - 支持自然语言说"打电话给某人"
user-invocable: true
argument-hint: "<联系人名字或电话号码> [--video]"
---

# FaceTime 呼叫

通过自然语言发起 FaceTime 音频/视频通话或普通电话。

## 使用方式

```bash
# 直接使用 skill
/call 张三
/call 张三 --video
/call +86 138 1234 5678

# 自然语言触发 (自动识别)
我要打电话给张三
帮我呼叫李四
视频联系王五
打给妈妈
```

## 自然语言模式识别

当用户说以下类似的话时，自动触发呼叫：

| 用户说 | 动作 |
|-------|------|
| "我要打电话给张三" | FaceTime 音频呼叫张三 |
| "打给妈妈" | FaceTime 音频呼叫妈妈 |
| "视频呼叫李四" | FaceTime 视频呼叫李四 |
| "帮我联系王总" | FaceTime 音频呼叫王总 |
| "call John" | FaceTime 音频呼叫 John |

## 执行流程

### 1. 解析意图

```typescript
// 识别呼叫动作
const intent = parseCallIntent(input);
// { action: "call" | "video" | "audio", target: "张三" }
```

### 2. 搜索联系人

```bash
# 使用 AppleScript 从通讯录搜索
osascript -e 'tell application "Contacts" to get name of people whose name contains "张"'
```

支持的搜索方式：
- **精确匹配**: 名字完全相同
- **前缀匹配**: 名字以查询开头
- **包含匹配**: 名字包含查询词
- **拼音首字母**: ZS 匹配 "张三"

### 3. 发起呼叫

```bash
# FaceTime 视频
open "facetime://+8613812345678"

# FaceTime 音频
open "facetime-audio://+8613812345678"

# 普通电话 (通过 iPhone Handoff)
open "tel://+8613812345678"
```

## 联系人优先级

1. **手机号** (mobile/iPhone/手机)
2. **其他电话**
3. **邮箱** (用于 Apple ID FaceTime)

## 输出格式

```
┌─ 📞 Call Agent ─────────────────────────────────────────┐
│ 正在发起 FaceTime 音频呼叫...                            │
├─────────────────────────────────────────────────────────┤
│ 联系人: 张三                                            │
│ 号码:   +86 138 1234 5678                               │
│ 方式:   FaceTime Audio                                  │
└─────────────────────────────────────────────────────────┘
```

## 错误处理

```
┌─ ⚠️ 呼叫失败 ────────────────────────────────────────────┐
│ 未找到联系人: 张三                                       │
├─────────────────────────────────────────────────────────┤
│ 建议:                                                   │
│ 1. 检查名字拼写                                         │
│ 2. 使用 /call search 张 搜索                            │
│ 3. 直接输入电话号码                                     │
└─────────────────────────────────────────────────────────┘
```

## 子命令

| 命令 | 说明 |
|------|------|
| `/call <名字>` | FaceTime 音频呼叫 |
| `/call <名字> --video` | FaceTime 视频呼叫 |
| `/call <号码>` | 直接呼叫号码 |
| `/call search <关键词>` | 搜索联系人 |
| `/call recent` | 显示最近通话 |

## 权限要求

- **通讯录访问**: 需要授权访问 Apple Contacts
- **FaceTime**: 需要 macOS 已登录 FaceTime

## 配置

可在 `~/.solar/call-config.json` 配置：

```json
{
  "defaultMethod": "facetime-audio",
  "autoConfirm": false,
  "aliases": {
    "老板": "张三",
    "boss": "John Smith"
  }
}
```

## 示例

```
用户: 我要打电话给妈妈

┌─ 📞 Call Agent ─────────────────────────────────────────┐
│ 正在发起 FaceTime 音频呼叫...                            │
├─────────────────────────────────────────────────────────┤
│ 联系人: 妈妈                                            │
│ 号码:   +86 139 8765 4321                               │
│ 方式:   FaceTime Audio                                  │
└─────────────────────────────────────────────────────────┘

✅ 呼叫已发起，FaceTime 窗口应该已经打开
```
