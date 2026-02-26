#!/bin/bash
# solar-install.sh - Solar 完整安装/恢复
# 用法: ./solar-install.sh [--check|--sync|--help]

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 配置
MACMINI="lisihao@192.168.50.194"
MACMINI_PATH="/Users/lisihao"

# 计数器
CHECKS=0
PASSES=0
FAILS=0

# 辅助函数
pass() { echo -e "${GREEN}✓${NC} $1"; PASSES=$((PASSES+1)); CHECKS=$((CHECKS+1)); }
fail() { echo -e "${RED}✗${NC} $1"; FAILS=$((FAILS+1)); CHECKS=$((CHECKS+1)); }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
info() { echo "  $1"; }

# ========================================
# Phase 1: 运行时环境
# ========================================
check_runtime() {
  echo ""
  echo "=== Phase 1: 运行时环境 ==="

  # Bun
  if command -v bun &> /dev/null; then
    pass "Bun: $(bun --version)"
  else
    fail "Bun 未安装"
    info "安装: curl -fsSL https://bun.sh/install | bash"
  fi

  # Node
  if command -v node &> /dev/null; then
    pass "Node: $(node --version)"
  else
    fail "Node 未安装"
    info "安装: brew install node"
  fi

  # SQLite
  if command -v sqlite3 &> /dev/null; then
    pass "SQLite: $(sqlite3 --version | awk '{print $1}')"
  else
    fail "SQLite 未安装"
    info "安装: brew install sqlite"
  fi

  # Git
  if command -v git &> /dev/null; then
    pass "Git: $(git --version | awk '{print $3}')"
  else
    fail "Git 未安装"
  fi

  # Cargo (可选)
  if command -v cargo &> /dev/null; then
    pass "Cargo: $(cargo --version | awk '{print $2}')"
  else
    warn "Cargo 未安装 (搜索需要)"
  fi
}

# ========================================
# Phase 2: 目录结构
# ========================================
create_directories() {
  echo ""
  echo "=== Phase 2: 目录结构 ==="

  dirs=(
    "$HOME/.claude"
    "$HOME/.claude/rules"
    "$HOME/.claude/rules/archive"
    "$HOME/.claude/skills"
    "$HOME/.claude/agents"
    "$HOME/.claude/hooks"
    "$HOME/.claude/core"
    "$HOME/.claude/modes"
    "$HOME/.claude/solar/bin"
    "$HOME/.solar"
    "$HOME/.solar/search-index"
    "$HOME/.solar/brain-router"
    "$HOME/.solar/cortex"
  )

  dir_ok=0
  dir_create=0
  for d in "${dirs[@]}"; do
    if [ -d "$d" ]; then
      ((dir_ok++))
    else
      mkdir -p "$d"
      ((dir_create++))
    fi
  done

  echo "  已存在: $dir_ok 个, 新建: $dir_create 个"
  pass "目录结构完整"
}

# ========================================
# Phase 3: 核心文件
# ========================================
check_files() {
  echo ""
  echo "=== Phase 3: 核心文件 ==="

  files=(
    "$HOME/.claude/CLAUDE.md:5725"
    "$HOME/.claude/settings.json:1000"
    "$HOME/.claude/STATE.md:100"
    "$HOME/.claude/niumao-anchors.json:2000"
    "$HOME/.mcp.json:100"
    "$HOME/.solar/solar.db:100000000"
  )

  for item in "${files[@]}"; do
    f="${item%%:*}"
    min_size="${item##*:}"

    if [ -f "$f" ]; then
      size=$(wc -c < "$f" 2>/dev/null | tr -d ' ')
      if [ "$size" -ge "$min_size" ]; then
        pass "$(basename $f) ($size bytes)"
      else
        fail "$(basename $f) ($size bytes, 需要 > $min_size)"
      fi
    else
      fail "$(basename $f) 不存在"
    fi
  done
}

