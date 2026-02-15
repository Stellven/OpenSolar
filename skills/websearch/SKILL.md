# Web Search Skill

WebSearch 工具的可靠替代方案，使用开放 API 进行网络搜索。

## 用法

```
/websearch <搜索关键词>
```

## 数据源

- **Wikipedia API** - 百科知识
- **DuckDuckGo Instant Answer** - 摘要信息
- **Hacker News Algolia** - 技术资讯

## 示例

```
/websearch Claude AI
/websearch machine learning
/websearch React hooks
```

## 实现位置

`~/.claude/core/web-search/web-search.ts`

## 技术细节

- 使用开放 API，无需 API Key
- 自动合并多个数据源结果
- 支持 JSON 输出格式
- 独立于 Anthropic WebSearch 工具

## 限制

- DuckDuckGo Instant Answer 可能对某些查询无结果
- 主要适合英文搜索
- 实时新闻类内容较少
