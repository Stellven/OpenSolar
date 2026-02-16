# /xiaoai - 调用小爱 (OpenClaw)

> 小爱是 Solar 的 AI 秘书，负责日常事务和消息处理

## 用法

```bash
/xiaoai <任务描述>
/xiaoai --agent <agent名> <任务描述>
```

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--agent` | 指定 OpenClaw agent | main |
| `--thinking` | 思考深度 (off/minimal/low/medium/high) | medium |
| `--model` | 指定模型 | glm-4.7 |

## 示例

```bash
# 日常任务
/xiaoai 查一下今天的邮件

# 深度分析
/xiaoai --thinking high 分析这封邮件的优先级

# 指定模型
/xiaoai --model glm-5 帮我写个周报

# 发送消息
/xiaoai 发微信给张三说明天开会
```

## 小爱的能力

| 类别 | 技能 |
|------|------|
| 📧 邮件 | 查邮件、发邮件、邮件摘要 |
| 📅 日历 | 查日程、加日程、提醒 |
| 📝 笔记 | Obsidian 读写 |
| ✅ 任务 | Things 3、提醒事项 |
| 📨 消息 | iMessage、WhatsApp、Telegram |
| 🌐 浏览器 | 网页自动化 |
| 🤖 自动化 | 工作流编排 |

## 执行方式

```bash
openclaw agent --local --agent main --message "<任务>"
```

## 与 Solar 的分工

| Solar (Claude) | 小爱 (OpenClaw) |
|----------------|-----------------|
| 架构设计 | 日常事务 |
| 代码开发 | 邮件/日历/提醒 |
| 深度分析 | 网页抓取 |
| 牛马管理 | 消息发送 |

## 注意事项

- 小爱默认用 GLM-4.7，便宜快速
- 复杂任务可以 `--thinking high`
- 小爱是系统服务，会话重启后依然可用