# ========================================
# Phase 4: 组件统计
# ========================================
check_components() {
  echo ""
  echo "=== Phase 4: 组件统计 ==="

  printf "  %-15s %8s %8s %8s\n" "组件" "当前" "标准" "状态"
  echo "  ─────────────────────────────────────────"

  # Rules
  current=$(ls ~/.claude/rules/*.md 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 10 ]; then
    printf "  %-15s %8s %8s %8s\n" "Rules" "$current" "10" "✓"
    ((PASSES++))
  else
    printf "  %-15s %8s %8s %8s\n" "Rules" "$current" "10" "✗"
    ((FAILS++))
  fi
  ((CHECKS++))

  # Skills
  current=$(ls ~/.claude/skills 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 90 ]; then
    printf "  %-15s %8s %8s %8s\n" "Skills" "$current" "93" "✓"
    ((PASSES++))
  else
    printf "  %-15s %8s %8s %8s\n" "Skills" "$current" "93" "✗"
    ((FAILS++))
  fi
  ((CHECKS++))

  # Agents
  current=$(ls ~/.claude/agents 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 15 ]; then
    printf "  %-15s %8s %8s %8s\n" "Agents" "$current" "16" "✓"
    ((PASSES++))
  else
    printf "  %-15s %8s %8s %8s\n" "Agents" "$current" "16" "✗"
    ((FAILS++))
  fi
  ((CHECKS++))

  # Hooks
  current=$(ls ~/.claude/hooks 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 70 ]; then
    printf "  %-15s %8s %8s %8s\n" "Hooks" "$current" "77" "✓"
    ((PASSES++))
  else
    printf "  %-15s %8s %8s %8s\n" "Hooks" "$current" "77" "✗"
    ((FAILS++))
  fi
  ((CHECKS++))

  # Core
  current=$(ls ~/.claude/core 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 50 ]; then
    printf "  %-15s %8s %8s %8s\n" "Core" "$current" "51" "✓"
    ((PASSES++))
  else
    printf "  %-15s %8s %8s %8s\n" "Core" "$current" "51" "✗"
    ((FAILS++))
  fi
  ((CHECKS++))

  # Favorites
  current=$(sqlite3 ~/.solar/solar.db "SELECT COUNT(*) FROM sys_favorites" 2>/dev/null || echo 0)
  if [ "$current" -ge 80 ]; then
    printf "  %-15s %8s %8s %8s\n" "Favorites" "$current" "90" "✓"
    ((PASSES++))
  else
    printf "  %-15s %8s %8s %8s\n" "Favorites" "$current" "90" "✗"
    ((FAILS++))
  fi
  ((CHECKS++))
}

# ========================================
# Phase 5: 数据库
# ========================================
check_database() {
  echo ""
  echo "=== Phase 5: 数据库 ==="

  DB="$HOME/.solar/solar.db"

  if [ ! -f "$DB" ]; then
    fail "solar.db 不存在"
    return 1
  fi

  # 检查完整性
  result=$(sqlite3 "$DB" "PRAGMA integrity_check" 2>&1)
  if [ "$result" = "ok" ]; then
    pass "数据库完整性: ok"
  else
    fail "数据库损坏: $result"
  fi
}

# ========================================
# Phase 6: 搜索引擎
# ========================================
check_search() {
  echo ""
  echo "=== Phase 6: 搜索引擎 ==="

  SEARCH_BIN="$HOME/.claude/solar/bin/solar-search"

  if [ -f "$SEARCH_BIN" ]; then
    pass "solar-search 存在"
  else
    fail "solar-search 不存在"
    info "编译: cd ~/.claude/solar/core/search && cargo build --release"
  fi

  if [ -d "$HOME/.solar/search-index" ]; then
    index_count=$(ls ~/.solar/search-index 2>/dev/null | wc -l | tr -d ' ')
    if [ "$index_count" -gt 100 ]; then
      pass "搜索索引存在 ($index_count 个文件)"
    else
      warn "搜索索引可能不完整 ($index_count 个文件)"
    fi
  else
    fail "搜索索引不存在"
  fi
}

# ========================================
# Phase 7: 密钥检查
# ========================================
check_secrets() {
  echo ""
  echo "=== Phase 7: 密钥检查 ==="

  # SSH
  if [ -f "$HOME/.ssh/id_ed25519" ]; then
    pass "SSH id_ed25519 存在"
  else
    fail "SSH id_ed25519 不存在"
  fi

  # API 密钥
  api_keys=(
    "ANTHROPIC_API_KEY"
    "GOOGLE_API_KEY"
    "DEEPSEEK_API_KEY"
    "ZHIPU_API_KEY"
  )

  key_count=0
  for key in "${api_keys[@]}"; do
    if [ -n "$(printenv $key 2>/dev/null)" ]; then
      ((key_count++))
    fi
  done

  if [ "$key_count" -ge 2 ]; then
    pass "API 密钥: $key_count 个已设置"
  else
    fail "API 密钥: 仅 $key_count 个已设置 (需要 >= 2)"
  fi
}

# ========================================
# 同步功能
# ========================================
sync_from_macmini() {
  echo ""
  echo "=== 从 Mac Mini 同步 ==="

  # 测试连接
  if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$MACMINI" "echo ok" &>/dev/null; then
    fail "无法连接到 Mac Mini ($MACMINI)"
    info "请确保: 1) 在同一网络 2) SSH 密钥已配置"
    return 1
  fi

  pass "已连接到 Mac Mini"

  echo ""
  echo "同步 .claude..."
  rsync -avz --delete "$MACMINI:$MACMINI_PATH/.claude/" "$HOME/.claude/"
  echo "✓ .claude 同步完成"

  echo ""
  echo "同步 .solar (不含大文件)..."
  rsync -avz --exclude 'trajectories' --exclude '*.jsonl' --exclude 'versions' \
    "$MACMINI:$MACMINI_PATH/.solar/" "$HOME/.solar/"
  echo "✓ .solar 同步完成"

  echo ""
  echo "同步 MCP 配置..."
  rsync -avz "$MACMINI:$MACMINI_PATH/.mcp.json" "$HOME/" 2>/dev/null || true
  rsync -avz "$MACMINI:$MACMINI_PATH/.claude.json" "$HOME/" 2>/dev/null || true
  echo "✓ MCP 配置同步完成"

  # 删除 WAL 文件
  rm -f "$HOME/.solar/solar.db-wal" "$HOME/.solar/solar.db-shm" 2>/dev/null || true
}

# ========================================
# 主程序
# ========================================
main() {
  echo "╭─────────────────────────────────────────────────────────────────╮"
  echo "│                    🔧 Solar 安装/恢复                           │"
  echo "│                    $(date '+%Y-%m-%d %H:%M:%S')                            │"
  echo "├─────────────────────────────────────────────────────────────────┤"

  local do_sync=false
  case "${1:-}" in
    --sync)
      do_sync=true
      ;;
    --check|"")
      ;;
    --help|-h)
      echo "用法: $0 [选项]"
      echo ""
      echo "选项:"
      echo "  (无参数)    执行完整检查"
      echo "  --check     仅检查，不修复"
      echo "  --sync      从 Mac Mini 同步后检查"
      echo "  --help      显示此帮助"
      exit 0
      ;;
    *)
      echo "未知选项: $1"
      echo "运行 '$0 --help' 查看帮助"
      exit 1
      ;;
  esac

  # 执行同步
  if [ "$do_sync" = true ]; then
    sync_from_macmini
  fi

  # 执行检查
  check_runtime
  create_directories
  check_files
  check_components
  check_database
  check_search
  check_secrets

  echo ""
  echo "├─────────────────────────────────────────────────────────────────┤"
  echo "│  检查完成: $PASSES/$CHECKS 通过, $FAILS 失败"
  if [ "$FAILS" -eq 0 ]; then
    echo -e "│  ${GREEN}✓ 所有检查通过${NC}"
  else
    echo -e "│  ${RED}✗ 请修复上方失败项${NC}"
  fi
  echo "╰─────────────────────────────────────────────────────────────────╯"

  # 返回码
  [ "$FAILS" -eq 0 ]
}

main "$@"
