# /install - Solar 安装/恢复清单

> **用途**: 新机器安装、环境恢复、配置同步
> **来源**: Mac Mini 4 Pro (192.168.50.194)
> **更新**: 2026-02-18

## 功能

执行 Solar 系统的完整安装/恢复流程：
1. 检查当前状态
2. 识别缺失项
3. 自动修复/同步
4. 验证安装结果

## 使用方式

```bash
# 完整安装/恢复
/install

# 仅检查不修复
/install --check

# 从 Mac Mini 同步
/install --sync

# 安装特定组件
/install skills
/install rules
/install database
```

## 安装流程

### Phase 1: 环境检查

```bash
# 检查必需运行时
check_runtime() {
  echo "=== Phase 1: 运行时环境 ==="

  # Bun
  if ! command -v bun &> /dev/null; then
    echo "安装 Bun..."
    curl -fsSL https://bun.sh/install | bash
  fi

  # Node
  if ! command -v node &> /dev/null; then
    echo "安装 Node..."
    brew install node
  fi

  # SQLite
  if ! command -v sqlite3 &> /dev/null; then
    echo "安装 SQLite..."
    brew install sqlite
  fi

  # Rust/Cargo
  if ! command -v cargo &> /dev/null; then
    echo "安装 Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
  fi

  echo "✓ 运行时环境就绪"
}
```

### Phase 2: 目录结构

```bash
# 创建目录结构
create_directories() {
  echo "=== Phase 2: 目录结构 ==="

  dirs=(
    "$HOME/.claude/rules/archive"
    "$HOME/.claude/skills"
    "$HOME/.claude/agents"
    "$HOME/.claude/hooks"
    "$HOME/.claude/core"
    "$HOME/.claude/modes"
    "$HOME/.claude/solar/bin"
    "$HOME/.solar/search-index"
    "$HOME/.solar/brain-router"
    "$HOME/.solar/cortex"
  )

  for d in "${dirs[@]}"; do
    if [ ! -d "$d" ]; then
      mkdir -p "$d"
      echo "✓ 创建 $d"
    else
      echo "  已存在 $d"
    fi
  done
}
```

### Phase 3: 从 Mac Mini 同步

```bash
# 同步配置
sync_from_macmini() {
  echo "=== Phase 3: 从 Mac Mini 同步 ==="

  MACMINI="lisihao@192.168.50.194"
  MACMINI_PATH="/Users/lisihao"

  # 测试连接
  if ! ssh -o ConnectTimeout=5 "$MACMINI" "echo ok" &>/dev/null; then
    echo "✗ 无法连接到 Mac Mini"
    echo "  请确保在同一网络，且 SSH 已配置"
    return 1
  fi

  echo "✓ 已连接到 Mac Mini"

  # 同步 .claude
  echo "同步 .claude..."
  rsync -avz --delete "$MACMINI:$MACMINI_PATH/.claude/" "$HOME/.claude/"

  # 同步 .solar (不含大文件)
  echo "同步 .solar..."
  rsync -avz --exclude 'trajectories' --exclude '*.jsonl' \
    "$MACMINI:$MACMINI_PATH/.solar/" "$HOME/.solar/"

  # 同步 MCP 配置
  echo "同步 MCP 配置..."
  rsync -avz "$MACMINI:$MACMINI_PATH/.mcp.json" "$HOME/"
  rsync -avz "$MACMINI:$MACMINI_PATH/.claude.json" "$HOME/"

  echo "✓ 同步完成"
}
```

### Phase 4: 数据库修复

```bash
# 数据库检查与修复
fix_database() {
  echo "=== Phase 4: 数据库修复 ==="

  DB="$HOME/.solar/solar.db"

  if [ ! -f "$DB" ]; then
    echo "✗ 数据库不存在，需要从 Mac Mini 同步"
    return 1
  fi

  # 删除 WAL/SHM 文件
  rm -f "$DB-wal" "$DB-shm"

  # 检查完整性
  result=$(sqlite3 "$DB" "PRAGMA integrity_check" 2>&1)
  if [ "$result" != "ok" ]; then
    echo "✗ 数据库损坏: $result"
    echo "  需要重新同步"
    return 1
  fi

  # 优化
  sqlite3 "$DB" "VACUUM" 2>/dev/null

  echo "✓ 数据库完整"
}
```

### Phase 5: 搜索引擎

