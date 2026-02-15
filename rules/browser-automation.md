# 浏览器自动化选择指南

## 工具选择矩阵

| 场景 | 推荐工具 | 原因 |
|------|----------|------|
| 简单 API 调用 | WebFetch | 快速、轻量 |
| 静态页面抓取 | WebFetch | 足够用 |
| 需要登录 | Playwright | 支持 Cookie/Session |
| JavaScript 渲染页面 | Playwright | 完整浏览器环境 |
| 表单填写 | Playwright | browser_fill_form |
| 截图需求 | Playwright | browser_take_screenshot |
| 多步骤操作 | Playwright | 状态保持 |
| 需要点击交互 | Playwright | browser_click |

## Playwright 常用操作

```bash
# 导航
mcp__playwright__browser_navigate url="https://..."

# 截图
mcp__playwright__browser_take_screenshot type="png"

# 获取页面快照 (比截图更省 token)
mcp__playwright__browser_snapshot

# 点击元素
mcp__playwright__browser_click ref="button#submit"

# 填写表单
mcp__playwright__browser_fill_form fields=[...]

# 关闭页面
mcp__playwright__browser_close
```

## 触发条件

当用户请求涉及以下关键词时，优先考虑 Playwright:
- "登录"、"login"
- "截图"、"screenshot"
- "填写"、"表单"
- "点击"、"click"
- "自动化"
- 具体网站交互

## 练习建议

定期使用 Playwright 完成以下任务以提升熟练度:
1. 网站状态检查 (navigate + snapshot)
2. 页面截图存档
3. 表单自动填写
4. 多页面导航流程
