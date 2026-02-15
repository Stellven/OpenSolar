---
name: email-search
description: 搜索邮件并显示摘要 (CLI)
user-invocable: true
argument-hint: "<keyword>"
---

# /mail - 邮件搜索

通过关键词搜索邮件，显示前 3 封的摘要。

## 用法

```bash
/mail <keyword>           # 搜索包含关键词的邮件
/mail deepseek            # 搜索 deepseek 相关邮件
/mail anthropic           # 搜索 anthropic 相关邮件
```

## 执行流程

### 1. 搜索邮件

使用 himalaya CLI 搜索邮件:

```bash
himalaya envelope list --page-size 10 --output json "subject <keyword>"
```

### 2. 读取邮件内容

对前 3 封邮件读取完整内容:

```bash
himalaya message read <email_id>
```

### 3. 生成摘要

提取邮件中的关键句子，生成简洁摘要。

### 4. TVS 渲染输出

使用 TVS solar-dark 主题渲染结果:

```
┌─────────────────────────────────────────────────────────────┐
│                     📧 EMAIL SEARCH                          │
├─────────────────────────────────────────────────────────────┤
│  Keyword       <keyword>                                    │
│  Total Found   <count>                                      │
│  Showing       Top 3                                        │
├─────────────────────────────────────────────────────────────┤
│  #   From                    Date         Subject           │
│  ─────────────────────────────────────────────────────────  │
│  1   <from>                  <date>       <subject>         │
│  2   <from>                  <date>       <subject>         │
│  3   <from>                  <date>       <subject>         │
└───────────────────────────── [solar-dark] Powered by TVS v0.3.0 ─┘
```

然后对每封邮件显示详细摘要卡片。

## 依赖

- **himalaya**: CLI 邮件客户端 (`brew install himalaya`)
- **配置**: `~/.config/himalaya/config.toml` 需配置邮箱账户

## 示例输出

```
┌─────────────────────────────────────────────────────────────┐
│  📩 Email 1: DeepSeek - 新的结果                             │
├─────────────────────────────────────────────────────────────┤
│  From    Google 学术搜索快讯                                 │
│  Date    2026-01-29 18:17 PST                               │
├─────────────────────────────────────────────────────────────┤
│  SUMMARY                                                    │
│  • LLM 在心血管磁共振成像中的可靠性比较                      │
│  • DeepSeek 生成摘要的语言特征研究                           │
│  • AI 驱动的 ESG 评估分析                                   │
└───────────────────────────── [solar-dark] Powered by TVS v0.3.0 ─┘
```

## 相关 Skill

- `/email-web` - 启动 Web 界面搜索邮件
- `/office-email` - 完整邮件管理 (发送/回复/删除)
