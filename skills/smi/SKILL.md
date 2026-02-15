# /smi - Solar Metadata Index

> 快速查询表结构，告别盲目尝试

## 命令

| 命令 | 说明 |
|------|------|
| `/smi <table>` | 查看表结构 |
| `/smi search <keyword>` | 搜索包含关键词的表 |
| `/smi list [pattern]` | 列出所有表 (可选模式过滤) |
| `/smi refresh` | 刷新 Schema 注册表 |

## 示例

```bash
# 查看表结构
/smi evo_memory_semantic
# Output: memory_id, namespace, key, value, embedding, ...

# 搜索表
/smi search preference
# Output: ont_preference_dimensions, ont_preference_history

# 列出所有 evo_ 表
/smi list evo_%

# 刷新注册表
/smi refresh
```

## 实现

执行: `bun run ~/.claude/skills/smi/smi.ts`
