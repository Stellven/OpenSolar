# WebFetch 使用经验

## 常见失败原因

1. **Redirect** - URL 重定向到其他域，需要重新请求
2. **Rate Limit** - API 限制
3. **Network** - 网络超时

## 最佳实践

- 遇到 redirect 提示时，立即用新 URL 重新请求
- 优先使用 MCP 工具 (如 playwright) 获取复杂页面
- 简单 API 调用用 WebFetch，复杂页面用 Playwright
