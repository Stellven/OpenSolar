# /chatgpt - ChatGPT 网页版集成

> 使用你的 ChatGPT Plus 订阅，通过浏览器自动化调用

## 功能

通过 Playwright 自动化 chatgpt.com，使用你已登录的 Chrome session。

## 使用方式

```
/chatgpt 帮我分析这段代码
/chatgpt 用 GPT-4o 生成一个 React 组件
@ChatGPT 分析这个问题
```

## 工作原理

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Solar/Claude  │ ──▶ │  Playwright     │ ──▶ │   chatgpt.com   │
│                 │     │  (Chrome Profile)│     │   (已登录)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        │                   ◀───────────────────────────┘
        │                      返回 ChatGPT 回复
        ▼
```

## 配置

### 1. 确保 Chrome 已登录 ChatGPT

在 Chrome 中访问 https://chatgpt.com 并登录你的 Plus 账号。

### 2. Chrome Profile 路径

macOS 默认路径:
- Default: `~/Library/Application Support/Google/Chrome/Default`
- Profile 1: `~/Library/Application Support/Google/Chrome/Profile 1`

### 3. 选择使用的 Profile

在 `settings.json` 中配置:
```json
{
  "chatgpt": {
    "chrome_profile": "Profile 1",
    "model": "GPT-4o"
  }
}
```

## 快速开始

### 1. 确保 Chrome 已登录 ChatGPT

```bash
# 在 Chrome 中访问并登录
open -a "Google Chrome" https://chatgpt.com
```

### 2. 测试调用

```bash
# 使用 CLI
bun ~/.claude/core/chatgpt-web/client.ts ask "什么是量子计算？"

# 指定模型
bun ~/.claude/core/chatgpt-web/client.ts ask "解释相对论" --model o1
```

### 3. 在 Solar 中使用

```typescript
// 方式 1: 通过 Skill 触发
"/chatgpt 分析这段代码的问题"

// 方式 2: 在 Agent 中调用
import { askChatGPT } from '~/.claude/core/chatgpt-web/client';

const response = await askChatGPT('你的问题', {
  model: 'GPT-4o',
  profile: 'Profile 1'
});
```

## 支持的模型

通过 ChatGPT 网页的模型选择器:
- GPT-4o
- GPT-4o mini
- o1 (推理)
- o3-mini

## 注意事项

1. **首次使用**: 需要先在 Chrome 中手动登录 ChatGPT
2. **并发限制**: ChatGPT 网页一次只能处理一个对话
3. **速度**: 比直接 API 慢（需要浏览器渲染）
4. **稳定性**: OpenAI 可能更新网页结构，需要维护

## 成本对比

| 方式 | 费用 | 限制 |
|------|------|------|
| OpenAI API | $15/1M tokens | 按量付费 |
| **ChatGPT Plus** | **$20/月** | **无限使用** ✅ |

对于大量使用场景，ChatGPT 网页版能节省大量费用！

## 故障排除

### 问题: 未登录
```
解决: 在 Chrome 中手动访问 chatgpt.com 登录
```

### 问题: 找不到输入框
```
解决: ChatGPT 可能更新了页面结构，需要更新选择器
```

### 问题: 回复超时
```
解决: 增加 waitForSelector 的超时时间
```
