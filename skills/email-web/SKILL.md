---
name: email-web
description: 启动 TVS 邮件搜索 Web 界面
user-invocable: true
---

# /email-web - TVS 邮件搜索 Web 界面

启动基于 TVS 风格的邮件搜索 Web 应用。

## 用法

```bash
/email-web              # 启动服务器并打开浏览器
/email-web start        # 仅启动服务器
/email-web stop         # 停止服务器
/email-web status       # 查看服务器状态
```

## 执行流程

### 1. 启动服务器

```bash
cd /Users/sihaoli/Solar/core/tvs/web
python3 server.py
```

服务器启动后显示:

```
┌─────────────────────────────────────────────────────────────┐
│                 TVS EMAIL SEARCH SERVER                      │
├─────────────────────────────────────────────────────────────┤
│  Status     RUNNING                                         │
│  Port       3847                                            │
│  URL        http://localhost:3847                           │
└───────────────────────────── [solar-dark] Powered by TVS v0.3.0 ─┘
```

### 2. 打开浏览器

```bash
open http://localhost:3847
```

### 3. Web 界面功能

- **搜索框**: 输入关键词搜索邮件
- **结果统计**: 显示找到的邮件总数
- **邮件列表**: 表格形式展示搜索结果
- **邮件摘要**: 每封邮件的详细摘要卡片

## Web 界面截图

```
┌─────────────────────────────────────────────────────────────┐
│                    TVS EMAIL SEARCH                          │
│                Terminal Visual System v0.3.0                 │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [搜索框: deepseek                    ] [SEARCH]     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─ SEARCH RESULTS ─────────────────────────────────────┐  │
│  │ Keyword: deepseek                                    │  │
│  │ Total: 10  |  Showing: Top 3                         │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ EMAIL LIST ─────────────────────────────────────────┐  │
│  │ #  From                  Date        Subject         │  │
│  │ 1  Google 学术搜索       2026-01-29  DeepSeek - 新结果│  │
│  │ 2  InfoQ                 2026-01-30  硅谷刷屏...      │  │
│  │ 3  The Deep View         2026-01-28  Clawdbot viral  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│                    [solar-dark] Powered by TVS v0.3.0       │
└─────────────────────────────────────────────────────────────┘
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web 界面 |
| `/search?keyword=xxx` | GET | 搜索邮件 API |
| `/health` | GET | 健康检查 |

## 文件位置

```
/Users/sihaoli/Solar/core/tvs/web/
├── index.html      # Web 前端 (TVS 风格)
├── server.py       # Python API 服务器
└── server.mjs      # Node.js 备用服务器
```

## 依赖

- **Python 3**: 运行服务器
- **himalaya**: CLI 邮件客户端
- **浏览器**: Chrome/Safari/Firefox

## 停止服务器

```bash
# 方法 1: 使用 skill
/email-web stop

# 方法 2: 手动停止
lsof -ti:3847 | xargs kill
```

## 配置

服务器默认端口: `3847`

如需修改，编辑 `/Users/sihaoli/Solar/core/tvs/web/server.py`:

```python
PORT = 3847  # 改为其他端口
```

## 相关 Skill

- `/mail` - 命令行邮件搜索
- `/office-email` - 完整邮件管理
