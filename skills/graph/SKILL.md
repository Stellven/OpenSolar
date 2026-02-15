# /graph - 知识图谱可视化

## 触发
- `/graph memory` - 记忆关系图
- `/graph deps` - 依赖关系图
- `/graph calls` - 调用关系图
- `/graph files` - 文件关系图
- `/graph <table>` - 数据库表关系

## 执行

### 记忆关系图

```bash
# 提取记忆关联
sqlite3 ~/.solar/solar.db "
SELECT
  e.memory_id as from_id,
  'episodic' as from_type,
  s.memory_id as to_id,
  'semantic' as to_type,
  'derives' as relation
FROM evo_memory_episodic e
JOIN evo_memory_semantic s ON e.content LIKE '%' || s.namespace || '%'
LIMIT 50;
" | while IFS='|' read from_id from_type to_id to_type rel; do
  echo "\"$from_id\" -> \"$to_id\" [label=\"$rel\"];"
done
```

### Graphviz DOT 格式

```bash
# 生成 DOT 文件
cat > /tmp/memory-graph.dot << 'EOF'
digraph MemoryGraph {
  rankdir=LR;
  node [shape=box];

  // Episodic memories (蓝色)
  subgraph cluster_episodic {
    label="Episodic";
    style=filled;
    color=lightblue;
    // 节点
  }

  // Semantic memories (绿色)
  subgraph cluster_semantic {
    label="Semantic";
    style=filled;
    color=lightgreen;
    // 节点
  }

  // Relations
  // e1 -> s1 [label="derives"];
}
EOF

# 生成 SVG
dot -Tsvg /tmp/memory-graph.dot -o /tmp/memory-graph.svg
open /tmp/memory-graph.svg
```

### 依赖关系图 (Node.js)

```bash
# 使用 madge
npm install -g madge

# 生成依赖图
madge --image graph.svg src/

# 检测循环依赖
madge --circular src/

# 只看特定入口
madge --image graph.svg src/index.ts
```

### 调用关系图

```bash
# 从工具调用数据生成
sqlite3 ~/.solar/solar.db "
SELECT tool_name, COUNT(*) as cnt
FROM evo_tool_calls
GROUP BY tool_name
ORDER BY cnt DESC
LIMIT 20;
" | awk -F'|' '{
  printf "  \"%s\" [label=\"%s\\n(%d calls)\"];\n", $1, $1, $2
}'
```

### ASCII 图 (终端友好)

```bash
# 使用 graph-easy
brew install cpanm
cpanm Graph::Easy

echo "[Read] -> [Process] -> [Write]" | graph-easy

# 更复杂的图
cat << 'EOF' | graph-easy
[User] -> [Solar]
[Solar] -> [Memory]
[Solar] -> [Skills]
[Solar] -> [Agents]
[Memory] -> [Episodic]
[Memory] -> [Semantic]
[Memory] -> [Procedural]
EOF
```

### Mermaid 格式 (Markdown 友好)

```markdown
# 生成 Mermaid 图
echo '```mermaid'
echo 'graph LR'
sqlite3 ~/.solar/solar.db "
SELECT 'A[' || from_table || '] --> B[' || to_table || ']'
FROM (
  SELECT DISTINCT
    substr(fk.'from', 1, instr(fk.'from', '.')-1) as from_table,
    fk.'table' as to_table
  FROM pragma_foreign_key_list(fk.'table') as fk
);
"
echo '```'
```

## 输出格式

```
┌─ 🕸️ Knowledge Graph ────────────────────────────────────────────┐
│                                                                  │
│  类型: Memory Relations                                          │
│  节点: 45 | 边: 78                                               │
│                                                                  │
├─ ASCII 预览 ─────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐                 │
│  │ Episodic │────▶│ Semantic │────▶│Procedural│                 │
│  │  (123)   │     │  (45)    │     │  (28)    │                 │
│  └──────────┘     └──────────┘     └──────────┘                 │
│       │                │                                         │
│       ▼                ▼                                         │
│  ┌──────────┐     ┌──────────┐                                  │
│  │ Sessions │     │  Rules   │                                  │
│  │  (567)   │     │  (34)    │                                  │
│  └──────────┘     └──────────┘                                  │
│                                                                  │
├─ 导出 ───────────────────────────────────────────────────────────┤
│                                                                  │
│  SVG: /tmp/memory-graph.svg                                      │
│  DOT: /tmp/memory-graph.dot                                      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 在 Web 中查看

```bash
# 启动本地服务器查看 SVG
python3 -m http.server 8000 -d /tmp &
open http://localhost:8000/memory-graph.svg
```

## 工具推荐

| 工具 | 用途 | 安装 |
|------|------|------|
| Graphviz | DOT 图渲染 | `brew install graphviz` |
| madge | JS 依赖图 | `npm i -g madge` |
| graph-easy | ASCII 图 | `cpanm Graph::Easy` |
| D2 | 现代图表语言 | `brew install d2` |
