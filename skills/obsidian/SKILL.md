# Obsidian Skill

与 iCloud 上的 "solar know" vault 双向同步 + 知识抽取。

## 用法

```
/obsidian new <标题>           # 创建新笔记
/obsidian search <关键词>      # 搜索笔记
/obsidian read <文件名>        # 读取笔记
/obsidian today               # 创建/打开今日日记
/obsidian sync <内容>         # 同步内容到 vault
/obsidian list                # 列出所有笔记
/obsidian extract             # 抽取知识到 Solar 知识库
/obsidian extract-all         # 抽取所有笔记的知识
/obsidian status              # 查看抽取状态
```

## Vault 路径

`~/Library/Mobile Documents/com~apple~CloudDocs/solar know`

## 知识抽取

从 Obsidian 笔记中抽取结构化知识，写入 `cortex_sources` 表：

```bash
bun ~/.claude/skills/obsidian/knowledge-extractor.ts extract-all
```

**抽取内容**:
- 核心概念 (concept)
- 洞察结论 (insight)
- 方法论 (method)
- 参考文献 (reference)
- 经验教训 (lesson)

## 自动同步

以下内容会自动同步到 Obsidian：
- `/insight` 深度研究报告 → `Insights/` 目录
- 重要分析结论 → `Analysis/` 目录
- 每日总结 → `Daily/` 目录

## 定期任务建议

```bash
# 每周抽取一次知识（可加入 crontab）
0 9 * * 1 bun ~/.claude/skills/obsidian/knowledge-extractor.ts extract-all
```

## 文件列表

| 文件 | 功能 |
|------|------|
| `obsidian.ts` | 核心操作（新建/搜索/读取/日记） |
| `auto-sync.ts` | 自动同步（被其他模块调用） |
| `knowledge-extractor.ts` | 知识抽取（写入 cortex_sources） |
