---
name: browser
description: 浏览器自动化 - 网页操作、表单填写、数据抓取 (Playwright MCP)
user-invocable: true
argument-hint: "[open <url>|fill|click|screenshot]"
---

# 浏览器自动化 (Playwright MCP)

通过 Playwright MCP Server 控制浏览器，实现网页自动化。

## 前提条件

- 已安装: `npm install -g @playwright/mcp`
- 已配置: `~/.mcp.json`
- 需要重启 Claude Code 加载 MCP Server

## 可用操作

### 导航
- **browser_navigate**: 打开 URL
- **browser_go_back**: 后退
- **browser_go_forward**: 前进
- **browser_reload**: 刷新页面

### 交互
- **browser_click**: 点击元素
- **browser_fill**: 填写表单
- **browser_select**: 选择下拉选项
- **browser_hover**: 悬停元素
- **browser_press_key**: 按键

### 信息获取
- **browser_screenshot**: 截图
- **browser_get_text**: 获取文本
- **browser_get_html**: 获取 HTML
- **browser_get_url**: 获取当前 URL

### 等待
- **browser_wait_for**: 等待元素出现
- **browser_wait_for_navigation**: 等待导航完成

## 使用示例

### 1. 打开网页并截图
```
用户: 打开 baidu.com 并截图

Claude: [使用 browser_navigate 打开 https://baidu.com]
        [使用 browser_screenshot 截图]
```

### 2. 自动填写表单
```
用户: 在登录页面填写用户名 test@example.com

Claude: [使用 browser_fill 填写表单]
        selector: input[name="email"]
        value: test@example.com
```

### 3. 抓取数据
```
用户: 获取页面上所有商品价格

Claude: [使用 browser_get_text 获取文本]
        selector: .product-price
```

### 4. 自动化流程
```
用户: 帮我在 12306 查询北京到上海的车票

Claude: [执行以下步骤]
        1. browser_navigate: https://www.12306.cn
        2. browser_fill: 出发城市 = 北京
        3. browser_fill: 到达城市 = 上海
        4. browser_click: 查询按钮
        5. browser_wait_for: 结果列表
        6. browser_screenshot: 保存结果
```

## 常见场景

| 场景 | 操作 |
|------|------|
| 网页截图 | navigate → screenshot |
| 表单提交 | fill → click |
| 数据抓取 | navigate → get_text/get_html |
| 自动登录 | fill(用户名) → fill(密码) → click(登录) |
| 订票/抢购 | 完整流程自动化 |

## 注意事项

- 首次使用会自动安装 Chromium 浏览器
- 默认使用无头模式 (headless)
- 敏感操作需用户确认
- 不要用于恶意爬虫或攻击

## MCP 工具列表

重启后可使用以下 MCP 工具:
- `mcp__playwright__browser_navigate`
- `mcp__playwright__browser_click`
- `mcp__playwright__browser_fill`
- `mcp__playwright__browser_screenshot`
- 等等...