```bash
# 搜索引擎检查
check_search() {
  echo "=== Phase 5: 搜索引擎 ==="

  SEARCH_BIN="$HOME/.claude/solar/bin/solar-search"

  if [ ! -f "$SEARCH_BIN" ]; then
    echo "✗ solar-search 不存在"
    echo "  从 Mac Mini 复制或编译:"
    echo "  cd ~/.claude/solar/core/search && cargo build --release"
    return 1
  fi

  if [ ! -d "$HOME/.solar/search-index" ] || [ -z "$(ls -A $HOME/.solar/search-index 2>/dev/null)" ]; then
    echo "⚠ 搜索索引为空，需要重建"
    echo "  运行: $SEARCH_BIN index all"
  fi

  echo "✓ 搜索引擎就绪"
}
```

### Phase 6: 验证

```bash
# 验证安装
verify_installation() {
  echo "=== Phase 6: 验证安装 ==="

  echo "           当前值    标准值    状态"
  echo "─────────────────────────────────────"

  checks=0
  passes=0

  # Rules
  current=$(ls ~/.claude/rules/*.md 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 10 ]; then
    echo "Rules       $current        10       ✓"
    ((passes++))
  else
    echo "Rules       $current        10       ✗"
  fi
  ((checks++))

  # Skills
  current=$(ls ~/.claude/skills 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 90 ]; then
    echo "Skills      $current        93       ✓"
    ((passes++))
  else
    echo "Skills      $current        93       ✗"
  fi
  ((checks++))

  # Agents
  current=$(ls ~/.claude/agents 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 15 ]; then
    echo "Agents      $current        16       ✓"
    ((passes++))
  else
    echo "Agents      $current        16       ✗"
  fi
  ((checks++))

  # Hooks
  current=$(ls ~/.claude/hooks 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 70 ]; then
    echo "Hooks       $current        77       ✓"
    ((passes++))
  else
    echo "Hooks       $current        77       ✗"
  fi
  ((checks++))

  # Core
  current=$(ls ~/.claude/core 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 50 ]; then
    echo "Core        $current        51       ✓"
    ((passes++))
  else
    echo "Core        $current        51       ✗"
  fi
  ((checks++))

  # Favorites
  current=$(sqlite3 ~/.solar/solar.db "SELECT COUNT(*) FROM sys_favorites" 2>/dev/null)
  if [ "$current" -ge 80 ]; then
    echo "Favorites   $current        90       ✓"
    ((passes++))
  else
    echo "Favorites   $current        90       ✗"
  fi
  ((checks++))

  echo ""
  echo "通过: $passes / $checks"

  if [ "$passes" -eq "$checks" ]; then
    echo "✓ 安装验证通过"
    return 0
  else
    echo "✗ 部分检查未通过，请检查上方 ✗ 项"
    return 1
  fi
}
```

## 完整安装脚本

```bash
#!/bin/bash
# solar-install.sh - Solar 完整安装/恢复

set -e

echo "╭─────────────────────────────────────────────────────────────────╮"
echo "│                    🔧 Solar 安装/恢复                           │"
echo "│                    $(date '+%Y-%m-%d %H:%M:%S')                            │"
echo "├─────────────────────────────────────────────────────────────────┤"
echo ""

# Phase 1
check_runtime
echo ""

# Phase 2
create_directories
echo ""

# Phase 3 (可选)
if [ "$1" = "--sync" ]; then
  sync_from_macmini
  echo ""
fi

# Phase 4
fix_database
echo ""

# Phase 5
check_search
echo ""

# Phase 6
verify_installation

echo ""
echo "├─────────────────────────────────────────────────────────────────┤"
echo "│  安装完成！                                                     │"
echo "╰─────────────────────────────────────────────────────────────────╯"
```

## 参数说明

| 参数 | 说明 |
|------|------|
| 无参数 | 执行完整安装流程 (不同步) |
| `--check` | 仅检查，不执行任何修复 |
| `--sync` | 从 Mac Mini 同步配置 |
| `--help` | 显示帮助信息 |

## 依赖

- **Mac Mini 连接**: 需要能 SSH 连接到 `lisihao@192.168.50.194`
- **rsync**: 用于同步文件
- **brew**: 用于安装依赖 (macOS)

## 注意事项

1. **数据库同步**: 需要先关闭目标机器上的数据库连接
2. **WAL 文件**: 同步前删除 `.db-wal` 和 `.db-shm` 文件
3. **搜索索引**: 如未同步，需要手动重建

---

*Install Skill v1.0*
*创建于: 2026-02-18*
