# Knowledge Skill - 知识库同步

统一知识库同步引擎，支持多种外部知识源。

## 用法

```
/knowledge sync        # 同步所有知识源
/knowledge obsidian    # 同步 Obsidian
/knowledge rules       # 同步 Solar Rules
/knowledge query <词>  # 查询知识库
/knowledge status      # 查看状态
```

## 支持的知识源

| 来源 | 类型 | 状态 |
|------|------|------|
| Solar Rules | markdown | ✅ 已同步 (65篇) |
| Obsidian | markdown | 🔧 待配置 |
| Apple Notes | sqlite | 🔧 待开发 |
| Notion | api | 🔧 待开发 |
| GitHub | git | 🔧 待开发 |

## 配置 Obsidian

1. 安装 Obsidian: https://obsidian.md
2. 创建 Vault 或使用现有的
3. 配置路径（二选一）:
   - iCloud: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/`
   - 本地: `~/Obsidian/`
4. 运行 `/knowledge obsidian` 同步

## 实现

文件: `~/.claude/core/cortex/knowledge-sync.ts`
